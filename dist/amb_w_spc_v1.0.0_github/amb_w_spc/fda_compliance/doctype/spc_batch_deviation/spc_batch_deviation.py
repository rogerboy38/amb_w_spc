import frappe
from frappe.model.document import Document

class SpcBatchDeviation(Document):
    def validate(self):
        if not self.deviation_number:
            frappe.throw("Field 'Deviation Number' is required.")
        if self.impact and self.impact not in ['No Impact', 'Minor', 'Major', 'Critical']:
            frappe.throw("Field 'Impact' must be one of ['No Impact', 'Minor', 'Major', 'Critical'].")
        if self.resolution_status and self.resolution_status not in ['Open', 'Resolved', 'Accepted']:
            frappe.throw("Field 'Resolution Status' must be one of ['Open', 'Resolved', 'Accepted'].")
