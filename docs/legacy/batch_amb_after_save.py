"""
Archived Server Script: Batch AMB After Save

V13.6.0 P3 Server Script Migration
Decision: DEL / archived
Script Type: DocType Event
Reference DocType: Batch AMB
Disabled: 1

Runtime status:
  DO NOT IMPORT. Archive only.
"""

ORIGINAL_SCRIPT = """
#import frappe
#from frappe import _
#from frappe.utils import getdate, add_years
#from frappe.utils.nestedset import rebuild_tree

# Global flag to prevent recursion
amb_updating_nsm = False

def on_update(doc, method):
    """Handle after save events"""
    global amb_updating_nsm
    
    # Prevent recursion
    if amb_updating_nsm:
        return
        
    amb_updating_nsm = True
    
    try:
        # Update parent's is_group flag if needed
        if doc.parent_batch_amb:
            update_parent_is_group(doc.parent_batch_amb)
            
        # Rebuild tree if necessary (be cautious as this is heavy operation)
        # rebuild_tree("Batch AMB")
        
    finally:
        amb_updating_nsm = False
        # Don't clear cache here as it can interfere with UI state

def update_parent_is_group(parent_name):
    """Update parent's is_group flag without triggering full save"""
    parent = frappe.get_doc("Batch AMB", parent_name)
    if parent and not parent.is_group:
        # Use db_set to update without triggering full document save
        frappe.db.set_value("Batch AMB", parent_name, "is_group", 1)
        frappe.db.commit()
"""
