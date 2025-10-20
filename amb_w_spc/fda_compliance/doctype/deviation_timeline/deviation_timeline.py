import frappe
from frappe.model.document import Document

class SPCDeviationTimeline(Document):
    def validate(self):
        if not self.milestone:
            frappe.throw("Field 'Milestone' is required.")
        if not self.planned_date:
            frappe.throw("Field 'Planned Date' is required.")
        if not self.responsible_person:
            frappe.throw("Field 'Responsible Person' is required.")
        if self.status and self.status not in ['Not Started', 'In Progress', 'Completed', 'Delayed', 'Cancelled']:
            frappe.throw("Field 'Status' must be one of ['Not Started', 'In Progress', 'Completed', 'Delayed', 'Cancelled'].")
