# Copyright (c) 2026, AMB and contributors
"""TASKS-390 item 7 (decision 339): lots set Passed / Failed / Hold by hand under the old guard are reset at install.

Every Batch AMB whose `quality_status` is not Pending (empty counts as Pending, as everywhere in lot_quality) and
whose `released_by` is empty is set to Pending through THE ONE WRITER of lot_quality, with no hand path:

  * a record that can carry a history row (a plant, and a current item or an item to manufacture): the writer's
    document save (`lot_quality._set` on the writer's table: guard pass, ONE history row "reset at install: no
    certificate", the save); the lot controller's per-record mail and Lote AMB sync do not run for these saves,
    as for a release's (`lot_quality.is_release_save`: the table carries `release`);
  * a record that cannot carry one (no plant, or neither item field): reset all the same by the writer's direct
    column write (`LotTable.write_columns`, the one the writer uses for containers: no document event, no history
    row), and LISTED in this patch's output and in an Info Comment on the record. Never skipped silently.

What the writer decides stays decided: a record on a hand hold (`status_source` "Hold action", decision 315) keeps
"Hold" whatever is asked of it, so the writer writes nothing there; such a record is listed as kept.

A save the lot controller refuses (TASKS-390 review, finding 3). The full save runs the whole lot controller on a
legacy record, and one record with a broken link or any other failed validation would stop the whole migrate. So
each save runs inside a savepoint (`frappe.db.savepoint`); when it raises a `frappe.ValidationError` the record is
rolled back to that savepoint (`frappe.db.rollback(save_point=...)`: what the failed save wrote to the database is
undone) and reset by the same column write as a record that cannot carry a history row, LISTED in the output with
the refusal and given an Info Comment that says why. Never skipped silently. Why `ValidationError` and only that:
it is what `frappe.throw` raises by default and the base of every refusal of a document's content in Frappe
16.17.5 (`LinkValidationError` for a broken link, `MandatoryError`, `CharacterLengthExceededError`,
`DoesNotExistError`, `TimestampMismatchError`, `UniqueValidationError`, `DataError`, ... are subclasses), i.e. a
fault of the RECORD. Two subclasses are not about the record and still fail the patch: `ImplicitCommitError` (a DDL
statement inside the save: code, not data) and `InReadOnlyMode` (the site cannot be written at all). Everything
else also fails the patch, with the record's name printed and noted on the exception: a database error (deadlock,
lock timeout, lost connection; MariaDB may have rolled back the whole transaction, savepoint included),
`frappe.DuplicateEntryError` (a NameError, not a ValidationError), `frappe.PermissionError`, or a programming error of
a hook (TypeError, AttributeError, KeyError, ...). The patch then stops migrate; nothing of it is kept (Frappe rolls
the patch back) and it runs again at the next migrate. A savepoint undoes database writes only: what a failed save
queued to run after the commit (`frappe.db.after_commit`, a job enqueued after commit, a realtime message) is not
taken back (Frappe's own note on `Database.savepoint`); the lot controller's mail and Lote AMB sync do not run in
these saves (see above).

What the full save may also rewrite on a legacy record (the cost of going through the one writer; the column write
does none of this): Batch AMB `validate` / `before_save` (`batch_amb.py`) recompute the golden number fields when
empty (`set_batch_naming`: `custom_golden_number`, `custom_generated_batch_name`, family / subfamily /
consecutive), `planned_qty` from the Work Order (`update_planned_qty_from_work_order`, with a history row of its own
when it differs), empty item / BOM fields backfilled from the Work Order (`_sync_from_work_order`), `item_name` /
`uom` from the Item, the title (`auto_set_title`), container totals and weights, costs, yield, the processing
timestamps, and the derived expiry (`batch_amb_expiry_hook`: `expiry_date` = manufacturing date + the Item's shelf
life, only when empty); `on_update` runs the batch projection (flag-gated, `project_batch_amb_outputs`) and the
nested-set update. `modified` / `modified_by` change in both paths.

Lots a legacy certificate still names (finding 5). The ruling is literal: what is reset is decided by
`released_by` alone, so a lot whose `released_by` is empty is reset even when a COA AMB or COA AMB2 that names it in
`batch_reference` still stands (Certificate Shared at docstatus 1, or Approved at docstatus 0, approved by a recorded
person: `approved_by` set, and not Administrator or Guest). Its history row still says "no certificate". This patch
does not change that; it COUNTS and LISTS these lots apart, with the certificate(s), so the reader sees how many.
The certificates are read only where they exist: amb_w_tds may not be installed, or an older one may lack a field;
then that certificate type is not read and the output says so.

Counts are printed before and after. Idempotent: a second run finds nothing to reset (every record it reset is
Pending) and writes nothing; Frappe's Patch Log runs it once anyway.

Where it runs: `patches.txt` of this app has no section headers, so Frappe reads it in the old format and runs
every line BEFORE the DocType sync of migrate (pre_model_sync). On a site that does not yet have the new fields
(`status_source`, `released_by`, ... of TASKS-384) they would not exist when this runs, and the patch, logged as
run, would never reset anything. So it first reloads the two DocTypes it writes (Batch AMB and its history row,
`frappe.reload_doc`, what the DocType sync would do a moment later). If a field is still absent after that, it
prints which and does nothing.
"""

