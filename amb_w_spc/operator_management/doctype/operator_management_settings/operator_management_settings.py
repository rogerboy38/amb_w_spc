import frappe
from frappe.model.document import Document

class OperatorManagementSettings(Document):
    def validate(self):
        self.validate_shift_hours()
        self.validate_max_operators()
        
    def validate_shift_hours(self):
        if self.default_shift_hours and self.default_shift_hours <= 0:
            frappe.throw("Default Shift Hours must be greater than 0")
            
    def validate_max_operators(self):
        if self.max_operators_per_shift and self.max_operators_per_shift <= 0:
            frappe.throw("Max Operators Per Shift must be greater than 0")
