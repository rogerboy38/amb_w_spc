"""v15_1_5 — Rename Quality Inspection Parameter Custom Fields from custom_specification* → custom_value_*/custom_method.

Context (sysmayal-3 RELAY 20260601T013000Z + 20260601T020000Z): VM3 has the
NEW field names (custom_method, custom_value_text/min/max) but vpt-docker
still has the OLD names (custom_specification, custom_specification_text/
min/max). The rename was done on VM3 out-of-band (creation timestamps
2026-05-31 18:15Z on VM3 CFs) — never committed via a tracked patch. The
divergence was hidden until T18 Wave 2 (v15_2_0) STEP 0 pre-flight check
for NEW CFs would have failed on vpt-docker.

L180 in action: prod-only customization gap. VM3's CF rename via desk UI
(or programmatic out-of-band) was not captured in git history.

Sysmayal empirical inputs 20260601T020000Z:
  - 76 QIP rows on vpt-docker; 34/76 have custom_specification data
  - 0/76 have data in custom_specification_text/min/max (those are unused)
  - Sub-second ALTER lock; no concurrent-write concern
  - custom_specification is Link to Quality Inspection Method (must preserve FK)
  - Opinion: Frappe-native frappe.model.utils.rename_field preferred over
    hand-rolled SQL (atomic, FK-preserving, cache-invalidation built-in)

This patch implements the 4 renames using a hybrid approach:
  1. Create NEW Custom Field if missing (triggers Frappe's auto-schema-sync
     to add the NEW column to tabQuality Inspection Parameter)
  2. Call frappe.model.utils.rename_field.rename_field() to copy data from
     OLD column → NEW column (Frappe-native; preserves Link FK semantics)
  3. Delete OLD Custom Field (drops OLD column via Custom Field on_trash
     hook; next bench migrate's schema sync confirms drop)
  4. Clear meta cache so downstream patches (e.g. v15_2_0 STEP 0 preflight)
     see the NEW CFs

Renames (4 total):
  custom_specification        → custom_method            (Link → Quality Inspection Method)
  custom_specification_text   → custom_value_text        (Data)
  custom_specification_min    → custom_value_min         (Float)
  custom_specification_max    → custom_value_max         (Float)

Idempotency:
  - If NEW CF already exists AND OLD CF doesn't (VM3 path / post-rename
    sites): patch skips entirely
  - If both exist (mid-rename / partial sites): copies data + deletes OLD
  - If only OLD exists (fresh vpt-docker / hostinger-vpp path): performs
    full rename
  - If neither exists (fresh-fresh install pre-fixture-sync): skip; sync_
    fixtures will create NEW CFs via custom_field.json fixture

L188-safety: this patch touches `tabCustom Field` + `tabQuality Inspection
Parameter` only (both core ERPnext, always schema-synced). No sync_fixtures
call. No L188.5 hazard.

L192 compliance: companion fixture update (custom_field.json now has the
NEW-name CF entries) ships in the same commit. Fresh sites get NEW CFs via
fixture sync; patched sites get them via this rename.

References:
  - L150 (NestedSet parent_field) — sister: Frappe-native preferred over hand-rolled
  - L180 (prod-only customizations need periodic export audit) — this is the
    customization that needed audit
  - L188 / L188.5 (pre-fixture-sync hazards) — avoided by patch design
  - L190 (sub-numbered naming) — v15_1_5 between v15_1_0 and v15_2_0
  - L192 (fixture-edit-with-patch) — fixture + patch in same commit

Author: claude-sandbox @ VMBox3
Date: 2026-06-01
Task: T21+W2 bundled transport unblock (sysmayal-3 RELAY 20260601T020000Z)
"""
import frappe
from frappe.model.utils.rename_field import rename_field


QIP = "Quality Inspection Parameter"

