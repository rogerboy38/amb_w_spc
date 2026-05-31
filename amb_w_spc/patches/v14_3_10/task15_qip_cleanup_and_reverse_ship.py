"""Task #15 — QIP cleanup + reverse-ship of legitimate vpt-only additions.

Context: Sysmayal Phase 1 findings 20260531T002500Z identified 21 vpt-only
QIPs on vpt-docker that aren't in canonical 71. Alicia ratified taxonomy
2026-05-31 morning + afternoon (main packet §1.D + §2.A-D + §2.E anexo
D1-D4). Resolution categories:

  - 2 confirmed dup orphans (Mesh Size, TOTAL ALOIN A + ALOIN B) → DELETE
    Sandbox §2.A dup-verification ratified: Mesh Size dup of Particle Size
    (same QIPG); TOTAL ALOIN A + ALOIN B case-variant of Total Aloin A+
    Total Aloin B (handled separately) + redundant with Aloin A + Aloin B.
  - 11 value-shape misclassified QIPs → VALUE-MOVE to iqi.value + delete
  - 1 method-shape misclassified QIP → METHOD-MOVE to iqi.custom_method + delete
  - 5 explicit re-link targets (typo / variant / reverse-ship target):
      Brix grado (typo) → Brix grados (Alicia §2.E D2)
      Diacetil Rhen + DIACETYL RHEN (case variants) → new Diacetyl Rhein QIP (D3)
      HAD* → new Hydroxyanthracene Derivatives QIP (§2.D)
      Total Aloin A+ Total Aloin B (variant) → new Total Aloin A + Aloin B (D1)
  - 5 REVERSE-SHIP additions to canonical:
      Candida Albicans QIP under Microbiological (§2.C)
      Pseudomonas Aeruginosa QIP under Microbiological (§2.C)
      Hydroxyanthracene Derivatives QIP under existing HAD QIPG (§2.D)
      Total Aloin A + Aloin B QIP under existing HAD QIPG (D1)
      Diacetyl Rhein QIP under new "Physicochemical Diacetyl Rhein" QIPG (D3)
  - 1 new QIPG: Physicochemical Diacetyl Rhein (peer of HAD under Physicochemical)

Net post-patch: vpt 92 → 73 (19 deletes from misclassified bucket);
canonical 71 → 76 (5 new QIPs).

Shared-DB-with-vpp constraint (Task #11 pattern): patch runs on either
side; the other side's re-run produces 0 writes. Each operation is
select-before-write idempotent. On VM3 (= Alicia's prod via tunnel), the
misclassified vpt-only QIPs DON'T exist locally, so STEP 2-5 produce
mostly no-ops. STEP 1 inserts (REVERSE-SHIP) ARE the VM3 writes.

On vpt-docker, STEP 1 inserts are no-ops (canonical was added by VM3
prior to transport); STEP 2-5 do the actual cleanup work.

Case-sensitivity guards (L162 / feedback_frappe_naming_case_sensitivity):
Two distinct case-sensitivity hazards:

  1. vpt TDS doc names use mixed case (e.g. 'Mold and Yeast') while
     canonical QIPs use title case ('Mold And Yeast'). Python lookup is
     case-sensitive; MariaDB collation is case-insensitive.
     _resolve_canonical_qip() does a case-insensitive lookup + returns
     the canonical-case name.

  2. The PURE_DELETE entry 'TOTAL ALOIN A + ALOIN B' (all-caps, orphan)
     case-folds to the same key as the new canonical 'Total Aloin A +
     Aloin B' (REVERSE-SHIP) in MariaDB's utf8mb4_general_ci collation.
     Caught in VM3 rehearsal 2026-05-31: with PURE_DELETES running AFTER
     STEP 1, frappe.db.exists('TOTAL ALOIN A + ALOIN B') matched the
     freshly-created 'Total Aloin A + Aloin B' and STEP 4's
     frappe.delete_doc destroyed it. Fix: (a) reorder PURE_DELETES to
     STEP 0 (pre-create), (b) use BINARY collation case-exact match in
     pure-delete existence check so VM3 (no all-caps row) correctly
     skips and vpt-docker (all-caps row exists) correctly deletes.

Algorithm:
  STEP 0 — PRE-CLEANUP pure-orphan deletes (Mesh Size, TOTAL ALOIN A +
           ALOIN B) — must run BEFORE STEP 1 to avoid case-collision
           with new REVERSE-SHIP canonical 'Total Aloin A + Aloin B'.
  STEP 1 — Create 1 new QIPG + 5 new QIPs (REVERSE-SHIP additions)
  STEP 2 — VALUE-MOVE 11 misclassified value-shape QIPs (vpt-only)
  STEP 3 — METHOD-MOVE 1 misclassified method-shape QIP (vpt-only)
  STEP 4 — EXPLICIT RE-LINK 5 typo / variant / reverse-ship targets
  STEP 5 — NSM rebuild_tree (only if any STEP wrote)
  STEP 6 — Integrity checks per L172 (counts, stranded IQI)

Author: claude-sandbox @ VMBox3
Date: 2026-05-31
Task: #15 (Phase 2 cleanup patch; companion to Task #15 §1 fixture commit on amb_w_tds)
"""
import frappe
from frappe.utils.nestedset import rebuild_tree


