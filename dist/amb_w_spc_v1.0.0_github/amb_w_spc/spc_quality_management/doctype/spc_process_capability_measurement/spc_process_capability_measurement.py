import frappe
from frappe.model.document import Document

class SPCProcessCapabilityMeasurement(Document):
    def validate(self):
        if not self.sequence_number:
            frappe.throw("Field 'Sequence #' is required.")
        if self.sequence_number is not None and not isinstance(self.sequence_number, int):
            frappe.throw("Field 'Sequence #' must be an integer.")
        if self.subgroup is not None and not isinstance(self.subgroup, int):
            frappe.throw("Field 'Subgroup' must be an integer.")
        if not self.measurement_value:
            frappe.throw("Field 'Value' is required.")
        if self.measurement_value is not None and not isinstance(self.measurement_value, float):
            frappe.throw("Field 'Value' must be a float.")
