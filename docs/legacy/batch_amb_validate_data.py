"""
Archived Server Script: batch_amb_validate_data

V13.6.0 P3 Server Script Migration
Decision: DEL / archived
Script Type: DocType Event
Reference DocType: Batch AMB
Disabled: 1

Runtime status:
  DO NOT IMPORT. Archive only.
"""

ORIGINAL_SCRIPT = """
def var_to_int(v, d=0):
    try: 
        return int(v)
    except Exception:
        return d

def var_code39_ok(txt):
    if not txt:
        return False
    s = (txt or '').upper()
    allowed = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.$/+%* ')
    for ch in s:
        if ch not in allowed:
            return False
    return True

# Validate parent relationship
level = var_to_int(doc.custom_batch_level, 0)
if level > 1 and not doc.parent_batch_amb:
    frappe.throw(f"Parent Batch AMB is required for level {doc.custom_batch_level}")

# Coerce numeric fields if possible
if doc.get('custom_plant_code'):
    try:
        doc.custom_plant_code = int(doc.custom_plant_code)
    except Exception:
        pass

if  doc.get('custom_sublot_consecutive'):
    try:
        doc.custom_sublot_consecutive = int(doc.custom_sublot_consecutive)
    except Exception:
        pass

# Level 3: validate container barrels
rows = doc.get('container_barrels') or []
if str(doc.custom_batch_level) == '3' and rows:
    for i, row in enumerate(rows, start=1):
        serial = (row.get('barrel_serial_number') or '').strip()
        gross = row.get('gross_weight')
        tara = row.get('tara_weight')
        net = row.get('net_weight')
        pkg = row.get('packaging_type')

        if serial and not gross:
            frappe.throw(f"Row {i}: Gross weight is required for barrel {serial}")

        if gross and not pkg:
            frappe.throw(f"Row {i}: Packaging type is required when gross weight is entered")

        if gross is not None and tara is not None:
            calc_net = float(gross) - float(tara)
            if calc_net <= 0:
                frappe.throw(f"Row {i}: Net weight cannot be zero or negative for barrel {serial}")
            if not net or abs(float(net) - calc_net) > 0.001:
                row['net_weight'] = calc_net

        if serial and not var_code39_ok(serial):
            frappe.throw(f"Row {i}: Invalid CODE-39 barcode format for barrel {serial}")
"""
