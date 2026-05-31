"""T18 Wave 1 — Aloe Vera Nutrients cleanup (Alicia-OK'd rows only).

Source: Alicia revised nutrients spreadsheet
        E:\\Claude\\local-agent-mode-sessions\\T18_alicia_OK_rows_for_sandbox.csv
        (146 OK rows total; this patch handles 42 = 31 DUPLICATE_EN_ES + 11 CONTAMINANT)

Wave 1 scope: cleanup-only ops on EMPTY QIPGs (qip_count=0 across all 139
Nutrient QIPGs per cowork-ops diagnostic 2026-05-31). Zero IQI dependencies
on Nutrient QIPGs — verified safe to delete / rename / reclassify.

Wave 2 (deferred): 103 NUTRIENT additions + 1 AMBIGUOUS row.

Embedded data approach: the CSV file lives on Hugh's Windows host and is
NOT shipped to vpt-docker / hostinger-vpp. So the 42-row Wave 1 dataset
is encoded INLINE in this patch (mojibake already stripped on extraction)
to remain transport-portable. Patch runs identically on VM3 / vpt-docker /
hostinger-vpp without external file dependency.

Operations:
  STEP 1 — DUPLICATE_EN_ES (31 rows):
    For each (Spanish name, English merge_target):
      Case A: both `<Spanish> - Nutrients` AND `<English> - Nutrients` exist
              → DELETE the Spanish dup (substrate child rows cascade)
      Case B: only `<Spanish> - Nutrients` exists
              → RENAME Spanish → English (substrate child rows follow)
      Case C: neither exists → SKIP (Wave 2 will create fresh)
              (3 sterol-family entries currently in Physicochemical L2,
               not Nutrients — flagged in dispatch .ack 2026-05-31)
  STEP 2 — CONTAMINANT (11 rows):
    For each `<name> - Nutrients`:
      → RENAME suffix '- Nutrients' → '- Contaminant'
      → UPDATE custom_parameter_group_child='Contaminant'
      (substrate child rows follow the rename)

Idempotency:
  - Case A re-run: Spanish already deleted → frappe.db.exists False → skip
  - Case B re-run: Spanish renamed to English; on re-run Spanish doesn't
    exist (it IS the English now) → Case C path (skip; English exists)
  - CONTAMINANT re-run: '- Nutrients' suffix QIPG gone; '- Contaminant'
    target exists → skip rename
  - All steps are idempotent select-before-write.

L188-family check (sysmayal-3 NACK2): this patch does NOT call sync_fixtures
or import_file_by_path. Only touches tabQuality Inspection Parameter Group
(core ERPnext, always schema-synced). Safe in any patches.txt phase.

after_migrate hook fires automatically post-patch — rebuild_qipg_tree
normalizes any NSM lft/rgt drift from the rename/delete ops.

References:
  - L188 (banked) — pre-fixture-sync patch preconditions
  - L188.5 (banked) — sync_fixtures broad-iteration hazard (avoided here)
  - L187 (banked) — after_migrate hook handles NSM post-rebuild
  - L150 (banked) — NestedSet nsm_parent_field

Author: claude-sandbox @ VMBox3
Date: 2026-05-31
Task: T18 Wave 1 (Aloe Vera Nutrients cleanup before Wave 2 bulk additions)
"""
import frappe


QIPG = "Quality Inspection Parameter Group"
NUTRIENTS_SUFFIX = " - Nutrients"
CONTAMINANT_SUFFIX = " - Contaminant"
CONTAMINANT_L2 = "Contaminant"

