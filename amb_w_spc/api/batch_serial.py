"""
V13.6.0 P3 Migration: Batch and Serial
Original Server Script: Batch and Serial
Type: Whitelisted API
"""

import frappe

# Auto-create barrel serials when Sub-Batch is submitted
@frappe.whitelist()
def create_barrel_serials(batch_id, barrel_count=20):
    batch = frappe.get_doc("Batch", batch_id)
    
    if not batch.custom_is_sub_batch:
        frappe.throw("Barrel serials can only be created for Sub-Batches!")
    
    serials = []
    for i in range(1, barrel_count + 1):
        serial_no = f"{batch.name}-{i:02d}"  # Format: "PARENT_BATCH-TRUCK_SEQ-BARREL_NO"
        
        frappe.get_doc({
            "doctype": "Serial No",
            "serial_no": serial_no,
            "item_code": batch.item,
            "batch_no": batch.name,
            "status": "Active"
        }).insert()
        
        serials.append(serial_no)
    
    return serials

# Hook to auto-trigger on Batch submit
def on_submit(doc, method):
    if doc.custom_is_sub_batch:
        create_barrel_serials(doc.name)
