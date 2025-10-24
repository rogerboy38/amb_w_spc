import frappe
from frappe.model.document import Document

class SPCReport(Document):
    def before_save(self):
        # Auto-generate report name if not provided
        if not self.report_name and self.report_type and self.time_period:
            self.report_name = f"{self.report_type} Report - {self.time_period}"