# (old_fieldname, new_fieldname, fieldtype, options, insert_after, label)
RENAMES = [
    ("custom_specification",      "custom_method",     "Link",  "Quality Inspection Method", "parameter_group",   "Method"),
    ("custom_specification_text", "custom_value_text", "Data",  None,                        "description",       "Specification Text"),
    ("custom_specification_min",  "custom_value_min",  "Float", None,                        "custom_value_text", "Specification Min"),
    ("custom_specification_max",  "custom_value_max",  "Float", None,                        "custom_value_min",  "Specification Max"),
]


def _ensure_new_cf(new_fn, fieldtype, options, insert_after, label):
    """Create the NEW Custom Field if it doesn't already exist. Triggers Frappe's
    auto-schema-sync which adds the new column to tabQuality Inspection Parameter."""
    new_cf_name = f"{QIP}-{new_fn}"
    if frappe.db.exists("Custom Field", new_cf_name):
        return False
    doc_data = {
        "doctype": "Custom Field",
        "dt": QIP,
        "fieldname": new_fn,
        "fieldtype": fieldtype,
        "insert_after": insert_after,
        "label": label,
    }
    if options:
        doc_data["options"] = options
    doc = frappe.get_doc(doc_data)
    doc.insert(ignore_permissions=True)
    print(f"  Created NEW CF: {new_cf_name} (fieldtype={fieldtype}, insert_after={insert_after})")
    return True


def execute():
    if not frappe.db.exists("DocType", QIP):
        raise AssertionError(f"v15_1_5 STEP 0: {QIP} doctype missing")

    print(f"\nv15_1_5 — Rename QIP Custom Fields (custom_specification* → custom_value_*/custom_method)")
    pre_qip = frappe.db.count(QIP)
    print(f"  QIP row count: {pre_qip}")

    cfs_created = 0
    fields_renamed = 0
    old_cfs_deleted = 0
    skipped_already_renamed = 0

    for old_fn, new_fn, fieldtype, options, insert_after, label in RENAMES:
        old_cf_name = f"{QIP}-{old_fn}"
        new_cf_name = f"{QIP}-{new_fn}"
        old_cf_exists = frappe.db.exists("Custom Field", old_cf_name)
        new_cf_exists = frappe.db.exists("Custom Field", new_cf_name)

        if not old_cf_exists and new_cf_exists:
            # VM3 path: already renamed
            print(f"  Skip {old_fn} → {new_fn}: OLD absent, NEW present (already renamed)")
            skipped_already_renamed += 1
            continue

        if not old_cf_exists and not new_cf_exists:
            # Pre-fixture-sync fresh site (sync_fixtures will install NEW)
            print(f"  Skip {old_fn} → {new_fn}: neither OLD nor NEW exists (fresh site; sync_fixtures will install NEW)")
            continue

        # Either:
        #   (a) OLD exists and NEW doesn't — fresh vpt-docker; do the full rename
        #   (b) Both exist — partial state; copy data + delete OLD
        if not new_cf_exists:
            _ensure_new_cf(new_fn, fieldtype, options, insert_after, label)
            cfs_created += 1
            # Clear meta cache so rename_field sees the new field
            frappe.clear_cache(doctype=QIP)

        # Copy data via Frappe-native rename_field (preserves Link FK + cache invalidation)
        rename_field(QIP, old_fn, new_fn)
        fields_renamed += 1
        print(f"  rename_field: copied {old_fn} → {new_fn}")

        # Delete OLD CF (triggers column drop via Custom Field on_trash)
        frappe.delete_doc("Custom Field", old_cf_name, force=1, ignore_permissions=True)
        old_cfs_deleted += 1
        print(f"  Deleted OLD CF: {old_cf_name}")

    # Final cache flush
    frappe.clear_cache(doctype=QIP)
    frappe.db.commit()

    print(f"\nv15_1_5 summary:")
    print(f"  NEW CFs created: {cfs_created}")
    print(f"  Fields data-copied: {fields_renamed}")
    print(f"  OLD CFs deleted: {old_cfs_deleted}")
    print(f"  Skipped (already renamed): {skipped_already_renamed}")
    print(f"  Downstream v15_2_0 STEP 0 preflight will now find NEW CFs ✓")
