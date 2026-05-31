"""Task #12 — v14_3_10 follow-up: Diacetyl Rhein substrates + Mercury/E.coli re-parent.

Context: v14_3_10 (Task #15 cleanup + REVERSE-SHIP) landed clean on vpt-docker
(REAL_EXIT=0, QIP=76 confirmed, all 7 STEPs green, 0 stranded IQI). Browser-
verify on vpt-docker surfaced 2 visibility gaps that integrity checks didn't
catch:

  1. New canonical QIP `Diacetyl Rhein` is invisible to the Path Y picker.
     v14_3_10 STEP 1 created leaf QIPG `Physicochemical Diacetyl Rhein` but
     forgot to insert applicable_substrates Table MultiSelect child rows.
     Path Y picker filters QIPs by parent QIPG's substrate filter — 0
     substrate rows = picker hides every QIP under this QIPG. (See L183
     candidate: leaf QIPG must populate substrate child rows.)

  2. Mercury + E.coli QIPs still parented to substrate-segmented legacy
     leaves with DOUBLE-SPACE pattern `<L2> LQD  <Leaf>` (note 2 spaces).
     Task #11 strip_substrate_suffix regex matched only single-space
     pattern `<L2> <SUB> <Leaf>` → double-space variants escaped + remain
     parented to LEGACY-2026-05 L2 categories instead of canonical L2.

Fix in v14_3_11:
  STEP 0 — Pre-flight precondition check (selects only). Skips downstream
           STEPs cleanly if prerequisites missing (e.g. v14_3_10 not yet
           applied on this site).
  STEP 1 — Insert 5 applicable_substrates child rows on `Physicochemical
           Diacetyl Rhein` (LQD/LQDC/LQDF/PWD/PWDF default per Task #67
           M3.5 baseline). Idempotent — skips already-present rows.
  STEP 2 — Re-parent Mercury QIP from `Physicochemical LQD  Lead Mercury`
           legacy → `MERCURY - Physicochemical` canonical. Conditional
           UPDATE — fires only if Mercury currently in legacy parent.
  STEP 3 — Re-parent E.coli QIP from `Microbiological LQD  E.coli` legacy
           → `Microbiological E.coli` canonical. Same conditional pattern.
  STEP 4 — IQI integrity defensive scan. Verify no stranded IQI rows
           (specification → non-existent QIP). Mercury + E.coli IQI
           rows reference qip.name not parameter_group, so re-parent
           shouldn't affect IQI resolution; this STEP confirms.
  STEP 5 — NSM rebuild_tree (defensive). Legacy QIPGs left intact for
           T13 hygiene cleanup; rebuild ensures lft/rgt correctness
           after any STEP 1-3 writes.
  STEP 6 — Integrity verification (counts, parents, substrate rows).

Shared-DB-with-vpp constraint (Task #11 pattern): patch runs on either
side; the other side's re-run produces 0 writes. All operations are
select-before-write idempotent. STEPs 2-3 are inherently conditional
on current state.

VM3 (= Alicia's prod via tunnel): STEP 2 + STEP 3 are no-ops because
Mercury sits in different (non-legacy) parent (`Physicochemical Lead
Mercury`, parent=Contaminant L2) and E.coli is already canonical
(`Microbiological E.coli`). The legacy double-space QIPGs are
vpt-docker-specific T11 transport residue.

vpt-docker: STEP 2 + STEP 3 fire — re-parent both QIPs to canonical.
STEP 1 fires on both sites because v14_3_10 created the QIPG without
substrates.

L183 reference (banked 2026-05-31): "Leaf QIPG must populate substrate
child rows" — v14_3_10 STEP 1 omission. This patch fixes the omission.

NOT in scope (deferred to T13 hygiene):
  - Delete now-empty legacy QIPGs (`Physicochemical LQD  Lead Mercury`,
    `Microbiological LQD  E.coli`) — defensive: leave until full T13 audit
  - Delete redundant Mercury/E.coli variants (MERCURIO -, MERCURY (PPM) -,
    MERCURY* -, ENTEROHEMORRHAGIC E.COLI -, ESCHERICHA COLI -, etc.)
  - Clean Aloe Vera Nutrients empty bloat (~100 QIPGs with qip_count=0)

Author: claude-sandbox @ VMBox3
Date: 2026-05-31
Task: #12 (v14_3_10 follow-up; companion to Task #15)
References: L162 (case-sensitivity), L183 (substrate child rows), L171
"""
import frappe
from frappe.utils.nestedset import rebuild_tree


# ─── Targets ───
TARGET_QIPG_DIACETYL = "Physicochemical Diacetyl Rhein"
SUBSTRATES = ["LQD", "LQDC", "LQDF", "PWD", "PWDF"]

# (qip_name, legacy_parameter_group, canonical_parameter_group)
REPARENT_OPS = [
    ("Mercury", "Physicochemical LQD  Lead Mercury", "MERCURY - Physicochemical"),
    ("E.coli",  "Microbiological LQD  E.coli",       "Microbiological E.coli"),
]


