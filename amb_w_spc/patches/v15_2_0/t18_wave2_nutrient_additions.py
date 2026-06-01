"""T18 Wave 2 — Aloe Vera Nutrients QIP additions (103 NUTRIENT rows).

Source: Alicia revised nutrients spreadsheet (146 OK'd rows). Wave 1 (commit
ad2cadb) handled cleanup. Wave 2 (this commit) adds 103 net-new QIPs under
canonical Nutrients tree + 3 sterol markers under new Physicochemical
Authenticity Markers QIPG (Option C per Hugh+Alicia ratification 2026-05-31).

Steps:
  0 — Pre-flight: verify QIP doctype + Custom Fields
  1 — Create 1 Option C QIPG + 5 missing Nutrient leaf QIPGs
  2 — Create 17 UOMs (case-insensitive idempotent)
  3 — Create 71 Quality Inspection Method records
  4 — import_file_by_path on t18_wave2_data.json (103 QIP records)
  5 — Integrity verification

References:
  L187 (after_migrate hook), L188.5 (targeted import), L190 (sub-numbering),
  L191 (mojibake fix applied at extraction), L192 (fixture edit accompanies).

Author: claude-sandbox @ VMBox3
Date: 2026-05-31
Task: T18 Wave 2
"""
import os
import frappe
from frappe.modules.import_file import import_file_by_path


QIPG = "Quality Inspection Parameter Group"
QIP = "Quality Inspection Parameter"
UOM = "UOM"
QIM = "Quality Inspection Method"

ALOE_STEROLS_QIPG = "Physicochemical Authenticity Markers (Aloe Sterols)"
PHYSICOCHEMICAL_L2 = "Physicochemical"
ALOE_VERA_NUTRIENTS_L2 = "Aloe Vera Nutrients"
DATA_JSON_FILENAME = "t18_wave2_data.json"
STD_SUBSTRATES = ["LQD", "LQDC", "LQDF", "PWD", "PWDF"]

MISSING_NUTRIENT_LEAVES = [
    "BETA-SITOSTEROL - Nutrients",
    "GLUCOSE - Nutrients",
    "LOPHENOL - Nutrients",
    "NICKEL (NI) - Nutrients",
    "TOTAL POLYSACCHARIDES - Nutrients",
]

UOM_TO_CREATE = [
    '% or mg/100g', '% w/w or mg/100g', 'U/g', 'U/g or U/mL', 'g/100g',
    'mg QE/100g (quercetin equivalents)', 'mg/100g',
    'mg/100g or % w/w of total FA', 'mg/100g or mg/kg', 'mg/g', 'ng/g',
    'ug/100g or mg/100g', 'ug/g', 'ug/g or mg/100g', 'µg/100g',
    'µg/g (AVGP basis) or mg/100g', 'µg/g (AVGP) or mg/100g',
]

