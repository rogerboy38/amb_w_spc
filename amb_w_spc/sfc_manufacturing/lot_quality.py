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
commit. A release never fails because of mail (TASKS-388, decision 328): a summary that cannot be queued is
written into the release's own history row as "summary not sent: <reason>" and the release stands.

TASKS-390: muted mail is noted, not queued (decision 333, `_send_summary`); a share is summed up like a release
(decision 334, `certificate_shared`); a child created after its parent's certificate was approved is born Pending
(decision 336, `insert_child`); the worst result wins when more than one certificate stands for a record
(decision 338, `others` of `certificate_approved`, a list as `standing` of `certificate_withdrawn`).

TASKS-391: a container created under a sub-lot whose status comes from a certificate inherits it at its birth
(decision 342, amends 336, `insert_child`); a sub-lot created after an approval is still born Pending.
TASKS-392: the same for a container created directly under a lot (decision 344); a copy of a lot record carries
no certificate link (decision 345, `reset_for_copy`; the three link fields are also "no copy" in the DocType).
TASKS-397: a duplicate of a lot record is a clean new record (decision 346, `insert_copy`): none of the source's
history rows (the history table is also "no copy" in the DocType), one row "copied from <source>" written here, the
parent pointer kept, and a duplicated container under a certified lot or sub-lot inherits as a new one does (344).

No move under a hold (TASKS-388, decision 329): `parent_batch_amb` of a record cannot be changed while the chain
above its stored parent, or above its new parent, holds a record on a hand hold (`_refuse_move_under_hold`), and a
merge of a record whose chain or whose target's chain holds one is refused (`refuse_merge_under_hold`).
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
HISTORY_DOCTYPE = "Batch Processing History"  # the child DocType of HISTORY_TABLE
HISTORY_ACTION = "Quality Status Changed"  # an option of Batch Processing History.processing_action

