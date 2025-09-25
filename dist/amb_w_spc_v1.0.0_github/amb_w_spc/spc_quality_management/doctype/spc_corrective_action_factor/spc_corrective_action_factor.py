import frappe
from frappe.model.document import Document

class SPCCorrectiveActionFactor(Document):
    def validate(self):
        if not self.factor_type:
            frappe.throw("Field 'Factor Type' is required.")
        if self.factor_type and self.factor_type not in ['Man', 'Machine', 'Method', 'Material', 'Measurement', 'Environment']:
            frappe.throw("Field 'Factor Type' must be one of ['Man', 'Machine', 'Method', 'Material', 'Measurement', 'Environment'].")
        if not self.description:
            frappe.throw("Field 'Description' is required.")
        if self.impact_level and self.impact_level not in ['Low', 'Medium', 'High']:
            frappe.throw("Field 'Impact Level' must be one of ['Low', 'Medium', 'High'].")