# 31 DUPLICATE_EN_ES rows (Spanish parameter_name, English merge_target).
# Spanish names are mojibake-cleaned at extraction time (CSV had CP1252-
# via-UTF-8 double-encoding; this patch ships the canonical UTF-8 forms).
EN_ES_ROWS = [
    ("24-ETIL-LOFENOL",                    "24-ETHYL-LOPHENOL"),
    ("24-METIL-LOFENOL",                   "24-METHYL-LOPHENOL"),
    ("24-METILENO-CICLOARTANOL",           "24-METHYLENE-CYCLOARTANOL"),
    ("ÁCIDO ACÉTICO",                      "ACETIC ACID"),
    ("ÁCIDO ASPÁRTICO",                    "ASPARTIC ACID"),
    ("ÁCIDO BUTÍRICO",                     "BUTYRIC ACID"),
    ("ÁCIDO CAPRÍLICO",                    "CAPRYLIC ACID"),
    ("ÁCIDO CÁPRICO",                      "CAPRIC ACID"),
    ("ÁCIDO CÍTRICO",                      "CITRIC ACID"),
    ("ÁCIDO FUMÁRICO",                     "FUMARIC ACID"),
    ("ÁCIDO FÓLICO (B9)",                  "FOLIC ACID (B9)"),
    ("ÁCIDO FÓRMICO",                      "FORMIC ACID"),
    ("ÁCIDO GLICÓLICO",                    "GLYCOLIC ACID"),
    ("ÁCIDO HEXADECADIENOICO",             "HEXADECADIENOIC ACID"),
    ("ÁCIDO ISOBUTÍRICO (%)",              "ISOBUTYRIC ACID (%)"),
    ("ÁCIDO ISOVALÉRICO (%)",              "ISOVALERIC ACID (%)"),
    ("ÁCIDO LINOLÉICO",                    "LINOLEIC ACID"),
    ("ÁCIDO LINOLÉNICO",                   "LINOLENIC ACID"),
    ("ÁCIDO LINOTÉNICO",                   "LINOTENIC ACID"),
    ("ÁCIDO LÁCTICO",                      "LACTIC ACID"),
    ("ÁCIDO LÁURICO",                      "LAURIC ACID"),
    ("ÁCIDO MÁLICO",                       "MALIC ACID"),
    ("ÁCIDO OLEICO",                       "OLEIC ACID"),
    ("ÁCIDO PALMITOLEICO",                 "PALMITOLEIC ACID"),
    ("ÁCIDO PANTOTÉNICO (B5)",             "PANTOTHENIC ACID (B5)"),
    ("ÁCIDO PIROGLUTÁMICO",                "PYROGLUTAMIC ACID"),
    ("ÁCIDO PIRÚVICO",                     "PYRUVIC ACID"),
    ("ÁCIDO PROPIÓNICO",                   "PROPIONIC ACID"),
    ("ÁCIDO QUÍNICO",                      "QUINIC ACID"),
    ("ÁCIDO SUCCÍNICO",                    "SUCCINIC ACID"),
    ("ÁCIDO VALÉRICO (%)",                 "VALERIC ACID (%)"),
]

# 11 CONTAMINANT rows (parameter_name; all to be reclassified Nutrients→Contaminant)
CONTAMINANT_ROWS = [
    "AMMONIUM SULFATE",
    "2,4,6-TRICHLOROPHENOL (CAS 88-06-2)",
    "2,4-DICHLOROPHENOL",
    "2,4-DIMETHYLPHENOL",
    "2,6-DICHLOROPHENOL",
    "2-CHLOROPHENOL",
    "2-CRESOL",
    "3-CRESOL",
    "4-CHLORO 3-METHYLPHENOL",
    "4-CRESOL",
    "PHENOL [017]",
]