# How the guard knows a save is this module's: the writer puts THIS OBJECT in doc.flags for the length of its own
# save. It is compared by identity, so nothing that arrives as data (a form, the REST API, an import file, a
# Server Script's dict) can be it; see `refuse_hand_change` for what remains.
WRITER_FLAG = "lot_quality_writer"
_WRITER = object()
# The same, for the saves of a RELEASE only (an approval or a withdrawal of a certificate, `LotTable.save` with
# `LotTable.release` set): the lot controller asks `is_release_save` and skips its per-record mail and its Lote AMB
# sync. Not set by `insert_child`, nor by a hand hold placed or lifted: those saves are not a release. Also set for
# the saves of the install reset (TASKS-390 item 7, `patches/v15_9_0`): a reset at migrate mails nobody per record.
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
	type (the field links to one type), else empty. `standing`: a list (`_standing_list`); of several of the
	same type, the one that holds the status when it is of that type, else the first."""
	fieldname = CERTIFICATE_LINKS.get(certificate_doctype)
	if not fieldname or record.get(fieldname) != certificate:
		return {}
	same = [s for s in standing if s.get("doctype") == certificate_doctype and s.get("name")]
	if not same:
		return {fieldname: None}
	# a result with no mapping is refused, with its own message, where the status is decided
	mapped = [
		(s.get("doctype"), s.get("name"), s.get("result"), RESULT_TO_LOT_STATUS[s.get("result")])
		for s in standing
		if s.get("result") in RESULT_TO_LOT_STATUS
	]
	holder = _worst(mapped)
	if holder and holder[0] == certificate_doctype and holder[1]:
		return {fieldname: holder[1]}
	return {fieldname: same[0].get("name")}


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
	on a hand hold that no certificate speaks for, unless a hand hold is on the chain above its stored parent or
	above its new parent (decision 329, `_refuse_move_under_hold`). Not covered: a direct column write of the
	parent, as above; `certificate_withdrawn` therefore also looks for its records by `released_by*`. A merge:
	`refuse_merge_under_hold`.
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
		_refuse_move_under_hold(doc, old, new)
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


def _hold_on_chain(start, skip=()):
	"""Walk up `parent_batch_amb` from `start` (included), reading each stored record -> the name of the first one
	whose `status_source` is "Hold action", or None. Loop guard: a record met twice ends the walk, and so does a
	record in `skip` (the record being moved: its own row is the one being changed) or one that does not exist;
	neither refuses."""
	seen, name = set(skip), start
	while name and name not in seen:
		seen.add(name)
		record = frappe.db.get_value(DOCTYPE, name, ["name", PARENT_FIELD, "status_source"], as_dict=True)
		if not record:
			return None
		if record.get("status_source") == HOLD_ACTION:
			return record.get("name") or name
		name = record.get(PARENT_FIELD)
	return None


def _refuse_move_under_hold(doc, old, new):
	"""Decision 329: a change of `parent_batch_amb` is refused when the chain above the stored parent `old` (the
	parent included) or above the new parent `new` (included) holds a record on a hand hold: the move would take
	the record, and what is below it, out from under the hold, or put it under one. The record itself is not
	judged (narrowest reading): a hold on the record being moved moves with it. Every role; the guard's two
	lines call it."""
	for parent, way in ((old, "off"), (new, "under")):
		held = _hold_on_chain(parent, skip=(doc.name,) if doc.name else ())
		if not held:
			continue
		if way == "off":
			what = _("it would leave the hold on lot record {0} (its parent {1} or above)").format(held, old)
		else:
			what = _("it would come under the hold on lot record {0} (its new parent {1} or above)").format(
				held, new
			)
		frappe.throw(
			_(
				"Lot record {0} cannot be moved (parent: {1} to {2}): {3}. A record on a hand hold, and what is below it, stays where it is until the hold is lifted."
			).format(doc.name or _("new"), old or _("none"), new or _("none"), what),
			frappe.ValidationError,
			title=_("Quality status"),
		)


def refuse_merge_under_hold(doc, method=None, old=None, new=None, merge=False):
	"""doc_events hook on Batch AMB, `before_rename` (decision 329). What Frappe 16.17.5 does
	(`frappe/model/rename_doc.py` `rename_doc`): it runs `before_rename` on the record (the controller's, then the
	hooks), then rewrites EVERY Link field that names the old name to the new one by a direct column write
	(`update_link_field_values` -> `frappe.db.set_value(..., update_modified=False)`: no event on the records
	changed), the children's `parent_batch_amb` included; on a merge it then deletes the old record.
	  * A plain rename moves nothing: the children follow the renamed record, the hold stays on it. Not refused.
	  * A merge moves the old record's children (and every other Link to it: Batches, certificates) under the
	    target, and deletes the old record with its hold. Refused when the chain from the old record (included)
	    or from the target (included) holds a record on a hand hold, for every role.
	Not covered: `rename_doc(..., validate=False)` from server code, which skips `before_rename`."""
	if not merge:
		return
	for start in (old or doc.name, new):
		held = _hold_on_chain(start)
		if held:
			frappe.throw(
				_(
					"Lot record {0} cannot be merged into {1}: lot record {2} is on a hand hold, and a merge would move the records linked to {0} out from under that hold, or under it. Lift the hold first."
				).format(old or doc.name, new, held),
				frappe.ValidationError,
				title=_("Quality status"),
			)


# every link from a lot record to a certificate: the two the approval writes and the older `coa_amb`
COPY_CLEARED_LINKS = (*LINK_FIELDS, "coa_amb")
# Decision 353 (TASKS-398): the child tables of a lot record that hold what THIS lot did or holds (record tables).
# A copy starts with none of their rows; the setup table (`batch_parameters`: what to measure, with its limits) is
# kept. `processing_history` (346) is emptied with them. `custom_historic_sales_lots` is a site Custom Field (patch
# v15_8_0): emptied here when present; the form's Duplicate copies it (its "no copy" is not in the DocType JSON).
# TASKS-398 review, finding 1: on a site where `output_products` / `batch_output_products` ALSO exist as site Custom
# Fields (no copy off), Frappe's meta keeps the Custom Field over the DocType JSON, so the form's Duplicate copies
# them there despite the JSON's "no copy"; only a Custom Field change fixes that (for a ruling). The server copy
# empties them on every site.
COPY_EMPTIED_RECORD_TABLES = (
	"output_products",
	"batch_output_products",
	"container_barrels",
	"quality_test_results",
	"custom_historic_sales_lots",
)
COPY_KEPT_SETUP_TABLES = ("batch_parameters",)


def reset_for_copy(doc):
	"""A copy of a lot record is a new record: it starts Pending, with no certificate and, decision 345 (TASKS-392,
	extends 343), with no certificate link (`coa_reference`, `coa_amb2`, `coa_amb`), as a new child does.
	Decision 346 (TASKS-397): and with none of the source's history rows (`processing_history` empty); the parent
	pointer is kept. `frappe.copy_doc` copies child tables whatever "no copy" says (its `ignore_no_copy` defaults
	to True), so the rows are emptied here, not left to the DocType flag. Decision 353 (TASKS-398): so are the record
	tables (`COPY_EMPTIED_RECORD_TABLES`); the setup table (`COPY_KEPT_SETUP_TABLES`) is kept."""
	doc.quality_status = PENDING
	for fieldname in GUARDED_FIELDS[1:]:
		doc.set(fieldname, None)
	for fieldname in COPY_CLEARED_LINKS:
		doc.set(fieldname, None)
	doc.set(HISTORY_TABLE, [])
	# decision 353 (TASKS-398): no record table is copied; the setup table is kept as copied
	for fieldname in COPY_EMPTIED_RECORD_TABLES:
		doc.set(fieldname, [])


def insert_copy(copy, source):
	"""`duplicate_batch`'s insert (decision 346, TASKS-397). `copy` is the new document made by `frappe.copy_doc`
	of lot record `source` (its name), not yet inserted. It is reset (`reset_for_copy`: Pending, no certificate,
	no certificate link, no history row of the source) and inserted by `insert_child` under the record its parent
	pointer names, which it keeps: the same function, so the same rule, as a child created under that record
	(336, 342, 344), and ONE history row that says "copied from <source>" in every case.

	The parent is read as stored (`LotTable.get`), not from the copy. A copy with no parent (a lot) is born Pending
	with the one row "copied from <source>". (A parent pointer to a record that no longer exists is refused by the
	framework's link check before this runs.)

	TASKS-397 review, finding 1: the one row needs a plant and an item, as every history row does. A source that
	lacks them is refused here, naming the source and what it lacks, before anything is written: a copy of it
	could not carry its "copied from" row."""
	missing = missing_for_history_row(copy)
	if missing:
		frappe.throw(
			_(
				"Lot record {0} cannot be duplicated: it has no {1}, and the copy's one history row (\"copied from "
				'{0}") needs it. Fill it on lot record {0} and duplicate it again.'
			).format(source, _(" and no ").join(missing)),
			title=_("Duplicate Batch"),
		)
	reset_for_copy(copy)
	parent_name = copy.get(PARENT_FIELD)
	parent = (LotTable().get(parent_name) if parent_name else None) or {}
	return insert_child(copy, parent, copied_from=source)


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
	# {record name: name of the history row its FIRST save of this table wrote}, in the order saved: where a
	# summary that was not sent is recorded (`_note_on_release_row`, decision 328). An attribute, not a method:
	# amb_w_tds's cross-app test checks that its table answers every public method of this one.
	written_rows = None

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
		The install reset (TASKS-390 item 7) uses it too, for a record that cannot carry a history row: that
		record is then named in the patch's output and in an Info Comment on it.
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
		row = doc.append(HISTORY_TABLE, _history_row(doc, before, after, reason, note, self.acting_on))
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
		# Frappe names the appended child row when the save inserts it
		row_name = row.get("name") if isinstance(row, dict) else getattr(row, "name", None)
		if row_name:
			if self.written_rows is None:
				self.written_rows = {}
			self.written_rows.setdefault(name, row_name)
		return True

	def _add_to_row(self, row_name, text):
		"""Append `text` to the `comments` of one stored history row, by a direct column write on the child table
		(`Batch Processing History`): no document event runs, the lot record itself is not saved again, and no
		guarded field is touched. Private: see `written_rows`."""
		_append_to_row(row_name, text)


def missing_for_history_row(doc):
	"""-> the labels of what a lot record lacks to carry a history row (its plant; its current item or its item to
	manufacture), [] when it can carry one. The rule of `_history_row`; the install reset (item 7) asks it too."""
	plant = doc.get("current_plant2")
	item_code = doc.get("current_item_code") or doc.get("item_to_manufacture")
	return [
		label
		for label, value in (
			(_("Current Plant"), plant),
			(_("Current Item Code / Item to Manufacture"), item_code),
		)
		if not value
	]


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
	missing = missing_for_history_row(doc)
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


def certificate_approved(certificate_doctype, certificate, lot, result, others=None):
	"""The certificate reached "Approved". Map `result` (Pass/Fail/Partial) and write the lot `lot` (a Batch AMB
	name, level 1 or 2) as source "Own certificate", with the certificate in the lot's link field of its type
	(`coa_reference` / `coa_amb2`), then write down the hierarchy (B4): every record below it becomes "Inherited"
	from this certificate (no link written), except a record with a certificate of its own and what is below
	that. Raises (frappe.throw) if result has no mapping or a record cannot be written; everything is written
	in the caller's transaction, nothing is committed here. When any record was written, ONE summary is queued
	(`send_release_summary`). -> the number of records written.

	`others` (decision 338, worst result wins): None, or a list of dicts {"doctype", "name", "result"} of the OTHER
	certificates that still stand for the same record `lot` (amb_w_tds's definition of "standing"). The record
	takes the worst mapped status (Failed over Hold over Passed) of this certificate and `others`; when one of
	`others` is strictly worse, IT holds the status: `released_by*` name it, the records below inherit from it, and
	the history row says that it holds the status. On a tie this certificate holds it. The link field still
	names this certificate (it is the one approved for the record). None or [] is the behaviour before TASKS-390."""
	journal, table = [], LotTable()
	written = _approve(table, certificate_doctype, certificate, lot, result, journal, others=others)
	send_release_summary(certificate_doctype, certificate, lot, journal, result=result, table=table)
	return written


def certificate_withdrawn(certificate_doctype, certificate, lot, standing=None):
	"""The certificate left "Approved" by Reject (to Draft) or a shared COA AMB was cancelled.

	`standing` = None, or a dict {"doctype":…, "name":…, "result":…} of ANOTHER approved certificate of the same
	record that still stands: the lot then takes that one's mapped status instead of Pending. It may also be a
	list of such dicts (decision 338): the lot then takes the worst mapped status of them (Failed over Hold over
	Passed; on a tie the first in the list), from the certificate that has it. Resets only the
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
	journal, table = [], LotTable()
	written = _withdraw(table, certificate_doctype, certificate, lot, standing, journal)
	send_release_summary(certificate_doctype, certificate, lot, journal, withdrawn=True, table=table)
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


# decision 338: the worse verdict wins when more than one certificate stands for a record
SEVERITY = {"Passed": 1, "Hold": 2, "Failed": 3}


def _standing_list(standing):
	"""`standing` as a list: None or [] -> [], one dict -> [it], a list -> itself."""
	if not standing:
		return []
	if isinstance(standing, dict):
		return [standing]
	return list(standing)


def _checked(entry, this, what):
	"""One standing certificate -> (doctype, name, result, mapped status), or refused: it must not be `this`, its
	result must have a mapping and it must be named with its type."""
	if (entry.get("doctype"), entry.get("name")) == this:
		frappe.throw(what)
	status = _mapped(entry.get("result"))
	if not (entry.get("doctype") and entry.get("name")):
		frappe.throw(_("The certificate that still stands must be named with its type."))
	return (entry.get("doctype"), entry.get("name"), entry.get("result"), status)


def _worst(candidates):
	"""-> the candidate (doctype, name, result, status) with the worst status; the first of equals."""
	worst = None
	for candidate in candidates:
		if worst is None or SEVERITY[candidate[3]] > SEVERITY[worst[3]]:
			worst = candidate
	return worst


def _approve(table, certificate_doctype, certificate, lot, result, journal=None, others=None):
	status = _mapped(result)
	this = (certificate_doctype, certificate)
	beside = [
		_checked(entry, this, _("The certificate being approved cannot also be one that stands beside it."))
		for entry in _standing_list(others)
	]
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
	holder = _worst([(certificate_doctype, certificate, result, status), *beside])
	view = (holder[0], holder[1], holder[3])
	reason = f"certificate {certificate_doctype} {certificate} approved with result {result}"
	if holder[:2] != this:
		reason += (
			"; {} {} (result {}) still stands for this record and holds the status {}: the worst result wins"
		).format(*holder)
	return _write_down(
		table,
		record,
		dict(_values(record, view, OWN_CERTIFICATE), **_link_at_approval(certificate_doctype, certificate)),
		view,
		_has_no_certificate_of_its_own,
		reason,
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

	standing = _standing_list(standing)
	link = _link_at_withdrawal(record, certificate_doctype, certificate, standing)
	written = 0
	if wrote(record):
		if standing:
			stands = [
				_checked(
					entry, this, _("The certificate that still stands cannot be the one that is withdrawn.")
				)
				for entry in standing
			]
			holder = _worst(stands)
			view = (holder[0], holder[1], holder[3])
			source = OWN_CERTIFICATE
			reason = (
				f"certificate {certificate_doctype} {certificate} withdrawn; "
				f"{holder[0]} {holder[1]} still stands with result {holder[2]}"
			)
			if len(stands) > 1:
				listed = ", ".join(f"{d} {n} {r}" for d, n, r, _s in stands)
				reason += (
					f"; it holds the status {holder[3]}, the worst of the {len(stands)} certificates still "
					f"standing ({listed})"
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


def _inherits_at_birth(child, parent):
	"""Decisions 342 and 344 (TASKS-391/392, amend 336): -> (doctype, certificate, status) a new child takes as
	"Inherited", or None when it is born Pending. Only a CONTAINER (level 3) created directly under a LOT (level 1,
	also an empty level) or a SUB-LOT (level 2) whose status comes from a certificate (`released_by` and its type
	set) and whose `certificate_status` is a status a certificate gives (Passed / Failed / Hold): the record
	directly above it, as the write-down of an approval writes containers under either. Everything else is born
	Pending as in 336: a sub-lot (level 2) under anything, a container under another container, a child of any
	other level.

	The status is the parent's `certificate_status`, not its `quality_status`: the two are the same unless the
	parent is on a hand hold, and then the container takes what the parent's certificate says, not the hold,
	exactly as the write-down of an approval writes the containers below a held lot or sub-lot (`_plan`; decision 315,
	reading 1 of TASKS-391): the hold is on the one record that is held."""
	if _level(child) != CONTAINER_LEVEL or _level(parent) not in CERTIFICATE_LEVELS:
		return None
	certificate = _certificate_of(parent)
	says = parent.get("certificate_status")
	if not certificate or not certificate[0] or says not in RESULT_TO_LOT_STATUS.values():
		return None
	return (certificate[0], certificate[1], says)


def insert_child(child, parent, copied_from=None):
	"""`create_child_batch`'s insert, and `insert_copy`'s. `child` is the new document, not yet inserted; `parent`
	the document it is created under. Whatever the caller put in the quality fields is cleared first.

	Decisions 342 and 344 (TASKS-391/392, amend 336): a CONTAINER (level 3) created directly under a LOT (level 1)
	or a SUB-LOT (level 2) whose status comes from a certificate takes that record's verdict as "Inherited" from
	the same certificate (`released_by_doctype` / `released_by` / `certificate_status` the same as the parent's),
	with ONE history row "created after approval of <certificate>: inherits from <parent>": containers follow the
	record above them (decision 319), and a container born Pending there could never be certified (certificates
	are made for levels 1 and 2). A parent on a hand hold: the container takes what the parent's certificate says
	(its `certificate_status`), not Hold, as the write-down does (`_inherits_at_birth`). No certificate link is written on the container (the
	write-down writes none on records that inherit either).

	Decision 336 (TASKS-390), for every other child: born Pending with no certificate (empty `status_source`,
	`released_by*`, `certificate_status`). Under a parent that names a certificate it gets one history row
	"created after approval of <certificate>: Pending until certified". That is: a SUB-LOT (level 2) created after
	an approval; a container under another container (`create_child_batch` does not check the parent's level); a
	container under a lot or sub-lot whose certificate says no status. How "after" is
	decided: a child inserted here is after the approval of every certificate its parent carries at this moment,
	with no date to compare. A record carries a certificate in `released_by*` only once an approval (or the
	write-down of one, decision 319) has written it there, and the write-down reaches every record below that
	exists at that moment; the child does not exist until this insert. A parent that names no certificate
	(Pending, or a hand hold with no certificate behind it): the child is born Pending with no row, an insert like
	any other, judged by the guard.

	A record of level 4 or more is never created here by `create_child_batch`, which refuses every level but 2
	and 3. The write-down does not write such a record either (`_plan`).

	`copied_from` (decision 346, TASKS-397, from `insert_copy`): the name of the lot record this one is a copy of.
	The rule above is the same; the one history row also says "copied from <source>", and a copy gets that row
	even under a parent that names no certificate (then it says only that, and the copy is Pending). A copy may
	be of any level, a lot (level 1, usually with no parent) included."""
	for fieldname in GUARDED_FIELDS:
		child.set(fieldname, None)
	child.set("quality_status", PENDING)
	certificate = _certificate_of(parent)
	if not certificate and not copied_from:
		return child.insert()  # Pending, no certificate: an insert like any other, judged by the guard
	values = dict.fromkeys(GUARDED_FIELDS)
	values["quality_status"] = PENDING
	named = f"{certificate[0]} {certificate[1]}".strip() if certificate else ""
	inherits = _inherits_at_birth(child, parent) if certificate else None
	if not certificate:
		reason = f"copied from {copied_from}"
		note = None
	elif inherits:
		values = {
			"quality_status": inherits[2],
			"status_source": INHERITED,
			"released_by_doctype": inherits[0],
			"released_by": inherits[1],
			"certificate_status": inherits[2],
		}
		reason = "created after approval of {}: inherits from {}".format(named, parent.get("name"))
		note = None
		if parent.get("status_source") == HOLD_ACTION:
			note = (
				"{} is on a hand hold: the container takes what {} says ({}), not the hold, as the write-down "
				"of an approval does".format(parent.get("name"), named, inherits[2])
			)
		for fieldname, value in values.items():
			child.set(fieldname, value)
	else:
		reason = f"created after approval of {named}: Pending until certified"
		note = "created under {}, whose status comes from {}".format(parent.get("name"), named)
	if certificate and copied_from:
		note = " | ".join(part for part in (note, f"copied from {copied_from}") if part)
	child.append(HISTORY_TABLE, _history_row(child, dict.fromkeys(GUARDED_FIELDS), values, reason, note))
	# the row is the module's: the guard's first line names it (`_name_own_rows`)
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


NOT_SENT = "summary not sent"


def _valid_addresses(emails):
	"""-> the addresses Frappe would accept (`frappe.utils.validate_email_address`, without raising). Checked here,
	before `sendmail`, because Frappe's queue drops a mail with an invalid recipient by writing an Error Log
	("Invalid email address", `QueueBuilder.as_dict`) and queuing nothing; decision 328 wants no Error Log. A User's
	address is validated when the User is saved, so this matters only for an address written past that."""
	return [email for email in emails if frappe.utils.validate_email_address(email)]


def _note_on_release_row(table, lot, journal, text):
	"""Write `text` into the release's own history row (decision 328), in the release's transaction: the row of the
	certificate's lot record `lot` when this release saved it, else the row of the first record this release saved
	(a release that wrote only records elsewhere: a withdrawal that reset moved records). Every release that wrote
	anything saved at least one record with a row (a container is column-written only together with the saved
	record above it), so a row is there. -> the record whose row got the text, or None."""
	rows = getattr(table, "written_rows", None) or {}
	order = [lot] + [j["name"] for j in journal]
	for name in order:
		if name in rows:
			table._add_to_row(rows[name], text)
			return name
	return None


def _append_to_row(row_name, text):
	"""Append `text` to the `comments` of one stored history row (`Batch Processing History`) by a direct column
	write on the child table: no document event runs, the lot record is not saved again, no guarded field is
	touched, `modified` is not changed."""
	stored = frappe.db.get_value(HISTORY_DOCTYPE, row_name, "comments") or ""
	frappe.db.set_value(
		HISTORY_DOCTYPE,
		row_name,
		"comments",
		f"{stored} | {text}" if stored else text,
		update_modified=False,
	)


def _info_comment(lot, text):
	"""An Info Comment on lot record `lot` (what `Document.add_comment("Info", text)` inserts, without loading the
	record). Used where a lot record has no history row to carry `text`."""
	return frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"comment_email": frappe.session.user,
			"reference_doctype": DOCTYPE,
			"reference_name": lot,
			"content": text,
		}
	).insert(ignore_permissions=True)


def _note_on_latest_row(lot, text):
	"""Decision 334 (the share writes no row of its own): append `text` to the LATEST history row of lot record `lot`
	(highest `idx` of its `processing_history`), by the same column write as a release's note. A lot record with no
	history row gets an Info Comment instead. -> where it was written, in words for the user."""
	row_name = frappe.db.get_value(
		HISTORY_DOCTYPE,
		{"parent": lot, "parenttype": DOCTYPE, "parentfield": HISTORY_TABLE},
		"name",
		order_by="idx desc",
	)
	if row_name:
		_append_to_row(row_name, text)
		return _("This is written in the history of lot record {0}.").format(lot)
	_info_comment(lot, text)
	return _("Lot record {0} has no history row: this is written in a comment on it.").format(lot)


def send_release_summary(
	certificate_doctype, certificate, lot, journal, result=None, withdrawn=False, table=None
):
	"""ONE message for one approval or withdrawal that wrote any record (`journal` non-empty); nothing otherwise.

	Sent after commit only, and dropped on rollback, because of how Frappe 16.17.5 queues mail:
	`frappe.sendmail` (`frappe/email/__init__.py`) builds an Email Queue document and INSERTS it in the current
	transaction (`QueueBuilder.process(send_now=False)` -> `EmailQueue.new` -> `insert`; Email Queue is InnoDB).
	With the default `delayed=True` and no `now`, nothing else happens: the row is sent later by the scheduler's
	queue flush, which sees it only once the transaction has committed; a rollback removes the row with the
	release (also a rollback to a savepoint). `now=True` would add `q.send` to `frappe.db.after_commit` (reset on
	a full rollback, but not on a savepoint rollback), so it is NOT used. No commit here.

	A release never fails because of mail (decision 328). What is not a sent summary is written into the release's
	own history row ("summary not sent: <reason>", no address; `_note_on_release_row`, a column write of that row's
	`comments` in the same transaction), and the release stands, with no Error Log: see `_send_summary`, the one
	function of this module that calls `frappe.sendmail`. No recipient at all (every one disabled, or without an
	address): nothing is sent and nothing is written, as before."""
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

	def note(text):
		where = _note_on_release_row(table, lot, journal, text)
		return _("This is written in the history of lot record {0}.").format(where) if where else None

	return _send_summary(certificate_doctype, certificate, recipients, subject, body, note, _("the release"))


def share_summary_text(certificate_doctype, certificate, lot, result):
	"""-> (subject, HTML body) of the share's summary (decision 334): the certificate, its result, that it was
	shared, by whom, for which lot record."""
	e = html.escape
	subject = f"{certificate_doctype} {certificate} shared ({result or ''}): lot record {lot}"
	body = (
		f"<p>{e(certificate_doctype)} {e(certificate)} was shared with result {e(result or '')}, "
		f"for lot record {e(lot)}.</p><p>Shared by {e(frappe.session.user or '')}.</p>"
	)
	return subject, body


def certificate_shared(certificate_doctype, certificate, lot):
	"""The certificate was shared (COA AMB `on_submit`; decision 334): ONE summary, under the rules of a release.

	Writes no lot status and no history row of its own. Recipients as for a release (`release_summary_recipients`:
	the certificate's `filled_by`, the session user who shared, the owner of the Work Order of lot record `lot`;
	enabled users only, never Administrator or Guest, each once). Queued, no `now`, through `_send_summary`, so it
	never fails the share for a reason of mail: muted mail, no outgoing account, nothing queued or no valid address
	is written as "summary not sent: <reason>" on the LATEST history row of lot record `lot` by a column write in
	the share's transaction, or in an Info Comment on the lot record when it has no history row
	(`_note_on_latest_row`); no Error Log. `lot` empty: nothing. -> what `frappe.sendmail` returned, or None."""
	if not lot:
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
	subject, body = share_summary_text(certificate_doctype, certificate, lot, row.get("overall_result"))
	return _send_summary(
		certificate_doctype,
		certificate,
		recipients,
		subject,
		body,
		lambda text: _note_on_latest_row(lot, text),
		_("the share"),
	)


def _send_summary(certificate_doctype, certificate, recipients, subject, body, note, what):
	"""THE ONE call of `frappe.sendmail` in this module (a release's summary and a share's). `note(text)` writes
	"summary not sent: ..." where the caller keeps it and returns, in words, where that is (or None); `what` names
	the action that stands ("the release", "the share"). What is not a sent summary, each written by `note`:
	  * mail is muted (decision 333): `frappe.are_emails_muted()` (Frappe 16.17.5: `flags.mute_emails` or the site
	    config's `mute_emails`) is asked BEFORE `sendmail`, which is then not called. Under muted mail Frappe's
	    `EmailAccount.find_default_outgoing` returns a dummy account, so `sendmail` would queue a row "Not Sent" that
	    leaves when mail is unmuted;
	  * every address invalid (`_valid_addresses`), so nothing reaches Frappe's queue, which would write an Error Log;
	  * `sendmail` raises `frappe.OutgoingEmailError`: there is no outgoing Email Account
	    (`EmailAccount.find_outgoing(_raise_error=True)` throws it while the queue row is built). It is the only
	    exception caught, because it is the only one queuing a mail raises for a reason of mail: an invalid address
	    is caught inside Frappe (`QueueBuilder.as_dict`, which logs it and queues nothing; see `_valid_addresses`),
	    and SMTP is not touched without `now`. Anything else (a read, the insert of the queue row, a bug) is not
	    mail being off and still fails the action. The message `frappe.throw` put on the response for that
	    exception is taken off again (the action did not fail), and a notice says the summary was not sent;
	  * `sendmail` queues nothing for a non-empty list (every recipient has unsubscribed, or an address refused).
	A recipient left out for an invalid address, when others were queued, is noted too."""
	valid = _valid_addresses(recipients)
	if not valid:
		reason = f"no valid address for its {len(recipients)} recipient(s)"
		return _not_sent(certificate_doctype, certificate, reason, note, what)
	if frappe.are_emails_muted():
		return _not_sent(certificate_doctype, certificate, "mail is muted", note, what)
	messages = getattr(frappe.local, "message_log", None)
	shown = len(messages) if isinstance(messages, list) else None
	try:
		queued = frappe.sendmail(
			recipients=valid,
			subject=subject,
			message=body,
			reference_doctype=certificate_doctype,
			reference_name=certificate,
		)
	except frappe.OutgoingEmailError:
		if shown is not None:
			frappe.local.message_log = frappe.local.message_log[:shown]  # the action stands: not an error
		reason = "no outgoing email account (OutgoingEmailError)"
		return _not_sent(certificate_doctype, certificate, reason, note, what)
	if not queued:
		# TASKS-388 review, finding 1: Frappe queues nothing both when every recipient has unsubscribed and when the
		# queue refused an address (a recipient's or the sender's); the text says both, not a cause it cannot know.
		reason = (
			f"no mail queued for its {len(valid)} recipient(s) "
			"(every recipient unsubscribed, or an address the mail queue refused)"
		)
		return _not_sent(certificate_doctype, certificate, reason, note, what)
	if len(valid) < len(recipients):
		# TASKS-388 review, finding 3: a recipient left out for an invalid address is said on the action's row.
		dropped = len(recipients) - len(valid)
		note(f"{NOT_SENT} to {dropped} recipient(s): no valid address")
	return queued


def _not_sent(certificate_doctype, certificate, reason, note, what):
	"""The summary was not sent: `note` writes why, the user is told, the action stands. -> None"""
	where = note(f"{NOT_SENT}: {reason}")
	frappe.msgprint(
		_("{0} {1}: {2} stands; its summary was not sent ({3}).").format(
			certificate_doctype, certificate, what, reason
		)
		+ (" " + where if where else ""),
		indicator="orange",
		alert=True,
	)
	return None
