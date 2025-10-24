import frappe
from frappe.model.document import Document

class SPCParameterMaster(Document):
    def validate(self):
        self.validate_limits()
        
    def validate_limits(self):
        if self.upper_spec_limit and self.lower_spec_limit:
            if self.upper_spec_limit <= self.lower_spec_limit:
                frappe.throw("Upper Specification Limit must be greater than Lower Specification Limit")