def _step_0_preflight():
    """Pre-flight precondition check. Returns dict of facts; downstream
    STEPs skip cleanly if prerequisites missing."""
    facts = {}
    facts['diacetyl_qipg_exists'] = bool(
        frappe.db.exists("Quality Inspection Parameter Group", TARGET_QIPG_DIACETYL)
    )
    facts['diacetyl_substrate_count'] = frappe.db.count(
        "Parameter Group Substrate",
        {"parent": TARGET_QIPG_DIACETYL, "parenttype": "Quality Inspection Parameter Group"},
    )
    for qip_name, legacy_pg, canonical_pg in REPARENT_OPS:
        facts[f'{qip_name}_exists'] = bool(
            frappe.db.exists("Quality Inspection Parameter", qip_name)
        )
        facts[f'{qip_name}_current_pg'] = frappe.db.get_value(
            "Quality Inspection Parameter", qip_name, "parameter_group"
        )
        facts[f'{qip_name}_canonical_pg_exists'] = bool(
            frappe.db.exists("Quality Inspection Parameter Group", canonical_pg)
        )

    print(f"  STEP 0 facts:")
    for k, v in facts.items():
        print(f"    {k}: {v}")
    return facts


def _step_1_diacetyl_substrates(facts):
    """Insert 5 applicable_substrates child rows on Physicochemical Diacetyl
    Rhein QIPG. Idempotent — skip already-present rows."""
    if not facts['diacetyl_qipg_exists']:
        print(f"  STEP 1 SKIP: target QIPG '{TARGET_QIPG_DIACETYL}' missing "
              f"(v14_3_10 must run first; patches.txt order ensures this)")
        return 0
    writes = 0
    for sub in SUBSTRATES:
        # Idempotent existence check — keyed by (parent, parenttype, substrate)
        existing = frappe.db.sql(
            "SELECT name FROM `tabParameter Group Substrate` "
            "WHERE parent = %s AND parenttype = %s AND substrate = %s",
            (TARGET_QIPG_DIACETYL, "Quality Inspection Parameter Group", sub),
            as_list=True,
        )
        if existing:
            print(f"  STEP 1 skip substrate (exists): {TARGET_QIPG_DIACETYL} / {sub}")
            continue
        doc = frappe.get_doc({
            "doctype": "Parameter Group Substrate",
            "parent": TARGET_QIPG_DIACETYL,
            "parenttype": "Quality Inspection Parameter Group",
            "parentfield": "applicable_substrates",
            "substrate": sub,
        })
        doc.insert(ignore_permissions=True)
        writes += 1
        print(f"  STEP 1 inserted substrate: {TARGET_QIPG_DIACETYL} / {sub}")
    return writes


def _step_2_and_3_reparent(facts):
    """Re-parent Mercury + E.coli from legacy QIPGs to canonical. Conditional
    UPDATE — fires only if QIP currently in named legacy parent. L127 safe-
    update compliant (PK = name in WHERE)."""
    writes = 0
    for qip_name, legacy_pg, canonical_pg in REPARENT_OPS:
        if not facts.get(f'{qip_name}_exists'):
            print(f"  STEP 2/3 SKIP {qip_name}: QIP doesn't exist on this site")
            continue
        if not facts.get(f'{qip_name}_canonical_pg_exists'):
            print(f"  STEP 2/3 ERROR {qip_name}: canonical parent '{canonical_pg}' missing")
            continue
        current_pg = facts.get(f'{qip_name}_current_pg')
        if current_pg != legacy_pg:
            print(f"  STEP 2/3 SKIP {qip_name}: current parent '{current_pg}' "
                  f"!= legacy '{legacy_pg}' (no-op — already correct or different residue)")
            continue
        # Fire: re-parent to canonical
        frappe.db.set_value(
            "Quality Inspection Parameter", qip_name,
            "parameter_group", canonical_pg,
            update_modified=False,
        )
        writes += 1
        print(f"  STEP 2/3 re-parented {qip_name}: '{legacy_pg}' → '{canonical_pg}'")
    return writes


def _step_4_iqi_integrity():
    """Defensive scan: verify no stranded IQI rows. Mercury + E.coli IQI
    rows reference qip.name (PK), not parameter_group — re-parent shouldn't
    affect IQI resolution; this STEP confirms."""
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
        print(f"  STEP 4 WARN: {len(stranded)} stranded IQI specifications "
              f"(no matching QIP): {[s[0] for s in stranded[:5]]}")
    else:
        print(f"  STEP 4 ok: no stranded IQI specifications")
    return len(stranded)


