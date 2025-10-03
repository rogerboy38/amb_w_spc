# amb_w_spc/amb_w_spc/sfc_manufacturing/doctype/container_barrels/container_barrels.py

import frappe
from frappe.model.document import Document

class ContainerBarrels(Document):
    def validate(self):
        self.validate_serial_number()
        self.validate_weights()
        self.calculate_net_weight()
        
    def before_save(self):
        """Auto-set scan timestamp if not set"""
        if not self.scan_timestamp and self.barrel_serial_number:
            self.scan_timestamp = frappe.utils.now_datetime()
    
    def validate_serial_number(self):
        """Validate barrel serial number format"""
        if not self.barrel_serial_number:
            return
            
        # Check for CODE-39 format (A-Z, 0-9, and special characters: - . $ / + % *)
        import re
        if not re.match(r'^[A-Z0-9\-\.\s$\/+%*]+$', self.barrel_serial_number.upper()):
            frappe.throw("Invalid barrel serial number format. Only CODE-39 characters are allowed: A-Z, 0-9, and - . $ / + % *")
    
    def validate_weights(self):
        """Validate weight values"""
        if self.gross_weight and self.gross_weight < 0:
            frappe.throw("Gross weight cannot be negative")
            
        if self.tara_weight and self.tara_weight < 0:
            frappe.throw("Tara weight cannot be negative")
            
        if self.net_weight and self.net_weight < 0:
            frappe.throw("Net weight cannot be negative")
    
    def calculate_net_weight(self):
        """Calculate net weight from gross and tara weights"""
        if self.gross_weight is not None and self.tara_weight is not None:
            self.net_weight = self.gross_weight - self.tara_weight
            # Auto-validate if weights are reasonable
            self.weight_validated = 1 if (self.net_weight > 0 and self.net_weight < self.gross_weight) else 0
