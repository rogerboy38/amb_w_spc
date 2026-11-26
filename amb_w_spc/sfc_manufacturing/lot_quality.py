"""The quality status of a lot record (Batch AMB) and the one place that writes it (TASKS-384 B3).

A lot record's `quality_status` says what its certificate says. Nobody edits it by hand: a certificate that reaches
"Approved" sets it (`certificate_approved`), a certificate that leaves "Approved" takes it back
(`certificate_withdrawn`), and both go through `set_lot_quality_status`, THE ONLY WRITER. Every other change of the
status, or of the four fields that say where it came from, is refused on the server for every role
(`refuse_hand_change`, hooked on Batch AMB in hooks.py).

The vocabulary (decisions 303 and 315) is fixed here and must equal the option lists of the DocType JSON
(tests/test_lot_quality.py fails when they drift) and the same constants of amb_w_tds/quality_vocabulary.py.

Hand hold (decision 315): a record whose `status_source` is "Hold action" keeps `quality_status` "Hold" whatever a
certificate does. The certificate's verdict is stored in `certificate_status` / `released_by*` and takes effect when
the hold is lifted (`lift_hand_hold`, which the hold action of a later task will call; no button calls it today).

What the refusal covers and what it does not: see `refuse_hand_change`.
"""

import frappe
from frappe import _

# ---- vocabulary: the same text in amb_w_tds/quality_vocabulary.py ----
LOT_STATUSES = ("Pending", "Passed", "Failed", "Hold")
CERTIFICATE_RESULTS = ("Pending", "Pass", "Fail", "Partial", "No Tests")
RESULT_TO_LOT_STATUS = {"Pass": "Passed", "Fail": "Failed", "Partial": "Hold"}
STATUS_SOURCES = ("", "Own certificate", "Inherited", "Hold action")

PENDING = "Pending"
HOLD = "Hold"
OWN_CERTIFICATE = "Own certificate"
INHERITED = "Inherited"
HOLD_ACTION = "Hold action"

DOCTYPE = "Batch AMB"
# the status and the four fields that say where it came from: written by this module only
GUARDED_FIELDS = (
	"quality_status",
	"status_source",
	"released_by_doctype",
	"released_by",
	"certificate_status",
)
RECORD_FIELDS = ("name", "parent_batch_amb", "custom_batch_level", *GUARDED_FIELDS)
CERTIFICATE_LEVELS = (
	"1",
	"2",
)  # a certificate is made for a lot or a sub-lot; containers follow (decision 319)

HISTORY_TABLE = "processing_history"
HISTORY_ACTION = "Quality Status Changed"  # an option of Batch Processing History.processing_action

# How the guard knows a save is this module's: the writer puts THIS OBJECT in doc.flags for the length of its own
# save. It is compared by identity, so nothing that arrives as data (a form, the REST API, an import file, a
# Server Script's dict) can be it; see `refuse_hand_change` for what remains.
WRITER_FLAG = "lot_quality_writer"
_WRITER = object()


# ----------------------------------------------------------------------------------------------------------------
# small pure helpers
# ----------------------------------------------------------------------------------------------------------------
def _norm(fieldname, value):
	"""An empty status is "Pending" everywhere in this app; an empty other field is ""."""
	if fieldname == "quality_status":
		return value or PENDING
	return value or ""


def _level(record):
	return str(record.get("custom_batch_level") or "1")


def _after(before, values):
	"""-> the GUARDED_FIELDS of a record once `values` are written, or None when that changes nothing."""
	after = dict({fieldname: before.get(fieldname) for fieldname in GUARDED_FIELDS}, **values)
	if all(_norm(f, before.get(f)) == _norm(f, after[f]) for f in GUARDED_FIELDS):
		return None
	return after


def _certificate_of(record):
	"""-> (doctype, name) of the certificate the record's status comes from, or None."""
	if record.get("released_by"):
		return (record.get("released_by_doctype") or "", record.get("released_by"))
	return None


