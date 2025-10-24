import frappe
from frappe.model.document import Document

class SFCTransaction(Document):
    def before_save(self):
        # Auto-set transaction time if empty
        if not self.transaction_time:
            self.transaction_time = frappe.utils.now_datetime()
            
    def validate(self):
        self.validate_quantity()
        
    def validate_quantity(self):
        if self.quantity and self.quantity < 0:
            frappe.throw("Quantity cannot be negative")
