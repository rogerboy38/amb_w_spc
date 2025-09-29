import frappe
from frappe.model.document import Document

class SpcAlertRecipient(Document):
    def validate(self):
        if not self.user:
            frappe.throw("Field 'User' is required.")
        if not self.notification_method:
            frappe.throw("Field 'Method' is required.")
        if self.notification_method and self.notification_method not in ['Email', 'SMS', 'Both']:
            frappe.throw("Field 'Method' must be one of ['Email', 'SMS', 'Both'].")
        if self.priority_level and self.priority_level not in ['Low', 'Medium', 'High', 'Critical']:
            frappe.throw("Field 'Priority' must be one of ['Low', 'Medium', 'High', 'Critical'].")