def _is_writer_save(doc):
	flags = getattr(doc, "flags", None)
	get = getattr(flags, "get", None)
	return bool(get) and get(WRITER_FLAG) is _WRITER


def _label(fieldname):
	return {
		"quality_status": _("Quality Status"),
		"status_source": _("Status Source"),
		"released_by_doctype": _("Released By (type)"),
		"released_by": _("Released By"),
		"certificate_status": _("Certificate Status"),
	}[fieldname]


# ----------------------------------------------------------------------------------------------------------------
# the refusal
# ----------------------------------------------------------------------------------------------------------------
def refuse_hand_change(doc, method=None):
	"""doc_events hook on Batch AMB (`before_validate` and `on_update`): refuse, for EVERY role (System Manager and
	Administrator included), a save that changes `quality_status`, `status_source`, `released_by_doctype`,
	`released_by` or `certificate_status`, unless the save is made by this module. A new record may only be
	inserted with the status empty or "Pending" and the other four empty, unless this module inserts it.

	Two lines, the same check:
	  * `before_validate` runs before the controller and the other hooks, and Frappe does not skip it under
	    `doc.flags.ignore_validate`. It stops a changed value that ARRIVES with the document (form, REST,
	    `frappe.client.set_value`, Data Import, another app's `doc.save()`).
	  * `on_update` runs after the write, inside the same transaction, also under `ignore_validate`. It stops a
	    value changed DURING the save, after the first line ran (a `validate` / `before_save` hook or Server
	    Script that assigns the field). The refusal makes the request fail, which rolls the write back; code that
	    catches the error and commits anyway keeps the row.

	The pass is `doc.flags[WRITER_FLAG] is _WRITER`, an object of this module compared by identity, set only for
	the length of the writer's own save. A caller cannot send it: flags are not part of a document's data and a
	value that travelled as JSON is never that object. What is NOT covered, named so that a green test is not
	over-read:
	  * a direct column write (`frappe.db.set_value`, `doc.db_set`, `frappe.db.sql`, the query builder) runs no
	    document event at all;
	  * Python code on the server that imports this module and sets the flag itself, or that calls
	    `set_lot_quality_status` directly: the writer is not whitelisted, but any server-side code can call it;
	  * a save with no previous row to compare against is judged as an insert (only empty / "Pending" pass).
	"""
	if _is_writer_save(doc):
		return
	before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
	changed = []
	for fieldname in GUARDED_FIELDS:
		old = _norm(fieldname, before.get(fieldname) if before else None)
		new = _norm(fieldname, doc.get(fieldname))
		if old != new:
			changed.append((fieldname, old, new))
	if not changed:
		return
	what = ", ".join(
		_("{0}: {1} to {2}").format(_label(fieldname), old or _("empty"), new or _("empty"))
		for fieldname, old, new in changed
	)
	if before:
		message = _(
			"The quality status of a lot record is set by its certificate and cannot be changed by hand, by any role ({0}: {1}). Approve or reject the certificate instead."
		).format(doc.name or _("new"), what)
	else:
		message = _(
			"A new lot record starts with the quality status Pending and no certificate ({0}: {1}). Its status is set by its certificate."
		).format(doc.name or _("new"), what)
	frappe.throw(message, frappe.ValidationError, title=_("Quality status"))


def reset_for_copy(doc):
	"""A copy of a lot record is a new record: it starts Pending, with no certificate."""
	doc.quality_status = PENDING
	for fieldname in GUARDED_FIELDS[1:]:
		doc.set(fieldname, None)