# ─── Canonical structure constants ───
L2_PHYSICOCHEMICAL = "Physicochemical"
L2_MICROBIOLOGICAL = "Microbiological"
QIPG_HAD = "Physicochemical Hydroxyanthracene Derivatives"
QIPG_DIACETYL_RHEIN_NEW = "Physicochemical Diacetyl Rhein"

# ─── STEP 1 — New canonical entries (REVERSE-SHIP) ───

# (group_name, parent_qipg, is_group)
NEW_QIPGS = [
    (QIPG_DIACETYL_RHEIN_NEW, L2_PHYSICOCHEMICAL, 0),
]

# (parameter_name, parameter_group)
NEW_QIPS = [
    ("Candida Albicans",              L2_MICROBIOLOGICAL),
    ("Pseudomonas Aeruginosa",        L2_MICROBIOLOGICAL),
    ("Hydroxyanthracene Derivatives", QIPG_HAD),
    ("Total Aloin A + Aloin B",       QIPG_HAD),
    ("Diacetyl Rhein",                QIPG_DIACETYL_RHEIN_NEW),
]

# ─── STEP 2 — VALUE-MOVE (parent TDS doc IS canonical QIP) ───

# (misclassified_qip, normalized_value)
VALUE_MOVE_OPS = [
    ("NMT 0.1 PPM",     "≤0.1 PPM"),
    ("Negative",        "Negative"),
    ("NMT 50 CFU/G",    "≤50 CFU/G"),
    ("Typical of Aloe", "Typical of Aloe"),
    ("1.002 - 1.020",   "1.002 - 1.020"),
    ("3.5 - 5.0",       "3.5 - 5.0"),
    ("C 1-2",           "C 1-2"),
    ("Hazy Liquid",     "Hazy Liquid"),
    ("Light Amber",     "Light Amber"),
    ("NMT 10%",         "≤10%"),
    ("NMT 35%",         "≤35%"),
]

# ─── STEP 3 — METHOD-MOVE ───

# (misclassified_qip, canonical_qip, method_value)
METHOD_MOVE_OPS = [
    ("ANTHRAQUINONE (ALOIN) BY HPLC", "Aloin Content", "HPLC"),
]

# ─── STEP 0 — Pure deletes (Alicia §2.A dup-confirmed; pre-create order) ───
PURE_DELETES = ["Mesh Size", "TOTAL ALOIN A + ALOIN B"]

# ─── STEP 4 — Explicit re-link (typo / variant / reverse-ship target) ───

# (misclassified_qip, canonical_qip)
EXPLICIT_RELINKS = [
    ("Brix grado",                   "Brix grados"),
    ("Diacetil Rhen",                "Diacetyl Rhein"),
    ("DIACETYL RHEN",                "Diacetyl Rhein"),
    ("HAD*",                         "Hydroxyanthracene Derivatives"),
    ("Total Aloin A+ Total Aloin B", "Total Aloin A + Aloin B"),
]


