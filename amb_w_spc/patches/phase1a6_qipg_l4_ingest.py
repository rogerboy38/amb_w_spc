"""Phase 1A.6 - Final QIPG L4 ingest of Posibles Valores from FoxPro.

Correlation: comet-final-qipg-l4-ingest-post-alicia-disposition
Commissioned: 2026-05-14T20:30Z by claude-cowork after Alicia disposition.

Alicia's 4 dispositions (authoritative):
  1. Official language is English. label_en preferred; label_es is fallback for the 138 EN-empty rows.
     Translation work is deferred; Frappe i18n handles ES at display time.
  2. Pesticides catalog (n=7) is sufficient (controlled by certifications).
  3. Skip non-AUTORIZADO rows. 226 archived to det_anal_NOT_AUTORIZADO.csv.
  4. detanal_es preserved untouched for Phase 2 (task #21).

Placement strategy: each analyte is inserted ONCE as an L4 leaf under its L2 group's
  LQD variant (e.g. 'Physicochemical LQD'), matching the cowork verification sample.
  Expected node-count delta = 507 (§7 of commission letter).

Idempotent: skip-if-exists by deterministic name. Safe to replay on rehearsal + prod.
"""
import csv, os
import frappe
from frappe.utils.nestedset import rebuild_tree

# Authoritative CSV path on the UbuntuVM shared folder. Override via env for rehearsal/prod replays.
INPUT_CSV = os.environ.get(
    'PHASE1A6_QIPG_CSV',
    '/media/sf_E_DRIVE/Claude/sysmayal/ingest/out/qipg_mapping.csv',
)

L2_TO_ERPNEXT_BASE = {
    'Physicochemical':     'Physicochemical',
    'Aloe Vera Nutrients': 'Nutrients',     # ERPNext uses "Nutrients"
    'Microbiological':     'Microbiological',
    'Organoleptic':        'Organoleptic',
    'Other Analysis':      'Other Analysis',
    'Pesticides':          'Pesticides',
    'Contaminants':        'Contaminant',   # ERPNext uses singular "Contaminant"
}
DEFAULT_L1_SUFFIX = 'LQD'  # canonical single placement per cowork §7 sample


def execute():
    if not os.path.exists(INPUT_CSV):
        frappe.log_error(f'Phase1A.6 ingest: CSV not found at {INPUT_CSV}', 'phase1a6_qipg_l4_ingest')
        return

    with open(INPUT_CSV, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    created = skipped = errors = no_label = 0
    errors_log = []
    for row in rows:
        l2_csv = (row.get('l2_group') or '').strip()
        en = (row.get('label_en') or '').strip()
        es = (row.get('label_es') or '').strip()
        label = en or es  # English canonical; ES fallback for EN-empty rows
        if not label:
            no_label += 1
            continue
        base = L2_TO_ERPNEXT_BASE.get(l2_csv)
        if not base:
            errors += 1
            errors_log.append(f'unmapped L2: {l2_csv!r}')
            continue
        parent_l2 = f'{base} {DEFAULT_L1_SUFFIX}'
        if not frappe.db.exists('Quality Inspection Parameter Group', parent_l2):
            errors += 1
            errors_log.append(f'missing parent: {parent_l2!r}')
            continue
        safe = label.replace('<','lt').replace('>','gt')
        leaf_name = f'{safe} - {parent_l2}'
        if frappe.db.exists('Quality Inspection Parameter Group', leaf_name):
            skipped += 1
            continue
        try:
            doc = frappe.get_doc({
                'doctype': 'Quality Inspection Parameter Group',
                'group_name': leaf_name,
                'is_group': 0,
                'custom_parameter_group_child': parent_l2,
            })
            doc.insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors += 1
            errors_log.append(f'{leaf_name!r}: {e}')

    frappe.db.commit()
    try:
        rebuild_tree('Quality Inspection Parameter Group')
        frappe.db.commit()
    except Exception as e:
        errors_log.append(f'rebuild_tree: {e}')

    msg = (f'phase1a6_qipg_l4_ingest summary: created={created} skipped={skipped} '
           f'errors={errors} no_label={no_label} csv_rows={len(rows)}')
    print(msg)
    if errors_log:
        print('errors (first 10):')
        for e in errors_log[:10]:
            print(' ', e)
    return {'created': created, 'skipped': skipped, 'errors': errors,
            'no_label': no_label, 'csv_rows': len(rows)}