import frappe

from amb_w_spc.sfc_manufacturing import lot_quality as lq

REASON = "reset at install: no certificate"
NEEDED_FIELDS = (*lq.GUARDED_FIELDS,)
READ_FIELDS = ["name", *lq.GUARDED_FIELDS, "current_plant2", "current_item_code", "item_to_manufacture"]
# one savepoint around each save, reused record after record (a savepoint of the same name replaces the earlier one)
SAVEPOINT = "reset_lots_at_install"
# finding 5: the certificates (amb_w_tds) that may still stand for a lot, and the field that holds each one's
# workflow state (amb_w_tds `certificate_rules.STATE_FIELD`, the `workflow_state_field` of its workflows)
CERTIFICATE_STATE_FIELDS = {"COA AMB": "workflow_state_1", "COA AMB2": "workflow_state"}
# (state, docstatus) in which a certificate still stands for the lot it names
STANDING_STATES = (("Certificate Shared", 1), ("Approved", 0))
CERTIFICATE_LOT_FIELD = "batch_reference"
CERTIFICATE_APPROVER_FIELD = "approved_by"


class InstallTable(lq.LotTable):
	"""The writer's table, for this patch: its saves are quiet like a release's (no per-record mail to the quality
	roles, no Lote AMB sync), and three reads / one write of its own."""

	release = ("install", "reset at install")

	def missing_fields(self):
		return [f for f in NEEDED_FIELDS if not frappe.db.has_column(lq.DOCTYPE, f)]

	def records(self):
		return frappe.get_all(lq.DOCTYPE, fields=READ_FIELDS, order_by="name asc", limit_page_length=0)

	def comment(self, name, text):
		return lq._info_comment(name, text)

	# finding 3: one savepoint around each save (Frappe 16.17.5 `Database.savepoint` / `rollback(save_point=)` /
	# `release_savepoint`)
	def savepoint(self):
		frappe.db.savepoint(SAVEPOINT)

	def rollback_to_savepoint(self):
		frappe.db.rollback(save_point=SAVEPOINT)

	def release_savepoint(self):
		frappe.db.release_savepoint(SAVEPOINT)

	def standing_certificates(self):
		"""Finding 5. -> ({lot: [(certificate type, certificate, state), ...]}, [what could not be read]): every COA
		AMB / COA AMB2 that names a lot in `batch_reference` and still stands (STANDING_STATES), approved by a
		recorded person. A certificate type whose DocType or one of whose fields is not on this site is not read
		and is named in the second list."""
		found, unread = {}, []
		for doctype, state_field in CERTIFICATE_STATE_FIELDS.items():
			if not frappe.db.exists("DocType", doctype):
				unread.append(f"{doctype} (no such DocType on this site)")
				continue
			meta = frappe.get_meta(doctype)
			absent = [
				f
				for f in (CERTIFICATE_LOT_FIELD, CERTIFICATE_APPROVER_FIELD, state_field)
				if not meta.has_field(f)
			]
			if absent:
				unread.append(f"{doctype} (no field {', '.join(absent)})")
				continue
			for state, docstatus in STANDING_STATES:
				rows = frappe.get_all(
					doctype,
					filters={
						state_field: state,
						"docstatus": docstatus,
						CERTIFICATE_LOT_FIELD: ["is", "set"],
						CERTIFICATE_APPROVER_FIELD: ["is", "set"],
					},
					fields=["name", CERTIFICATE_LOT_FIELD, CERTIFICATE_APPROVER_FIELD],
					order_by="name asc",
					limit_page_length=0,
				)
				for row in rows:
					approver = (row.get(CERTIFICATE_APPROVER_FIELD) or "").strip()
					if approver and approver not in lq.NOT_PEOPLE:
						found.setdefault(row[CERTIFICATE_LOT_FIELD], []).append((doctype, row["name"], state))
		return found, unread


def execute():
	for doctype in ("batch_amb", "batch_processing_history"):
		frappe.reload_doc("sfc_manufacturing", "doctype", doctype)
	run(InstallTable())


def _to_reset(record):
	pending = lq._norm("quality_status", record.get("quality_status")) == lq.PENDING
	return not pending and not record.get("released_by")


def _counts(records):
	by_status = {status: 0 for status in lq.LOT_STATUSES}
	for record in records:
		status = lq._norm("quality_status", record.get("quality_status"))
		by_status[status] = by_status.get(status, 0) + 1
	return {
		"records": len(records),
		"by_status": by_status,
		"not_pending_without_certificate": sum(1 for r in records if _to_reset(r)),
	}