METHOD_TO_CREATE = [
    'AAS (FAAS or GFAAS) or ICP-MS per AOAC 999.11 / AOAC 2011.14 / EAM 4.7',
    'AAS or ICP after acid digestion',
    'AAS or ICP-MS per AOAC 2015.01 / 999.11',
    'AAS or ICP-MS per AOAC 999.11',
    'AOAC 2007.04 / 2017.06 (Davis et al.) — DA-FLD or LC-MS/MS for ascorbate',
    'AOAC 985.35 / 985.34 / 984.27 (atomic absorption spectroscopy after acid digestion)',
    'AOAC 985.35 / 985.34 (AAS after digestion)',
    'AOAC 985.35 / 985.34 (AAS or ICP after dry-ash or microwave digestion)',
    'AOAC 985.35 / 985.34 (AAS or ICP-MS) after wet/dry-ash digestion',
    'AOAC 985.35 / 985.34 (AAS or ICP-OES) after acid digestion',
    'AOAC 985.35 / 985.34 (FAAS or ICP) after dry-ash/wet-ash digestion',
    'AOAC 985.35 / 985.34 (Flame AAS or ICP-MS) after digestion',
    'AOAC 985.35 / 985.34 (Flame AAS or ICP-OES) after dry-ash or microwave digestion',
    'AOAC 985.35 / 985.34 / 984.27 (AAS / ICP after acid digestion)',
    'AOAC 985.35 / 985.34 / 984.27 (Flame AAS or ICP after wet/dry-ash digestion)',
    'AOAC 985.35 / 985.34 / 999.11 (AAS or ICP-MS after acid digestion)',
    'Carrez clarification + HPLC-RID or enzymatic (GOD/POD)',
    'Carrez-clarification + HPLC-RID or enzymatic (GOD/POD)',
    'Carrez-clarification + HPLC-RID per AOAC 977.20',
    'Carrez-clarification + HPLC-RID per AOAC 977.20 / 982.14',
    'Direct titration (Tillmans / 2,6-DCPIP)',
    'Enzymatic activity assay (DNS method or Phadebas) at 540 nm',
    'Enzymatic activity assay (azocasein or Anson method)',
    'Enzymatic activity assay (titrimetric pNPP or olive-oil emulsion)',
    'Enzymatic clinical assay (LDH-NADH) per AOAC SMPR for organic acids; alternativ...',
    'Enzymatic kit assay (UV-Vis spectrophotometry) per Megazyme or Sigma protocols',
    'Enzymatic kit assay or HPLC after derivatization',
    'GC-FID after methylation (FAME)',
    'GC-FID after methylation to FAME (AOAC 996.06 / AOCS Ce 1h-05)',
    'GC-FID after methylation to FAME (AOCS Ce 1h-05)',
    'GC-FID after methylation to FAME (AOCS Ce 1h-05 / AOAC 996.06)',
    'GC-FID after methylation to FAME per AOAC 996.06 / AOCS Ce 1h-05',
    'GC-FID after silylation (TMS) per AOCS Ch 6-91',
    'GC-FID after silylation (TMS) per AOCS Ch 6-91 / Ce 12-16',
    'GC-FID/MS after derivatization (TMS)',
    'GC-FID/MS after derivatization (silylation)',
    'GC-FID/MS after silylation (TMS)',
    'GC-MS after derivatization (oxime + TMS)',
    'HPLC with ion-exclusion column (SUPELCOGEL C-610H / Aminex HPX-87H) and DAD or ...',
    'HPLC-DAD (210 nm) per FoodChem standard methods',
    'HPLC-DAD (290 nm) with C18 column',
    'HPLC-DAD or LC-MS per Megazyme / WHO flavonoid method',
    'HPLC-DAD per AOAC 991.20 / 982.14',
    'HPLC-DAD per Pharmacopeia (USP) or LC-MS',
    'HPLC-MS or pyrrolizidine alkaloid assays',
    'HPLC-RID per AOAC 977.20 or 982.14',
    'HPLC-RID per AOAC 977.20/982.14',
    'HPLC-UV (321 nm) after extraction',
    'HPLC-UV (340 nm) after extraction',
    'HPLC-UV at 280 nm (after Maillard reaction analysis)',
    'HPLC-UV at 365 nm or LC-MS',
    'LC-MS/MS (validated for 5 Aloe sterols incl. 24-ethyl-lophenol) per Hattori et ...',
    'LC-MS/MS (validated for 5 Aloe sterols incl. 24-methyl-lophenol) per Hattori et...',
    'LC-MS/MS (validated for 5 Aloe sterols incl. 24-methylene-cycloartanol) per Hat...',
    'LC-MS/MS per AOAC 2017.05 / FDA SLF 96',
    'LC-MS/MS per FDA Compliance method',
    'Microbiological assay or LC-MS',
    'Microbiological assay or LC-MS per AOAC 2011.06',
    'Microbiological assay (Lactobacillus) or HPLC-DAD/MS',
    'Microbiological assay (Lactobacillus) or HPLC-DAD/MS per AOAC 944.05',
    'Microbiological assay (Lactobacillus) per AOAC 944.05',
    'Phytosterol fingerprint by GC-FID after silylation (AOCS Ch 6-91)',
    'Phytosterol fingerprint by GC-FID after silylation (TMS) per AOCS Ch 6-91',
    'Phytosterol fingerprint by GC-FID after silylation (TMS) per AOCS Ch 6-91 / Ce ...',
    'Phytosterol fingerprint by GC-FID/MS after silylation (TMS) per AOCS Ch 6-91',
    'Phytosterol profile by GC-FID after silylation (TMS) per AOCS Ch 6-91',
    'Pyrogallol-fluorimetric or H2O2-coupled spectrophotometric assay',
    'Total polysaccharides by phenol-sulfuric (Dubois) method as glucose equivalents',
    'UHPLC-UV after acid/alkaline hydrolysis with OPA derivatization',
    'UHPLC-UV after acid/alkaline hydrolysis with OPA derivatization (AOAC 994.12)',
    'Wet-ash + AAS or ICP-OES per AOAC 985.35 / 985.34',
    'Wet-ash + AAS or ICP-OES per AOAC 985.35 / 985.34 / EAM 4.7',
]


