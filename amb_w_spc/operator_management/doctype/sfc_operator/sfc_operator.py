import frappe
from frappe.model.document import Document

class SFCOperator(Document):
    def before_save(self):
        # Auto-populate employee_name if employee is provided
        if self.employee and not self.employee_name:
            employee_name = frappe.get_value("Employee", self.employee, "employee_name")
            if employee_name:
                self.employee_name = employee_name
