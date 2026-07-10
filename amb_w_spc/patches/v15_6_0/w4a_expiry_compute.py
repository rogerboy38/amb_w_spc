# Copyright (c) 2026, AMB and contributors
"""W4a v15_6_0 — neutralize the wrong ``fetch_from`` on Batch AMB ``expiry_date``.

The field fetched ``work_order_ref.actual_start_date`` — i.e. the START date —
which mislabels expiry as the manufacturing date and overwrites any expiry value
on every save that has a linked Work Order. This patch clears that ``fetch_from``
via a Property Setter, so the field is no longer auto-filled from the WO start.

Idempotent (Property Setter upsert). One Property Setter row; zero data rows.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    make_property_setter(
        "Batch AMB", "expiry_date", "fetch_from", "", "Data",
        validate_fields_for_doctype=False,
    )
    frappe.clear_cache(doctype="Batch AMB")
