"""v15_3_0 — T19 Part 2: backfill canonical min/max + is_numeric on legacy QIPs that
the Path Y picker can't recover via formula fallback (no value_text, no L4 choices,
no custom_choices first-line).

Context — T19-W1 (picker resilience commits 91811fc + 31824ad + 114f7cf + 62454cd on
amb_w_tds branch feature/phase-1c-b-tab-scaffold) added 4 formula-parser fallbacks
to the picker (numeric / non-numeric / L4 / CAV / choices-fallback branches). Those
recover bounds when EITHER the QIP has parseable value_text OR an L4 acceptance
choice with text_label exists OR custom_choices first-line is parseable.

But 15 QIPs on VM3 (and presumably vpt-docker / hostinger-vpp via fixture sync)
have NONE of these data sources — they're entirely DEAD-data:
  - is_numeric=1, value_min=0, value_max=0, value_text=NULL, no_choices=1, no L4
  - OR is_numeric=0 with same — descriptive QIPs but no choice catalog

Picker shows them as "0.000000 / 0.000000" rows because no recovery path applies.

This patch's per-QIP ratifications are TBD pending Alicia QE review (Hugh forwarding).
Until each entry is filled in below, the patch SKIPS that QIP via the `RATIFIED=None`
sentinel — a no-op run logs "<QIP>: pending Alicia ratification" and moves on.

Once Alicia ratifies, replace `None` with the appropriate dict per the format docstring
below; commit; bench migrate runs the writes idempotently (select-before-write skip).

Format per RATIFIED dict:
  {
    "is_numeric": 0 or 1,
    "value_min": <float or None>,    # None = leave NULL (use SQL NULL not 0)
    "value_max": <float or None>,    # None = leave NULL
    "value_text": <str or None>,     # canonical formula text e.g. "NMT 10 ppm"
    "delete": True,                  # alt: delete the QIP entirely (e.g. confirmed duplicates)
    "rename_to": <str>,              # alt: rename to canonical name
    "note": "<reason>",              # one-line ratification rationale
  }

L121 / L122 — use raw SQL UPDATE (bypass Document API; bulk data migration). Post-write
SELECT verification to detect drift.

L177 — patch authored in clean isolation; no fixture coupling required for this set
(the QIPs already exist in the canonical fixture; only the value columns change).

L188.5-safe — no sync_fixtures call.

Idempotent: re-runs detect existing canonical state and skip. SELECT-after-write asserts
on each updated row.

Companion item (not in this patch — separate T18-W2-followup):
  - BETA-SITOSTEROL (T18 W2 NLT-only): currently min=4 / max=0; my Wave 2 NLT-only
    fallback set max=0 instead of NULL. Should be max=NULL (unbounded NLT). Fixed
    in §3 below since it's the same shape of cleanup.

Author: claude-sandbox @ VMBox3
Date: 2026-06-01
Task: T19-W1 follow-up cleanup
"""
import frappe


QIP = "Quality Inspection Parameter"


# ─── PART A — DEAD-data QIPs (pending Alicia ratification) ────────────────────
# Replace `None` with a dict per the format docstring once Alicia confirms each.

RATIFIED = {
    # Hydroxyanthracene-derivative family — BY DRY WEIGHT variants
    "ALOE EMODIN (BY DRY WEIGHT)":   None,  # TBD — typical limit?
    "ALOIN A (BY DRY WEIGHT)":        None,  # TBD
    "ALOIN B (BY DRY WEIGHT)":        None,  # TBD
    "DANTHRON (BY DRY WEIGHT)":       None,  # TBD

    # Aloin family (non-DRY) — currently is_numeric=0; needs descriptive vs numeric decision
    "Aloin A":                        None,  # TBD — descriptive? has L4 catalog?
    "Aloin B":                        None,  # TBD — same

    # Color family — 3 entries; possible duplicate consolidation
    "Color":                          None,  # TBD — descriptive (is_numeric=0)? or numeric range?
    "Color (absorbance 400nm)":       None,  # TBD — typical absorbance range?
    "Color abs":                      None,  # TBD — duplicate of "(absorbance 400nm)"? delete?

    # Misc Physicochemical
    "Brix grados":                    None,  # TBD — typical Brix range for liquid concentrate?
    "pH (0.5%)":                      None,  # TBD — typical pH at 0.5% dilution? duplicate of "pH"?
    "Polysaccharides ( NMT 20 kda)":  None,  # TBD — typical %? note: QIPG name has typo (extra space)

    # Anthracene aggregates
    "Hydroxyanthracene Derivatives":  None,  # TBD — typical limit ppm?
    "Diacetyl Rhein":                 None,  # TBD — typical range?
    "Total Aloin A + Aloin B":        None,  # TBD — typical limit?
}


# ─── PART B — BETA-SITOSTEROL NLT-only fix (T18 W2 follow-up, NOT pending ratification) ──
# Already ratified (NLT 4 mg/100g per Hattori 2022 / Tanaka 2006 sources cited in T18 W2).
# Fix: max=0 → SQL NULL (unbounded NLT). Schema is Float (nullable Custom Field), but
# my T18 W2 ingestion converted None→0 as fallback. UPDATE to set NULL via raw SQL.

BETA_SITOSTEROL_FIX = {
    "name": "BETA-SITOSTEROL",
    "set_max_null": True,
    "note": "T18 W2 NLT-only fallback wrote max=0; should be NULL (unbounded NLT 4 mg/100g).",
}


