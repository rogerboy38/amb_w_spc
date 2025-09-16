import frappe
from frappe.model.document import Document

class SpcParameterControlLimit(Document):
    def validate(self):
        if not self.chart_type:
            frappe.throw("Field 'Chart Type' is required.")
        if self.chart_type and self.chart_type not in ['X-bar R', 'Individual-Moving Range', 'p-chart', 'c-chart', 'u-chart', 'np-chart']:
            frappe.throw("Field 'Chart Type' must be one of ['X-bar R', 'Individual-Moving Range', 'p-chart', 'c-chart', 'u-chart', 'np-chart'].")
        if not self.ucl:
            frappe.throw("Field 'Upper Control Limit (UCL)' is required.")
        if self.ucl is not None and not isinstance(self.ucl, float):
            frappe.throw("Field 'Upper Control Limit (UCL)' must be a float.")
        if not self.lcl:
            frappe.throw("Field 'Lower Control Limit (LCL)' is required.")
        if self.lcl is not None and not isinstance(self.lcl, float):
            frappe.throw("Field 'Lower Control Limit (LCL)' must be a float.")
        if self.center_line is not None and not isinstance(self.center_line, float):
            frappe.throw("Field 'Center Line' must be a float.")
        if self.sigma_level is not None and not isinstance(self.sigma_level, float):
            frappe.throw("Field 'Sigma Level' must be a float.")
        if not self.effective_from:
            frappe.throw("Field 'Effective From' is required.")
