# Copyright (c) 2026, AMB and contributors
"""TASKS-399 (decisions 355 and 356) and TASKS-400 (decision 357): "no copy" on the site Custom Fields of
Batch AMB that hold what the source lot did, so the form's Duplicate does not copy them.

On a site where one of these fields is ALSO a site Custom Field, Frappe 16.17.5's meta keeps the Custom Field over
the DocType JSON (`Meta.add_custom_fields` appends it; the field map keeps the last of a name), so the JSON's "no
copy" (decisions 353 and 356) does not hold there. For each name below, wherever a Custom Field of Batch AMB with
that fieldname exists, this patch sets its `no_copy` to 1 and nothing else: it deletes nothing and changes no other
property, by a single-column write (`frappe.db.set_value`, `update_modified=False`) rather than a Custom Field save,
which would also rewrite the DocType's columns. Then the Batch AMB meta cache is cleared.

Printed per field: "absent", "already 1" or "set". Idempotent: a second run prints "already 1" and writes nothing;
safe on a site where none exists.

Where it runs: `patches.txt` of this app has no section headers, so Frappe runs every line BEFORE the DocType sync
(pre_model_sync). That order is right: the patch writes rows of Custom Field, a core DocType whose table and
`no_copy` column exist before any app's sync, and the sync of Batch AMB's JSON neither reads nor rewrites Custom
Field rows; migrate clears the caches after the sync in any case."""

import frappe

from amb_w_spc.sfc_manufacturing.lot_quality import COPY_CLEARED_HEADER_FIGURES, COPY_CLEARED_PROCESS_FIELDS

DOCTYPE = "Batch AMB"
# decision 355: the three record tables that are site Custom Fields on the sandbox (353); decision 356: every header
# figure a copy clears, since any of them may be a site Custom Field on a site not read (TASKS-399 review, finding
# 1; on the sandbox only `custom_produced_qty` is). An absent one prints "absent" and costs nothing.
FIELDS = (
	"output_products",
	"batch_output_products",
	"custom_historic_sales_lots",
	*COPY_CLEARED_HEADER_FIGURES,
	*COPY_CLEARED_PROCESS_FIELDS,  # decision 357 (TASKS-400); on the sandbox the production dates and batch_status
)


def execute():
	results = set_no_copy()
	for fieldname, state in results:
		print(f"{DOCTYPE}.{fieldname}: {state}")
	return results


def set_no_copy():
	"""-> [(fieldname, "absent" | "already 1" | "set")], one per name of FIELDS (and per Custom Field row)."""
	results = []
	changed = False
	for fieldname in FIELDS:
		rows = frappe.get_all(
			"Custom Field", filters={"dt": DOCTYPE, "fieldname": fieldname}, fields=["name", "no_copy"]
		)
		if not rows:
			results.append((fieldname, "absent"))
			continue
		for row in rows:
			if int(row.get("no_copy") or 0) == 1:
				results.append((fieldname, "already 1"))
				continue
			frappe.db.set_value("Custom Field", row["name"], "no_copy", 1, update_modified=False)
			results.append((fieldname, "set"))
			changed = True
	if changed:
		frappe.clear_cache(doctype=DOCTYPE)
	return results
