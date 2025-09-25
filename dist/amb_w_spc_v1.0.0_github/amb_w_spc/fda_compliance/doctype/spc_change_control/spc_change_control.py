import frappe
from frappe.model.document import Document

class SpcChangeControl(Document):
    def validate(self):
        if not self.change_control_number:
            frappe.throw("Field 'Change Control Number' is required.")
        if not self.change_description:
            frappe.throw("Field 'Change Description' is required.")
        if not self.change_type:
            frappe.throw("Field 'Change Type' is required.")
        if self.change_type and self.change_type not in ['Temporary', 'Permanent', 'Emergency']:
            frappe.throw("Field 'Change Type' must be one of ['Temporary', 'Permanent', 'Emergency'].")
        if self.approval_status and self.approval_status not in ['Pending', 'Approved', 'Rejected']:
            frappe.throw("Field 'Approval Status' must be one of ['Pending', 'Approved', 'Rejected'].")