def _say_counts(when, counts, out):
	statuses = ", ".join(f"{status} {n}" for status, n in counts["by_status"].items())
	out(
		f"{when}: {counts['records']} Batch AMB; {statuses}; "
		f"not Pending with no certificate: {counts['not_pending_without_certificate']}"
	)


def _refusal(e):
	"""A refusal as one line of the output: its type and its message, whitespace collapsed, at most 300 characters."""
	text = " ".join(str(e).split())
	if len(text) > 300:
		text = text[:297] + "..."
	return f"{type(e).__name__}: {text}" if text else type(e).__name__


def _is_record_fault(e):
	"""Finding 3: a refusal of the record's content (see the module docstring), not of the site or of the code."""
	not_the_record = tuple(
		c
		for c in (getattr(frappe, "ImplicitCommitError", None), getattr(frappe, "InReadOnlyMode", None))
		if c
	)
	return isinstance(e, frappe.ValidationError) and not isinstance(e, not_the_record)


def _column_reset(table, name, was, why):
	"""The reset by the writer's column write, with an Info Comment on the record. -> True when written, False when
	the writer keeps the record as it is (a hand hold)."""
	current = table.get(name)
	values = lq._resolve(current, lq.PENDING, source="")
	if lq._after(current, values) is None:
		return False
	table.write_columns([name], values)
	table.comment(
		name,
		"Quality status reset at install (TASKS-390, decision 339) from {} to {}: no certificate. {} The reset was "
		"a direct column write of the lot quality fields.".format(was, values["quality_status"], why),
	)
	return True


def _listed(names):
	return f"{len(names)}{': ' + ', '.join(names) if names else ''}"


def run(table, out=print):
	"""The reset against `table` (`InstallTable`, or an in-memory table in the tests). -> a dict of what was done."""
	out("Batch AMB quality status reset at install (TASKS-390, decision 339)")
	missing = table.missing_fields()
	if missing:
		out(
			"Batch AMB has no field {}: this site does not have the lot quality fields; nothing done.".format(
				", ".join(missing)
			)
		)
		return {
			"missing": missing,
			"before": None,
			"after": None,
			"saved": [],
			"column": [],
			"refused": [],
			"kept": [],
			"certified": [],
		}
	records = table.records()
	before = _counts(records)
	_say_counts("before", before, out)
	standing, unread = table.standing_certificates()
	for what in unread:
		out(f"certificates not read: {what}")
	saved, column, refused, kept = [], [], [], []
	for record in records:
		if not _to_reset(record):
			continue
		name, was = record["name"], lq._norm("quality_status", record.get("quality_status"))
		missing_for_row = lq.missing_for_history_row(record)
		if not missing_for_row:
			table.savepoint()
			try:
				changed = lq._set(table, name, lq.PENDING, reason=REASON)
			except Exception as e:
				if not _is_record_fault(e):
					out(f"failed on {name}: {_refusal(e)}; the patch stops, nothing of it is kept")
					e.add_note(f"Batch AMB {name}: quality status reset at install (TASKS-390, decision 339)")
					raise
				# finding 3: what the refused save wrote is undone, then the column write
				table.rollback_to_savepoint()
				reason = _refusal(e)
				if _column_reset(
					table,
					name,
					was,
					f"The save of this record through the writer was refused ({reason}); no history row was written.",
				):
					refused.append((name, reason))
				else:
					kept.append(name)
				continue
			table.release_savepoint()
			(saved if changed else kept).append(name)
			continue
		if _column_reset(
			table,
			name,
			was,
			"No history row could be written, the record has no {}.".format(" / ".join(missing_for_row)),
		):
			column.append(name)
		else:
			kept.append(name)
	reset = sorted([*saved, *column, *(n for n, _r in refused)])
	certified = [n for n in reset if n in standing]
	out(f"reset with a history row ({REASON!r}): {len(saved)}")
	out(
		"reset WITHOUT a history row (no plant, or neither item field; an Info Comment on each): "
		f"{_listed(column)}"
	)
	out(
		"the writer's save refused, so reset WITHOUT a history row (an Info Comment on each): "
		f"{len(refused)}{': ' + '; '.join(f'{n} ({r})' for n, r in refused) if refused else ''}"
	)
	out(
		"reset although a certificate names it (the ruling resets by released_by alone): "
		f"{len(certified)}"
		+ (
			": "
			+ "; ".join(
				"{}, {}".format(
					n, ", ".join(f"certificate {dt} {c} ({state})" for dt, c, state in standing[n])
				)
				for n in certified
			)
			if certified
			else ""
		)
	)
	out(f"kept: on a hand hold, which the writer keeps (decision 315): {_listed(kept)}")
	after = _counts(table.records())
	_say_counts("after", after, out)
	return {
		"missing": [],
		"before": before,
		"after": after,
		"saved": saved,
		"column": column,
		"refused": [n for n, _r in refused],
		"kept": kept,
		"certified": certified,
	}
