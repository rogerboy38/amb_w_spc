"""
V13.6.0 P3 Migration: Batch AMB Custom Tree API + Prevent NestedSet Processing
Original Server Scripts: Batch AMB Custom Tree API, Prevent NestedSet Processing
Type: Whitelisted APIs
"""

import frappe
from frappe import _
import json
import re

# ============================================================
# Batch AMB Custom Tree API
# ============================================================

#import frappe
#from frappe import _
#import json
#import re

def before_insert(self, method):
    """Set up parent relationship before insert"""
    if self.custom_batch_level and int(self.custom_batch_level) > 1:
        if not self.parent_batch_amb:
            frappe.throw(_("Parent Batch AMB is required for level {0}").format(self.custom_batch_level))
        
        # Ensure parent field is set for nested set to work properly
        if not hasattr(self, 'parent'):
            self.parent = self.parent_batch_amb

def before_save(self, method):
    """Validate data before saving"""
    # Validate batch level and parent relationship
    if self.custom_batch_level and int(self.custom_batch_level) > 1:
        if not self.parent_batch_amb:
            frappe.throw(_("Parent Batch AMB is required for level {0}").format(self.custom_batch_level))
    
    # Ensure numeric fields are properly typed (prevent string concatenation errors)
    if self.custom_plant_code:
        try:
            self.custom_plant_code = int(self.custom_plant_code)
        except (ValueError, TypeError):
            pass
    
    if self.custom_sublot_consecutive:
        try:
            self.custom_sublot_consecutive = int(self.custom_sublot_consecutive)
        except (ValueError, TypeError):
            pass
    
    # Validate barrel data for Level 3 containers
    if self.custom_batch_level == '3' and self.container_barrels:
        validate_container_barrel_data(self)
    
    # Never manually set lft/rgt - let Frappe handle them
    if hasattr(self, 'lft') and self.lft is not None and not isinstance(self.lft, (int, float)):
        self.lft = None
    if hasattr(self, 'rgt') and self.rgt is not None and not isinstance(self.rgt, (int, float)):
        self.rgt = None

def on_update(self, method):
    """Called after document is saved"""
    # Update weight totals for Level 3 containers
    if self.custom_batch_level == '3' and self.container_barrels:
        calculate_container_weight_totals(self)
    
    # Let the parent class handle nested set updates
    # Don't interfere with lft/rgt calculations
    pass

def validate(self, method):
    """Validate the document"""
    # Ensure title is set
    if not self.title and self.custom_generated_batch_name:
        self.title = self.custom_generated_batch_name
    
    # Set is_group based on level
    if self.custom_batch_level:
        level = int(self.custom_batch_level)
        if level in [1, 2, 3]:  # Levels 1-3 are groups
            self.is_group = 1
        else:  # Level 4 and beyond are not groups
            self.is_group = 0
    
    # Validate barrel serial number uniqueness for Level 3
    if self.custom_batch_level == '3' and self.container_barrels:
        validate_barrel_serial_uniqueness(self)

def validate_container_barrel_data(self):
    """Validate barrel data in container"""
    if not self.container_barrels:
        return
    
    for idx, barrel in enumerate(self.container_barrels):
        row_num = idx + 1
        
        # Validate required fields
        if barrel.barrel_serial_number and not barrel.gross_weight:
            frappe.throw(_("Row {0}: Gross weight is required for barrel {1}").format(
                row_num, barrel.barrel_serial_number
            ))
        
        if barrel.gross_weight and not barrel.packaging_type:
            frappe.throw(_("Row {0}: Packaging type is required when gross weight is entered").format(row_num))
        
        # Validate weight calculations
        if barrel.gross_weight and barrel.tara_weight:
            calculated_net = barrel.gross_weight - barrel.tara_weight
            
            if calculated_net <= 0:
                frappe.throw(_("Row {0}: Net weight cannot be zero or negative for barrel {1}").format(
                    row_num, barrel.barrel_serial_number
                ))
            
            # Auto-calculate net weight if not set or different
            if not barrel.net_weight or abs(barrel.net_weight - calculated_net) > 0.001:
                barrel.net_weight = calculated_net
        
        # Validate CODE-39 barcode format
        if barrel.barrel_serial_number and not validate_code39_barcode(barrel.barrel_serial_number):
            frappe.throw(_("Row {0}: Invalid CODE-39 barcode format for barrel {1}").format(
                row_num, barrel.barrel_serial_number
            ))

