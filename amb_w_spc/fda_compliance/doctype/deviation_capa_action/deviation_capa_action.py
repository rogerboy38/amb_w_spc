import frappe
from frappe.model.document import Document

class SPCDeviationCapaAction(Document):
    def validate(self):
        if not self.action_description:
            frappe.throw("Field 'Action Description' is required.")
        if not self.action_type:
            frappe.throw("Field 'Action Type' is required.")
        if self.action_type and self.action_type not in ['Corrective', 'Preventive']:
            frappe.throw("Field 'Action Type' must be one of ['Corrective', 'Preventive'].")
        if not self.responsible_person:
            frappe.throw("Field 'Responsible Person' is required.")
        if not self.target_completion_date:
            frappe.throw("Field 'Target Completion Date' is required.")
        if not self.status:
            frappe.throw("Field 'Status' is required.")
        if self.status and self.status not in ['Open', 'In Progress', 'Completed', 'Verified', 'Closed']:
            frappe.throw("Field 'Status' must be one of ['Open', 'In Progress', 'Completed', 'Verified', 'Closed'].")
