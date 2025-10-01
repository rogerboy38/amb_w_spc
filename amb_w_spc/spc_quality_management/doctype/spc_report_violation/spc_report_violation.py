import frappe
from frappe.model.document import Document

class SpcReportViolation(Document):
    def validate(self):
        if not self.parameter:
            frappe.throw("Field 'Parameter' is required.")
        if self.violation_type and self.violation_type not in ['Out of Control', 'Trend', 'Shift', 'Run']:
            frappe.throw("Field 'Violation Type' must be one of ['Out of Control', 'Trend', 'Shift', 'Run'].")
        if self.rule_number and self.rule_number not in ['Rule 1', 'Rule 2', 'Rule 3', 'Rule 4', 'Rule 5', 'Rule 6', 'Rule 7', 'Rule 8']:
            frappe.throw("Field 'Rule' must be one of ['Rule 1', 'Rule 2', 'Rule 3', 'Rule 4', 'Rule 5', 'Rule 6', 'Rule 7', 'Rule 8'].")
        if self.violation_count is not None and not isinstance(self.violation_count, int):
            frappe.throw("Field 'Count' must be an integer.")