def _step_0_preflight():
    if not frappe.db.exists("DocType", QIP):
        raise AssertionError(f"v15_2_0 STEP 0: {QIP} doctype missing")
    required_cfs = ["custom_value_text", "custom_value_min", "custom_value_max",
                    "custom_unit", "custom_method", "custom_is_numeric"]
    for fn in required_cfs:
        if not frappe.db.exists("Custom Field", {"dt": QIP, "fieldname": fn}):
            raise AssertionError(f"v15_2_0 STEP 0: Custom Field '{fn}' missing on {QIP}")
    print(f"  STEP 0 ok: {QIP} + {len(required_cfs)} Custom Fields present")


def _step_1_create_qipgs():
    writes = 0
    if not frappe.db.exists(QIPG, ALOE_STEROLS_QIPG):
        if not frappe.db.exists(QIPG, PHYSICOCHEMICAL_L2):
            raise AssertionError(f"v15_2_0 STEP 1: parent L2 '{PHYSICOCHEMICAL_L2}' missing")
        doc = frappe.get_doc({
            "doctype": QIPG,
            "group_name": ALOE_STEROLS_QIPG,
            "custom_parameter_group_child": PHYSICOCHEMICAL_L2,
            "is_group": 0,
            "applicable_substrates": [{"substrate": s} for s in STD_SUBSTRATES],
        })
        doc.insert(ignore_permissions=True)
        writes += 1
        print(f"  STEP 1 created Option C QIPG: {ALOE_STEROLS_QIPG}")
    for qipg_name in MISSING_NUTRIENT_LEAVES:
        if frappe.db.exists(QIPG, qipg_name):
            continue
        doc = frappe.get_doc({
            "doctype": QIPG,
            "group_name": qipg_name,
            "custom_parameter_group_child": ALOE_VERA_NUTRIENTS_L2,
            "is_group": 0,
            "applicable_substrates": [{"substrate": s} for s in STD_SUBSTRATES],
        })
        doc.insert(ignore_permissions=True)
        writes += 1
        print(f"  STEP 1 created Nutrient leaf: {qipg_name}")
    return writes


def _step_2_create_uoms():
    writes = 0
    for uom_name in UOM_TO_CREATE:
        existing = frappe.db.sql(
            "SELECT name FROM tabUOM WHERE LOWER(name) = LOWER(%s) LIMIT 1",
            (uom_name,), as_list=True,
        )
        if existing:
            continue
        doc = frappe.get_doc({"doctype": UOM, "uom_name": uom_name, "enabled": 1})
        doc.insert(ignore_permissions=True)
        writes += 1
    print(f"  STEP 2 UOMs created: {writes} of {len(UOM_TO_CREATE)} candidates")
    return writes


