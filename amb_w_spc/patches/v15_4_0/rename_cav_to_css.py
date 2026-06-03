"""Rename Customer Acceptable Value DocType -> Customer-Specific Specification.

Driven by Mavis peer review (2026-06-03, 27 regulatory + industry sources)
finding that "Customer Acceptable Value" is non-standard.
"Customer-Specific Specification" (CSS) is the AS9100/IATF 16949 standard.

Idempotent: skips if NEW exists or OLD missing. Uses frappe.rename_doc
with force=True to handle both DocType meta + tab<Name> table rename in
one atomic operation. Companion to amb_w_tds v14_3_8 field rename.

Rollback (if needed post vpt-docker failure):
    frappe.rename_doc('DocType', 'Customer-Specific Specification',
                      'Customer Acceptable Value', force=True)
or, equivalently, deploy a reverse-patch with the names swapped.

Brown-field VM3: existing CAV doctype + tabCustomer Acceptable Value
table renamed in place.
Fresh-install vpt-docker: no CAV doctype exists; "OLD missing" guard
fires; patch no-ops; schema_sync then creates tabCustomer-Specific
Specification from the renamed JSON directly.
"""
import frappe


def execute():
    OLD = "Customer Acceptable Value"
    NEW = "Customer-Specific Specification"

    if not frappe.db.exists("DocType", OLD):
        return  # fresh install or already migrated

    if frappe.db.exists("DocType", NEW):
        return  # rename already applied (idempotent guard)

    frappe.rename_doc("DocType", OLD, NEW, force=True, merge=False)
    frappe.db.commit()
