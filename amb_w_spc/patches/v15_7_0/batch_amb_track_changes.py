# Copyright (c) 2026, AMB and contributors
"""Enable the Batch AMB audit trail: ``track_changes = 1`` (DocType-level).

``track_changes`` is a DocType-LEVEL property (not a field property), so this
creates a DocType-level Property Setter (``for_doctype=True``, ``fieldname=None``).
With it on, ``doc.save()`` on a Batch AMB writes a Version row — capturing
child-table (container_barrels) deltas for the label/lot pass. Ordered after
v15_6_0 so the expiry_date fetch_from is cleared first, then tracking enables.

Idempotent (Property Setter upsert). One Property Setter row; zero data rows.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    make_property_setter(
        "Batch AMB", None, "track_changes", 1, "Check",
        for_doctype=True, validate_fields_for_doctype=False,
    )
    frappe.clear_cache(doctype="Batch AMB")
