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

Down the hierarchy (TASKS-384 B4, decision 319): an approval is written down `parent_batch_amb` to the sub-lots
and the containers below the certificate's record, as source "Inherited" naming the same certificate. A record with
a certificate of its own is left alone together with everything below it (those follow it). A withdrawal resets only
the records this certificate wrote; a sub-lot that loses its own certificate takes the status of its nearest
certified ancestor. A hand hold is a matter of the one record that is held: its status stays "Hold" while its
`certificate_status` / `released_by*` keep following the certificate like any other record, and the records below
it are written as usual.

How an approval is written, for a lot with S sub-lots and C containers: 1 + S full document saves (the lot and each
sub-lot), each with ONE history row; the containers are written by a direct column write, one UPDATE per saved
record that has containers below it, with no history row of their own. The row of the lot or sub-lot above them
names every container written with it and its status before and after. See `LotTable.write_columns` for why, and
for what a direct column write does not do.

The parent pointer (review of TASKS-384, finding 3): a record that carries a certificate's state cannot be moved
under another record by hand (`refuse_hand_change`), and a withdrawal also resets every record that still names
the withdrawn certificate in `released_by*`, wherever it sits in the tree (`_reset_elsewhere`), so a record moved
before that refusal existed is found too.

The certificate link (finding 7): the approval writes the certificate on the record it is approved for, in
`coa_reference` (COA AMB) or `coa_amb2` (COA AMB2), in the same save and the same history row; the withdrawal
takes it back when the field still points at the withdrawn certificate. Records that inherit get no link written.
The two fields stay editable by hand and are NOT guarded: they are a pointer for readers, not the status.

What the refusal covers and what it does not: see `refuse_hand_change`.

A release is quiet record by record and summed up once (TASKS-387 item 4, decisions 324 and 325): the saves of
`LotTable.save` made for a certificate's approval or withdrawal carry a second private object (`is_release_save`),
and the lot controller then skips its per-record mail (`notify_stakeholders`, with its "Notifications Sent" history
row) and its Lote AMB sync. Instead `certificate_approved` / `certificate_withdrawn` send ONE summary per call that
wrote any record (`send_release_summary`): who, what, every record written. See there for how it waits for the
commit.
"""

import html

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
# the lot record's link to its certificate, by the certificate's type: written with the approval, on the record
# the certificate is approved for only; editable by hand, not guarded
CERTIFICATE_LINKS = {"COA AMB": "coa_reference", "COA AMB2": "coa_amb2"}
LINK_FIELDS = tuple(CERTIFICATE_LINKS.values())
PARENT_FIELD = "parent_batch_amb"
RECORD_FIELDS = ("name", PARENT_FIELD, "custom_batch_level", *GUARDED_FIELDS, *LINK_FIELDS)
# a certificate is made for a lot or a sub-lot; containers follow (decision 319)
CERTIFICATE_LEVELS = ("1", "2")
# written down to, without a history row of its own; a record of any other level is not written
CONTAINER_LEVEL = "3"

HISTORY_TABLE = "processing_history"
HISTORY_ACTION = "Quality Status Changed"  # an option of Batch Processing History.processing_action

# How the guard knows a save is this module's: the writer puts THIS OBJECT in doc.flags for the length of its own
# save. It is compared by identity, so nothing that arrives as data (a form, the REST API, an import file, a
# Server Script's dict) can be it; see `refuse_hand_change` for what remains.
WRITER_FLAG = "lot_quality_writer"
_WRITER = object()
# The same, for the saves of a RELEASE only (an approval or a withdrawal of a certificate, `LotTable.save` with
# `LotTable.release` set): the lot controller asks `is_release_save` and skips its per-record mail and its Lote AMB
# sync. Not set by `insert_child`, nor by a hand hold placed or lifted: those saves are not a release.
RELEASE_FLAG = "lot_quality_release"
_RELEASE = object()
# who never receives a summary (narrowest reading of "enabled users only": these two are not people)
NOT_PEOPLE = ("Administrator", "Guest")


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
	"""-> the GUARDED_FIELDS of a record once `values` are written (and the certificate link, when `values`
	names one), or None when that changes nothing."""
	after = dict({fieldname: before.get(fieldname) for fieldname in GUARDED_FIELDS}, **values)
	if all(_norm(f, before.get(f)) == _norm(f, after[f]) for f in after):
		return None
	return after


def _link_at_approval(certificate_doctype, certificate):
	"""-> {link field: certificate} for the record the certificate is approved for, {} for a type with no field."""
	fieldname = CERTIFICATE_LINKS.get(certificate_doctype)
	return {fieldname: certificate} if fieldname else {}


def _link_at_withdrawal(record, certificate_doctype, certificate, standing):
	"""-> what becomes of the record's link when the certificate is withdrawn: nothing ({}) unless the field
	still points at the withdrawn certificate; then the certificate that still stands when it is of the same
	type (the field links to one type), else empty."""
	fieldname = CERTIFICATE_LINKS.get(certificate_doctype)
	if not fieldname or record.get(fieldname) != certificate:
		return {}
	if standing and standing.get("doctype") == certificate_doctype and standing.get("name"):
		return {fieldname: standing.get("name")}
	return {fieldname: None}


def _name_own_rows(doc):
	"""A record inserted by this module (`insert_child`) gets its history row before it has a name. Frappe names
	the document before `before_validate`, so the first line of the guard, which runs there, writes the name in
	the row: the same insert, no second save."""
	name = getattr(doc, "name", None)
	if not name:
		return
	for row in doc.get(HISTORY_TABLE) or []:
		if row.get("processing_action") != HISTORY_ACTION or row.get("batch_reference"):
			continue
		if isinstance(row, dict):
			row["batch_reference"] = name
		else:
			row.set("batch_reference", name)


def _certificate_of(record):
	"""-> (doctype, name) of the certificate the record's status comes from, or None."""
	if record.get("released_by"):
		return (record.get("released_by_doctype") or "", record.get("released_by"))
	return None


