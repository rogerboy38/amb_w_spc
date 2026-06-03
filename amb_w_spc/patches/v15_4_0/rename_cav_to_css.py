"""Rename Customer Acceptable Value DocType -> Customer-Specific Specification.

Driven by Mavis peer review (2026-06-03, 27 regulatory + industry sources)
finding that "Customer Acceptable Value" is non-standard.
"Customer-Specific Specification" (CSS) is the AS9100/IATF 16949 standard.

Idempotent: skips if NEW exists or OLD missing. Uses frappe.rename_doc
with force=True to handle both DocType meta + tab<Name> table rename in
one atomic operation. Companion to amb_w_tds v14_3_8 field rename.

Rollback (if needed post vpt-docker failure):
    Re-apply with OLD/NEW swapped in a reverse-patch (same in-flight
    developer_mode dance).

Brown-field VM3: existing CAV doctype + tabCustomer Acceptable Value
table renamed in place.
Fresh-install vpt-docker: no CAV doctype exists; "OLD missing" guard
fires; patch no-ops; schema_sync then creates tabCustomer-Specific
Specification from the renamed JSON directly.

Pre-flight discovery on VM3 (2026-06-03): frappe.rename_doc on standard
(non-custom) DocTypes checks frappe.conf.developer_mode and raises
CannotCreateStandardDoctypeError when off. Production sites don't enable
developer_mode. We temporarily flip it inside the patch and restore in
finally — contained to this single patch execution, doesn't affect other
patches in the same migrate run.
"""
import frappe


def execute():
    OLD = "Customer Acceptable Value"
    NEW = "Customer-Specific Specification"

    if not frappe.db.exists("DocType", OLD):
        return  # fresh install or already migrated

    if frappe.db.exists("DocType", NEW):
        return  # rename already applied (idempotent guard)

    # rename_doc on standard (non-custom) DocType requires developer_mode.
    # Production sites have it OFF; temporarily flip for this rename only.
    original_dev_mode = getattr(frappe.conf, "developer_mode", 0)
    frappe.conf.developer_mode = 1
    try:
        frappe.rename_doc("DocType", OLD, NEW, force=True, merge=False)
        frappe.db.commit()
    finally:
        frappe.conf.developer_mode = original_dev_mode
