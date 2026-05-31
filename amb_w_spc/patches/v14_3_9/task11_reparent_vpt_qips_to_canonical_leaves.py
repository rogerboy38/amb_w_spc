"""Task #11 — Re-parent substrate-segmented QIPs to canonical L2 leaves
+ legacy-rename orphaned substrate-segmented QIPGs per Alicia §5 ratification.

Context: Task #9 (commit 730491f) shipped the canonical QIPG tree fixture
(Common Root + 7 L2 categories + 411 leaves) to vpt-docker via bench migrate.
Browser smoke on TDS 0705 TEST V2 1 (Hugh, 2026-05-30 ~15:20 local) showed
the picker rendering 7 L2 categories but 0 parameters in each — vpt's 71
QIPs are still parented under substrate-segmented legacy QIPGs (e.g.
"Organoleptic LQD Color Visual") which are OUTSIDE the Common Root
subtree. Picker correctly filters them out per Path Y architecture; we
need to move the QIPs into the canonical tree.

Algorithm (strip-substrate-suffix patterns per Hugh's Task #11 brief):
  "<L2> LQD <Leaf>"   → "<L2> <Leaf>"   (e.g. "Organoleptic LQD Color Visual" → "Organoleptic Color Visual")
  "<L2> PWD <Leaf>"   → "<L2> <Leaf>"
  "<L2> LQDC <Leaf>"  → "<L2> <Leaf>"
  "<L2> LQDF <Leaf>"  → "<L2> <Leaf>"
  "<L2> PWDF <Leaf>"  → "<L2> <Leaf>"
  "<L2> LQD"          → "<L2>"          (group-level → L2 root)
  "<L2> PWD"          → "<L2>"
  "<L2> [ARCHIVED-2026-05]"  → "<L2>"   (drop archive suffix)
  "<L2> <SUB> [ARCHIVED-2026-05]"  → "<L2>"  (handle archived-substrate combos)
  All others: LOG and DEFER (don't auto-rewrite — needs human review)

Migrates legacy substrate-segmented QIPG tree (Products Liquid/Powder
Parameter Group containers + Microbiological/Physicochemical/Organoleptic/
Other LQD substrate-suffix subgroups) to canonical 8-L2 tree (Common Root +
7 L2 categories). Prerequisite: v14_3_9.1
(`amb_w_spc.patches.v14_3_9_1.install_canonical_qipg_tree_prereq`) must
install the canonical tree first on any fresh site where the tree isn't
already present from a prior migrate. On sites with canonical tree already
installed (vpt-docker post-2026-05-30, VM3 / Alicia's prod), v14_3_9.1
short-circuits (idempotent skip) and v14_3_9 proceeds with legacy → canonical
re-parenting.

Idempotent: select-before-write on every set_value; safe to re-run.

Self-bootstrap: aborts BEFORE any writes if Common Root + 7 L2 categories
aren't present. The expected ordering is now:
  patches.txt:  v14_3_7 → v14_3_9_1 → v14_3_9 → v14_3_10 → ...

Stale-claim removed 2026-05-31 (L189 cand): an earlier docstring revision
claimed a "Shared-DB constraint with vpp (per transport playbook v2 PART B)
— the patch may fire on either side and the other side's re-run produces 0
writes." Hugh clarified 2026-05-31: hostinger-vpp has STANDALONE DB (not
shared with vpt-docker). The idempotency property still holds independently
because all operations are select-before-write — but the framing of
"either-side" provenance was inaccurate.

Legacy QIPG renames (Alicia §5): once QIPs are re-parented, the orphaned
substrate-segmented parent QIPGs (e.g. "Organoleptic LQD") get renamed to
"Organoleptic LQD [LEGACY-2026-05]". Reversible; preserves audit trail.
One frappe.rename_doc + commit per op per L165 (don't loop in a try/except
that would roll back all preceding renames on a single failure).

Author: claude-sandbox @ VMBox3
Date: 2026-05-30
Task: #11 (follow-up to Task #9 canonical tree fixture)
"""
import re
import frappe
from frappe.utils.nestedset import rebuild_tree