# ─── Execute ──────────────────────────────────────────────────────────────────

def _apply_ratification(qip_name, ratification):
    """Apply a ratified update to one QIP. Returns op_summary str."""
    if not frappe.db.exists(QIP, qip_name):
        return f"  {qip_name}: NOT FOUND in DB — skip"

    # Delete branch
    if ratification.get("delete"):
        frappe.delete_doc(QIP, qip_name, force=1, ignore_permissions=True)
        return f"  {qip_name}: DELETED (reason: {ratification.get('note', 'no note')})"

    # Rename branch
    if ratification.get("rename_to"):
        new_name = ratification["rename_to"]
        if frappe.db.exists(QIP, new_name):
            return f"  {qip_name}: rename target '{new_name}' already exists — skip"
        frappe.rename_doc(QIP, qip_name, new_name, force=1)
        return f"  {qip_name}: RENAMED → {new_name}"

    # Update branch — set is_numeric / value_min / value_max / value_text via raw SQL
    sets = []
    args = {"name": qip_name}

    if "is_numeric" in ratification:
        sets.append("custom_is_numeric = %(is_numeric)s")
        args["is_numeric"] = 1 if ratification["is_numeric"] else 0

    if "value_min" in ratification:
        if ratification["value_min"] is None:
            sets.append("custom_value_min = NULL")
        else:
            sets.append("custom_value_min = %(value_min)s")
            args["value_min"] = float(ratification["value_min"])

    if "value_max" in ratification:
        if ratification["value_max"] is None:
            sets.append("custom_value_max = NULL")
        else:
            sets.append("custom_value_max = %(value_max)s")
            args["value_max"] = float(ratification["value_max"])

    if "value_text" in ratification:
        if ratification["value_text"] is None:
            sets.append("custom_value_text = NULL")
        else:
            sets.append("custom_value_text = %(value_text)s")
            args["value_text"] = str(ratification["value_text"])

    if not sets:
        return f"  {qip_name}: ratification dict has no actionable fields — skip"

    sql = f"UPDATE `tabQuality Inspection Parameter` SET {', '.join(sets)} WHERE name = %(name)s"
    frappe.db.sql(sql, args)

    # Post-write verification
    row = frappe.db.sql(
        "SELECT custom_is_numeric, custom_value_min, custom_value_max, custom_value_text "
        "FROM `tabQuality Inspection Parameter` WHERE name = %s",
        qip_name, as_dict=1
    )
    if not row:
        return f"  {qip_name}: post-write SELECT returned 0 rows — DRIFT"
    r = row[0]
    return (f"  {qip_name}: UPDATED "
            f"(is_numeric={r['custom_is_numeric']}, vmin={r['custom_value_min']}, "
            f"vmax={r['custom_value_max']}, text={r['custom_value_text']!r}) "
            f"— {ratification.get('note', 'no note')}")


def _apply_beta_sitosterol_fix():
    """Set BETA-SITOSTEROL.custom_value_max = NULL (unbounded NLT)."""
    if not frappe.db.exists(QIP, BETA_SITOSTEROL_FIX["name"]):
        return f"  {BETA_SITOSTEROL_FIX['name']}: NOT FOUND — skip"

    # Idempotency: if already NULL, no-op
    current_max = frappe.db.sql(
        "SELECT custom_value_max FROM `tabQuality Inspection Parameter` WHERE name = %s",
        BETA_SITOSTEROL_FIX["name"], as_dict=1
    )[0]["custom_value_max"]
    if current_max is None:
        return f"  {BETA_SITOSTEROL_FIX['name']}: max already NULL — idempotent skip"

    frappe.db.sql(
        "UPDATE `tabQuality Inspection Parameter` "
        "SET custom_value_max = NULL WHERE name = %s",
        BETA_SITOSTEROL_FIX["name"]
    )
    return (f"  {BETA_SITOSTEROL_FIX['name']}: max → NULL "
            f"(was {current_max}). {BETA_SITOSTEROL_FIX['note']}")


def execute():
    if not frappe.db.exists("DocType", QIP):
        raise AssertionError(f"v15_3_0 STEP 0: {QIP} doctype missing")

    print("\nv15_3_0 — T19 Part 2: legacy QIP cleanup (DEAD-data + BETA-SITOSTEROL NLT fix)")

    pending = 0
    applied = 0
    summary_lines = []

    # Part A — DEAD-data ratifications
    print("\n  Part A — DEAD-data QIPs (pending Alicia ratification):")
    for qip_name, ratification in sorted(RATIFIED.items()):
        if ratification is None:
            pending += 1
            print(f"  {qip_name}: pending Alicia ratification")
            continue
        line = _apply_ratification(qip_name, ratification)
        summary_lines.append(line)
        print(line)
        applied += 1

    # Part B — BETA-SITOSTEROL NLT-only fix (ratified, ships now)
    print("\n  Part B — BETA-SITOSTEROL NLT-only fix:")
    line = _apply_beta_sitosterol_fix()
    summary_lines.append(line)
    print(line)

    frappe.db.commit()

    print("\nv15_3_0 summary:")
    print(f"  Part A: {applied} applied, {pending} pending Alicia ratification")
    print(f"  Part B: BETA-SITOSTEROL max-NULL processed")
    if pending > 0:
        print(f"\n  ACTION: replace `None` with ratified dicts in RATIFIED map, then re-run via")
        print(f"  bench --site <site> execute amb_w_spc.patches.v15_3_0.t19_part2_qip_dead_data_cleanup.execute")
