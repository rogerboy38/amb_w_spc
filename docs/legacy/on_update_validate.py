"""
Archived Server Script: on_update_validate

V13.6.0 P3 Server Script Migration
Decision: DEL / archived
Script Type: DocType Event
Reference DocType: Batch AMB
Disabled: 1

Runtime status:
  DO NOT IMPORT. Archive only.
"""

ORIGINAL_SCRIPT = """
# Remove any function definitions and use direct calculation
if str(doc.custom_batch_level) == '3':
    # Initialize totals
    tg = 0.0
    tt = 0.0
    tn = 0.0
    cnt = 0
    
    # Get the child table rows
    rows = doc.get('container_barrels') or []
    
    # Calculate totals using simple loops
    for row in rows:
        if row.gross_weight:
            tg += flt(row.gross_weight)
        if row.tara_weight:
            tt += flt(row.tara_weight)
        if row.net_weight:
            tn += flt(row.net_weight)
        if row.barrel_serial_number and str(row.barrel_serial_number).strip():
            cnt += 1
    
    # Assign values directly (avoid complex assignments)
    doc.total_gross_weight = tg
    doc.total_tara_weight = tt
    doc.total_net_weight = tn
    doc.barrel_count = cnt
"""