# Mirrors phase_1c_tab_v2.js SC5V2_COMMON_ROOT + SC5V2_L2_CATEGORIES.qipg
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

SUBSTRATES = ["LQD", "LQDC", "LQDF", "PWD", "PWDF"]
ARCHIVE_SUFFIX = "[ARCHIVED-2026-05]"
LEGACY_SUFFIX = "[LEGACY-2026-05]"


def strip_substrate_suffix(parameter_group):
    """Return canonical target name for a substrate-segmented parameter_group,
    or None if the name doesn't match any known pattern.

    Patterns evaluated in priority order (more specific first):
      1. "<L2> <SUB> [ARCHIVED-2026-05]"  → "<L2>"
      2. "<L2> [ARCHIVED-2026-05]"        → "<L2>"
      3. "<L2> <SUB> <Leaf>"              → "<L2> <Leaf>"
      4. "<L2> <SUB>"                     → "<L2>"
    """
    if not parameter_group:
        return None
    for L2 in L2_CATEGORIES:
        # Pattern 1: "<L2> <SUB> [ARCHIVED-2026-05]"
        for sub in SUBSTRATES:
            if parameter_group == f"{L2} {sub} {ARCHIVE_SUFFIX}":
                return L2
        # Pattern 2: "<L2> [ARCHIVED-2026-05]"
        if parameter_group == f"{L2} {ARCHIVE_SUFFIX}":
            return L2
        # Pattern 3: "<L2> <SUB> <Leaf>"
        for sub in SUBSTRATES:
            prefix = f"{L2} {sub} "
            if parameter_group.startswith(prefix):
                leaf = parameter_group[len(prefix):]
                return f"{L2} {leaf}"
        # Pattern 4: "<L2> <SUB>" exact
        for sub in SUBSTRATES:
            if parameter_group == f"{L2} {sub}":
                return L2
    return None


def _verify_canonical_tree_present():
    """Self-bootstrap precondition: Common Root + 7 L2 categories must exist."""
    missing = []
    if not frappe.db.exists("Quality Inspection Parameter Group", COMMON_ROOT):
        missing.append(COMMON_ROOT)
    for L2 in L2_CATEGORIES:
        if not frappe.db.exists("Quality Inspection Parameter Group", L2):
            missing.append(L2)
    if missing:
        frappe.throw(
            f"Task #11 prerequisites missing: {missing}. Canonical QIPG tree "
            "(Common Root + 7 L2 categories) must be installed first (Task #9 "
            f"fixture in amb_w_spc/fixtures/quality_inspection_parameter_group.json "
            "via bench migrate). ABORTING — no writes attempted."
        )


def _pre_post_count_qips_in_common_root():
    """Count QIPs whose parameter_group is within Common Root subtree (lft/rgt)."""
    cr = frappe.db.get_value(
        "Quality Inspection Parameter Group", COMMON_ROOT,
        ["lft", "rgt"], as_dict=True,
    )
    if not cr or cr.lft is None:
        return 0
    return frappe.db.sql(
        """
        SELECT COUNT(*)
        FROM `tabQuality Inspection Parameter` q
        JOIN `tabQuality Inspection Parameter Group` g
          ON g.name = q.parameter_group
        WHERE g.lft >= %s AND g.rgt <= %s
        """,
        (cr.lft, cr.rgt),
    )[0][0]


