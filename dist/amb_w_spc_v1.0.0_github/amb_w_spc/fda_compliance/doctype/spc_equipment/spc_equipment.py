import frappe
from frappe.model.document import Document

class SpcEquipment(Document):
    def validate(self):
        if not self.equipment_id:
            frappe.throw("Field 'Equipment ID' is required.")
        if not self.equipment_name:
            frappe.throw("Field 'Equipment Name' is required.")
        if not self.calibration_status:
            frappe.throw("Field 'Calibration Status' is required.")
        if self.calibration_status and self.calibration_status not in ['Valid', 'Due', 'Overdue', 'Not Required']:
            frappe.throw("Field 'Calibration Status' must be one of ['Valid', 'Due', 'Overdue', 'Not Required'].")
        if self.usage_hours is not None and not isinstance(self.usage_hours, float):
            frappe.throw("Field 'Usage Hours' must be a float.")