def _step_6_verification(facts_pre):
    """Post-patch integrity verification per Hugh's STEP 6 directive."""
    checks = {}

    # Check 1: substrate count on Diacetyl Rhein
    sub_count = frappe.db.count(
        "Parameter Group Substrate",
        {"parent": TARGET_QIPG_DIACETYL, "parenttype": "Quality Inspection Parameter Group"},
    )
    checks['diacetyl_substrate_count'] = sub_count
    expected_sub = 5 if facts_pre['diacetyl_qipg_exists'] else 0
    sub_ok = sub_count == expected_sub
    print(f"  CHECK substrate count for {TARGET_QIPG_DIACETYL}: "
          f"actual={sub_count}, expected={expected_sub} → {'✓' if sub_ok else '✗'}")

    # Checks 2/3: Mercury + E.coli parameter_group
    for qip_name, legacy_pg, canonical_pg in REPARENT_OPS:
        if not facts_pre.get(f'{qip_name}_exists'):
            print(f"  CHECK {qip_name} parameter_group: SKIP (QIP doesn't exist)")
            continue
        current_pg = frappe.db.get_value(
            "Quality Inspection Parameter", qip_name, "parameter_group"
        )
        checks[f'{qip_name}_parameter_group'] = current_pg
        was_legacy = facts_pre.get(f'{qip_name}_current_pg') == legacy_pg
        if was_legacy:
            ok = current_pg == canonical_pg
            print(f"  CHECK {qip_name} parameter_group: actual='{current_pg}', "
                  f"expected='{canonical_pg}' → {'✓' if ok else '✗'}")
        else:
            print(f"  CHECK {qip_name} parameter_group: actual='{current_pg}' "
                  f"(was NOT in legacy state; STEP 2/3 was no-op)")

    # Check 4: QIPs under LEGACY L2 (expected to be 0 after re-parent; was 2 if vpt state)
    qips_under_legacy = frappe.db.sql(
        """
        SELECT q.name, q.parameter_group
        FROM `tabQuality Inspection Parameter` q
        JOIN `tabQuality Inspection Parameter Group` g
          ON g.name = q.parameter_group
        WHERE g.custom_parameter_group_child LIKE '%[LEGACY-%'
           OR g.name LIKE '%[LEGACY-%'
        """,
        as_dict=True,
    )
    checks['qips_under_legacy'] = len(qips_under_legacy)
    print(f"  CHECK QIPs under LEGACY L2: {len(qips_under_legacy)} "
          f"(should converge to 0 over T13 hygiene; v14_3_11 reduces Mercury+E.coli)")
    if qips_under_legacy:
        for r in qips_under_legacy[:5]:
            print(f"    - {r['name']} → {r['parameter_group']}")

    return checks


def execute():
    pre_qip = frappe.db.count("Quality Inspection Parameter")
    pre_qipg = frappe.db.count("Quality Inspection Parameter Group")
    pre_substrate = frappe.db.count("Parameter Group Substrate")
    print(f"\nTask #12 v14_3_11 pre-state: QIP={pre_qip}, QIPG={pre_qipg}, "
          f"substrate_rows={pre_substrate}\n")

    print(f"STEP 0 — Pre-flight precondition check (selects only)")
    facts = _step_0_preflight()

    print(f"\nSTEP 1 — Insert {len(SUBSTRATES)} substrate child rows on "
          f"{TARGET_QIPG_DIACETYL}")
    w1 = _step_1_diacetyl_substrates(facts)

    print(f"\nSTEP 2 + STEP 3 — Conditional re-parent Mercury + E.coli "
          f"(skips if not in named legacy parent)")
    w23 = _step_2_and_3_reparent(facts)

    print(f"\nSTEP 4 — IQI integrity defensive scan")
    stranded = _step_4_iqi_integrity()

    total_writes = w1 + w23
    if total_writes > 0:
        print(f"\nSTEP 5 — NSM rebuild_tree (writes={total_writes})")
        try:
            rebuild_tree("Quality Inspection Parameter Group")
            print(f"  STEP 5 ok: NSM tree rebuilt")
        except Exception as e:
            print(f"  STEP 5 WARN: rebuild_tree raised {type(e).__name__}: {e}")
    else:
        print(f"\nSTEP 5 — NSM rebuild_tree SKIPPED (no writes)")

    print(f"\nSTEP 6 — Integrity verification (post-state)")
    checks = _step_6_verification(facts)

    post_qip = frappe.db.count("Quality Inspection Parameter")
    post_qipg = frappe.db.count("Quality Inspection Parameter Group")
    post_substrate = frappe.db.count("Parameter Group Substrate")
    print(f"\nTask #12 v14_3_11 summary:")
    print(f"  QIP: {pre_qip} → {post_qip} (Δ={post_qip-pre_qip:+d})")
    print(f"  QIPG: {pre_qipg} → {post_qipg} (Δ={post_qipg-pre_qipg:+d})")
    print(f"  Substrate rows: {pre_substrate} → {post_substrate} "
          f"(Δ={post_substrate-pre_substrate:+d})")
    print(f"  Total writes: {total_writes}")
    print(f"  Stranded IQI: {stranded}")
