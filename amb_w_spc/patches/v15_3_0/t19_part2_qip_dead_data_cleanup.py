"""v15_3_0 — T19 Part 2: backfill canonical min/max + is_numeric on legacy QIPs that
the Path Y picker can't recover via formula fallback (no value_text, no L4 choices,
no custom_choices first-line).

═══════════════════════════════════════════════════════════════════════════════
§1 — Regulatory anchors (per Hugh's research letter 2026-06-01)
═══════════════════════════════════════════════════════════════════════════════

  - EU Regulation (EU) 2021/468 (in force April 2021, Annex III prohibition):
    ≥1 ppm aloin A+B per "as ready for use" finished product = public health
    concern. <1 ppm = acceptable. Same 1 ppm threshold applies to aloe-emodin
    and emodin individually.

  - IASC quality standard: <10 ppm total aloins for finished Aloe Vera leaf
    juice products (oral consumption).

  - AOAC 2016.09: HPLC-UV-MS method for aloin A, B, aloe-emodin, emodin,
    danthron. LOQ = 1 ppm (analytical limit of quantification per EU Standing
    Committee SCOPAFF, Oct 2020).

  - Convention split: BY DRY WEIGHT entries (#1-#4) ratified at NMT 10 ppm
    per WHO/IASC raw-material spec; "as consumed" entries (#5-#7, #14) at
    NMT 1 ppm per EU 2021/468.

═══════════════════════════════════════════════════════════════════════════════
§2 — Per-QIP ratification summary (15 entries)
═══════════════════════════════════════════════════════════════════════════════

  Option distribution per Hugh's filled questionnaire:
    Numeric range (option 1):    2  — Color (absorbance 400nm), Brix grados
    NMT only (option 2):         8  — 4 BY DRY WEIGHT + 3 Aloin + HAD aggregate
    NLT only (option 3):         0
    Descriptive (option 4):      2  — Color, Diacetyl Rhein
    DELETE (option 5):           1  — Color abs (duplicate)
    RENAME (option 6):           2  — pH (0.5%), Polysaccharides ( NMT 20 kda)
                                ────
    Total in-scope:             15

  Rename pairs:
    "pH (0.5%)" → "pH (0.5% solution)"           # remove trailing space, clarify
    "Polysaccharides ( NMT 20 kda)" → "Polysaccharides (NMT 20 kDa)"  # typo+caps

  Delete (DELETE blocked if any IQI row references — patch will print + skip):
    "Color abs"                                   # consolidate into Color (absorbance 400nm)

═══════════════════════════════════════════════════════════════════════════════
§3 — Outstanding Alicia QE rulings (Hugh's session-end punch list)
═══════════════════════════════════════════════════════════════════════════════

  Patch ships with PROVISIONAL values per Hugh's research. Alicia's final
  ratifications still pending on these 4 items:

  ⚠ FLAG 1 — BY DRY WEIGHT limit (affects #1-#4):
     Hugh proposed NMT 10 ppm dry-weight basis. EU 2021/468's 1 ppm threshold
     is for "as consumed" finished products, not raw material. Does AMB have
     a tighter internal spec for dry extract material?

  ⚠ FLAG 2 — Brix grados (#11):
     Brix on powder requires 5% redissolution + dilution-correction formula.
     Does AMB have an SOP? If not, restrict this parameter to LQD-family
     substrate only (remove from PWD/PWDF Parameter Group Substrate child rows).

  ⚠ FLAG 3 — Diacetyl Rhein (#15):
     Not in EU HAD regulation. Tested routinely by AMB? What acceptance
     criterion applies — "NMT LOQ" or "Not detected at 1 ppm" or descriptive?

  ⚠ FLAG 4 — BETA-SITOSTEROL NLT vs NMT (T18 W2 brief):
     T18 W2 brief specified NLT 4 mg/100g (individual sterol; report sum
     of campesterol+stigmasterol+β-sitosterol). Patch §B sets max=NULL on
     this premise. Confirm NLT (not NMT) is the right direction.

  Sister anomaly (NOT in this patch — separate Alicia anomaly packet):
     CFPA-10 — method vs parameter overlap. Best-fit disposition: split into
     Quality Inspection Method doctype + parameter linkage. Awaiting Alicia
     ruling on scope.

═══════════════════════════════════════════════════════════════════════════════
§4 — Original technical context
═══════════════════════════════════════════════════════════════════════════════


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

# Provisional ratification per Hugh's filled questionnaire 2026-06-01
# (regulatory anchors: EU 2021/468 Annex III, IASC quality standard, AOAC 2016.09,
# WHO/IASC raw-material conventions). Awaiting Alicia QE FINAL ratification on 4
# flagged items — see §3 in module docstring.

RATIFIED = {
    # ─── Hydroxyanthracene-derivative family — BY DRY WEIGHT variants ─────────
    # ⚠ ALICIA FLAG 1: NMT 10 ppm on dry-weight basis mirrors WHO/IASC raw-material
    # convention. EU 2021/468's 1 ppm threshold is for finished product "as
    # consumed", not raw material. Confirm AMB doesn't have a tighter internal
    # spec for dry extract.
    "ALOE EMODIN (BY DRY WEIGHT)": {
        "is_numeric": 1, "value_min": 0, "value_max": 10, "value_text": "NMT 10 ppm",
        "note": "NMT 10 ppm dry-weight basis (WHO/IASC convention); EU 2021/468 1 ppm applies to finished product — Hugh proposal pending Alicia ⚠FLAG1",
    },
    "ALOIN A (BY DRY WEIGHT)": {
        "is_numeric": 1, "value_min": 0, "value_max": 10, "value_text": "NMT 10 ppm",
        "note": "NMT 10 ppm dry-weight basis — same reasoning as ALOE EMODIN DRY ⚠FLAG1",
    },
    "ALOIN B (BY DRY WEIGHT)": {
        "is_numeric": 1, "value_min": 0, "value_max": 10, "value_text": "NMT 10 ppm",
        "note": "NMT 10 ppm dry-weight basis — same reasoning as ALOE EMODIN DRY ⚠FLAG1",
    },
    "DANTHRON (BY DRY WEIGHT)": {
        "is_numeric": 1, "value_min": 0, "value_max": 10, "value_text": "NMT 10 ppm",
        "note": "NMT 10 ppm dry-weight basis; danthron included in EU 2021/468 alongside aloin/emodin ⚠FLAG1",
    },

    # ─── Aloin family (non-DRY) — EU 2021/468 finished-product limit ─────────
    "Aloin A": {
        "is_numeric": 1, "value_min": 0, "value_max": 1, "value_text": "NMT 1 ppm",
        "note": "NMT 1 ppm per EU Reg. 2021/468 (Annex III). Individual aloin A component of total A+B sum limit",
    },
    "Aloin B": {
        "is_numeric": 1, "value_min": 0, "value_max": 1, "value_text": "NMT 1 ppm",
        "note": "NMT 1 ppm per EU Reg. 2021/468 (Annex III). Individual aloin B component of total A+B sum limit",
    },
    "Total Aloin A + Aloin B": {
        "is_numeric": 1, "value_min": 0, "value_max": 1, "value_text": "NMT 1 ppm",
        "note": "NMT 1 ppm per EU Reg. 2021/468 (primary regulatory trigger for HAD compliance in Aloe preparations)",
    },

    # ─── Color family — 3 entries; consolidation per Hugh proposal ──────────
    "Color": {
        "is_numeric": 0,
        "note": "Descriptive (text-only choices: Incoloro / Conforme / No conforme per AMB spec sheet). No numeric absorbance",
    },
    "Color (absorbance 400nm)": {
        "is_numeric": 1, "value_min": 0, "value_max": 0.5, "value_text": "0 - 0.5 AU @ 400 nm",
        "note": "Numeric absorbance reading at 400 nm. ≤0.5 AU typical for purified Aloe Vera; AMB to confirm upper bound",
    },
    "Color abs": {
        "delete": True,
        "note": "DELETE — confirmed duplicate of 'Color (absorbance 400nm)'. Keep canonical form only",
    },

    # ─── Misc Physicochemical ────────────────────────────────────────────────
    # ⚠ ALICIA FLAG 2: AMB SOP for Brix on powder requires 5% redissolution +
    # dilution correction. If no SOP, restrict to LQD only (remove from PWD/PWDF
    # Parameter Group Substrate child rows).
    "Brix grados": {
        "is_numeric": 1, "value_min": 0, "value_max": 80, "value_text": "0 - 80 °Bx",
        "note": "Numeric 0-80 °Bx. Powder SOP gap: 5% redissolution + dilution-correction formula needed — Hugh ⚠FLAG2",
    },

    "pH (0.5%)": {
        "rename_to": "pH (0.5% solution)",
        "is_numeric": 1, "value_min": 3.0, "value_max": 5.0, "value_text": "3.0 - 5.0",
        "note": "Rename to remove trailing space + clarify '0.5% solution'. Distinct from undiluted pH parameter; numeric range 3.0-5.0 typical for Aloe 0.5% solution",
    },

    "Polysaccharides ( NMT 20 kda)": {
        "rename_to": "Polysaccharides (NMT 20 kDa)",
        "is_numeric": 1, "value_min": 0, "value_max": 20, "value_text": "NMT 20 kDa",
        "note": "Rename: fix typo (extra space) + capitalize NMT/kDa. NMT 20 kDa molecular weight cutoff for polysaccharide fraction",
    },

    # ─── Anthracene aggregates ──────────────────────────────────────────────
    "Hydroxyanthracene Derivatives": {
        "is_numeric": 1, "value_min": 0, "value_max": 1, "value_text": "NMT 1 ppm",
        "note": "NMT 1 ppm — total HAD sum per EU Reg. 2021/468 aggregate limit (aloins A+B + aloe-emodin + emodin)",
    },

    # ⚠ ALICIA FLAG 3: Diacetyl rhein (diacerein prodrug) is not regulated under
    # EU 2021/468 HAD list but is an anthraquinone derivative. AMB to confirm
    # acceptance criterion — descriptive only (Presente/No detectado) or NMT LOQ?
    "Diacetyl Rhein": {
        "is_numeric": 0,
        "note": "Descriptive (Presente / No detectado). Not regulated under EU 2021/468 — AMB to confirm test routine + criterion ⚠FLAG3",
    },
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
    """Apply a ratified update to one QIP. Returns op_summary str.

    Supports combined rename + value-updates: if rename_to is set, rename FIRST,
    then apply value fields to the (now-renamed) record."""
    if not frappe.db.exists(QIP, qip_name):
        return f"  {qip_name}: NOT FOUND in DB — skip"

    # Delete branch — short-circuits all other actions
    if ratification.get("delete"):
        # L_universal_link_discovery: pre-check for IQI rows referencing this QIP
        in_use = frappe.db.count(
            "Item Quality Inspection Parameter",
            filters={"specification": qip_name}
        )
        if in_use:
            return (f"  {qip_name}: DELETE blocked — {in_use} IQI row(s) reference this QIP. "
                    f"Reassign or delete those rows first. {ratification.get('note', '')}")
        frappe.delete_doc(QIP, qip_name, force=1, ignore_permissions=True)
        return f"  {qip_name}: DELETED (reason: {ratification.get('note', 'no note')})"

    # Rename branch — combine with value updates if other fields are set
    op_name = qip_name
    rename_msg = ""
    if ratification.get("rename_to"):
        new_name = ratification["rename_to"]
        if new_name != qip_name:
            if frappe.db.exists(QIP, new_name):
                return f"  {qip_name}: rename target '{new_name}' already exists — skip"
            frappe.rename_doc(QIP, qip_name, new_name, force=1)
            rename_msg = f"RENAMED → {new_name}; "
            op_name = new_name  # subsequent updates target the new name
        # else: already at canonical name — idempotent, just apply other fields

    # Update fields — is_numeric / value_min / value_max / value_text via raw SQL
    sets = []
    args = {"name": op_name}

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
        if rename_msg:
            return f"  {qip_name}: {rename_msg}no further field updates — {ratification.get('note', '')}"
        return f"  {qip_name}: ratification dict has no actionable fields — skip"

    sql = f"UPDATE `tabQuality Inspection Parameter` SET {', '.join(sets)} WHERE name = %(name)s"
    frappe.db.sql(sql, args)

    # Post-write verification
    row = frappe.db.sql(
        "SELECT custom_is_numeric, custom_value_min, custom_value_max, custom_value_text "
        "FROM `tabQuality Inspection Parameter` WHERE name = %s",
        op_name, as_dict=1
    )
    if not row:
        return f"  {qip_name}: post-write SELECT returned 0 rows — DRIFT"
    r = row[0]
    return (f"  {qip_name}: {rename_msg}UPDATED "
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
