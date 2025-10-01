import frappe
from frappe.model.document import Document

class SpcBatchParameter(Document):
    def validate(self):
        if not self.parameter_name:
            frappe.throw("Field 'Parameter Name' is required.")
        if not self.specification:
            frappe.throw("Field 'Specification' is required.")
        if not self.result:
            frappe.throw("Field 'Result' is required.")
        if not self.pass_fail:
            frappe.throw("Field 'Pass/Fail' is required.")
        if self.pass_fail and self.pass_fail not in ['Pass', 'Fail', 'Investigate']:
            frappe.throw("Field 'Pass/Fail' must be one of ['Pass', 'Fail', 'Investigate'].")
