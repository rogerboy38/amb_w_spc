import frappe
from frappe.model.document import Document

class SPCDeviation(Document):
    def validate(self):
        if not self.deviation_number:
            frappe.throw("Field 'Deviation Number' is required.")
        if not self.deviation_type:
            frappe.throw("Field 'Deviation Type' is required.")
        if self.deviation_type and self.deviation_type not in ['Manufacturing', 'Quality Control', 'Documentation', 'Equipment', 'Personnel', 'Environmental', 'System', 'Other']:
            frappe.throw("Field 'Deviation Type' must be one of ['Manufacturing', 'Quality Control', 'Documentation', 'Equipment', 'Personnel', 'Environmental', 'System', 'Other'].")
        if not self.severity:
            frappe.throw("Field 'Severity' is required.")
        if self.severity and self.severity not in ['Critical', 'Major', 'Minor']:
            frappe.throw("Field 'Severity' must be one of ['Critical', 'Major', 'Minor'].")
        if not self.plant:
            frappe.throw("Field 'Plant' is required.")
        if not self.department:
            frappe.throw("Field 'Department' is required.")
        if not self.reported_by:
            frappe.throw("Field 'Reported By' is required.")
        if not self.occurrence_date:
            frappe.throw("Field 'Occurrence Date' is required.")
        if not self.detection_date:
            frappe.throw("Field 'Detection Date' is required.")
        if not self.deviation_description:
            frappe.throw("Field 'Deviation Description' is required.")
        if not self.impact_assessment:
            frappe.throw("Field 'Impact Assessment' is required.")
        if not self.deviation_status:
            frappe.throw("Field 'Deviation Status' is required.")
        if self.deviation_status and self.deviation_status not in ['Open', 'Under Investigation', 'Pending CAPA', 'CAPAs In Progress', 'Pending QA Review', 'Closed', 'Cancelled']:
            frappe.throw("Field 'Deviation Status' must be one of ['Open', 'Under Investigation', 'Pending CAPA', 'CAPAs In Progress', 'Pending QA Review', 'Closed', 'Cancelled'].")
