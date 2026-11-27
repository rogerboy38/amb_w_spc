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
"Hold" whatever is asked of it, so the writer writes nothing there; such a record is listed as kept. Any other
failure of a save (a validation of the lot controller) is not caught: the patch fails, visibly, with the record's
name, and migrate stops; nothing of it is kept (Frappe rolls the patch back) and it runs again at the next migrate.

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
		return {"missing": missing, "before": None, "after": None, "saved": [], "column": [], "kept": []}
	records = table.records()
	before = _counts(records)
	_say_counts("before", before, out)
	saved, column, kept = [], [], []
	for record in records:
		if not _to_reset(record):
			continue
		name, was = record["name"], lq._norm("quality_status", record.get("quality_status"))
		missing_for_row = lq.missing_for_history_row(record)
		if not missing_for_row:
			if lq._set(table, name, lq.PENDING, reason=REASON):
				saved.append(name)
			else:
				kept.append(name)
			continue
		current = table.get(name)
		values = lq._resolve(current, lq.PENDING, source="")
		if lq._after(current, values) is None:
			kept.append(name)
			continue
		table.write_columns([name], values)
		table.comment(
			name,
			"Quality status reset at install (TASKS-390, decision 339) from {} to {}: no certificate. No history "
			"row could be written, the record has no {}; the reset was a direct column write of the lot quality "
			"fields.".format(was, values["quality_status"], " / ".join(missing_for_row)),
		)
		column.append(name)
	out(f"reset with a history row ({REASON!r}): {len(saved)}")
	out(
		"reset WITHOUT a history row (no plant, or neither item field; an Info Comment on each): "
		f"{len(column)}{': ' + ', '.join(column) if column else ''}"
	)
	out(
		"kept: on a hand hold, which the writer keeps (decision 315): "
		f"{len(kept)}{': ' + ', '.join(kept) if kept else ''}"
	)
	after = _counts(table.records())
	_say_counts("after", after, out)
	return {"missing": [], "before": before, "after": after, "saved": saved, "column": column, "kept": kept}
