# Copyright (c) 2026, AMB and contributors
"""B-3b (LOOP-1) — historic FoxPro lot capture on Batch AMB, AT THE PARENT.

Adds two additive fields, both Custom Fields so delivery is a DB fact:

    custom_historic_lot_real    Data  — scalar, 1:1. The FoxPro `lote_real`
                                        verbatim for a Migrated lot.
    custom_historic_sales_lots  Table — 1:N. `lote_de_venta` rows: a lot can be
                                        sold under many sales lots, so a scalar
                                        could only store the second by
                                        destroying the first.

⭐ WHY A CHILD TABLE ON THE PARENT AND NOT INSIDE `container_barrels` (G-5/M90):
`base_document` gives every child row `_table_fieldnames = MappingProxyType({})`
— empty and immutable — and both load and save iterate exactly that. A table
nested in a child table is never loaded, never saved, and NEVER THROWS: the grid
renders, accepts input and discards it. `Batch AMB` is a parent (`istable=0`),
so a child table on it is the supported shape.

⛔ THIS IS NOT `in_pedvta` REBUILT. It captures what the legacy system recorded;
it does not reimplement the sales-order document.

⚠ DELIVERY IS A DB FACT, NOT A GIT FACT (H-1d / I-1). A git-scoped check goes
GREEN on a site where this patch never ran and the fields do not exist. The
criterion is: this patch is logged in `tabPatch Log` AND both fields exist in
`tabCustom Field` on the target site. `custom_batch_origin` is DB-only for the
same reason and was the finding that produced this rule.

⭐ ADDITIVE ONLY. The golden minter, `_enforce_l1_golden_fence`, the mint block
and `_apply_golden_decomposition` are untouched. Nothing here derives, mints,
re-mints or validates a golden number.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CHILD_DOCTYPE = "Batch Historic Sales Lot"


def execute():
    # The child DocType ships in the app; on a site that has not reloaded it yet
    # the Table field would point at nothing, so make the dependency explicit
    # rather than relying on migrate ordering.
    if not frappe.db.exists("DocType", CHILD_DOCTYPE):
        frappe.reload_doc("sfc_manufacturing", "doctype", "batch_historic_sales_lot")

    create_custom_fields(
        {
            "Batch AMB": [
                {
                    "fieldname": "custom_historic_section",
                    "label": "Historic Lot Capture (FoxPro)",
                    "fieldtype": "Section Break",
                    "insert_after": "custom_batch_origin",
                    "collapsible": 1,
                },
                {
                    "fieldname": "custom_historic_lot_real",
                    "label": "Historic Lot Real (lote_real)",
                    "fieldtype": "Data",
                    "insert_after": "custom_historic_section",
                    "read_only": 0,
                    "in_standard_filter": 1,
                    "description": (
                        "The FoxPro lote_real, verbatim. Quality may hand-edit this to "
                        "link a new Sysmayal-2.0 lot to its legacy past (C3). Never "
                        "derived from the golden and never used to mint one."
                    ),
                },
                {
                    "fieldname": "custom_historic_sales_lots",
                    "label": "Historic Sales Lots (lote_de_venta)",
                    "fieldtype": "Table",
                    "options": CHILD_DOCTYPE,
                    "insert_after": "custom_historic_lot_real",
                    "description": (
                        "1:N — a lot may be sold under several sales lots. Migration "
                        "populates these and users may add re-designations (C4)."
                    ),
                },
            ]
        },
        ignore_validate=True,
    )
