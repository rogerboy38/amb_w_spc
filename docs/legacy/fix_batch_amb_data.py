"""
Archived Server Script: Fix Batch AMB Data

V13.6.0 P3 Server Script Migration
Decision: DEL / archived
Script Type: API
Reference DocType: Batch AMB
Disabled: 1

Runtime status:
  DO NOT IMPORT. Archive only.
"""

ORIGINAL_SCRIPT = """
#import frappe

#@frappe.whitelist()
def fix_batch_amb_data():
    """Fix existing Batch AMB data by converting lft/rgt to strings"""
    try:
        batches = frappe.get_all("Batch AMB", fields=["name", "lft", "rgt"])
        
        for batch in batches:
            updates = {}
            
            if batch.lft is None or batch.lft == "":
                updates["lft"] = "0001"
            elif isinstance(batch.lft, int):
                updates["lft"] = str(batch.lft).zfill(4)
            elif isinstance(batch.lft, str) and batch.lft.isdigit():
                updates["lft"] = batch.lft.zfill(4)
            
            if batch.rgt is None or batch.rgt == "":
                updates["rgt"] = "0002"
            elif isinstance(batch.rgt, int):
                updates["rgt"] = str(batch.rgt).zfill(5)
            elif isinstance(batch.rgt, str) and batch.rgt.isdigit():
                updates["rgt"] = batch.rgt.zfill(5)
            
            if updates:
                frappe.db.set_value("Batch AMB", batch.name, updates)
        
        frappe.db.commit()
        return f"Updated {len(batches)} Batch AMB records"
        
    except Exception as e:
        frappe.log_error(f"Error fixing Batch AMB data: {str(e)}")
        return f"Error: {str(e)}"
"""
