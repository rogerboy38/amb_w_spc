import frappe
from frappe.model.document import Document

class SPCCorrectiveActionItem(Document):
    def validate(self):
        if self.sequence is not None and not isinstance(self.sequence, int):
            frappe.throw("Field '#' must be an integer.")
        if not self.action_description:
            frappe.throw("Field 'Action Description' is required.")
        if not self.responsible_person:
            frappe.throw("Field 'Responsible' is required.")
        if not self.target_date:
            frappe.throw("Field 'Target Date' is required.")
        if self.status and self.status not in ['Open', 'In Progress', 'Completed', 'Overdue']:
            frappe.throw("Field 'Status' must be one of ['Open', 'In Progress', 'Completed', 'Overdue'].")
