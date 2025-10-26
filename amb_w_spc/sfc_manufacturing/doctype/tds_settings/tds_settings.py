import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime
import json

class TDSSettings(Document):
    def validate(self):
        self.validate_naming_series()
        self.validate_item_code()
        self.update_sequence_if_needed()
    
    def before_save(self):
        self.set_default_values()
        self.ensure_single_record()
    
    def on_update(self):
        self.update_linked_tds_documents()
    
    def validate_naming_series(self):
        """Validate naming series format"""
        if self.naming_series and not self.naming_series.startswith(self.prefix):
            frappe.throw(f"Naming series must start with the prefix: {self.prefix}")
    
    def validate_item_code(self):
        """Validate that item code exists"""
        if self.item_code and not frappe.db.exists("Item", self.item_code):
            frappe.throw(f"Item {self.item_code} does not exist")
    
    def update_sequence_if_needed(self):
        """Update sequence if naming series suggests a new sequence"""
        if self.naming_series and self.auto_increment_sequence:
            current_sequence = self.extract_sequence_from_naming_series()
            if current_sequence > self.last_sequence_used:
                self.last_sequence_used = current_sequence
    
    def extract_sequence_from_naming_series(self):
        """Extract sequence number from naming series"""
        try:
            # Extract numbers from naming series (e.g., TDS-SET-2024-00001 -> 1)
            import re
            numbers = re.findall(r'\d+', self.naming_series)
            if numbers:
                return int(numbers[-1])  # Get the last sequence number
        except:
            pass
        return self.last_sequence_used
    
    def set_default_values(self):
        """Set default values if not provided"""
        if not self.prefix:
            self.prefix = "TDS-SET"
        
        if not self.default_workflow_state:
            self.default_workflow_state = "Draft"
    
    def ensure_single_record(self):
        """Ensure only one TDS Settings record exists"""
        existing_records = frappe.get_all("TDS Settings", filters={"name": ["!=", self.name]})
        if existing_records:
            frappe.throw("Only one TDS Settings record is allowed. Please update the existing record.")
    
    def update_linked_tds_documents(self):
        """Update linked TDS Product Specification documents when settings change"""
        try:
            linked_tds = frappe.get_all("TDS Product Specification", 
                                       filters={"tds_settings": self.name})
            
            for tds in linked_tds:
                tds_doc = frappe.get_doc("TDS Product Specification", tds.name)
                tds_doc.tds_settings = self.name
                tds_doc.tds_naming_series = self.naming_series
                tds_doc.tds_version = self.get_next_version()
                tds_doc.save()
                
            if linked_tds:
                frappe.msgprint(f"Updated {len(linked_tds)} linked TDS documents")
                
        except Exception as e:
            frappe.log_error(f"Error updating linked TDS documents: {str(e)}")
    
    def get_next_version(self):
        """Get next version number based on current sequence"""
        if self.auto_increment_sequence:
            return f"v{self.last_sequence_used + 1}"
        else:
            return f"v{self.last_sequence_used}"
    
    def get_version_control_info(self):
        """Get version control information"""
        return {
            "current_sequence": self.last_sequence_used,
            "prefix": self.prefix,
            "naming_series": self.naming_series,
            "next_version": self.get_next_version()
        }

# Server-side methods
@frappe.whitelist()
def get_tds_settings():
    """Get current TDS Settings"""
    try:
        settings = frappe.get_single("TDS Settings")
        return {
            "success": True,
            "settings": settings.as_dict(),
            "version_info": settings.get_version_control_info()
        }
    except Exception as e:
        frappe.log_error(f"Error getting TDS Settings: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def increment_sequence():
    """Manually increment the sequence"""
    try:
        settings = frappe.get_single("TDS Settings")
        settings.last_sequence_used += 1
        settings.save()
        
        frappe.msgprint(f"Sequence incremented to: {settings.last_sequence_used}")
        return {"success": True, "new_sequence": settings.last_sequence_used}
    except Exception as e:
        frappe.log_error(f"Error incrementing sequence: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def generate_next_naming_series():
    """Generate next naming series based on current settings"""
    try:
        settings = frappe.get_single("TDS Settings")
        next_sequence = settings.last_sequence_used + 1
        
        # Generate naming series with padded sequence
        year = nowdate()[:4]
        padded_sequence = str(next_sequence).zfill(5)
        
        new_naming_series = f"{settings.prefix}-{year}-{padded_sequence}"
        
        return {
            "success": True,
            "naming_series": new_naming_series,
            "next_sequence": next_sequence
        }
    except Exception as e:
        frappe.log_error(f"Error generating naming series: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def apply_settings_to_all_tds():
    """Apply current settings to all TDS Product Specification documents"""
    try:
        settings = frappe.get_single("TDS Settings")
        all_tds = frappe.get_all("TDS Product Specification")
        
        updated_count = 0
        for tds in all_tds:
            tds_doc = frappe.get_doc("TDS Product Specification", tds.name)
            tds_doc.tds_settings = settings.name
            tds_doc.tds_naming_series = settings.naming_series
            tds_doc.tds_version = settings.get_next_version()
            tds_doc.save()
            updated_count += 1
        
        frappe.msgprint(f"Applied settings to {updated_count} TDS documents")
        return {"success": True, "updated_count": updated_count}
    except Exception as e:
        frappe.log_error(f"Error applying settings to TDS documents: {str(e)}")
        return {"success": False, "error": str(e)}
