import frappe
from frappe.model.document import Document

class SpcEnvironment(Document):
    def validate(self):
        if not self.parameter:
            frappe.throw("Field 'Parameter' is required.")
        if self.parameter and self.parameter not in ['Temperature', 'Humidity', 'Pressure', 'Air Quality', 'Cleanroom Grade', 'Particle Count', 'Other']:
            frappe.throw("Field 'Parameter' must be one of ['Temperature', 'Humidity', 'Pressure', 'Air Quality', 'Cleanroom Grade', 'Particle Count', 'Other'].")
        if not self.specification:
            frappe.throw("Field 'Specification' is required.")
        if not self.actual_value:
            frappe.throw("Field 'Actual Value' is required.")
        if self.monitoring_frequency and self.monitoring_frequency not in ['Continuous', 'Hourly', 'Daily', 'Batch Start', 'Batch End']:
            frappe.throw("Field 'Monitoring Frequency' must be one of ['Continuous', 'Hourly', 'Daily', 'Batch Start', 'Batch End'].")