def validate_barrel_serial_uniqueness(self):
    """Ensure barrel serial numbers are unique within the container"""
    if not self.container_barrels:
        return
    
    seen_serials = set()
    
    for idx, barrel in enumerate(self.container_barrels):
        if barrel.barrel_serial_number:
            if barrel.barrel_serial_number in seen_serials:
                frappe.throw(_("Duplicate barrel serial number: {0} (Row {1})").format(
                    barrel.barrel_serial_number, idx + 1
                ))
            seen_serials.add(barrel.barrel_serial_number)
    
    # Check for duplicates across other containers in the system
    if seen_serials:
        existing_serials = frappe.db.sql("""
            SELECT cb.barrel_serial_number, ba.name as container_name
            FROM `tabContainer Barrels` cb
            INNER JOIN `tabBatch AMB` ba ON cb.parent = ba.name
            WHERE cb.barrel_serial_number IN %(serials)s
            AND ba.name != %(current_doc)s
        """, {
            'serials': list(seen_serials),
            'current_doc': self.name or 'new'
        }, as_dict=True)
        
        if existing_serials:
            duplicate_info = ", ".join([
                f"{row['barrel_serial_number']} (in {row['container_name']})"
                for row in existing_serials
            ])
            frappe.throw(_("Barrel serial numbers already exist in other containers: {0}").format(duplicate_info))

def calculate_container_weight_totals(self):
    """Calculate and update weight totals for the container"""
    if not self.container_barrels:
        return
    
    total_gross = 0.0
    total_tara = 0.0
    total_net = 0.0
    barrel_count = 0
    
    for barrel in self.container_barrels:
        if barrel.gross_weight:
            total_gross = total_gross + float(barrel.gross_weight)
        if barrel.tara_weight:
            total_tara = total_tara + float(barrel.tara_weight)
        if barrel.net_weight:
            total_net = total_net + float(barrel.net_weight)
        if barrel.barrel_serial_number:
            barrel_count = barrel_count + 1
    
    # Update totals
    self.total_gross_weight = total_gross
    self.total_tara_weight = total_tara
    self.total_net_weight = total_net
    self.barrel_count = barrel_count
    
    # Update in database if document is saved
    if not self.is_new():
        frappe.db.set_value('Batch AMB', self.name, {
            'total_gross_weight': total_gross,
            'total_tara_weight': total_tara,
            'total_net_weight': total_net,
            'barrel_count': barrel_count
        })

def validate_code39_barcode(barcode):
    """Validate CODE-39 barcode format"""
    if not barcode:
        return False
    
    # CODE-39 allows alphanumeric characters and specific symbols
    return re.match(r'^[A-Z0-9\-\\.\s\$\/\+\%\\*]+$', barcode.upper()) is not None

# API Methods for client script support

@frappe.whitelist()
def get_packaging_item_weight(item_code):
    """Get tara weight for packaging item"""
    if not item_code:
        return {"weight_per_unit": 0}
    
    item = frappe.get_doc("Item", item_code)
    return {
        "weight_per_unit": item.weight_per_unit or 0,
        "item_name": item.item_name,
        "uom": item.weight_uom or "Kg"
    }

@frappe.whitelist()
def get_packaging_items():
    """Get list of packaging items (E0% items)"""
    items = frappe.get_all("Item", 
        filters={
            "item_code": ["like", "E0%"],
            "disabled": 0
        },
        fields=["name", "item_name", "weight_per_unit", "weight_uom"]
    )
    return items

@frappe.whitelist()
def validate_barrel_serial_number(serial_number, container_name=None):
    """Check if barrel serial number already exists"""
    if not serial_number:
        return {"valid": True}
    
    filters = {
        "barrel_serial_number": serial_number
    }
    
    if container_name:
        filters["parent"] = ["!=", container_name]
    
    existing = frappe.get_all("Container Barrels", filters=filters, limit=1)
    
    if existing:
        container_info = frappe.db.get_value("Container Barrels", existing[0].name, "parent")
        return {
            "valid": False,
            "message": f"Serial number {serial_number} already exists in container {container_info}"
        }
    
    return {"valid": True}

@frappe.whitelist()
def bulk_update_tara_weights(container_name, packaging_type):
    """Update tara weights for all barrels of a specific packaging type in container"""
    if not container_name or not packaging_type:
        frappe.throw(_("Container name and packaging type are required"))
    
    # Get packaging item weight
    item_weight = get_packaging_item_weight(packaging_type)
    tara_weight = item_weight.get("weight_per_unit", 0)
    
    if not tara_weight:
        frappe.throw(_("No weight found for packaging type {0}").format(packaging_type))
    
    # Update all matching barrels
    barrels = frappe.get_all("Container Barrels",
        filters={
            "parent": container_name,
            "packaging_type": packaging_type
        },
        fields=["name"]
    )
    
    updated_count = 0
    for barrel in barrels:
        frappe.db.set_value("Container Barrels", barrel.name, "tara_weight", tara_weight)
        updated_count = updated_count + 1
    
    if updated_count > 0:
        # Recalculate net weights
        recalculate_net_weights_for_container(container_name)
        frappe.db.commit()
    
    return {
        "success": True,
        "updated_count": updated_count,
        "tara_weight": tara_weight
    }

