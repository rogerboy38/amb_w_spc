"""Task #9 — QIPG canonical tree reconstruction (DOCUMENTATION-OF-RECORD).

THIS PATCH IS NOT REGISTERED IN patches.txt.

It exists as an auditable, replayable artifact reconstructing what an
undocumented manual script did on VM3 between 2026-05-28T17:30Z and
2026-05-28T20:24Z. That script:
  1. Created Common Root + 7 L2 category groups (Organoleptic / Physicochemical
     / Microbiological / Pesticides / Contaminant / Other Analysis / Aloe Vera
     Nutrients), matching phase_1c_tab_v2.js's SC5V2_COMMON_ROOT +
     SC5V2_L2_CATEGORIES constants.
  2. Re-parented all `PARAM - {L2} LQD` leaves (created earlier by
     amb_w_spc.patches.phase1a6_qipg_l4_ingest from a HOST CSV at
     /media/sf_E_DRIVE/Claude/sysmayal/ingest/out/qipg_mapping.csv, not in
     repo) from their original `{L2} LQD` parents to the new canonical L2
     groups under Common Root.
  3. Stripped ` LQD` suffix from leaf names (e.g., "APPEARANCE -
     Organoleptic LQD" → "APPEARANCE - Organoleptic").
  4. Renamed each `{L2} LQD` parent → `{L2} LQD [ARCHIVED-2026-05]` (now
     top-level orphans, no QIPs attached).
  5. Called rebuild_tree to fix NSM lft/rgt.

The script itself was never committed to git, never logged in tabPatch Log.
Discovered via row-delta analysis on 2026-05-30 (Task #9 §0 reconstruction).

This patch is the canonical replay artifact: documented, deterministic,
in-repo. Anyone needing to reproduce VM3's QIPG state from scratch can run
this directly via `bench execute amb_w_spc.patches.v14_3_8.\
task9_qipg_canonical_tree_reconstructed.execute`.

For transport to vpt-docker / vpp: the parallel deliverable is the FIXTURE at
amb_w_spc/fixtures/quality_inspection_parameter_group.json (411 records
exported from VM3 post-mass-mod). bench migrate installs the fixture; this
patch is the WHY documentation, not the install mechanism.

Idempotency: select-before-write on every mutation. Safe to replay on any
site, including ones where the canonical tree is already partially or fully
present.

Caveats:
  - Depends on apps/amb_w_spc/amb_w_spc/data/foxpro_extracts/\
    parameter_group_and_choices.json (in-repo, 517 entries). Per-leaf names
    derive from the JSON keys (parameter names in ALL CAPS, e.g. "APPEARANCE").
  - The 2026-05-28 script may have made manual fixups (e.g. typo corrections,
    one-off renames) we cannot recover. This reconstruction matches the bulk
    pattern; the fixture is the source-of-truth for exact replication.
  - Does not handle the 8 Products * legacy top-levels or 4 ARCHIVED-2026-05
    orphans (those existed before the 2026-05-28 mass-mod and stay where
    they are).

Author: claude-sandbox @ VMBox3
Date: 2026-05-30
Task: #9 reconstruction (deep research path C)
"""
import json
from pathlib import Path

import frappe


# Mirrors phase_1c_tab_v2.js SC5V2_COMMON_ROOT + SC5V2_L2_CATEGORIES.
SC5V2_COMMON_ROOT = "Common Root"
SC5V2_L2_CATEGORIES = [
    "Organoleptic",
    "Physicochemical",
    "Microbiological",
    "Pesticides",
    "Contaminant",
    "Other Analysis",
    "Aloe Vera Nutrients",
]

# Mirrors phase1a6_qipg_l4_ingest L2_TO_ERPNEXT_BASE map. Used to derive
# leaf name suffix from FoxPro 'group' field.
L2_TO_ERPNEXT_BASE = {
    "organoleptic":     "Organoleptic",
    "physicochemical":  "Physicochemical",
    "microbiological":  "Microbiological",
    "other analysis":   "Other Analysis",
    "pesticides":       "Pesticides",
    "contaminant":      "Contaminant",
    "contaminants":     "Contaminant",   # accept plural input
    "nutrients":        "Nutrients",     # ERPNext uses singular "Nutrients" in legacy leaf names
    "aloe vera nutrients": "Aloe Vera Nutrients",  # but canonical L2 parent is plural "Nutrients" form
}

# Canonical L2 parent for each FoxPro group token. Differs from the legacy
# leaf-name suffix in the case of Nutrients (legacy: "Nutrients", canonical
# parent: "Aloe Vera Nutrients").
L2_TO_CANONICAL_PARENT = {
    "organoleptic":          "Organoleptic",
    "physicochemical":       "Physicochemical",
    "microbiological":       "Microbiological",
    "other analysis":        "Other Analysis",
    "pesticides":            "Pesticides",
    "contaminant":           "Contaminant",
    "contaminants":          "Contaminant",
    "nutrients":             "Aloe Vera Nutrients",
    "aloe vera nutrients":   "Aloe Vera Nutrients",
}


def _ensure_qipg(name: str, is_group: int, parent: str | None) -> bool:
    """Idempotent get-or-create. Returns True if created, False if existed."""
    if frappe.db.exists("Quality Inspection Parameter Group", name):
        return False
    doc = frappe.get_doc({
        "doctype": "Quality Inspection Parameter Group",
        "group_name": name,
        "is_group": is_group,
        "custom_parameter_group_child": parent,
    })
    doc.insert(ignore_permissions=True)
    return True


