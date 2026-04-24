"""
Archived Server Script: Batch AMB Validations

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

def validate(doc, method):
    """Main validation function for Batch AMB"""
    if frappe.flags.in_install or frappe.flags.in_migrate:
        return
        
    # Ensure lft and rgt are preserved as strings with leading zeros
    ensure_string_formats(doc)
    
    # Validate batch hierarchy
    validate_batch_hierarchy(doc)
    
    # Validate consecutive number uniqueness
    validate_consecutive_number(doc)
    
    # Auto-generate required fields
    auto_generate_fields(doc)
    
    # Validate batch code format
    validate_batch_code(doc)
    
    # Handle tree structure updates
    update_tree_structure(doc)

def ensure_string_formats(doc):
    """Ensure lft and rgt maintain string format with leading zeros"""
    if doc.lft is None or doc.lft == "":
        # Set initial values for new documents
        doc.lft = "0001"
        doc.rgt = "0002"
    else:
        # Convert integers to properly formatted strings
        if isinstance(doc.lft, int):
            doc.lft = str(doc.lft).zfill(4)
        if isinstance(doc.rgt, int):
            doc.rgt = str(doc.rgt).zfill(5)
        
        # Ensure existing strings have proper padding
        if isinstance(doc.lft, str) and doc.lft.isdigit():
            doc.lft = doc.lft.zfill(4)
        if isinstance(doc.rgt, str) and doc.rgt.isdigit():
            doc.rgt = doc.rgt.zfill(5)

def validate_batch_hierarchy(doc):
    """Validate that batch hierarchy is correct"""
    if not doc.custom_batch_level:
        doc.custom_batch_level = "1"
    
    level = int(doc.custom_batch_level)
    
    if level > 1 and not doc.parent_batch_amb:
        frappe.throw(_("Parent Batch AMB is required for batch level {0}").format(level))
    
    if doc.parent_batch_amb:
        try:
            parent_batch = frappe.get_doc("Batch AMB", doc.parent_batch_amb)
            parent_level = int(parent_batch.custom_batch_level or "1")
            
            if level != parent_level + 1:
                frappe.throw(_("Batch level must be one level below parent. Parent level: {0}, Current level: {1}").format(parent_level, level))
                
        except frappe.DoesNotExistError:
            frappe.throw(_("Parent batch {0} does not exist").format(doc.parent_batch_amb))

def validate_consecutive_number(doc):
    """Validate that consecutive number is unique within the same level and parent"""
    if not doc.consecutive_number:
        return
    
    filters = {
        "consecutive_number": doc.consecutive_number,
        "custom_batch_level": doc.custom_batch_level
    }
    
    if doc.parent_batch_amb:
        filters["parent_batch_amb"] = doc.parent_batch_amb
    else:
        filters["parent_batch_amb"] = ["is", "not set"]
    
    if not doc.is_new():
        filters["name"] = ["!=", doc.name]
    
    existing = frappe.get_all("Batch AMB", filters=filters, limit=1)
    
    if existing:
        frappe.throw(_("Consecutive number {0} already exists for this batch level and parent").format(doc.consecutive_number))

def auto_generate_fields(doc):
    """Auto-generate required fields if not set"""
    # Auto-generate consecutive number if not set
    if not doc.consecutive_number:
        doc.consecutive_number = get_next_consecutive_number(doc)
    
    # Auto-generate batch code
    if not doc.custom_generated_batch_name:
        doc.custom_generated_batch_name = generate_batch_code(doc)
    
    # Set title to batch code
    if doc.custom_generated_batch_name:
        doc.title = doc.custom_generated_batch_name
    
    # Set expiry date if not set (default to 2 years from today)
    if not doc.expiry_date:
        doc.expiry_date = add_years(getdate(), 2)
    
    # Set is_group based on batch level
    doc.is_group = 1 if int(doc.custom_batch_level or "1") < 4 else 0

def get_next_consecutive_number(doc):
    """Get next consecutive number for the batch"""
    filters = {"custom_batch_level": doc.custom_batch_level}
    
    if doc.parent_batch_amb:
        filters["parent_batch_amb"] = doc.parent_batch_amb
    else:
        filters["parent_batch_amb"] = ["is", "not set"]
    
    existing_batches = frappe.get_all(
        "Batch AMB",
        filters=filters,
        fields=["consecutive_number"],
        order_by="consecutive_number desc",
        limit=1
    )
    
    if existing_batches and existing_batches[0].consecutive_number:
        return int(existing_batches[0].consecutive_number) + 1
    else:
        return 1

def generate_batch_code(doc):
    """Generate batch code based on AMB requirements"""
    try:
        # Get plant code (first character of production plant name)
        plant_code = str(doc.production_plant_name)[0].upper() if doc.production_plant_name else "X"
        
        # Format consecutive number as 3 digits
        consecutive_formatted = str(doc.consecutive_number).zfill(3)
        
        # Use formatted lft and rgt values
        lft_str = str(doc.lft or "0000").zfill(4)
        rgt_str = str(doc.rgt or "00000").zfill(5)
        
        # Base batch code
        batch_code = f"{lft_str}{rgt_str}{plant_code}{consecutive_formatted}"
        
        # Add level-specific suffixes
        level = doc.custom_batch_level or "1"
        if level == "2":
            return f"{batch_code}-S{doc.consecutive_number}"
        elif level == "3":
            return f"{batch_code}-C{str(doc.consecutive_number).zfill(3)}"
        elif level == "4":
            return f"{batch_code}-P{doc.consecutive_number}"
        else:
            return batch_code
            
    except Exception as e:
        frappe.log_error(f"Error generating batch code: {str(e)}", "Batch AMB Code Generation")
        return doc.name

def validate_batch_code(doc):
    """Validate that batch code follows AMB format"""
    if not doc.custom_generated_batch_name:
        return
    
    # Check for duplicate batch codes
    filters = {"custom_generated_batch_name": doc.custom_generated_batch_name}
    if not doc.is_new():
        filters["name"] = ["!=", doc.name]
    
    existing = frappe.get_all("Batch AMB", filters=filters, limit=1)
    
    if existing:
        frappe.throw(_("Batch code {0} already exists").format(doc.custom_generated_batch_name))

def update_tree_structure(doc):
    """Handle custom tree structure updates for string-based lft/rgt"""
    global amb_updating_nsm
    
    if amb_updating_nsm:
        return
        
    try:
        amb_updating_nsm = True
        
        if doc.is_new():
            # New document - position it in the tree
            position_new_node(doc)
        else:
            # Existing document - check if parent changed
            old_parent = getattr(doc, "_doc_before_save", {}).get("parent_batch_amb")
            new_parent = doc.parent_batch_amb
            
            if old_parent != new_parent:
                # Parent changed, need to rebuild tree
                frappe.enqueue(rebuild_tree, doctype="Batch AMB", parent_field="parent_batch_amb")
                
    finally:
        amb_updating_nsm = False

def position_new_node(doc):
    """Position a new node in the tree structure"""
    if doc.parent_batch_amb:
        # Child node - position after parent's right value
        parent = frappe.get_doc("Batch AMB", doc.parent_batch_amb)
        if parent.rgt and parent.rgt.isdigit():
            parent_rgt = int(parent.rgt)
            doc.lft = str(parent_rgt).zfill(4)
            doc.rgt = str(parent_rgt + 1).zfill(5)
    else:
        # Root node - find max right value and add after it
        max_rgt = frappe.db.sql("""
            SELECT MAX(CAST(rgt AS UNSIGNED)) 
            FROM `tabBatch AMB` 
            WHERE ifnull(parent_batch_amb, '') = ''
        """)
        
        max_rgt_val = max_rgt[0][0] if max_rgt and max_rgt[0][0] else 0
        doc.lft = str(max_rgt_val + 1).zfill(4)
        doc.rgt = str(max_rgt_val + 2).zfill(5)

# Additional server script for After Save event
def on_update(doc, method):
    """Handle after save events"""
    # Clear cache to refresh tree views
    frappe.clear_cache(doctype="Batch AMB")
    
    # Update parent's is_group flag if needed
    if doc.parent_batch_amb:
        update_parent_is_group(doc.parent_batch_amb)

def on_trash(doc, method):
    """Handle before delete events"""
    # Check if batch has children
    if has_child_batches(doc.name):
        frappe.throw(_("Cannot delete batch {0} because it has child batches").format(doc.name))
    
    # Update parent's is_group flag if this was the last child
    if doc.parent_batch_amb:
        update_parent_is_group(doc.parent_batch_amb, exclude_doc=doc.name)

def has_child_batches(batch_name):
    """Check if a batch has child batches"""
    child_batches = frappe.get_all(
        "Batch AMB",
        filters={"parent_batch_amb": batch_name},
        limit=1
    )
    return len(child_batches) > 0

def update_parent_is_group(parent_name, exclude_doc=None):
    """Update parent's is_group flag based on whether it has children"""
    try:
        filters = {"parent_batch_amb": parent_name}
        if exclude_doc:
            filters["name"] = ["!=", exclude_doc]
        
        remaining_children = frappe.get_all("Batch AMB", filters=filters, limit=1)
        
        parent = frappe.get_doc("Batch AMB", parent_name)
        parent.is_group = 1 if remaining_children else 0
        parent.save(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Error updating parent is_group: {str(e)}", "Batch AMB Update Parent")

# Client-side utility functions (whitelisted)
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
        children = frappe.get_all(
            "Batch AMB",
            filters={"parent_batch_amb": parent_name},
            fields=["name", "title", "custom_batch_level", "custom_generated_batch_name", "is_group"],
            order_by="lft"
        )
        for child in children:
            child["children"] = get_children(child["name"])
        return children
    
    try:
        root_batch = frappe.get_doc("Batch AMB", batch_name)
        
        # If this is not a root batch, find the root
        while root_batch.parent_batch_amb:
            root_batch = frappe.get_doc("Batch AMB", root_batch.parent_batch_amb)
        
        tree = {
            "name": root_batch.name,
            "title": root_batch.title,
            "level": root_batch.custom_batch_level,
            "batch_code": root_batch.custom_generated_batch_name,
            "is_group": root_batch.is_group,
            "children": get_children(root_batch.name)
        }
        return tree
    except Exception as e:
        frappe.log_error(f"Error building batch tree: {str(e)}", "Batch AMB Tree Build")
        return None

#@frappe.whitelist()
def create_child_batch(parent_batch_name, batch_level=None):
    """Create a new child batch""" 
    try:
        parent_batch = frappe.get_doc("Batch AMB", parent_batch_name)
        
        new_batch = frappe.new_doc("Batch AMB")
        new_batch.parent_batch_amb = parent_batch_name
        new_batch.custom_batch_level = str(int(parent_batch.custom_batch_level or "1") + 1)
        new_batch.work_order_ref = parent_batch.work_order_ref
        new_batch.production_plant_name = parent_batch.production_plant_name
        new_batch.wo_item_name = parent_batch.wo_item_name
        new_batch.item_to_manufacture = parent_batch.item_to_manufacture
        
        return new_batch.as_dict()
    except Exception as e:
        frappe.log_error(f"Error creating child batch: {str(e)}", "Batch AMB Child Creation")
        frappe.throw(_("Error creating child batch: {0}").format(str(e)))
"""