# ----------------------------------------------------------------------------------------------------------------
# the data-access seam: everything this module reads from or writes to the lot table goes through these methods
# ----------------------------------------------------------------------------------------------------------------
class LotTable:
	"""The lot table as this module needs it. Tests replace it with an in-memory table."""

	def get(self, name):
		"""-> {RECORD_FIELDS} of one record, or None."""
		if not name:
			return None
		return frappe.db.get_value(DOCTYPE, name, list(RECORD_FIELDS), as_dict=True)

	def save(self, name, values, reason=None, note=None):
		"""Write `values` (some of GUARDED_FIELDS) on one record through a full document save, with ONE history
		row appended before the save so that this save writes it. -> True when something changed and was saved,
		False when the record already had these values (no save, no row). No try/except: what stops the save
		stops the caller."""
		doc = frappe.get_doc(DOCTYPE, name)
		before = {fieldname: doc.get(fieldname) for fieldname in GUARDED_FIELDS}
		after = _after(before, values)
		if after is None:
			return False
		for fieldname, value in values.items():
			doc.set(fieldname, value)
		doc.append(HISTORY_TABLE, _history_row(doc, before, after, reason, note))
		doc.flags[WRITER_FLAG] = _WRITER
		try:
			# the authority for this write is the certificate's approval, checked where the certificate is
			# approved: the approver need not hold write permission on the lot record
			doc.save(ignore_permissions=True)
		finally:
			doc.flags.pop(WRITER_FLAG, None)
		return True


def _history_row(doc, before, after, reason, note):
	"""The Batch Processing History row of one change: who, when, from, to, which certificate, why.

	The child table requires date, plant, item_code, quality_status and processing_action. Plant and item come
	from the lot record; nothing is invented: a record with no plant, or with neither a current item nor an item
	to manufacture, cannot carry the row, so the change is refused with a message that says which field to fill.
	From / to / certificate go in `comments`: `previous_value` and `new_value` are declared with length 1 and
	`coa_reference` is a link to COA AMB only."""
	plant = doc.get("current_plant2")
	item_code = doc.get("current_item_code") or doc.get("item_to_manufacture")
	missing = [
		label
		for label, value in (
			(_("Current Plant"), plant),
			(_("Current Item Code / Item to Manufacture"), item_code),
		)
		if not value
	]
	if missing:
		frappe.throw(
			_(
				"The quality status of lot record {0} cannot be changed: the record has no {1}, and the history row of the change needs it. Fill it on the lot record and repeat the action."
			).format(doc.name, " / ".join(missing)),
			frappe.ValidationError,
			title=_("Quality status"),
		)
	return {
		"date": frappe.utils.nowdate(),
		"plant": plant,
		"item_code": item_code,
		"batch_reference": doc.name,
		"quality_status": _norm("quality_status", after["quality_status"]),
		"processing_action": HISTORY_ACTION,
		"changed_by": frappe.session.user,
		"comments": _history_text(before, after, reason, note),
		"system_generated": 1,
	}


def _history_text(before, after, reason, note):
	def certificate(values):
		if not values.get("released_by"):
			return "none"
		said = values.get("certificate_status")
		return "{} {}{}".format(
			values.get("released_by_doctype") or "",
			values.get("released_by"),
			f" (says {said})" if said else "",
		).strip()

	parts = [
		"Quality status: from {} to {}".format(
			_norm("quality_status", before["quality_status"]),
			_norm("quality_status", after["quality_status"]),
		),
		"source: from {} to {}".format(
			before.get("status_source") or "none", after.get("status_source") or "none"
		),
		f"certificate: from {certificate(before)} to {certificate(after)}",
	]
	held = after.get("status_source") == HOLD_ACTION and before.get("status_source") == HOLD_ACTION
	if held:
		parts.append("hand hold in force: the status stays Hold, the certificate's verdict is stored")
	if reason:
		parts.append(f"reason: {reason}")
	if note:
		parts.append(note)
	parts.append(f"by {frappe.session.user} at {frappe.utils.now()}")
	return " | ".join(parts)


