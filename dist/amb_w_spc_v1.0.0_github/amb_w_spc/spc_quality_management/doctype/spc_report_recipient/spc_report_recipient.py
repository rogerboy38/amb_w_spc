import frappe
from frappe.model.document import Document

class SpcReportRecipient(Document):
    def validate(self):
        if not self.user:
            frappe.throw("Field 'User' is required.")
        if not self.delivery_method:
            frappe.throw("Field 'Method' is required.")
        if self.delivery_method and self.delivery_method not in ['Email', 'Dashboard', 'Both']:
            frappe.throw("Field 'Method' must be one of ['Email', 'Dashboard', 'Both'].")
        if self.frequency and self.frequency not in ['Real-time', 'Daily', 'Weekly', 'Monthly']:
            frappe.throw("Field 'Frequency' must be one of ['Real-time', 'Daily', 'Weekly', 'Monthly'].")
