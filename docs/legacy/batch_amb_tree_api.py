"""
Archived Server Script: Batch AMB Tree API

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
#from frappe import _

#@frappe.whitelist()
def add_batch_node(doctype, is_group, work_order_ref, parent=None, is_root=False):
    """Custom method to add Batch AMB nodes - replaces standard treeview"""
    try:
        # Create new document
        doc = frappe.new_doc(doctype)
        doc.is_group = int(is_group)
        doc.work_order_ref = work_order_ref
        
        if parent and parent != "null":
            doc.parent_batch_amb = parent
            # Get parent level and set child level
            parent_level = frappe.db.get_value("Batch AMB", parent, "custom_batch_level") or "1"
            doc.custom_batch_level = str(int(parent_level) + 1)
        else:
            doc.custom_batch_level = "1"
        
        # Set flag to indicate we're processing this document
        frappe.flags.batch_amb_processing = True
        
        try:
            doc.insert()
            
            return {
                "name": doc.name,
                "title": doc.title or doc.name,
                "is_group": doc.is_group,
                "custom_batch_level": doc.custom_batch_level
            }
        finally:
            frappe.flags.batch_amb_processing = False
        
    except Exception as e:
        frappe.log_error(f"Error adding Batch AMB node: {str(e)}")
        frappe.throw(_("Error creating batch: {0}").format(str(e)))

#@frappe.whitelist()
def get_batch_children(parent=None):
    """Get children for tree view"""
    filters = {}
    if parent and parent != "null":
        filters["parent_batch_amb"] = parent
    else:
        filters["parent_batch_amb"] = ["is", "not set"]
    
    children = frappe.get_all(
        "Batch AMB",
        filters=filters,
        fields=["name", "title", "is_group", "custom_batch_level", "custom_generated_batch_name"],
        order_by="lft"
    )
    
    # Add has_children flag for tree view
    for child in children:
        child_id = child["name"]
        has_children = frappe.db.exists("Batch AMB", {"parent_batch_amb": child_id})
        child["has_children"] = bool(has_children)
    
    return children
"""