# ----------------------------------------------------------------------------------------------------------------
# the rules, pure: what a record becomes
# ----------------------------------------------------------------------------------------------------------------
def _resolve(record, status, certificate_doctype=None, certificate=None, source=None):
	"""-> the new values of GUARDED_FIELDS for `record`, given what is asked. Refuses what the vocabulary does
	not allow. The hand hold rule lives here, so no caller can go round it: a record on hand hold keeps status
	"Hold" and source "Hold action"; only what its certificate says is updated."""
	if source is None:
		source = OWN_CERTIFICATE if certificate else ""
	if status not in LOT_STATUSES:
		frappe.throw(_("{0} is not a lot quality status ({1}).").format(status, ", ".join(LOT_STATUSES)))
	if source not in STATUS_SOURCES:
		frappe.throw(_("{0} is not a status source.").format(source))

	if source == HOLD_ACTION:
		# a hand hold keeps what the certificate says; it is lifted by lift_hand_hold
		if status != HOLD or certificate or certificate_doctype:
			frappe.throw(_("A hand hold sets the status Hold and names no certificate."))
		return {"quality_status": HOLD, "status_source": HOLD_ACTION}

	if source in (OWN_CERTIFICATE, INHERITED):
		if not (certificate and certificate_doctype):
			frappe.throw(_("A status that comes from a certificate must name the certificate and its type."))
		view = {
			"released_by_doctype": certificate_doctype,
			"released_by": certificate,
			"certificate_status": status,
		}
	else:
		# no source: no certificate says anything about this record
		if status != PENDING or certificate or certificate_doctype:
			frappe.throw(
				_("Without a certificate a lot record can only be Pending (asked: {0}).").format(status)
			)
		view = {"released_by_doctype": None, "released_by": None, "certificate_status": None}

	if record.get("status_source") == HOLD_ACTION:
		return dict(view, quality_status=HOLD, status_source=HOLD_ACTION)
	return dict(view, quality_status=status, status_source=source)


def _source_under_hold(record, parent):
	"""What the source of a record on hand hold is underneath the hold: the hold overwrote `status_source`, so it
	is read from the certificate: none -> "", the same certificate as the parent record -> "Inherited" (a
	certificate is the own certificate of one record only), else "Own certificate"."""
	mine = _certificate_of(record)
	if not mine:
		return ""
	if parent and _certificate_of(parent) == mine:
		return INHERITED
	return OWN_CERTIFICATE


def _set(table, lot, status, certificate=None, reason=None, certificate_doctype=None, source=None, note=None):
	record = table.get(lot)
	if not record:
		frappe.throw(_("Lot record {0} does not exist: its quality status cannot be set.").format(lot))
	if source == HOLD_ACTION and not reason:
		frappe.throw(_("A hand hold is placed with a reason."))
	values = _resolve(record, status, certificate_doctype, certificate, source)
	return table.save(record["name"], values, reason=reason, note=note)


# ----------------------------------------------------------------------------------------------------------------
# the contract: what amb_w_tds calls
# ----------------------------------------------------------------------------------------------------------------
def set_lot_quality_status(lot, status, certificate=None, reason=None, certificate_doctype=None, source=None):
	"""THE ONLY WRITER of Batch AMB.quality_status (and of status_source, released_by*, certificate_status).

	Sets the flag the lot's guard recognises, appends ONE history row (who, when, from, to, which certificate,
	reason) BEFORE the lot's save so that save writes it, and saves. No try/except around the write: if the lot
	cannot be written the caller's action fails and the user sees why.

	`source`: "Own certificate" (the default when a certificate is named), "Inherited", "Hold action" (status
	"Hold", no certificate: places a hand hold and keeps what the certificate says) or "" (the default without a
	certificate: status "Pending" only, the record is no longer released by anything). A record on hand hold
	keeps "Hold": only what its certificate says is updated (decision 315).
	-> True when the record changed, False when it already had these values (then nothing is saved)."""
	return _set(LotTable(), lot, status, certificate, reason, certificate_doctype, source)


def certificate_approved(certificate_doctype, certificate, lot, result):
	"""The certificate reached "Approved". Map `result` (Pass/Fail/Partial) and write the lot `lot` (a Batch AMB
	name, level 1 or 2) as source "Own certificate". Raises (frappe.throw) if result has no mapping or the lot
	cannot be written."""
	return _approve(LotTable(), certificate_doctype, certificate, lot, result)


