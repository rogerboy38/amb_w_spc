import frappe
from frappe.model.document import Document

class SPCControlChart(Document):
    def validate(self):
        self.validate_control_limits()
        
    def validate_control_limits(self):
        if self.upper_control_limit and self.lower_control_limit:
            if self.upper_control_limit <= self.lower_control_limit:
                frappe.throw("Upper Control Limit must be greater than Lower Control Limit")
                
        if self.center_line:
            if self.upper_control_limit and self.center_line > self.upper_control_limit:
                frappe.throw("Center Line cannot be greater than Upper Control Limit")
            if self.lower_control_limit and self.center_line < self.lower_control_limit:
                frappe.throw("Center Line cannot be less than Lower Control Limit")
