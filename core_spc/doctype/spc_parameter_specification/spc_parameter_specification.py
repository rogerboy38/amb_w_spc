import frappe
from frappe.model.document import Document

class SpcParameterSpecification(Document):
    def validate(self):
        if not self.specification_name:
            frappe.throw("Field 'Specification Name' is required.")
        if self.upper_spec_limit is not None and not isinstance(self.upper_spec_limit, float):
            frappe.throw("Field 'Upper Specification Limit (USL)' must be a float.")
        if self.lower_spec_limit is not None and not isinstance(self.lower_spec_limit, float):
            frappe.throw("Field 'Lower Specification Limit (LSL)' must be a float.")
        if self.target_value is not None and not isinstance(self.target_value, float):
            frappe.throw("Field 'Target Value' must be a float.")
        if self.cpk_target is not None and not isinstance(self.cpk_target, float):
            frappe.throw("Field 'Cpk Target' must be a float.")
        if not self.effective_from:
            frappe.throw("Field 'Effective From' is required.")