def _resolve_canonical_qip(name):
    """Case-insensitive lookup for QIP by name. Returns the canonical-case
    name as stored in tabQuality Inspection Parameter, or None if no match.

    Required because vpt TDS docs are named with mixed case (e.g.
    'Mold and Yeast') while canonical QIPs use title case ('Mold And Yeast').
    Python lookup is case-sensitive (L162 case-sensitivity).
    """
    if not name:
        return None
    rows = frappe.db.sql(
        "SELECT name FROM `tabQuality Inspection Parameter` "
        "WHERE LOWER(name) = LOWER(%s) LIMIT 1",
        (name,), as_list=True,
    )
    return rows[0][0] if rows else None


def _step_1_create_canonicals():
    writes = 0
    for qipg_name, parent_qipg, is_group in NEW_QIPGS:
        if frappe.db.exists("Quality Inspection Parameter Group", qipg_name):
            print(f"  STEP 1 skip QIPG (exists): {qipg_name}")
            continue
        if not frappe.db.exists("Quality Inspection Parameter Group", parent_qipg):
            print(f"  STEP 1 ERROR: parent QIPG '{parent_qipg}' missing — cannot create {qipg_name}")
            continue
        doc = frappe.get_doc({
            "doctype": "Quality Inspection Parameter Group",
            "group_name": qipg_name,
            "custom_parameter_group_child": parent_qipg,
            "is_group": is_group,
        })
        doc.insert(ignore_permissions=True)
        writes += 1
        print(f"  STEP 1 created QIPG: {qipg_name} (parent={parent_qipg})")

    for qip_name, parameter_group in NEW_QIPS:
        if frappe.db.exists("Quality Inspection Parameter", qip_name):
            print(f"  STEP 1 skip QIP (exists): {qip_name}")
            continue
        if not frappe.db.exists("Quality Inspection Parameter Group", parameter_group):
            print(f"  STEP 1 ERROR: parameter_group '{parameter_group}' missing — cannot create {qip_name}")
            continue
        doc = frappe.get_doc({
            "doctype": "Quality Inspection Parameter",
            "parameter": qip_name,
            "parameter_group": parameter_group,
        })
        doc.insert(ignore_permissions=True)
        writes += 1
        print(f"  STEP 1 created QIP: {qip_name} (parameter_group={parameter_group})")

    return writes


def _step_2_value_move():
    writes = 0
    for misclassified, normalized_value in VALUE_MOVE_OPS:
        iqi_rows = frappe.db.sql(
            "SELECT name, parent FROM `tabItem Quality Inspection Parameter` "
            "WHERE specification = %s",
            (misclassified,), as_dict=True,
        )
        if not iqi_rows:
            continue
        for r in iqi_rows:
            canonical = _resolve_canonical_qip(r['parent'])
            if not canonical:
                print(f"  STEP 2 WARN: IQI {r['name']} parent='{r['parent']}' "
                      f"can't resolve to canonical QIP — skipping")
                continue
            frappe.db.set_value(
                "Item Quality Inspection Parameter", r['name'],
                {"specification": canonical, "value": normalized_value},
                update_modified=False,
            )
            writes += 1
            print(f"  STEP 2 value-move: IQI {r['name']} "
                  f"spec '{misclassified}' → '{canonical}', value='{normalized_value}'")
        deps_remain = frappe.db.count(
            "Item Quality Inspection Parameter", {"specification": misclassified}
        )
        if deps_remain == 0 and frappe.db.exists("Quality Inspection Parameter", misclassified):
            frappe.delete_doc(
                "Quality Inspection Parameter", misclassified,
                force=1, ignore_permissions=True,
            )
            writes += 1
            print(f"  STEP 2 deleted misclassified QIP: {misclassified}")
        elif deps_remain > 0:
            print(f"  STEP 2 SKIP delete '{misclassified}': {deps_remain} IQI deps remain")
    return writes


