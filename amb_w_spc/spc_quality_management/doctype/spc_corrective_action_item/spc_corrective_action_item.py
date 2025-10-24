import frappe
from frappe.model.document import Document

class SPCCorrectiveActionItem(Document):
    def validate(self):
        self.validate_dates()
        
    def validate_dates(self):
        if self.target_date and self.completion_date:
            if self.completion_date < self.target_date:
                frappe.msgprint("Completion Date is before Target Date")