def _is_writer_save(doc):
	flags = getattr(doc, "flags", None)
	get = getattr(flags, "get", None)
	return bool(get) and get(WRITER_FLAG) is _WRITER


def is_release_save(doc):
	"""True while `doc` is being saved by this module's writer for a certificate's approval or withdrawal (TASKS-387
	item 4). The lot controller asks this, instead of reading a flag itself (contract point 3): under it the
	per-record mail and the Lote AMB sync do not run. Compared by identity, like the guard's pass: nothing that
	arrives as data can be it."""
	flags = getattr(doc, "flags", None)
	get = getattr(flags, "get", None)
	return _is_writer_save(doc) and bool(get) and get(RELEASE_FLAG) is _RELEASE


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
	    document event at all. This module makes one itself, for containers (`LotTable.write_columns`): the
	    guard neither sees it nor could stop the same write made by other code;
	  * Python code on the server that imports this module and sets the flag itself, or that calls
	    `set_lot_quality_status` directly: the writer is not whitelisted, but any server-side code can call it;
	  * a save with no previous row to compare against is judged as an insert (only empty / "Pending" pass).

	The parent pointer: a save that changes `parent_batch_amb` of a record whose stored `status_source` is
	"Inherited", or whose stored `released_by` names a certificate (its own, an inherited one, or one stored
	under a hand hold), is refused the same way: the record's status belongs to the tree it sits in, and what
	is below it inherits through it. A Pending record with no certificate moves freely, and so does a record
	on a hand hold that no certificate speaks for. Not covered: a direct column write of the parent, as above;
	`certificate_withdrawn` therefore also looks for its records by `released_by*`.
	"""
	if _is_writer_save(doc):
		_name_own_rows(doc)
		return
	before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
	changed = []
	for fieldname in GUARDED_FIELDS:
		old = _norm(fieldname, before.get(fieldname) if before else None)
		new = _norm(fieldname, doc.get(fieldname))
		if old != new:
			changed.append((fieldname, old, new))
	if not changed:
		_refuse_parent_change(doc, before)
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


def _refuse_parent_change(doc, before):
	if not before:
		return  # an insert: the new record is placed, not moved
	old, new = before.get(PARENT_FIELD) or "", doc.get(PARENT_FIELD) or ""
	if old == new:
		return
	if before.get("status_source") != INHERITED and not before.get("released_by"):
		return
	frappe.throw(
		_(
			"Lot record {0} cannot be moved (parent: {1} to {2}): its quality status comes from certificate {3} {4} (status source: {5}), and the records below it follow it. The certificate must be rejected first, so that the record is Pending with no certificate; then move it, and approve the certificate again where that applies."
		).format(
			doc.name or _("new"),
			old or _("none"),
			new or _("none"),
			before.get("released_by_doctype") or "",
			before.get("released_by") or _("unknown"),
			before.get("status_source") or _("none"),
		),
		frappe.ValidationError,
		title=_("Quality status"),
	)


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

	# the record of the certificate being approved or withdrawn, set by `_approve` / `_withdraw`: a refusal on
	# another record written with it says so (the user is looking at the certificate, not at that record)
	acting_on = None
	# (certificate type, certificate) while `_approve` / `_withdraw` write: each save is then a release save
	# (`is_release_save`)
	release = None

	def released_by(self, certificate_doctype, certificate):
		"""-> every record whose status is said by this certificate, wherever it sits in the tree."""
		if not (certificate_doctype and certificate):
			return []
		return frappe.get_all(
			DOCTYPE,
			filters={"released_by_doctype": certificate_doctype, "released_by": certificate},
			fields=list(RECORD_FIELDS),
			order_by="name asc",
			limit_page_length=0,
		)

	def get(self, name):
		"""-> {RECORD_FIELDS} of one record, or None."""
		if not name:
			return None
		return frappe.db.get_value(DOCTYPE, name, list(RECORD_FIELDS), as_dict=True)

	def children(self, names):
		"""-> the records whose parent is one of `names`: one query for a whole level of the tree."""
		names = list(names)
		if not names:
			return []
		return frappe.get_all(
			DOCTYPE,
			filters={"parent_batch_amb": ["in", names]},
			fields=list(RECORD_FIELDS),
			order_by="name asc",
			limit_page_length=0,
		)

	def write_columns(self, names, values):
		"""Write `values` (GUARDED_FIELDS only) on many CONTAINERS with one UPDATE, past the document.

		Said plainly: this is a direct column write. It runs no document event, so the guard does not see it
		(nor would it stop anyone else's), no validation of the container runs, no history row is appended on
		the container and its other hooks do not fire; `modified` / `modified_by` are set. It is used for
		containers only, by the approval / withdrawal of the certificate above them, because a lot can have
		hundreds of containers and a full save of each would run the whole lot controller per container inside
		the approval, and any unrelated validation failure of one container would stop the release of the lot.
		The record of each container's release is the history row of the lot or sub-lot it was written with
		(`_containers_note`: every container by name, with its status before and after, the certificate, who and
		when), and on the container itself `released_by*` and `status_source`."""
		names = list(names)
		if not names:
			return
		unknown = set(values) - set(GUARDED_FIELDS)
		if unknown:
			frappe.throw(
				_("Only the quality status fields are written this way (not {0}).").format(sorted(unknown))
			)
		frappe.db.set_value(DOCTYPE, {"name": ["in", names]}, dict(values))

	def save(self, name, values, reason=None, note=None, always=False):
		"""Write `values` (some of GUARDED_FIELDS and, on the record a certificate is approved for or withdrawn
		from, its LINK_FIELDS) on one record through a full document save, with ONE history
		row appended before the save so that this save writes it. -> True when something changed and was saved,
		False when the record already had these values (no save, no row). `always`: save the row even when the
		record's own values do not change (it then speaks for the containers written with it). No try/except:
		what stops the save stops the caller."""
		unknown = set(values) - set(GUARDED_FIELDS) - set(LINK_FIELDS)
		if unknown:
			frappe.throw(
				_(
					"Only the quality status fields and the certificate link are written this way (not {0})."
				).format(sorted(unknown))
			)
		doc = frappe.get_doc(DOCTYPE, name)
		before = {fieldname: doc.get(fieldname) for fieldname in (*GUARDED_FIELDS, *values)}
		after = _after(before, values)
		if after is None:
			if not always:
				return False
			after = dict(before)
		for fieldname, value in values.items():
			doc.set(fieldname, value)
		doc.append(HISTORY_TABLE, _history_row(doc, before, after, reason, note, self.acting_on))
		doc.flags[WRITER_FLAG] = _WRITER
		if self.release:
			doc.flags[RELEASE_FLAG] = _RELEASE
		try:
			# the authority for this write is the certificate's approval, checked where the certificate is
			# approved: the approver need not hold write permission on the lot record
			doc.save(ignore_permissions=True)
		finally:
			doc.flags.pop(WRITER_FLAG, None)
			doc.flags.pop(RELEASE_FLAG, None)
		return True


def _history_row(doc, before, after, reason, note, acting_on=None):
	"""The Batch Processing History row of one change: who, when, from, to, which certificate, why.

	The child table requires date, plant, item_code, quality_status and processing_action. Plant and item come
	from the lot record; nothing is invented: a record with no plant, or with neither a current item nor an item
	to manufacture, cannot carry the row, so the change is refused with a message that says which field to fill.
	From / to / certificate go in `comments`: `previous_value` and `new_value` are declared with length 1 and
	`coa_reference` is a link to COA AMB only.

	`acting_on`: the record of the certificate being approved or withdrawn. When the record that cannot carry
	the row is another one (a sub-lot written with it), the message names both: the user is looking at the
	certificate of `acting_on` and has never opened this record. The rule itself is the same."""
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
	if missing and acting_on and doc.name and acting_on != doc.name:
		frappe.throw(
			_(
				"This action on the certificate of lot record {2} also writes lot record {0} (it follows {2}, or it still carries this certificate), and {0} cannot be written: it has no {1}, and the history row of the change needs it. Open lot record {0}, fill it there, and repeat the action on the certificate. Nothing was changed."
			).format(doc.name, " / ".join(missing), acting_on),
			frappe.ValidationError,
			title=_("Quality status"),
		)
	if missing:
		frappe.throw(
			_(
				"The quality status of lot record {0} cannot be changed: the record has no {1}, and the history row of the change needs it. Fill it on the lot record and repeat the action."
			).format(doc.name or _("new"), " / ".join(missing)),
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
	for fieldname in LINK_FIELDS:
		if fieldname in after and (before.get(fieldname) or "") != (after.get(fieldname) or ""):
			parts.append(
				"certificate link {}: from {} to {}".format(
					fieldname, before.get(fieldname) or "none", after.get(fieldname) or "none"
				)
			)
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
	name, level 1 or 2) as source "Own certificate", with the certificate in the lot's link field of its type
	(`coa_reference` / `coa_amb2`), then write down the hierarchy (B4): every record below it becomes "Inherited"
	from this certificate (no link written), except a record with a certificate of its own and what is below
	that. Raises (frappe.throw) if result has no mapping or a record cannot be written; everything is written
	in the caller's transaction, nothing is committed here. When any record was written, ONE summary is queued
	(`send_release_summary`). -> the number of records written."""
	journal = []
	written = _approve(LotTable(), certificate_doctype, certificate, lot, result, journal)
	send_release_summary(certificate_doctype, certificate, lot, journal, result=result)
	return written


def certificate_withdrawn(certificate_doctype, certificate, lot, standing=None):
	"""The certificate left "Approved" by Reject (to Draft) or a shared COA AMB was cancelled.

	`standing` = None, or a dict {"doctype":…, "name":…, "result":…} of ANOTHER approved certificate of the same
	record that still stands: the lot then takes that one's mapped status instead of Pending. Resets only the
	records this certificate wrote (B4): the lot when its `released_by` is this certificate, and the records
	below it whose `released_by` is this certificate. Without a standing certificate a sub-lot takes the status
	of its nearest certified ancestor (as "Inherited"), or Pending when there is none.

	Every other record that still names this certificate in `released_by*`, wherever it sits in the tree (it was
	moved, or the walk down does not reach it), is reset too: each takes its own nearest certified ancestor's
	status, or Pending. The lot's link field (`coa_reference` / `coa_amb2`), when it still points at this
	certificate, is set to the standing certificate if that is of the same type, else emptied; this also when
	the lot's status comes from another certificate. When any record was written, ONE summary is queued
	(`send_release_summary`).
	-> the number of records written."""
	journal = []
	written = _withdraw(LotTable(), certificate_doctype, certificate, lot, standing, journal)
	send_release_summary(certificate_doctype, certificate, lot, journal, withdrawn=True)
	return written


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


def _values(record, view, source):
	"""What `record` becomes under `view` = (certificate type, certificate, status), or under no certificate."""
	if view is None:
		return _resolve(record, PENDING, source="")
	certificate_doctype, certificate, status = view
	return _resolve(record, status, certificate_doctype, certificate, source)


def _has_no_certificate_of_its_own(child, parent):
	"""An approval above is written to `child` unless the child has a certificate of its own. `parent` is the
	record above it as it was before the write (it tells the source of a child on hand hold)."""
	source = child.get("status_source")
	if source == HOLD_ACTION:
		source = _source_under_hold(child, parent)
	return source != OWN_CERTIFICATE


def _plan(table, top, top_values, view, follows):
	"""Read the tree below `top` (one query per level, nothing written) and decide what is written.

	-> [{"record", "values", "containers": [(record, values)]}], `top` first: the records saved with a history
	row (levels 1 and 2), each with the containers (level 3) that are written with it by a column write.
	`follows(child, parent as read)` says whether a record below takes the new values; a record that does not
	is left alone with everything below it. A record of another level is not written and not walked through."""
	plan = [{"record": top, "values": top_values, "containers": []}]
	speaks_for = {top["name"]: plan[0]}  # record -> the saved record whose history row covers it
	as_read = {top["name"]: top}
	frontier = [top["name"]]
	while frontier:
		children = table.children(frontier)
		frontier = []
		for child in children:
			if child["name"] in as_read:
				continue  # a loop in the parent pointers: every record is decided once
			parent = as_read.get(child.get("parent_batch_amb"))
			level = _level(child)
			if (
				not parent
				or level not in (*CERTIFICATE_LEVELS, CONTAINER_LEVEL)
				or not follows(child, parent)
			):
				continue
			as_read[child["name"]] = child
			values = _values(child, view, INHERITED)
			if level == CONTAINER_LEVEL:
				entry = speaks_for[parent["name"]]
				if _after(child, values) is not None:
					entry["containers"].append((child, values))
			else:
				entry = {"record": child, "values": values, "containers": []}
				plan.append(entry)
			speaks_for[child["name"]] = entry
			frontier.append(child["name"])
	return plan


def _containers_note(containers):
	"""The part of a history row that records the containers written with it: each by name, from what to what."""
	if not containers:
		return None
	groups = {}
	for record, values in containers:
		held = values.get("status_source") == HOLD_ACTION
		key = (_norm("quality_status", record.get("quality_status")), values.get("quality_status"), held)
		groups.setdefault(key, []).append(record["name"])
	parts = [
		"{} from {} to {}{}: {}".format(
			len(names), old, new, " (on hand hold: the verdict is stored)" if held else "", ", ".join(names)
		)
		for (old, new, held), names in groups.items()
	]
	return "containers written with this row, without a row of their own: " + "; ".join(parts)


def _journal(journal, record, values, how):
	"""One line of the release summary: a record counted as written, its status from -> to and its source."""
	if journal is None:
		return
	journal.append(
		{
			"name": record["name"],
			"level": _level(record),
			"from": _norm("quality_status", record.get("quality_status")),
			"to": _norm("quality_status", values.get("quality_status", record.get("quality_status"))),
			"source": values.get("status_source", record.get("status_source")) or "",
			"how": how,
		}
	)


def _write_down(table, top, top_values, view, follows, reason, journal=None):
	"""Write `top` and what follows it. Top first, then each sub-lot, each save followed by the column write of
	its containers. Nothing is caught: the first record that cannot be written stops the caller, whose
	transaction holds every write made so far. -> the number of records written; `journal` gets one line per
	record counted."""
	written = 0
	for entry in _plan(table, top, top_values, view, follows):
		record, containers = entry["record"], entry["containers"]
		saved = table.save(
			record["name"],
			entry["values"],
			reason=reason if record is top else "follows {}: {}".format(top["name"], reason),
			note=_containers_note(containers),
			always=bool(containers),
		)
		if saved:
			written += 1
			_journal(journal, record, entry["values"], "saved")
		groups = {}
		for container, values in containers:
			key = tuple((fieldname, values.get(fieldname)) for fieldname in GUARDED_FIELDS)
			groups.setdefault(key, []).append(container)
		for key, records in groups.items():
			table.write_columns([c["name"] for c in records], dict(key))
			written += len(records)
			for container in records:
				_journal(journal, container, dict(key), "column write")
	return written


def _nearest_certified_ancestor(table, record, excluding=None):
	"""Walk up `parent_batch_amb` to the nearest record whose source is "Own certificate" (underneath a hand
	hold, if it is held) -> that record, or None. `excluding`: a (type, certificate) that does not count (the
	one being withdrawn)."""
	chain, seen, parent = [], {record["name"]}, record.get("parent_batch_amb")
	while parent and parent not in seen:
		seen.add(parent)
		above = table.get(parent)
		if not above:
			break
		chain.append(above)
		parent = above.get("parent_batch_amb")
	for position, above in enumerate(chain):
		source = above.get("status_source")
		if source == HOLD_ACTION:
			source = _source_under_hold(above, chain[position + 1] if position + 1 < len(chain) else None)
		if (
			source == OWN_CERTIFICATE
			and _certificate_of(above)
			and _certificate_of(above) != excluding
			and above.get("certificate_status")
		):
			return above
	return None


def _approve(table, certificate_doctype, certificate, lot, result, journal=None):
	status = _mapped(result)
	# not locked: two approvals in the same tree at once each plan from this read (the concurrent-approval race)
	record = _target(table, certificate_doctype, certificate, lot)
	table.acting_on = record["name"]
	table.release = (certificate_doctype, certificate)
	if _level(record) not in CERTIFICATE_LEVELS:
		frappe.throw(
			_(
				"Lot record {0} is a level {1} record (a container). A certificate is approved for a lot or a sub-lot; containers follow their sub-lot."
			).format(record["name"], _level(record)),
			frappe.ValidationError,
			title=_("Quality status"),
		)
	view = (certificate_doctype, certificate, status)
	return _write_down(
		table,
		record,
		dict(_values(record, view, OWN_CERTIFICATE), **_link_at_approval(certificate_doctype, certificate)),
		view,
		_has_no_certificate_of_its_own,
		f"certificate {certificate_doctype} {certificate} approved with result {result}",
		journal,
	)


def _without(table, record, this, certificate_doctype, certificate):
	"""What a record that loses the certificate `this` falls back on: its nearest certified ancestor's status,
	as "Inherited", or Pending. -> (view, source, reason)"""
	above = _nearest_certified_ancestor(table, record, excluding=this)
	if not above:
		return None, "", f"certificate {certificate_doctype} {certificate} withdrawn"
	view = (above.get("released_by_doctype"), above.get("released_by"), above.get("certificate_status"))
	reason = "certificate {} {} withdrawn; follows {}, which {} {} says is {}".format(
		certificate_doctype, certificate, above["name"], view[0], view[1], view[2]
	)
	return view, INHERITED, reason


def _withdraw(table, certificate_doctype, certificate, lot, standing=None, journal=None):
	record = _target(table, certificate_doctype, certificate, lot)
	table.acting_on = record["name"]
	table.release = (certificate_doctype, certificate)
	this = (certificate_doctype, certificate)

	def wrote(child, parent=None):
		return _certificate_of(child) == this  # only the records this certificate wrote

	link = _link_at_withdrawal(record, certificate_doctype, certificate, standing)
	written = 0
	if wrote(record):
		if standing:
			if (standing.get("doctype"), standing.get("name")) == this:
				frappe.throw(_("The certificate that still stands cannot be the one that is withdrawn."))
			view = (standing.get("doctype"), standing.get("name"), _mapped(standing.get("result")))
			if not (view[0] and view[1]):
				frappe.throw(_("The certificate that still stands must be named with its type."))
			source = OWN_CERTIFICATE
			reason = "certificate {} {} withdrawn; {} {} still stands with result {}".format(
				certificate_doctype, certificate, view[0], view[1], standing.get("result")
			)
		else:
			view, source, reason = _without(table, record, this, certificate_doctype, certificate)
		written += _write_down(
			table, record, dict(_values(record, view, source), **link), view, wrote, reason, journal
		)
	elif link:
		# this certificate did not write the record's status (nothing of that to take back), but the record's
		# link still points at it
		saved = table.save(
			record["name"],
			link,
			reason=f"certificate {certificate_doctype} {certificate} withdrawn; the status comes from another certificate",
		)
		if saved:
			written += 1
			_journal(journal, record, link, "saved (certificate link only)")
	return written + _reset_elsewhere(table, record, this, certificate_doctype, certificate, wrote, journal)


def _reset_elsewhere(table, lot, this, certificate_doctype, certificate, wrote, journal=None):
	"""After the walk down from the certificate's lot: reset every record that STILL names the certificate in
	`released_by*` (a query on those two fields, not on the tree). These are records the walk does not reach: a
	record moved under another parent, a record below one of another level, a record below a sub-lot that got a
	certificate of its own. Each takes its nearest certified ancestor's status, or Pending (never the standing
	certificate: that one is of the certificate's lot, which such a record follows only if it is still below
	it, and then the ancestor rule gives it). Highest level first, so that a moved sub-lot is written with its
	own containers (one row, as in the walk down); a container found alone gets a full save and a row of its
	own, since no saved record speaks for it."""
	written = 0
	found = sorted(table.released_by(certificate_doctype, certificate), key=lambda r: (_level(r), r["name"]))
	for stale in found:
		record = table.get(stale["name"])
		if not record or not wrote(record):
			continue  # written meanwhile, with a record found before it
		view, source, reason = _without(table, record, this, certificate_doctype, certificate)
		written += _write_down(
			table,
			record,
			_values(record, view, source),
			view,
			wrote,
			"{} (found by its certificate, outside the walk down from {})".format(reason, lot["name"]),
			journal,
		)
	return written


def insert_child(child, parent):
	"""`create_child_batch`'s insert (B4). A new sub-lot or container under a record whose status comes from a
	certificate is born with that status: the parent's certificate, what it says, source "Inherited", and one
	history row. Under a record no certificate speaks for, it is born Pending. `child` is the new document, not
	yet inserted; `parent` the document it is created under.

	A parent on hand hold: the child takes what the parent's certificate says, not the hold (the hold is on the
	parent record; see the module docstring)."""
	certificate = _certificate_of(parent)
	says = parent.get("certificate_status")
	values = dict.fromkeys(GUARDED_FIELDS)
	values["quality_status"] = PENDING
	if certificate and says in LOT_STATUSES:
		values = {
			"quality_status": says,
			"status_source": INHERITED,
			"released_by_doctype": certificate[0] or None,
			"released_by": certificate[1],
			"certificate_status": says,
		}
	for fieldname, value in values.items():
		child.set(fieldname, value)
	if not values["status_source"]:
		return child.insert()  # Pending, no certificate: an insert like any other, judged by the guard
	child.append(
		HISTORY_TABLE,
		_history_row(
			child,
			dict.fromkeys(GUARDED_FIELDS),
			values,
			"created under {}, which {} {} says is {}".format(
				parent.get("name"), certificate[0], certificate[1], says
			),
			None,
		),
	)
	child.flags[WRITER_FLAG] = _WRITER
	try:
		return child.insert()
	finally:
		child.flags.pop(WRITER_FLAG, None)


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


# ----------------------------------------------------------------------------------------------------------------
# the release summary (TASKS-387 item 4, decision 325): one message per certificate event that wrote any record
# ----------------------------------------------------------------------------------------------------------------
def release_summary_recipients(certificate_doctype, certificate, lot, certificate_row=None):
	"""-> [e-mail] of the summary, each once: the certificate's `filled_by`, the session user (who approved, or who
	rejected or cancelled), and the owner of the Work Order named by the lot record named in the call
	(`work_order_ref`). Enabled users with an e-mail address only; "Administrator" and "Guest" never. No role is
	read: no role-wide mail. Read errors are not caught (a site without `filled_by` fails here, visibly)."""
	row = certificate_row
	if row is None:
		row = (
			frappe.db.get_value(certificate_doctype, certificate, ["filled_by", "docstatus"], as_dict=True)
			or {}
		)
	work_order = frappe.db.get_value(DOCTYPE, lot, "work_order_ref") if lot else None
	work_order_owner = frappe.db.get_value("Work Order", work_order, "owner") if work_order else None
	users = []
	for user in (row.get("filled_by"), frappe.session.user, work_order_owner):
		if user and user not in NOT_PEOPLE and user not in users:
			users.append(user)
	emails = []
	for user in users:
		person = frappe.db.get_value("User", user, ["enabled", "email"], as_dict=True)
		if not person or not int(person.get("enabled") or 0):
			continue  # a disabled or deleted user is skipped
		email = person.get("email")
		if email and email not in emails:
			emails.append(email)
	return emails


def release_summary_text(
	certificate_doctype, certificate, lot, journal, result=None, withdrawn=False, cancelled=False
):
	"""-> (subject, HTML body) of the summary: the certificate, its result (for a withdrawal: that it was withdrawn,
	how, and the status the lot record took), who, and every record written with its status from -> to, its source
	and how it was written (a full save with a history row, or a container's column write)."""
	e = html.escape
	if withdrawn:
		how = "cancelled" if cancelled else "rejected back from Approved"
		mine = [j for j in journal if j["name"] == lot]
		if mine:
			taken = "lot record {} now {} (source {})".format(
				e(lot), e(mine[0]["to"]), e(mine[0]["source"] or "none")
			)
		else:
			taken = f"lot record {e(lot)} was not written by this withdrawal"
		said = f" Its result was {e(result)}." if result else ""
		head = f"{e(certificate_doctype)} {e(certificate)} was withdrawn ({how}); {taken}.{said}"
		subject = f"{certificate_doctype} {certificate} withdrawn: {len(journal)} lot record(s) written"
	else:
		head = f"{e(certificate_doctype)} {e(certificate)} was approved with result {e(result or '')}."
		subject = (
			f"{certificate_doctype} {certificate} approved ({result}): {len(journal)} lot record(s) written"
		)
	lines = "".join(
		"<li>{} (level {}): {} &rarr; {}, source {}, {}</li>".format(
			e(j["name"]), e(j["level"]), e(j["from"]), e(j["to"]), e(j["source"] or "none"), e(j["how"])
		)
		for j in journal
	)
	body = (
		f"<p>{head}</p><p>By {e(frappe.session.user or '')}. {len(journal)} lot record(s) written:</p>"
		f"<ul>{lines}</ul>"
	)
	return subject, body


def send_release_summary(certificate_doctype, certificate, lot, journal, result=None, withdrawn=False):
	"""ONE message for one approval or withdrawal that wrote any record (`journal` non-empty); nothing otherwise.

	Sent after commit only, and dropped on rollback, because of how Frappe 16.17.5 queues mail:
	`frappe.sendmail` (`frappe/email/__init__.py`) builds an Email Queue document and INSERTS it in the current
	transaction (`QueueBuilder.process(send_now=False)` -> `EmailQueue.new` -> `insert`; Email Queue is InnoDB).
	With the default `delayed=True` and no `now`, nothing else happens: the row is sent later by the scheduler's
	queue flush, which sees it only once the transaction has committed; a rollback removes the row with the
	release (also a rollback to a savepoint). `now=True` would add `q.send` to `frappe.db.after_commit` (reset on
	a full rollback, but not on a savepoint rollback), so it is NOT used. No commit, no try/except here.

	A summary that cannot be queued fails the release, visibly: an exception of `sendmail` is not caught, and a
	`sendmail` that queues nothing for a non-empty list of recipients (Frappe drops an invalid address, logging it,
	and every recipient who has unsubscribed) is refused with a message; the caller's transaction then rolls the
	whole release back. No recipient at all (every one disabled, or without an address): nothing is sent, the
	release stands."""
	if not journal:
		return None
	row = (
		frappe.db.get_value(
			certificate_doctype, certificate, ["filled_by", "docstatus", "overall_result"], as_dict=True
		)
		or {}
	)
	recipients = release_summary_recipients(certificate_doctype, certificate, lot, row)
	if not recipients:
		return None
	subject, body = release_summary_text(
		certificate_doctype,
		certificate,
		lot,
		journal,
		# TASKS-387 review, finding 7: a withdrawal also gives the certificate's result, read from the certificate
		result=result if result is not None else row.get("overall_result"),
		withdrawn=withdrawn,
		cancelled=withdrawn and int(row.get("docstatus") or 0) == 2,
	)
	queued = frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=body,
		reference_doctype=certificate_doctype,
		reference_name=certificate,
	)
	if not queued:
		frappe.throw(
			_(
				"The release summary of {0} {1} could not be queued (Frappe queued no mail for its {2} recipient(s): an invalid address, or every recipient has unsubscribed). Nothing was written; correct the user's e-mail address and repeat the action."
			).format(certificate_doctype, certificate, len(recipients)),
			frappe.ValidationError,
			title=_("Quality status"),
		)
	return queued
