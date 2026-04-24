"""
Archived Server Script: Disable Batch AMB NestedSet

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

def validate(doc, method):
    """Disable standard nestedset behavior and handle tree manually"""
    
    # Prevent the standard nestedset on_update from running
    if hasattr(doc, 'amb_disable_nestedset'):
        return
        
    doc.amb_disable_nestedset = True
    
    # Ensure lft and rgt are properly formatted strings
    ensure_string_formats(doc)
    
    # Handle tree positioning for new documents
    if doc.is_new():
        position_new_node(doc)
    
    # Auto-generate fields
    auto_generate_fields(doc)
    
    # Validate hierarchy
    validate_batch_hierarchy(doc)

def ensure_string_formats(doc):
    """Ensure lft and rgt maintain string format with leading zeros""" 
    if doc.lft is None or doc.lft == "":
        doc.lft = "0001"
    elif isinstance(doc.lft, int):
        doc.lft = str(doc.lft).zfill(4)
    elif isinstance(doc.lft, str) and doc.lft.isdigit():
        doc.lft = doc.lft.zfill(4)
    
    if doc.rgt is None or doc.rgt == "":
        doc.rgt = "0002"
    elif isinstance(doc.rgt, int):
        doc.rgt = str(doc.rgt).zfill(5)
    elif isinstance(doc.rgt, str) and doc.rgt.isdigit():
        doc.rgt = doc.rgt.zfill(5)

def position_new_node(doc):
    """Position a new node in the tree structure"""
    if doc.parent_batch_amb:
        # Child node - get parent's right value and increment
        try:
            parent = frappe.get_doc("Batch AMB", doc.parent_batch_amb)
            if parent.rgt and parent.rgt.isdigit():
                parent_rgt = int(parent.rgt)
                doc.lft = str(parent_rgt).zfill(4)
                doc.rgt = str(parent_rgt + 1).zfill(5)
                
                # Update parent's right value
                parent.rgt = str(parent_rgt + 2).zfill(5)
                parent.save(ignore_permissions=True)
        except frappe.DoesNotExistError:
            frappe.throw(_("Parent batch {0} does not exist").format(doc.parent_batch_amb))
    else:
        # Root node - find max right value
        max_rgt = frappe.db.sql("""
            SELECT MAX(CAST(rgt AS UNSIGNED)) 
            FROM `tabBatch AMB` 
            WHERE ifnull(parent_batch_amb, '') = ''
        """)
        
        max_rgt_val = max_rgt[0][0] if max_rgt and max_rgt[0][0] else 0
        doc.lft = str(max_rgt_val + 1).zfill(4)
        doc.rgt = str(max_rgt_val + 2).zfill(5)

def auto_generate_fields(doc):
    """Auto-generate required fields"""
    if not doc.consecutive_number:
        doc.consecutive_number = get_next_consecutive_number(doc)
    
    if not doc.custom_generated_batch_name:
        doc.custom_generated_batch_name = generate_batch_code(doc)
    
    if doc.custom_generated_batch_name:
        doc.title = doc.custom_generated_batch_name
    
    if not doc.expiry_date:
        from frappe.utils import add_years, getdate
        doc.expiry_date = add_years(getdate(), 2)
    
    # Set is_group based on level
    level = int(doc.custom_batch_level or "1")
    doc.is_group = 1 if level < 4 else 0

def get_next_consecutive_number(doc):
    """Get next consecutive number"""
    filters = {"custom_batch_level": doc.custom_batch_level}
    
    if doc.parent_batch_amb:
        filters["parent_batch_amb"] = doc.parent_batch_amb
    else:
        filters["parent_batch_amb"] = ["is", "not set"]
    
    existing = frappe.get_all("Batch AMB", filters=filters, 
                            fields=["consecutive_number"],
                            order_by="consecutive_number desc", 
                            limit=1)
    
    return int(existing[0].consecutive_number) + 1 if existing and existing[0].consecutive_number else 1

def generate_batch_code(doc):
    """Generate batch code"""
    try:
        plant_code = str(doc.production_plant_name)[0].upper() if doc.production_plant_name else "X"
        consecutive = str(doc.consecutive_number).zfill(3)
        lft_str = str(doc.lft or "0000").zfill(4)
        rgt_str = str(doc.rgt or "00000").zfill(5)
        
        batch_code = f"{lft_str}{rgt_str}{plant_code}{consecutive}"
        
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
        frappe.log_error(f"Error generating batch code: {str(e)}")
        return doc.name

def validate_batch_hierarchy(doc):
    """Validate batch hierarchy"""
    if not doc.custom_batch_level:
        doc.custom_batch_level = "1"
    
    level = int(doc.custom_batch_level)
    
    if level > 1 and not doc.parent_batch_amb:
        frappe.throw(_("Parent Batch AMB is required for batch level {0}").format(level))
    
    if doc.parent_batch_amb:
        try:
            parent = frappe.get_doc("Batch AMB", doc.parent_batch_amb)
            parent_level = int(parent.custom_batch_level or "1")
            
            if level != parent_level + 1:
                frappe.throw(_("Batch level must be one level below parent. Parent level: {0}, Current level: {1}").format(parent_level, level))
                
        except frappe.DoesNotExistError:
            frappe.throw(_("Parent batch {0} does not exist").format(doc.parent_batch_amb))
"""
