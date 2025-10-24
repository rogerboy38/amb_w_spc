import frappe
from frappe.model.document import Document

class SPCCorrectiveAction(Document):
    def validate(self):
        self.validate_due_date()
        
    def validate_due_date(self):
        if self.due_date:
            from frappe.utils import nowdate
            if self.due_date < nowdate():
                frappe.msgprint("Due Date is in the past")