def _step_3_create_methods():
    """Create Quality Inspection Method records. QIM autoname='prompt' (verified
    via VM3 introspection), so name must be set explicitly. Set both name +
    inspection_method to the same value (mirrors existing record pattern)."""
    writes = 0
    for method_name in METHOD_TO_CREATE:
        existing = frappe.db.sql(
            "SELECT name FROM `tabQuality Inspection Method` WHERE LOWER(name) = LOWER(%s) LIMIT 1",
            (method_name,), as_list=True,
        )
        if existing:
            continue
        doc = frappe.get_doc({
            "doctype": QIM,
            "name": method_name,
            "inspection_method": method_name,
        })
        doc.insert(ignore_permissions=True)
        writes += 1
    print(f"  STEP 3 Methods created: {writes} of {len(METHOD_TO_CREATE)} candidates")
    return writes


def _step_4_import_qips():
    patch_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(patch_dir, DATA_JSON_FILENAME)
    if not os.path.exists(data_path):
        raise AssertionError(f"v15_2_0 STEP 4: data file missing at {data_path}")
    pre_count = frappe.db.count(QIP)
    print(f"  STEP 4 import_file_by_path: {data_path}")
    import_file_by_path(data_path, data_import=True, force=True, reset_permissions=True)
    frappe.db.commit()
    post_count = frappe.db.count(QIP)
    print(f"  STEP 4 QIP count: {pre_count} → {post_count} (Δ={post_count-pre_count:+d})")
    return post_count - pre_count


def _step_5_integrity_check():
    import json
    patch_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(patch_dir, DATA_JSON_FILENAME)
    with open(data_path, encoding="utf-8") as f:
        expected_rows = json.load(f)
    expected_names = {r["name"] for r in expected_rows}
    placeholders = ",".join(["%s"] * len(expected_names))
    actual_present = frappe.db.sql(
        f"SELECT name FROM `tab{QIP}` WHERE name IN ({placeholders})",
        tuple(expected_names), as_list=True,
    )
    actual_set = {n[0] for n in actual_present}
    missing = expected_names - actual_set
    if missing:
        print(f"  STEP 5 WARN: {len(missing)} expected QIPs missing: {sorted(missing)[:5]}")
    else:
        print(f"  STEP 5 ok: all {len(expected_names)} expected QIPs present")
    sterols = ["24-ETHYL-LOPHENOL", "24-METHYL-LOPHENOL", "24-METHYLENE-CYCLOARTANOL"]
    misparented = []
    for s in sterols:
        actual_pg = frappe.db.get_value(QIP, s, "parameter_group")
        if actual_pg != ALOE_STEROLS_QIPG:
            misparented.append((s, actual_pg))
    if misparented:
        print(f"  STEP 5 WARN: Option C misparenting: {misparented}")
    else:
        print(f"  STEP 5 ok: 3 Aloe sterols correctly parented to {ALOE_STEROLS_QIPG}")


def execute():
    pre = {dt: frappe.db.count(dt) for dt in [QIPG, QIP, UOM, QIM]}
    print(f"\nT18 Wave 2 pre-state: {pre}")
    print(f"\nSTEP 0 — Pre-flight"); _step_0_preflight()
    print(f"\nSTEP 1 — Create QIPGs ({1 + len(MISSING_NUTRIENT_LEAVES)} candidates)")
    w1 = _step_1_create_qipgs()
    print(f"\nSTEP 2 — Create UOMs ({len(UOM_TO_CREATE)} candidates)")
    w2 = _step_2_create_uoms()
    print(f"\nSTEP 3 — Create Quality Inspection Methods ({len(METHOD_TO_CREATE)} candidates)")
    w3 = _step_3_create_methods()
    print(f"\nSTEP 4 — Import 103 QIPs via import_file_by_path")
    w4 = _step_4_import_qips()
    print(f"\nSTEP 5 — Integrity verification")
    _step_5_integrity_check()
    post = {dt: frappe.db.count(dt) for dt in [QIPG, QIP, UOM, QIM]}
    print(f"\nT18 Wave 2 summary:")
    for dt in [QIPG, QIP, UOM, QIM]:
        print(f"  {dt}: {pre[dt]} → {post[dt]} (Δ={post[dt]-pre[dt]:+d})")
    print(f"  after_migrate hook will fire → rebuild_qipg_tree normalizes NSM.")
