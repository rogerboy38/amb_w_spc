"""
Archived Server Script: Batch AMB Penca

V13.6.0 P3 Server Script Migration
Decision: DEL / archived
Script Type: DocType Event
Reference DocType: Batch AMB
Disabled: 1

Runtime status:
  DO NOT IMPORT. Archive only.
"""

ORIGINAL_SCRIPT = """
# Batch AMB Server Script
# Place this code in Server Script doctype with Event: Before Save

#import frappe
#from frappe import _
#from frappe.utils import now_datetime, getdate, add_years

def validate(doc, method):
    """Validate Batch AMB document before saving"""
    
    # Validate batch level hierarchy
    validate_batch_hierarchy(doc)
    
    # Validate consecutive number uniqueness
    validate_consecutive_number(doc)
    
    # Auto-generate fields if not set
    auto_generate_fields(doc)
    
    # Validate batch code format
    validate_batch_code(doc)
    
    # Set tree structure fields
    set_tree_fields(doc)

def validate_batch_hierarchy(doc):
    """Validate that batch hierarchy is correct"""
    
    if doc.custom_batch_level and int(doc.custom_batch_level) > 1:
        if not doc.parent_batch_amb:
            frappe.throw(_("Parent Batch AMB is required for batch level {0}").format(doc.custom_batch_level))
        
        # Validate that parent exists and has correct level
        parent_batch = frappe.get_doc("Batch AMB", doc.parent_batch_amb)
        parent_level = int(parent_batch.custom_batch_level or 1)
        current_level = int(doc.custom_batch_level)
        
        if current_level != parent_level + 1:
            frappe.throw(_("Batch level must be one level below parent. Parent level: {0}, Current level: {1}").format(parent_level, current_level))

def validate_consecutive_number(doc):
    """Validate that consecutive number is unique within the same level and parent"""
    
    if not doc.consecutive_number:
        return
    
    filters = {
        "consecutive_number": doc.consecutive_number,
        "custom_batch_level": doc.custom_batch_level,
        "lft": doc.lft
    }
    
    if doc.parent_batch_amb:
        filters["parent_batch_amb"] = doc.parent_batch_amb
    
    if not doc.is_new():
        filters["name"] = ["!=", doc.name]
    
    existing = frappe.get_list("Batch AMB", filters=filters, limit=1)
    
    if existing:
        frappe.throw(_("Consecutive number {0} already exists for this batch level and parent").format(doc.consecutive_number))

def auto_generate_fields(doc):
    """Auto-generate required fields if not set"""
    
    # Auto-generate consecutive number if not set
    if not doc.consecutive_number:
        doc.consecutive_number = get_next_consecutive_number(doc)
    
    # Auto-generate batch code
    if doc.lft and doc.rgt and doc.consecutive_number and doc.production_plant_name:
        doc.custom_generated_batch_name = generate_batch_code(doc)
        doc.title = doc.custom_generated_batch_name
    
    # Set expiry date if not set (default to 2 years from today)
    if not doc.expiry_date:
        doc.expiry_date = add_years(getdate(), 2)
    
    # Set is_group flag
    doc.is_group = 1 if has_child_batches(doc) else 0

def get_next_consecutive_number(doc):
    """Get next consecutive number for the batch"""
    
    filters = {
        "custom_batch_level": doc.custom_batch_level,
        "lft": doc.lft
    }
    
    if doc.parent_batch_amb:
        filters["parent_batch_amb"] = doc.parent_batch_amb
    
    existing_batches = frappe.get_list(
        "Batch AMB",
        filters=filters,
        fields=["consecutive_number"],
        order_by="consecutive_number desc",
        limit=1
    )
    
    if existing_batches:
        return int(existing_batches[0].consecutive_number or 0) + 1
    else:
        return 1

def generate_batch_code(doc):
    """Generate batch code based on AMB requirements"""
    
    try:
        # Get plant code (first character of production plant name)
        plant_code = str(doc.production_plant_name)[0] if doc.production_plant_name else "0"
        
        # Format consecutive number as 3 digits
        consecutive_formatted = str(doc.consecutive_number).zfill(3)
        
        # Base batch code: lft(4) + rgt(5) + plant(1) + consecutive(3)
        batch_code = f"{doc.lft}{doc.rgt}{plant_code}{consecutive_formatted}"
        
        # Add level-specific suffixes
        level_suffix = get_batch_level_suffix(doc)
        
        return batch_code + level_suffix
        
    except Exception as e:
        frappe.log_error(f"Error generating batch code: {str(e)}", "Batch AMB Code Generation")
        return None

def get_batch_level_suffix(doc):
    """Get suffix based on batch level"""
    
    level = doc.custom_batch_level
    
    if level == "1":
        # Level 1: No suffix (parent batch)
        return ""
    elif level == "2":
        # Level 2: Sub-lots with -1, -2, etc.
        return f"-{doc.consecutive_number}"
    elif level == "3":
        # Level 3: Containers with -001, -002, etc.
        container_num = str(doc.consecutive_number).zfill(3)
        return f"-{container_num}"
    elif level == "4":
        # Level 4: Pallets with -P1, -P2, etc.
        return f"-P{doc.consecutive_number}"
    else:
        return ""

def validate_batch_code(doc):
    """Validate that batch code follows AMB format"""
    
    if not doc.custom_generated_batch_name:
        return
    
    # Check for duplicate batch codes
    filters = {"custom_generated_batch_name": doc.custom_generated_batch_name}
    if not doc.is_new():
        filters["name"] = ["!=", doc.name]
    
    existing = frappe.get_list("Batch AMB", filters=filters, limit=1)
    
    if existing:
        frappe.throw(_("Batch code {0} already exists").format(doc.custom_generated_batch_name))

def set_tree_fields(doc):
    """Set tree structure fields for hierarchical display"""
    
    # Set is_group based on whether batch has children
    doc.is_group = 1 if has_child_batches(doc) else 0
    
    # Update parent batches to set is_group flag
    if doc.parent_batch_amb:
        parent_batch = frappe.get_doc("Batch AMB", doc.parent_batch_amb)
        parent_batch.is_group = 1
        parent_batch.save(ignore_permissions=True)

def has_child_batches(doc):
    """Check if batch has child batches"""
    
    if doc.is_new():
        return False
    
    child_batches = frappe.get_list(
        "Batch AMB",
        filters={"parent_batch_amb": doc.name},
        limit=1
    )
    
    return len(child_batches) > 0

# Hook functions for document events
def on_update(doc, method):
    """Update tree structure after document update"""
    frappe.clear_cache(doctype="Batch AMB")

def on_trash(doc, method):
    """Validate before deleting batch"""
    
    # Check if batch has children
    if has_child_batches(doc):
        frappe.throw(_("Cannot delete batch {0} because it has child batches").format(doc.name))
    
    # Update parent batch is_group flag if this was the last child
    if doc.parent_batch_amb:
        remaining_children = frappe.get_list(
            "Batch AMB",
            filters={
                "parent_batch_amb": doc.parent_batch_amb,
                "name": ["!=", doc.name]
            },
            limit=1
        )
        
        if not remaining_children:
            parent_batch = frappe.get_doc("Batch AMB", doc.parent_batch_amb)
            parent_batch.is_group = 0
            parent_batch.save(ignore_permissions=True)

# Utility functions for client-side calls
#@frappe.whitelist()
def get_work_order_details(work_order_name):
    """Get Work Order details for client script"""
    
    try:
        work_order = frappe.get_doc("Work Order", work_order_name)
        
        return {
            "production_item": work_order.production_item,
            "item_name": work_order.item_name,
            "production_plant_name": getattr(work_order, "production_plant_name", ""),
            "sales_order": getattr(work_order, "sales_order", ""),
            "planned_end_date": work_order.planned_end_date
        }
    except Exception as e:
        frappe.log_error(f"Error fetching Work Order details: {str(e)}", "Batch AMB Work Order Fetch")
        return None

#@frappe.whitelist()
def get_batch_tree(batch_name):
    """Get complete batch hierarchy tree"""
    
    def get_children(parent_name):
        children = frappe.get_list(
            "Batch AMB",
            filters={"parent_batch_amb": parent_name},
            fields=["name", "title", "custom_batch_level", "custom_generated_batch_name"],
            order_by="custom_batch_level, consecutive_number"
        )
        
        for child in children:
            child["children"] = get_children(child["name"])
        
        return children
    
    # Get root batch
    root_batch = frappe.get_doc("Batch AMB", batch_name)
    
    # If this is not a root batch, find the root
    while root_batch.parent_batch_amb:
        root_batch = frappe.get_doc("Batch AMB", root_batch.parent_batch_amb)
    
    # Build tree structure
    tree = {
        "name": root_batch.name,
        "title": root_batch.title,
        "custom_batch_level": root_batch.custom_batch_level,
        "custom_generated_batch_name": root_batch.custom_generated_batch_name,
        "children": get_children(root_batch.name)
    }
    
    return tree

#@frappe.whitelist()
def create_child_batch(parent_batch_name, batch_level):
    """Create a new child batch"""
    
    try:
        parent_batch = frappe.get_doc("Batch AMB", parent_batch_name)
        
        # Create new batch document
        new_batch = frappe.new_doc("Batch AMB")
        new_batch.parent_batch_amb = parent_batch_name
        new_batch.custom_batch_level = str(int(parent_batch.custom_batch_level) + 1)
        new_batch.work_order_ref = parent_batch.work_order_ref
        new_batch.production_plant_name = parent_batch.production_plant_name
        new_batch.lft = parent_batch.lft
        new_batch.rgt = parent_batch.rgt
        new_batch.wo_item_name = parent_batch.wo_item_name
        new_batch.item_to_manufacture = parent_batch.item_to_manufacture
        
        return new_batch.as_dict()
        
    except Exception as e:
        frappe.log_error(f"Error creating child batch: {str(e)}", "Batch AMB Child Creation")
        frappe.throw(_("Error creating child batch: {0}").format(str(e)))
"""