def execute():
    # ─── Phase 1 — Create canonical skeleton ───
    created = 0
    if _ensure_qipg(SC5V2_COMMON_ROOT, is_group=1, parent=None):
        created += 1
    for l2 in SC5V2_L2_CATEGORIES:
        if _ensure_qipg(l2, is_group=1, parent=SC5V2_COMMON_ROOT):
            created += 1

    # ─── Phase 2 — Create canonical leaves from FoxPro JSON ───
    data_file = Path(
        frappe.get_app_path(
            "amb_w_spc", "data", "foxpro_extracts",
            "parameter_group_and_choices.json"
        )
    )
    if not data_file.exists():
        frappe.throw(
            f"Phase 2 prerequisite missing: {data_file}. The reconstruction "
            "patch depends on the bundled FoxPro extract; cannot proceed."
        )

    with open(data_file) as f:
        fox = json.load(f)

    leaf_created = 0
    leaf_skipped = 0
    leaf_unmapped = 0
    for param_caps, info in fox.items():
        fox_group_lower = (info.get("group") or "").strip().lower()
        legacy_l2_suffix = L2_TO_ERPNEXT_BASE.get(fox_group_lower)
        canonical_parent = L2_TO_CANONICAL_PARENT.get(fox_group_lower)
        if not legacy_l2_suffix or not canonical_parent:
            leaf_unmapped += 1
            continue
        # Match phase1a6's name format post-LQD-strip: "{PARAM} - {L2}"
        safe = param_caps.replace("<", "lt").replace(">", "gt")
        leaf_name = f"{safe} - {legacy_l2_suffix}"
        if _ensure_qipg(leaf_name, is_group=0, parent=canonical_parent):
            leaf_created += 1
        else:
            leaf_skipped += 1

    # ─── Phase 3 — Migrate any pre-existing substrate-segmented residue ───
    # If vpt-docker has e.g. "APPEARANCE - Organoleptic LQD" with parent
    # "Organoleptic LQD" (phase1a6 output, never went through 2026-05-28 mass-
    # mod), re-parent it to canonical "Organoleptic" + rename to drop " LQD".
    legacy_l2_groups = [f"{l2} LQD" for l2 in SC5V2_L2_CATEGORIES]
    legacy_l2_groups += [f"Nutrients LQD"]  # phase1a6 used "Nutrients" not "Aloe Vera Nutrients"
    migrated = 0
    for legacy_parent in legacy_l2_groups:
        if not frappe.db.exists("Quality Inspection Parameter Group", legacy_parent):
            continue
        children = frappe.db.sql(
            """
            SELECT name FROM `tabQuality Inspection Parameter Group`
            WHERE custom_parameter_group_child = %s
            """,
            (legacy_parent,), as_dict=True,
        )
        for c in children:
            # Derive canonical leaf name + parent
            current = c.name
            if current.endswith(f" - {legacy_parent}"):
                new_name = current[: -len(f" {SC5V2_L2_CATEGORIES[0]} LQD".replace(SC5V2_L2_CATEGORIES[0], "")) - len(legacy_parent.replace(' LQD', ''))]
                # Simpler: strip " LQD" from the suffix
                new_name = current.replace(" LQD", "", 1)
            else:
                new_name = current  # name doesn't match expected pattern; leave it
            # Derive canonical parent: strip " LQD" from legacy parent name,
            # then map "Nutrients" → "Aloe Vera Nutrients".
            l2_no_lqd = legacy_parent[:-4]  # strip " LQD"
            canonical_p = "Aloe Vera Nutrients" if l2_no_lqd == "Nutrients" else l2_no_lqd
            # Select-before-write idempotency
            cur_parent = frappe.db.get_value(
                "Quality Inspection Parameter Group", current,
                "custom_parameter_group_child"
            )
            if cur_parent != canonical_p:
                frappe.db.set_value(
                    "Quality Inspection Parameter Group", current,
                    "custom_parameter_group_child", canonical_p,
                    update_modified=False,
                )
                migrated += 1
            # Rename leaf if needed
            if new_name != current and not frappe.db.exists(
                "Quality Inspection Parameter Group", new_name
            ):
                frappe.rename_doc(
                    "Quality Inspection Parameter Group", current, new_name,
                    force=True, ignore_permissions=True,
                )
        # Rename legacy parent to ARCHIVED form
        archived_name = f"{legacy_parent} [ARCHIVED-2026-05]"
        if not frappe.db.exists("Quality Inspection Parameter Group", archived_name):
            frappe.rename_doc(
                "Quality Inspection Parameter Group", legacy_parent, archived_name,
                force=True, ignore_permissions=True,
            )

    # ─── Phase 4 — rebuild NSM ───
    from frappe.utils.nestedset import rebuild_tree
    rebuild_tree("Quality Inspection Parameter Group")

    frappe.db.commit()

    print(
        f"Task #9 canonical tree reconstruction: "
        f"skeleton created={created}; "
        f"leaves created={leaf_created} skipped={leaf_skipped} unmapped={leaf_unmapped}; "
        f"legacy migrated={migrated}; tree rebuilt."
    )
