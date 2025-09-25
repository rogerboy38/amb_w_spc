import frappe
from frappe.model.document import Document

class SpcReport(Document):
    def validate(self):
        if not self.report_name:
            frappe.throw("Field 'Report Name' is required.")
        if not self.report_type:
            frappe.throw("Field 'Report Type' is required.")
        if self.report_type and self.report_type not in ['Daily', 'Weekly', 'Monthly', 'Custom']:
            frappe.throw("Field 'Report Type' must be one of ['Daily', 'Weekly', 'Monthly', 'Custom'].")
        if not self.plant:
            frappe.throw("Field 'Plant' is required.")
        if self.reporting_frequency and self.reporting_frequency not in ['Real-time', 'Hourly', 'Daily', 'Weekly', 'Monthly', 'On-demand']:
            frappe.throw("Field 'Reporting Frequency' must be one of ['Real-time', 'Hourly', 'Daily', 'Weekly', 'Monthly', 'On-demand'].")
        if self.report_format and self.report_format not in ['PDF', 'Excel', 'Dashboard', 'Email']:
            frappe.throw("Field 'Report Format' must be one of ['PDF', 'Excel', 'Dashboard', 'Email'].")
        if self.shift and self.shift not in ['All Shifts', 'Shift A', 'Shift B', 'Shift C', 'Day Shift', 'Night Shift']:
            frappe.throw("Field 'Shift' must be one of ['All Shifts', 'Shift A', 'Shift B', 'Shift C', 'Day Shift', 'Night Shift'].")
        if self.generation_status and self.generation_status not in ['Scheduled', 'Generating', 'Completed', 'Failed']:
            frappe.throw("Field 'Generation Status' must be one of ['Scheduled', 'Generating', 'Completed', 'Failed'].")