def execute():
    pre_nutrient_count = frappe.db.count(QIPG, {"custom_parameter_group_child": "Aloe Vera Nutrients"})
    pre_contaminant_count = frappe.db.count(QIPG, {"custom_parameter_group_child": CONTAMINANT_L2})
    print(f"\nT18 W1 pre-state: Aloe Vera Nutrients L2 QIPGs={pre_nutrient_count}, "
          f"Contaminant L2 QIPGs={pre_contaminant_count}")

    # ─── STEP 1: DUPLICATE_EN_ES (31 rows) ───
    print(f"\nSTEP 1 — DUPLICATE_EN_ES ({len(EN_ES_ROWS)} rows)")
    case_a = case_b = case_c = 0
    for sp_name, en_name in EN_ES_ROWS:
        sp_qipg = f"{sp_name}{NUTRIENTS_SUFFIX}"
        en_qipg = f"{en_name}{NUTRIENTS_SUFFIX}"
        sp_exists = frappe.db.exists(QIPG, sp_qipg)
        en_exists = frappe.db.exists(QIPG, en_qipg)

        if sp_exists and en_exists:
            # Case A: delete Spanish dup
            frappe.delete_doc(QIPG, sp_qipg, force=1, ignore_missing=True)
            case_a += 1
            print(f"  Case A delete: '{sp_qipg}'")
        elif sp_exists and not en_exists:
            # Case B: rename Spanish → English (preserves substrate child rows)
            frappe.rename_doc(QIPG, sp_qipg, en_qipg, force=True, merge=False)
            case_b += 1
            print(f"  Case B rename: '{sp_qipg}' → '{en_qipg}'")
        else:
            # Case C (neither exists) OR EN_ONLY (already cleaned) — skip
            case_c += 1

    frappe.db.commit()
    print(f"  EN_ES summary: Case A deleted={case_a}, Case B renamed={case_b}, "
          f"skipped (C/already-cleaned)={case_c}")

    # ─── STEP 2: CONTAMINANT (11 rows) ───
    print(f"\nSTEP 2 — CONTAMINANT reclassify ({len(CONTAMINANT_ROWS)} rows)")
    cont_reclassified = cont_skipped = 0
    for name in CONTAMINANT_ROWS:
        current = f"{name}{NUTRIENTS_SUFFIX}"
        target = f"{name}{CONTAMINANT_SUFFIX}"

        if not frappe.db.exists(QIPG, current):
            # Already reclassified on a prior run OR never present
            cont_skipped += 1
            continue

        if frappe.db.exists(QIPG, target):
            # Both exist — target already present (unusual but defensive). Delete the Nutrients one.
            frappe.delete_doc(QIPG, current, force=1, ignore_missing=True)
            cont_reclassified += 1
            print(f"  Conflict-resolve delete: '{current}' (target '{target}' already present)")
            continue

        # Standard rename + L2 reclassification
        frappe.rename_doc(QIPG, current, target, force=True, merge=False)
        frappe.db.set_value(QIPG, target, "custom_parameter_group_child", CONTAMINANT_L2,
                            update_modified=False)
        cont_reclassified += 1
        print(f"  Reclassify: '{current}' → '{target}' (L2: Aloe Vera Nutrients → Contaminant)")

    frappe.db.commit()
    print(f"  CONTAMINANT summary: reclassified={cont_reclassified}, skipped={cont_skipped}")

    # ─── Post-state ───
    post_nutrient_count = frappe.db.count(QIPG, {"custom_parameter_group_child": "Aloe Vera Nutrients"})
    post_contaminant_count = frappe.db.count(QIPG, {"custom_parameter_group_child": CONTAMINANT_L2})
    total_ops = case_a + case_b + cont_reclassified

    print(f"\nT18 W1 summary:")
    print(f"  Aloe Vera Nutrients L2: {pre_nutrient_count} → {post_nutrient_count} "
          f"(Δ={post_nutrient_count - pre_nutrient_count:+d})")
    print(f"  Contaminant L2: {pre_contaminant_count} → {post_contaminant_count} "
          f"(Δ={post_contaminant_count - pre_contaminant_count:+d})")
    print(f"  Total ops: {total_ops} (Case A={case_a}, Case B={case_b}, "
          f"CONTAMINANT={cont_reclassified})")
    print(f"  after_migrate hook will fire post-patch → rebuild_qipg_tree normalizes NSM.")
