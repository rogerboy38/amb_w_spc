"""
Archived Server Script: validate_event

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

# Ensure title
if not doc.title and doc.custom_generated_batch_name:
    doc.title = doc.custom_generated_batch_name

# Set is_group by level
level = var_to_int(doc.custom_batch_level, 0)
doc.is_group = 1 if level in (1, 2, 3) else 0

# Uniqueness of barrel serials across containers
rows = doc.get('container_barrels') or []
serials = [(r.get('barrel_serial_number') or '').strip() for r in rows if r.get('barrel_serial_number')]
if serials:
    existing = frappe.db.sql("""
        SELECT cb.barrel_serial_number, ba.name AS container_name
        FROM `tabContainer Barrels` cb
        INNER JOIN `tabBatch AMB` ba ON cb.parent = ba.name
        WHERE cb.barrel_serial_number IN %(serials)s
          AND ba.name != %(current)s
    """, {'serials': serials, 'current': doc.name or 'new'}, as_dict=True)
    if existing:
        info = ", ".join([f"{r['barrel_serial_number']} (in {r['container_name']})" for r in existing])
        frappe.throw(f"Barrel serial numbers already exist in other containers: {info}")

"""
