"""
Archived Server Script: batch_naming_amb_old

V13.6.0 P3 Server Script Migration
Decision: DEL / archived
Script Type: DocType Event
Reference DocType: Batch AMB
Disabled: 1

Runtime status:
  DO NOT IMPORT. Archive only.
"""

ORIGINAL_SCRIPT = """
# Server Script: batch_naming_amb
frappe.get_doc({
  "doctype": "Server Script",
  #"name": "batch_naming_amb",
  "script_type": "DocType Event",
  "doctype_event": "Before Save",
  "reference_doctype": "Batch AMB",
  "script": """
if not doc.name and doc.tds_item:
    # Extract first 4 chars of Item Code
    item_prefix = doc.tds_item[:4]
    year = frappe.utils.getdate().strftime("%y")
    plant_code = frappe.db.get_value("Production Plant", doc.plant, "plant_code") or "0"
    
    # Get last batch for this item/year/plant
    last_batch = frappe.get_all("Batch AMB",
        filters={
            "tds_item": doc.tds_item,
            "creation": (">=", f"20{year}-01-01"),
            "name": ("like", f"{item_prefix}%{year}{plant_code}")
        },
        fields=["name"],
        order_by="creation DESC",
        limit=1
    )
    
    # Calculate next consecutive number
    if last_batch:
        last_id = last_batch[0].name
        consecutive = int(last_id[4:7]) + 1  # Positions 5-7
    else:
        consecutive = 1
    
    # Format: ItemPrefix(4) + Consecutive(3) + Year(2) + Plant(1)
    doc.name = f"{item_prefix}{consecutive:03d}{year}{plant_code}"
    frappe.msgprint(f"Generated Batch ID: {doc.name}")  # Debug
"""
}).insert()
"""