@frappe.whitelist()
def recalculate_net_weights_for_container(container_name):
    """Recalculate net weights for all barrels in a container"""
    if not container_name:
        return
    
    barrels = frappe.get_all("Container Barrels",
        filters={"parent": container_name},
        fields=["name", "gross_weight", "tara_weight"]
    )
    
    for barrel in barrels:
        if barrel.gross_weight and barrel.tara_weight:
            net_weight = barrel.gross_weight - barrel.tara_weight
            frappe.db.set_value("Container Barrels", barrel.name, "net_weight", net_weight)
    
    # Update container totals
    container_doc = frappe.get_doc("Batch AMB", container_name)
    calculate_container_weight_totals(container_doc)
    
    frappe.db.commit()

@frappe.whitelist()
def generate_container_report(container_name):
    """Generate weight summary report for container"""
    if not container_name:
        frappe.throw(_("Container name is required"))
    
    container = frappe.get_doc("Batch AMB", container_name)
    
    if container.custom_batch_level != '3':
        frappe.throw(_("This function is only for Level 3 containers"))
    
    # Get barrel details
    barrels = frappe.get_all("Container Barrels",
        filters={"parent": container_name},
        fields=[
            "barrel_serial_number", "packaging_type", 
            "gross_weight", "tara_weight", "net_weight",
            "weight_validated", "scan_timestamp", "notes"
        ],
        order_by="barrel_serial_number"
    )
    
    # Calculate statistics
    total_barrels = len(barrels)
    validated_barrels = sum(1 for b in barrels if b.weight_validated)
    avg_net_weight = sum(b.net_weight or 0 for b in barrels) / max(total_barrels, 1)
    
    # Group by packaging type
    packaging_summary = {}
    for barrel in barrels:
        pkg_type = barrel.packaging_type or "Unknown"
        if pkg_type not in packaging_summary:
            packaging_summary[pkg_type] = {
                "count": 0,
                "total_gross": 0,
                "total_tara": 0,
                "total_net": 0
            }
        
        summary = packaging_summary[pkg_type]
        summary["count"] = summary["count"] + 1
        summary["total_gross"] = summary["total_gross"] + (barrel.gross_weight or 0)
        summary["total_tara"] = summary["total_tara"] + (barrel.tara_weight or 0)
        summary["total_net"] = summary["total_net"] + (barrel.net_weight or 0)
    
    return {
        "container_info": {
            "name": container.name,
            "title": container.title,
            "level": container.custom_batch_level,
            "parent": container.parent_batch_amb
        },
        "summary": {
            "total_barrels": total_barrels,
            "validated_barrels": validated_barrels,
            "total_gross_weight": container.total_gross_weight or 0,
            "total_tara_weight": container.total_tara_weight or 0,
            "total_net_weight": container.total_net_weight or 0,
            "average_net_weight": round(avg_net_weight, 3)
        },
        "packaging_summary": packaging_summary,
        "barrels": barrels
    }

# ============================================================
# Prevent NestedSet Processing
# ============================================================

#import frappe
#from frappe.model.base_document import BaseDocument

#@frappe.whitelist()
def prevent_nestedset():
    """Monkey patch to prevent standard nestedset processing for Batch AMB"""
    
    original_on_update = None
    
    def custom_on_update(self):
        """Custom on_update that skips nestedset for Batch AMB"""
        if (hasattr(self, 'doctype') and self.doctype == "Batch AMB" and 
            hasattr(frappe.flags, 'batch_amb_processing') and frappe.flags.batch_amb_processing):
            # Skip standard nestedset processing
            return
            
        # Call original on_update for other doctypes
        if original_on_update:
            return original_on_update(self)
    
    # Store original method and replace it
    if hasattr(BaseDocument, 'on_update'):
        original_on_update = BaseDocument.on_update
        BaseDocument.on_update = custom_on_update
    
    return "NestedSet prevention applied"


def execute():
    """
    Patch to fix lft and rgt fields that are stored as strings in Batch AMB
    """
    # Fix lft and rgt fields that are stored as strings
    batches = frappe.get_all('Batch AMB', fields=['name', 'lft', 'rgt'])
    
    updated_count = 0
    
    for batch in batches:
        update_needed = False
        updates = {}
        
        if batch.lft and isinstance(batch.lft, str):
            try:
                updates['lft'] = int(batch.lft)
                update_needed = True
            except (ValueError, TypeError):
                updates['lft'] = 0
                update_needed = True
        
        if batch.rgt and isinstance(batch.rgt, str):
            try:
                updates['rgt'] = int(batch.rgt)
                update_needed = True
            except (ValueError, TypeError):
                updates['rgt'] = 0
                update_needed = True
        
        if update_needed:
            frappe.db.set_value('Batch AMB', batch.name, updates)
            updated_count += 1
    
    frappe.msgprint(f"Fixed {updated_count} Batch AMB records with string lft/rgt values")
