import frappe
from frappe.model.document import Document

class SpcAuditTrail(Document):
    def validate(self):
        if not self.record_id:
            frappe.throw("Field 'Record ID' is required.")
        if not self.timestamp:
            frappe.throw("Field 'Timestamp' is required.")
        if not self.user_id:
            frappe.throw("Field 'User ID' is required.")
        if not self.action_type:
            frappe.throw("Field 'Action Type' is required.")
        if self.action_type and self.action_type not in ['Create', 'Read', 'Update', 'Delete', 'Print', 'Export', 'Sign', 'Approve', 'Reject']:
            frappe.throw("Field 'Action Type' must be one of ['Create', 'Read', 'Update', 'Delete', 'Print', 'Export', 'Sign', 'Approve', 'Reject'].")
        if not self.table_name:
            frappe.throw("Field 'Table Name' is required.")
        if not self.record_name:
            frappe.throw("Field 'Record Name' is required.")
        if not self.ip_address:
            frappe.throw("Field 'IP Address' is required.")
        if not self.session_id:
            frappe.throw("Field 'Session ID' is required.")
        if self.backup_status and self.backup_status not in ['Pending', 'Completed', 'Failed']:
            frappe.throw("Field 'Backup Status' must be one of ['Pending', 'Completed', 'Failed'].")