def certificate_withdrawn(certificate_doctype, certificate, lot, standing=None):
	"""The certificate left "Approved" by Reject (to Draft) or a shared COA AMB was cancelled.

	`standing` = None, or a dict {"doctype":…, "name":…, "result":…} of ANOTHER approved certificate of the same
	record that still stands: the lot then takes that one's mapped status instead of Pending. Resets only a
	record this certificate wrote: a lot whose `released_by` is another certificate (or none) is left as it is."""
	return _withdraw(LotTable(), certificate_doctype, certificate, lot, standing)


def lift_hand_hold(lot, reason):
	"""Lift a hand hold: the record takes what its certificate says (`certificate_status`; Pending when no
	certificate says anything). For the hold action of a later task: nothing calls this today, it is not
	whitelisted and has no button."""
	return _lift(LotTable(), lot, reason)


# ----------------------------------------------------------------------------------------------------------------
# the same, against any table
# ----------------------------------------------------------------------------------------------------------------
def _mapped(result):
	status = RESULT_TO_LOT_STATUS.get(result)
	if not status:
		frappe.throw(
			_(
				"A certificate with the result {0} does not release or reject a lot: only {1} set a quality status."
			).format(result or _("empty"), ", ".join(RESULT_TO_LOT_STATUS)),
			frappe.ValidationError,
			title=_("Quality status"),
		)
	return status


def _target(table, certificate_doctype, certificate, lot):
	if not (certificate_doctype and certificate):
		frappe.throw(_("The certificate and its type must be named to set a lot's quality status."))
	record = table.get(lot)
	if not record:
		frappe.throw(
			_("Certificate {0} names the lot record {1}, which does not exist.").format(
				certificate, lot or _("empty")
			)
		)
	return record


def _approve(table, certificate_doctype, certificate, lot, result):
	status = _mapped(result)
	record = _target(table, certificate_doctype, certificate, lot)
	if _level(record) not in CERTIFICATE_LEVELS:
		frappe.throw(
			_(
				"Lot record {0} is a level {1} record (a container). A certificate is approved for a lot or a sub-lot; containers follow their sub-lot."
			).format(record["name"], _level(record)),
			frappe.ValidationError,
			title=_("Quality status"),
		)
	return _set(
		table,
		record["name"],
		status,
		certificate=certificate,
		certificate_doctype=certificate_doctype,
		source=OWN_CERTIFICATE,
		reason=f"certificate {certificate_doctype} {certificate} approved with result {result}",
	)


def _withdraw(table, certificate_doctype, certificate, lot, standing=None):
	record = _target(table, certificate_doctype, certificate, lot)
	if _certificate_of(record) != (certificate_doctype, certificate):
		return False  # this certificate did not write the record: nothing of its own to take back
	if standing:
		if (standing.get("doctype"), standing.get("name")) == (certificate_doctype, certificate):
			frappe.throw(_("The certificate that still stands cannot be the one that is withdrawn."))
		return _set(
			table,
			record["name"],
			_mapped(standing.get("result")),
			certificate=standing.get("name"),
			certificate_doctype=standing.get("doctype"),
			source=OWN_CERTIFICATE,
			reason="certificate {} {} withdrawn; {} {} still stands with result {}".format(
				certificate_doctype,
				certificate,
				standing.get("doctype"),
				standing.get("name"),
				standing.get("result"),
			),
		)
	return _set(
		table,
		record["name"],
		PENDING,
		source="",
		reason=f"certificate {certificate_doctype} {certificate} withdrawn",
	)


def _lift(table, lot, reason):
	record = table.get(lot)
	if not record:
		frappe.throw(_("Lot record {0} does not exist.").format(lot))
	if record.get("status_source") != HOLD_ACTION:
		frappe.throw(_("Lot record {0} is not on a hand hold.").format(record["name"]))
	if not reason:
		frappe.throw(_("A hand hold is lifted with a reason."))
	source = _source_under_hold(record, table.get(record.get("parent_batch_amb")))
	status = (record.get("certificate_status") or PENDING) if source else PENDING
	return table.save(
		record["name"],
		{"quality_status": status, "status_source": source},
		reason=f"hand hold lifted: {reason}",
	)
