import frappe
from frappe.model.document import Document

class SpcReportCpkValue(Document):
    def validate(self):
        if not self.parameter:
            frappe.throw("Field 'Parameter' is required.")
        if self.cpk_value is not None and not isinstance(self.cpk_value, float):
            frappe.throw("Field 'Cpk Value' must be a float.")
        if self.cp_value is not None and not isinstance(self.cp_value, float):
            frappe.throw("Field 'Cp Value' must be a float.")
        if self.capability_status and self.capability_status not in ['Capable', 'Marginal', 'Incapable']:
            frappe.throw("Field 'Status' must be one of ['Capable', 'Marginal', 'Incapable'].")
