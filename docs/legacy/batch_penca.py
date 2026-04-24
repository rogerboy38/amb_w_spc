"""
Archived Server Script: Batch PENCA

V13.6.0 P3 Server Script Migration
Decision: DEL / archived
Script Type: DocType Event
Reference DocType: Batch AMB
Disabled: 1

Runtime status:
  DO NOT IMPORT. Archive only.
"""

ORIGINAL_SCRIPT = """
# Batch AMB Server Script - Before Save
#import frappe
#from frappe import _
#from frappe.utils import getdate, add_years

def validate(doc, method):
    """Validate Batch AMB document before saving"""
    
    # Ensure lft and rgt are preserved as strings with leading zeros
    if doc.lft and isinstance(doc.lft, int):
        doc.lft = str(doc.lft).zfill(4)  # 4 digits for lft
    if doc.rgt and isinstance(doc.rgt, int):
        doc.rgt = str(doc.rgt).zfill(5)  # 5 digits for rgt (work order format)
    
    # Validate hierarchy
    validate_batch_hierarchy(doc)
    
    # Auto-generate fields
    if not doc.consecutive_number:
        doc.consecutive_number = get_next_consecutive_number(doc)
    
    if doc.consecutive_number and doc.production_plant_name:
        doc.custom_generated_batch_name = generate_batch_code(doc)
        doc.title = doc.custom_generated_batch_name or doc.name

def validate_batch_hierarchy(doc):
    """Validate batch hierarchy"""
    if doc.custom_batch_level and int(doc.custom_batch_level) > 1 and not doc.parent_batch_amb:
        frappe.throw(_("Parent Batch AMB is required for batch level {0}").format(doc.custom_batch_level))

def get_next_consecutive_number(doc):
    """Get next consecutive number"""
    filters = {"custom_batch_level": doc.custom_batch_level}
    if doc.parent_batch_amb:
        filters["parent_batch_amb"] = doc.parent_batch_amb
    
    existing = frappe.get_all("Batch AMB", filters=filters, 
                            fields=["consecutive_number"],
                            order_by="consecutive_number desc", limit=1)
    
    return int(existing[0].consecutive_number) + 1 if existing and existing[0].consecutive_number else 1

def generate_batch_code(doc):
    """Generate batch code preserving string formats"""
    plant_code = str(doc.production_plant_name)[0].upper() if doc.production_plant_name else "X"
    consecutive = str(doc.consecutive_number).zfill(3)
    
    lft_str = str(doc.lft or "0000").zfill(4)
    rgt_str = str(doc.rgt or "00000").zfill(5)
    
    return f"{lft_str}{rgt_str}{plant_code}{consecutive}"
"""
