"""v14_3_8.5 prerequisite — Install canonical QIPG tree for fresh-site deployments.

Context (sysmayal-3 NACK 20260531T164414Z + cowork-ops diagnostic intel):
Hostinger-vpp (srv1415373 / erp.sysmayal2.cloud) is a FRESH V14.2.0 deployment
with no canonical QIPG tree yet. State observed:
  - 0 canonical L2 categories (Common Root + 7 L2 absent)
  - 54 legacy substrate-segmented QIPGs ("Physicochemical LQD", etc.)
  - 91 QIPs, 2794 IQI rows pointing at legacy QIPGs
  - NSM zombie: "Physicochemical LQD Filtred Workstation" at lft=0, rgt=0
  - v15 schema patches already applied (setup_qip_group_tree_extension,
    phase1a6_qipg_l4_ingest, populate_iqi_parameter_group)
  - v14_3_7 backfill applied (1119 substrate writes)
  - v14_3_8/9/10/11/12/13 ALL BLOCKED

v14_3_9 task11 has a self-bootstrap precondition (line 106
`_verify_canonical_tree_present`) requiring 8 canonical QIPGs (Common Root +
7 L2 categories). On vpt-docker that tree was installed via sync_fixtures of
`amb_w_spc/fixtures/quality_inspection_parameter_group.json` (Task #9; 411
records; 210 KB) during a prior migrate cycle. On fresh-vpp this is the FIRST
migrate, and Frappe runs patches BEFORE sync_fixtures (per migrate.py:
patches → sync_fixtures → after_migrate). So v14_3_9 task11 fails immediately
with `ValidationError: Task #11 prerequisites missing` — chicken-and-egg.

v14_3_8.5 (this patch) breaks the egg:
  STEP 1 — Idempotent skip if Common Root already present (vpt-docker /
           VM3 path — no-op).
  STEP 2 — Defensive cleanup of NSM zombie at lft=0 if present (vpp-
           specific; harmless on sites without zombie).
  STEP 3 — Targeted single-fixture import: import_file_by_path on ONLY
           amb_w_spc/fixtures/quality_inspection_parameter_group.json.
           Avoids broad sync_fixtures(app='amb_w_spc') iteration which
           would touch fixture files for DocTypes whose tables aren't
           yet schema-synced (substrate.json → tabSubstrate missing →
           crash). L188.5 sibling pattern — see sysmayal-3 NACK2 catch
           2026-05-31T17:09Z.
  STEP 4 — rebuild_tree to ensure NSM positions consistent post-fixture-sync.
  STEP 5 — Assert verification: Common Root + 7 L2 categories now present.

Pre-condition: amb_w_spc/fixtures/quality_inspection_parameter_group.json
must be on disk at patch-execution time (it is, since v14_3_8_5 ships with
the same commit / branch tip as the fixture). Verified by sysmayal-3
diagnostic intel.

Side effects on sites where Common Root already exists (VM3 / vpt-docker):
ZERO. STEP 1 short-circuits the entire patch.

References:
  - L188 (banked 2026-05-31) — pre-fixture-sync patch preconditions on
    fresh sites (the original lesson).
  - L188.5 cand (banked 2026-05-31) — sync_fixtures(app=...) broad-app
    iteration touches DocType tables not yet schema-synced. Sibling of L188.
  - L189 (banked) — stale patch docstrings during architecture changes
    (applies to v14_3_9 task11 docstring update in this commit's predecessor).

Author: claude-sandbox @ VMBox3
Date: 2026-05-31
Task: #15 Phase B unblock v2 (hostinger-vpp NACK2 — substrate fixture
       crashed sync_fixtures iteration)
"""
import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.utils.nestedset import rebuild_tree


QIPG = "Quality Inspection Parameter Group"
COMMON_ROOT = "Common Root"
L2_CATEGORIES = [
    "Organoleptic",
    "Physicochemical",
    "Microbiological",
    "Pesticides",
    "Contaminant",
    "Other Analysis",
    "Aloe Vera Nutrients",
]
NSM_ZOMBIE_NAME = "Physicochemical LQD Filtred Workstation"


