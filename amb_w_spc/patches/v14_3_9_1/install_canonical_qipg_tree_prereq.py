"""v14_3_9.1 prerequisite — Install canonical QIPG tree for fresh-site deployments.

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

v14_3_9.1 (this patch) breaks the egg:
  STEP 1 — Idempotent skip if Common Root already present (vpt-docker /
           VM3 path — no-op).
  STEP 2 — Defensive cleanup of NSM zombie at lft=0 if present (vpp-
           specific; harmless on sites without zombie).
  STEP 3 — Trigger sync_fixtures(app='amb_w_spc') to install the canonical
           QIPG tree fixture BEFORE downstream patches need it.
  STEP 4 — rebuild_tree to ensure NSM positions consistent post-fixture-sync.
  STEP 5 — Assert verification: Common Root + 7 L2 categories now present.

Pre-condition: amb_w_spc/fixtures/quality_inspection_parameter_group.json
must be on disk at patch-execution time (it is, since v14_3_9_1 ships with
the same commit / branch tip as the fixture). Verified by sysmayal-3
diagnostic intel.

Side effects on sites where Common Root already exists (VM3 / vpt-docker):
ZERO. STEP 1 short-circuits the entire patch.

References: L188 (banked 2026-05-31) — pre-fixture-sync patch preconditions
on fresh sites. L189 (banked) — stale patch docstrings during architecture
changes (also applies to v14_3_9 task11 docstring update in this commit).

Author: claude-sandbox @ VMBox3
Date: 2026-05-31
Task: #15 Phase B unblock (hostinger-vpp v14_3_9 chicken-and-egg)
"""
import frappe
from frappe.utils.fixtures import sync_fixtures
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
        print(f"v14_3_9.1: '{COMMON_ROOT}' present → canonical tree already "
              f"installed; skipping prereq (vpt-docker / VM3 path).")
        return

    print(f"v14_3_9.1: '{COMMON_ROOT}' missing → fresh-site path (e.g. vpp). "
          f"Triggering pre-fixture-sync prereq install.")

    # ─── STEP 2: Defensive NSM zombie cleanup (vpp-specific) ───
    if frappe.db.exists(QIPG, NSM_ZOMBIE_NAME):
        zombie_lft = frappe.db.get_value(QIPG, NSM_ZOMBIE_NAME, "lft")
        if zombie_lft == 0:
            print(f"v14_3_9.1: removing NSM zombie '{NSM_ZOMBIE_NAME}' at lft=0 "
                  f"before fixture sync (would block tree rebuild integrity).")
            frappe.db.sql(
                "DELETE FROM `tabQuality Inspection Parameter Group` "
                "WHERE name = %s AND lft = 0",
                (NSM_ZOMBIE_NAME,),
            )
            frappe.db.commit()

    # ─── STEP 3: Install canonical tree via sync_fixtures ───
    print(f"v14_3_9.1: triggering sync_fixtures(app='amb_w_spc') to install "
          f"Common Root + 7 L2 + 411 canonical QIPG records from "
          f"amb_w_spc/fixtures/quality_inspection_parameter_group.json.")
    sync_fixtures(app="amb_w_spc")
    frappe.db.commit()

    # ─── STEP 4: NSM rebuild_tree ───
    print(f"v14_3_9.1: rebuild_tree to normalize NSM lft/rgt post-sync.")
    rebuild_tree(QIPG)
    frappe.db.commit()

    # ─── STEP 5: Assert verification ───
    if not frappe.db.exists(QIPG, COMMON_ROOT):
        raise AssertionError(
            f"v14_3_9.1 FAILED: '{COMMON_ROOT}' not installed after "
            f"sync_fixtures(app='amb_w_spc'). Check that "
            f"amb_w_spc/fixtures/quality_inspection_parameter_group.json "
            f"is present on disk + readable + valid JSON."
        )
    missing_l2 = [l2 for l2 in L2_CATEGORIES if not frappe.db.exists(QIPG, l2)]
    if missing_l2:
        raise AssertionError(
            f"v14_3_9.1 FAILED: L2 categories not installed after fixture sync: "
            f"{missing_l2}. Investigate fixture file integrity."
        )

    print(f"v14_3_9.1: canonical tree installation verified ✓ "
          f"(Common Root + {len(L2_CATEGORIES)} L2 categories present). "
          f"Downstream patches v14_3_9/v14_3_10/v14_3_11/v14_3_12/v14_3_13 "
          f"can now proceed.")