def execute():
    _verify_canonical_tree_present()

    # ─── Pre-state snapshot ───
    pre_qipg_count = frappe.db.count("Quality Inspection Parameter Group")
    pre_qip_count = frappe.db.count("Quality Inspection Parameter")
    pre_canonical_qip_count = _pre_post_count_qips_in_common_root()
    print(
        f"Task #11 pre-state: QIPG={pre_qipg_count}, QIP={pre_qip_count}, "
        f"QIPs under Common Root subtree={pre_canonical_qip_count}"
    )

    # ─── Phase 1: re-parent QIPs by strip-pattern ───
    all_qips = frappe.db.sql(
        "SELECT name, parameter_group FROM `tabQuality Inspection Parameter`",
        as_dict=True,
    )

    sample_anchors_pre_post = []  # (qip_name, old_pg, new_pg) for first 5 writes
    writes = 0
    unmatched = []  # parameter_group values that don't fit any strip pattern
    skipped_target_missing = []  # cases where target QIPG doesn't exist yet
    already_canonical = 0

    for qip in all_qips:
        target = strip_substrate_suffix(qip.parameter_group)
        if target is None:
            # Not a substrate-segmented parameter_group
            if qip.parameter_group:
                # Log only non-empty unmatched values (skip blanks)
                pg_lft = frappe.db.get_value(
                    "Quality Inspection Parameter Group", qip.parameter_group, "lft"
                )
                if pg_lft is None or pg_lft == 0:
                    # Parameter group doesn't exist in QIPG table — defer
                    unmatched.append((qip.name, qip.parameter_group, "QIPG missing"))
                else:
                    already_canonical += 1
            continue

        # Verify target exists in DB before writing
        if not frappe.db.exists("Quality Inspection Parameter Group", target):
            skipped_target_missing.append((qip.name, qip.parameter_group, target))
            continue

        # Idempotent: skip if already at target
        if qip.parameter_group == target:
            already_canonical += 1
            continue

        # Re-parent
        frappe.db.set_value(
            "Quality Inspection Parameter", qip.name,
            "parameter_group", target,
            update_modified=False,
        )
        writes += 1
        if len(sample_anchors_pre_post) < 5:
            sample_anchors_pre_post.append((qip.name, qip.parameter_group, target))

    frappe.db.commit()

    # ─── Phase 2: legacy-rename orphaned substrate-segmented QIPGs (Alicia §5) ───
    # Find QIPGs that:
    #   (a) match a substrate-segmented pattern
    #   (b) have ZERO QIPs currently parented under them (post-Phase-1 re-parent)
    # Rename to add [LEGACY-2026-05] suffix.
    # One frappe.rename_doc + commit per op (per L165 — never loop in
    # try/except that rolls back preceding renames).

    candidates = frappe.db.sql(
        "SELECT name FROM `tabQuality Inspection Parameter Group`",
        as_dict=True,
    )
    legacy_renames = 0
    legacy_renamed_names = []
    legacy_skipped_in_use = []
    legacy_skipped_already = []

    for qipg in candidates:
        name = qipg.name
        # Skip if already has [LEGACY-2026-05]
        if LEGACY_SUFFIX in name:
            legacy_skipped_already.append(name)
            continue
        # Skip if already has [ARCHIVED-2026-05] — Hugh's brief: "the 4
        # already-archived stay as-is (already disambiguated)". Without
        # this guard the patch double-suffixes them to
        # "X LQD [ARCHIVED-2026-05] [LEGACY-2026-05]" which is wrong.
        # Caught on second rehearsal pass.
        if ARCHIVE_SUFFIX in name:
            legacy_skipped_already.append(name)
            continue
        # Match substrate-segmented patterns (using same strip logic — non-None = match)
        target = strip_substrate_suffix(name)
        if target is None:
            # Not a substrate-segmented QIPG; check if it's a Products * top-level
            if name.startswith("Products ") and "Parameter Group" in name:
                pass  # match this case too — Hugh's Alicia §5
            else:
                continue
        # Check: any QIPs still using this as parameter_group?
        qip_count_here = frappe.db.count(
            "Quality Inspection Parameter", {"parameter_group": name}
        )
        if qip_count_here > 0:
            legacy_skipped_in_use.append((name, qip_count_here))
            continue
        # Safe to legacy-rename
        new_name = f"{name} {LEGACY_SUFFIX}"
        if frappe.db.exists("Quality Inspection Parameter Group", new_name):
            # Already renamed (idempotent re-run); skip
            legacy_skipped_already.append(name)
            continue
        try:
            # Frappe rename_doc kwargs (this version): doctype, old, new,
            # force, merge, *, ignore_if_exists, show_alert, rebuild_search.
            # NO `ignore_permissions` kwarg — that was rejected during
            # rehearsal. Use force=True instead.
            frappe.rename_doc(
                "Quality Inspection Parameter Group", name, new_name,
                force=True,
            )
            frappe.db.commit()  # commit-per-op per L165
            legacy_renames += 1
            legacy_renamed_names.append((name, new_name))
        except Exception as e:
            # Don't abort the loop on a single failure — log and continue
            print(f"  legacy-rename FAILED for {name!r}: {e}")
            frappe.db.rollback()

    # ─── Phase 3: rebuild NSM tree ───
    # rebuild_tree signature (this Frappe version): rebuild_tree(doctype).
    # Parent field is derived from doctype meta nsm_parent_field; do NOT
    # pass it as a second arg (TypeError on rehearsal).
    try:
        rebuild_tree("Quality Inspection Parameter Group")
        frappe.db.commit()
    except Exception as e:
        print(f"  rebuild_tree WARN: {e}")

    # ─── Post-state snapshot + integrity checks ───
    post_qipg_count = frappe.db.count("Quality Inspection Parameter Group")
    post_qip_count = frappe.db.count("Quality Inspection Parameter")
    post_canonical_qip_count = _pre_post_count_qips_in_common_root()

    nsm_integrity_violations = frappe.db.sql(
        """
        SELECT name FROM `tabQuality Inspection Parameter Group`
        WHERE lft IS NULL OR rgt IS NULL OR lft >= rgt
        LIMIT 5
        """,
        as_dict=True,
    )

    print(
        f"\nTask #11 post-state: QIPG={post_qipg_count} (Δ +{post_qipg_count - pre_qipg_count}), "
        f"QIP={post_qip_count} (Δ +{post_qip_count - pre_qip_count}), "
        f"QIPs under Common Root subtree={post_canonical_qip_count} "
        f"(Δ +{post_canonical_qip_count - pre_canonical_qip_count})"
    )
    print(
        f"\nTask #11 writes: {writes} re-parent set_value; "
        f"{already_canonical} already-canonical (skipped); "
        f"{len(unmatched)} unmatched/deferred; "
        f"{len(skipped_target_missing)} skipped-target-missing"
    )
    print(
        f"\nTask #11 legacy renames: {legacy_renames} [LEGACY-2026-05] renames; "
        f"{len(legacy_skipped_in_use)} skipped-still-in-use; "
        f"{len(legacy_skipped_already)} already-renamed"
    )

    if sample_anchors_pre_post:
        print("\nSample anchors (first 5 re-parents):")
        for q, old, new in sample_anchors_pre_post:
            print(f"  {q!r}: {old!r} → {new!r}")

    if legacy_renamed_names[:5]:
        print("\nSample legacy renames (first 5):")
        for old, new in legacy_renamed_names[:5]:
            print(f"  {old!r} → {new!r}")

    if unmatched[:10]:
        print("\nUnmatched parameter_groups (first 10 — needs human review):")
        for qip_name, pg, reason in unmatched[:10]:
            print(f"  QIP={qip_name!r} parameter_group={pg!r} ({reason})")

    if skipped_target_missing[:10]:
        print("\nTarget-missing (first 10 — canonical QIPG absent in DB):")
        for qip_name, old_pg, target in skipped_target_missing[:10]:
            print(f"  QIP={qip_name!r} {old_pg!r} → would-be {target!r} (missing)")

    if legacy_skipped_in_use[:10]:
        print("\nLegacy QIPGs still in use (first 10 — re-parent must complete first):")
        for name, ct in legacy_skipped_in_use[:10]:
            print(f"  {name!r}: {ct} QIPs still here")

    if nsm_integrity_violations:
        print(
            f"\nNSM INTEGRITY VIOLATIONS: {len(nsm_integrity_violations)} rows "
            "with NULL lft/rgt or lft >= rgt"
        )
        for v in nsm_integrity_violations:
            print(f"  {v.name!r}")
    else:
        print("\nNSM integrity: OK (no violations)")
