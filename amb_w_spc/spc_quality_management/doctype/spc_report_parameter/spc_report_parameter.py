import frappe
from frappe.model.document import Document

class SpcReportParameter(Document):
    def validate(self):
        if not self.parameter_name:
            frappe.throw("Field 'Parameter Name' is required.")
        if self.chart_type and self.chart_type not in ['Control Chart', 'Histogram', 'Trend Chart']:
            frappe.throw("Field 'Chart Type' must be one of ['Control Chart', 'Histogram', 'Trend Chart'].")
