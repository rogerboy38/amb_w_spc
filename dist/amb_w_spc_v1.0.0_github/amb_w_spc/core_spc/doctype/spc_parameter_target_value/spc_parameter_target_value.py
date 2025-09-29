import frappe
from frappe.model.document import Document

class SpcParameterTargetValue(Document):
    def validate(self):
        if not self.product_code:
            frappe.throw("Field 'Product Code' is required.")
        if not self.target_value:
            frappe.throw("Field 'Target Value' is required.")
        if self.target_value is not None and not isinstance(self.target_value, float):
            frappe.throw("Field 'Target Value' must be a float.")
        if self.tolerance is not None and not isinstance(self.tolerance, float):
            frappe.throw("Field 'Tolerance (+/-)' must be a float.")
        if not self.effective_from:
            frappe.throw("Field 'Effective From' is required.")
