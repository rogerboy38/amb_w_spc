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
	    document event at all. This module makes one itself, for containers (`LotTable.write_columns`): the
	    guard neither sees it nor could stop the same write made by other code;
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
		"""Write `values` (some of GUARDED_FIELDS) on one record through a full document save, with ONE history
		row appended before the save so that this save writes it. -> True when something changed and was saved,
		False when the record already had these values (no save, no row). `always`: save the row even when the
		record's own values do not change (it then speaks for the containers written with it). No try/except:
		what stops the save stops the caller."""
		doc = frappe.get_doc(DOCTYPE, name)
		before = {fieldname: doc.get(fieldname) for fieldname in GUARDED_FIELDS}
		after = _after(before, values)
		if after is None:
			if not always:
				return False
			after = dict(before)
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
	name, level 1 or 2) as source "Own certificate", then write down the hierarchy (B4): every record below it
	becomes "Inherited" from this certificate, except a record with a certificate of its own and what is below
	that. Raises (frappe.throw) if result has no mapping or a record cannot be written; everything is written
	in the caller's transaction, nothing is committed here. -> the number of records written."""
	return _approve(LotTable(), certificate_doctype, certificate, lot, result)


def certificate_withdrawn(certificate_doctype, certificate, lot, standing=None):
	"""The certificate left "Approved" by Reject (to Draft) or a shared COA AMB was cancelled.

	`standing` = None, or a dict {"doctype":…, "name":…, "result":…} of ANOTHER approved certificate of the same
	record that still stands: the lot then takes that one's mapped status instead of Pending. Resets only the
	records this certificate wrote (B4): the lot when its `released_by` is this certificate, and the records
	below it whose `released_by` is this certificate. Without a standing certificate a sub-lot takes the status
	of its nearest certified ancestor (as "Inherited"), or Pending when there is none.
	-> the number of records written."""
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


def _write_down(table, top, top_values, view, follows, reason):
	"""Write `top` and what follows it. Top first, then each sub-lot, each save followed by the column write of
	its containers. Nothing is caught: the first record that cannot be written stops the caller, whose
	transaction holds every write made so far. -> the number of records written."""
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
		written += 1 if saved else 0
		groups = {}
		for container, values in containers:
			key = tuple((fieldname, values.get(fieldname)) for fieldname in GUARDED_FIELDS)
			groups.setdefault(key, []).append(container["name"])
		for key, names in groups.items():
			table.write_columns(names, dict(key))
			written += len(names)
	return written


def _nearest_certified_ancestor(table, record):
	"""Walk up `parent_batch_amb` to the nearest record whose source is "Own certificate" (underneath a hand
	hold, if it is held) -> that record, or None."""
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
		if source == OWN_CERTIFICATE and _certificate_of(above) and above.get("certificate_status"):
			return above
	return None


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
	view = (certificate_doctype, certificate, status)
	return _write_down(
		table,
		record,
		_values(record, view, OWN_CERTIFICATE),
		view,
		_has_no_certificate_of_its_own,
		f"certificate {certificate_doctype} {certificate} approved with result {result}",
	)


def _withdraw(table, certificate_doctype, certificate, lot, standing=None):
	record = _target(table, certificate_doctype, certificate, lot)
	this = (certificate_doctype, certificate)
	if _certificate_of(record) != this:
		return 0  # this certificate did not write the record: nothing of its own to take back
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
		above = _nearest_certified_ancestor(table, record)
		if above:
			view = (
				above.get("released_by_doctype"),
				above.get("released_by"),
				above.get("certificate_status"),
			)
			source = INHERITED
			reason = "certificate {} {} withdrawn; follows {}, which {} {} says is {}".format(
				certificate_doctype, certificate, above["name"], view[0], view[1], view[2]
			)
		else:
			view, source = None, ""
			reason = f"certificate {certificate_doctype} {certificate} withdrawn"
	return _write_down(
		table,
		record,
		_values(record, view, source),
		view,
		lambda child, parent: _certificate_of(child) == this,  # only the records this certificate wrote
		reason,
	)


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