def execute():
    # ─── STEP 1: Idempotent skip ───
    if frappe.db.exists(QIPG, COMMON_ROOT):
        print(f"v14_3_8.5: '{COMMON_ROOT}' present → canonical tree already "
              f"installed; skipping prereq (vpt-docker / VM3 path).")
        return

    print(f"v14_3_8.5: '{COMMON_ROOT}' missing → fresh-site path (e.g. vpp). "
          f"Triggering pre-fixture-sync prereq install.")

    # ─── STEP 2: Defensive NSM zombie cleanup (vpp-specific) ───
    if frappe.db.exists(QIPG, NSM_ZOMBIE_NAME):
        zombie_lft = frappe.db.get_value(QIPG, NSM_ZOMBIE_NAME, "lft")
        if zombie_lft == 0:
            print(f"v14_3_8.5: removing NSM zombie '{NSM_ZOMBIE_NAME}' at lft=0 "
                  f"before fixture sync (would block tree rebuild integrity).")
            frappe.db.sql(
                "DELETE FROM `tabQuality Inspection Parameter Group` "
                "WHERE name = %s AND lft = 0",
                (NSM_ZOMBIE_NAME,),
            )
            frappe.db.commit()

    # --- STEP 2.5: ensure QIPG link-target tables exist (cowork-ops 2026-06-17) ---
    # QIPG fixture carries `applicable_substrates` (Table MultiSelect; its child
    # doctype "Parameter Group Substrate" Links to "Substrate"). Importing those
    # 393 child rows validates those tables, which 1146-crash on fresh/cleaned
    # substrates where the doctypes+tables were deleted (the STEP 3 targeted
    # import still triggers child-table validation). reload_doc rebuilds the
    # DocType record AND its table during the patches phase. Order: Substrate
    # (link target) first, then Parameter Group Substrate (child -> Substrate).
    QIPG_LINK_PREREQ = [
        ("core_spc", "substrate", "Substrate"),
        ("core_spc", "parameter_group_substrate", "Parameter Group Substrate"),
    ]
    for _mod, _slug, _dt in QIPG_LINK_PREREQ:
        if not frappe.db.table_exists(_dt):
            print(f"v14_3_8.5: link-target table for '{_dt}' missing -> "
                  f"reload_doc({_mod}/doctype/{_slug}) to recreate doctype+table.")
            frappe.reload_doc(_mod, "doctype", _slug)
            frappe.db.commit()

    # Seed Substrate MASTER data (cowork-ops follow-up 2026-06-17): STEP 2.5
    # recreates the TABLE but not its rows. v14_3_11.task12 STEP 1 inserts
    # applicable_substrates child rows LINKing to substrate masters
    # (LQD/LQDC/LQDF/PWD/PWDF) -> LinkValidationError on cleaned substrates
    # (Substrate count=0). Safe now: tabSubstrate was schema-synced above.
    if frappe.db.table_exists("Substrate") and not frappe.db.count("Substrate"):
        _sub_fixture = os.path.join(
            frappe.get_app_path("amb_w_spc"), "fixtures", "substrate.json")
        if os.path.exists(_sub_fixture):
            print("v14_3_8.5: seeding Substrate masters from fixtures/substrate.json "
                  "(empty on cleaned substrate; required by v14_3_11.task12 links).")
            import_file_by_path(_sub_fixture, data_import=True, force=True,
                                reset_permissions=True)
            frappe.db.commit()

    # ─── STEP 3: Targeted single-fixture import ───
    # IMPORTANT: do NOT call sync_fixtures(app='amb_w_spc') here. That iterates
    # ALL fixture files alphabetically, and substrate.json hits tabSubstrate
    # which isn't schema-synced yet during the patches phase. L188.5 sibling
    # to L188 — caught by sysmayal-3 NACK2 2026-05-31T17:09Z. Use targeted
    # single-file import_file_by_path instead.
    fixture_path = os.path.join(
        frappe.get_app_path("amb_w_spc"),
        "fixtures",
        "quality_inspection_parameter_group.json",
    )
    print(f"v14_3_8.5: import_file_by_path on {fixture_path} "
          f"(targeted — avoids broad sync_fixtures iteration that would "
          f"hit tabSubstrate / tabPreservative System schema gaps).")
    import_file_by_path(
        fixture_path,
        data_import=True,
        force=True,
        reset_permissions=True,
    )
    frappe.db.commit()

    # ─── STEP 4: NSM rebuild_tree ───
    print(f"v14_3_8.5: rebuild_tree to normalize NSM lft/rgt post-sync.")
    rebuild_tree(QIPG)
    frappe.db.commit()

    # ─── STEP 5: Assert verification ───
    if not frappe.db.exists(QIPG, COMMON_ROOT):
        raise AssertionError(
            f"v14_3_8.5 FAILED: '{COMMON_ROOT}' not installed after "
            f"import_file_by_path. Check that "
            f"amb_w_spc/fixtures/quality_inspection_parameter_group.json "
            f"is present on disk + readable + valid JSON."
        )
    missing_l2 = [l2 for l2 in L2_CATEGORIES if not frappe.db.exists(QIPG, l2)]
    if missing_l2:
        raise AssertionError(
            f"v14_3_8.5 FAILED: L2 categories not installed after fixture sync: "
            f"{missing_l2}. Investigate fixture file integrity."
        )

    print(f"v14_3_8.5: canonical tree installation verified ✓ "
          f"(Common Root + {len(L2_CATEGORIES)} L2 categories present). "
          f"Downstream patches v14_3_9/v14_3_10/v14_3_11/v14_3_12/v14_3_13 "
          f"can now proceed.")
