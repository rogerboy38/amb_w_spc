# Copyright (c) 2026, AMB and contributors
"""W1 (Task #36, ruling R-ID-1) — Batch AMB lot-identity regime.

Adds the `custom_batch_origin` marker (Native | Migrated) and relaxes
`work_order_ref` so Migrated lots — which carry a legacy FoxPro golden verbatim
and may have no Work Order — can save. Native keeps the hard WO requirement.

Schema-via-fixtures, not console (console-no-commit lesson x3, 2026-07-08):
create_custom_fields + Property Setters, both idempotent. The controller
(batch_amb.py) reads custom_batch_origin to gate golden derivation.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    create_custom_fields(
        {
            "Batch AMB": [
                {
                    "fieldname": "custom_batch_origin",
                    "label": "Batch Origin",
                    "fieldtype": "Select",
                    "options": "Native\nMigrated",
                    "default": "Native",
                    "reqd": 1,
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "insert_after": "custom_batch_level",
                    "description": (
                        "Native = golden minted from the Work Order (born-new). "
                        "Migrated = legacy FoxPro golden (lote_real) kept verbatim "
                        "per R-ID-1; never WO-derived or regenerated."
                    ),
                }
            ]
        },
        ignore_validate=True,
    )

    # REV-W1-3 (sandbox): reqd:1 field defaults apply to NEW docs only — every
    # PRE-W1 Batch AMB row has NULL custom_batch_origin and would throw "Batch
    # Origin is mandatory" on its next resave (prod edits batches daily).
    # Backfill them all to Native (true by definition — their goldens were
    # WO-minted). Idempotent: only touches NULL/empty rows.
    frappe.db.sql(
        "UPDATE `tabBatch AMB` SET custom_batch_origin = 'Native' "
        "WHERE custom_batch_origin IS NULL OR custom_batch_origin = ''"
    )

    # work_order_ref: mandatory for Native only. Migrated lots (pre-ERPNext,
    # no WO) set sales_order_related directly (O-1 hybrid). reqd:1 in the
    # doctype JSON is overridden to 0 + a conditional mandatory_depends_on.
    make_property_setter(
        "Batch AMB", "work_order_ref", "reqd", 0, "Check",
        validate_fields_for_doctype=False,
    )
    make_property_setter(
        "Batch AMB", "work_order_ref", "mandatory_depends_on",
        'eval:doc.custom_batch_origin!=="Migrated"', "Data",
        validate_fields_for_doctype=False,
    )

    frappe.clear_cache(doctype="Batch AMB")