def _step_3_method_move():
    writes = 0
    for misclassified, canonical_qip, method_value in METHOD_MOVE_OPS:
        if not frappe.db.exists("Quality Inspection Parameter", canonical_qip):
            print(f"  STEP 3 ERROR: canonical '{canonical_qip}' missing for {misclassified}")
            continue
        if not frappe.db.exists("Quality Inspection Method", method_value):
            print(f"  STEP 3 ERROR: Quality Inspection Method '{method_value}' missing")
            continue
        iqi_rows = frappe.db.sql(
            "SELECT name FROM `tabItem Quality Inspection Parameter` "
            "WHERE specification = %s",
            (misclassified,), as_list=True,
        )
        if not iqi_rows:
            continue
        for (iqi_name,) in iqi_rows:
            frappe.db.set_value(
                "Item Quality Inspection Parameter", iqi_name,
                {"specification": canonical_qip, "custom_method": method_value},
                update_modified=False,
            )
            writes += 1
            print(f"  STEP 3 method-move: IQI {iqi_name} "
                  f"spec '{misclassified}' → '{canonical_qip}', method='{method_value}'")
        deps_remain = frappe.db.count(
            "Item Quality Inspection Parameter", {"specification": misclassified}
        )
        if deps_remain == 0 and frappe.db.exists("Quality Inspection Parameter", misclassified):
            frappe.delete_doc(
                "Quality Inspection Parameter", misclassified,
                force=1, ignore_permissions=True,
            )
            writes += 1
            print(f"  STEP 3 deleted misclassified QIP: {misclassified}")
    return writes


def _step_0_pure_deletes_pre_create():
    """Pure-orphan deletes — MUST run before STEP 1 to avoid case-collision
    between PURE_DELETES entry 'TOTAL ALOIN A + ALOIN B' (all-caps orphan)
    and new canonical 'Total Aloin A + Aloin B' (created in STEP 1).
    MariaDB case-insensitive collation treats them as same PK.

    Uses BINARY collation case-exact match for existence check, so VM3
    (where only case-different rows might exist or none) correctly skips
    and vpt-docker (where the case-exact orphan row exists) correctly
    deletes.
    """
    writes = 0
    for misclassified in PURE_DELETES:
        # BINARY = case-EXACT match (defeats utf8mb4_general_ci case-folding)
        rows = frappe.db.sql(
            "SELECT name FROM `tabQuality Inspection Parameter` "
            "WHERE BINARY name = %s",
            (misclassified,), as_list=True,
        )
        if not rows:
            # No case-exact match — orphan doesn't exist here. Skip.
            continue
        deps = frappe.db.count(
            "Item Quality Inspection Parameter", {"specification": misclassified}
        )
        if deps > 0:
            print(f"  STEP 0 SKIP delete '{misclassified}': {deps} IQI deps "
                  f"(Alicia §2.A ratified as 0-dep orphan; investigate dep source)")
            continue
        frappe.delete_doc(
            "Quality Inspection Parameter", misclassified,
            force=1, ignore_permissions=True,
        )
        writes += 1
        print(f"  STEP 0 deleted pure orphan: {misclassified}")
    return writes


def _step_4_explicit_relinks():
    writes = 0
    for misclassified, canonical_qip in EXPLICIT_RELINKS:
        if not frappe.db.exists("Quality Inspection Parameter", canonical_qip):
            print(f"  STEP 4 ERROR: canonical '{canonical_qip}' missing for {misclassified} "
                  f"(STEP 1 must run first)")
            continue
        iqi_rows = frappe.db.sql(
            "SELECT name FROM `tabItem Quality Inspection Parameter` "
            "WHERE specification = %s",
            (misclassified,), as_list=True,
        )
        if not iqi_rows:
            # Either misclassified doesn't exist OR is an orphan with no deps
            if frappe.db.exists("Quality Inspection Parameter", misclassified):
                frappe.delete_doc(
                    "Quality Inspection Parameter", misclassified,
                    force=1, ignore_permissions=True,
                )
                writes += 1
                print(f"  STEP 4 deleted orphan misclassified QIP: {misclassified}")
            continue
        for (iqi_name,) in iqi_rows:
            frappe.db.set_value(
                "Item Quality Inspection Parameter", iqi_name,
                {"specification": canonical_qip},
                update_modified=False,
            )
            writes += 1
            print(f"  STEP 4 re-link: IQI {iqi_name} "
                  f"spec '{misclassified}' → '{canonical_qip}'")
        deps_remain = frappe.db.count(
            "Item Quality Inspection Parameter", {"specification": misclassified}
        )
        if deps_remain == 0 and frappe.db.exists("Quality Inspection Parameter", misclassified):
            frappe.delete_doc(
                "Quality Inspection Parameter", misclassified,
                force=1, ignore_permissions=True,
            )
            writes += 1
            print(f"  STEP 4 deleted misclassified QIP: {misclassified}")
    return writes


