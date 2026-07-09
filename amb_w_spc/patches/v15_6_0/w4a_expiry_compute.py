# Copyright (c) 2026, AMB and contributors
"""W4a (Task #36) — Expiry derivation prerequisite.

Neutralizes the wrong ``fetch_from`` on Batch AMB ``expiry_date``: it fetched
``work_order_ref.actual_start_date`` — i.e. the START date — which both mislabels
expiry as the manufacturing date AND clobbers the controller-derived expiry on
every save with a linked Work Order. W4a's controller compute
(``batch_amb_expiry_hook`` / ``compute_batch_expiry``) owns ``expiry_date`` now:
E.D. = M.D. + Item.shelf_life_in_days, derived only when empty.

Idempotent (Property Setter upsert). DEV-only build; no transport.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    make_property_setter(
        "Batch AMB", "expiry_date", "fetch_from", "", "Data",
        validate_fields_for_doctype=False,
    )
    frappe.clear_cache(doctype="Batch AMB")
