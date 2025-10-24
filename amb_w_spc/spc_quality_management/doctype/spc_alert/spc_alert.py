import frappe
from frappe.model.document import Document

class SPCAlert(Document):
    def validate(self):
        self.validate_assignments()
        
    def validate_assignments(self):
        # Auto-assign if not assigned and high severity
        if not self.assigned_to and self.severity in ["High", "Critical"]:
            # In a real system, you might assign to a quality manager
            # For now, we'll just log it
            frappe.msgprint("High severity alert - please assign to appropriate personnel")