def _integrity_checks():
    qip_count = frappe.db.count("Quality Inspection Parameter")
    qipg_count = frappe.db.count("Quality Inspection Parameter Group")

    stranded = frappe.db.sql(
        """
        SELECT DISTINCT iqi.specification
        FROM `tabItem Quality Inspection Parameter` iqi
        LEFT JOIN `tabQuality Inspection Parameter` qip
          ON qip.name = iqi.specification
        WHERE iqi.specification IS NOT NULL
          AND iqi.specification != ''
          AND qip.name IS NULL
        """,
        as_list=True,
    )
    if stranded:
        print(f"  STEP 6 WARN: {len(stranded)} stranded IQI specifications "
              f"(no matching QIP): {[s[0] for s in stranded[:5]]}")
    else:
        print(f"  STEP 6 ok: no stranded IQI specifications")
    return {"qip": qip_count, "qipg": qipg_count, "stranded": len(stranded)}


def execute():
    pre_qip = frappe.db.count("Quality Inspection Parameter")
    pre_qipg = frappe.db.count("Quality Inspection Parameter Group")
    print(f"\nTask #15 pre-state: QIP={pre_qip}, QIPG={pre_qipg}\n")

    print(f"STEP 0 — PRE-CLEANUP pure-orphan deletes ({len(PURE_DELETES)} candidates; case-exact match)")
    w0 = _step_0_pure_deletes_pre_create()

    print(f"\nSTEP 1 — Create {len(NEW_QIPGS)} new QIPG + {len(NEW_QIPS)} new QIPs (REVERSE-SHIP)")
    w1 = _step_1_create_canonicals()

    print(f"\nSTEP 2 — VALUE-MOVE {len(VALUE_MOVE_OPS)} misclassified value-shape QIPs")
    w2 = _step_2_value_move()

    print(f"\nSTEP 3 — METHOD-MOVE {len(METHOD_MOVE_OPS)} misclassified method-shape QIP")
    w3 = _step_3_method_move()

    print(f"\nSTEP 4 — EXPLICIT RE-LINK {len(EXPLICIT_RELINKS)} typo / variant / reverse-ship targets")
    w4 = _step_4_explicit_relinks()

    total_writes = w0 + w1 + w2 + w3 + w4

    if total_writes > 0:
        print(f"\nSTEP 5 — NSM rebuild_tree (writes={total_writes})")
        try:
            rebuild_tree("Quality Inspection Parameter Group")
            print(f"  STEP 5 ok: NSM tree rebuilt")
        except Exception as e:
            print(f"  STEP 5 WARN: rebuild_tree raised {type(e).__name__}: {e}")
    else:
        print(f"\nSTEP 5 — NSM rebuild_tree SKIPPED (no writes)")

    print(f"\nSTEP 6 — Integrity checks (post-state)")
    post = _integrity_checks()

    print(f"\nTask #15 summary:")
    print(f"  QIP: {pre_qip} → {post['qip']} (Δ={post['qip']-pre_qip:+d})")
    print(f"  QIPG: {pre_qipg} → {post['qipg']} (Δ={post['qipg']-pre_qipg:+d})")
    print(f"  Total writes: {total_writes}")
    print(f"  Stranded IQI: {post['stranded']}")
