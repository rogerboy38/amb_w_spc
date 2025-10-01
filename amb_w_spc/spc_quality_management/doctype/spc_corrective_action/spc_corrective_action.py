import frappe
from frappe.model.document import Document

class SPCCorrectiveAction(Document):
    def validate(self):
        if not self.ca_number:
            frappe.throw("Field 'CA Number' is required.")
        if not self.title:
            frappe.throw("Field 'Title' is required.")
        if not self.priority:
            frappe.throw("Field 'Priority' is required.")
        if self.priority and self.priority not in ['Low', 'Medium', 'High', 'Critical']:
            frappe.throw("Field 'Priority' must be one of ['Low', 'Medium', 'High', 'Critical'].")
        if not self.plant:
            frappe.throw("Field 'Plant' is required.")
        if not self.raised_by:
            frappe.throw("Field 'Raised By' is required.")
        if not self.raised_date:
            frappe.throw("Field 'Raised Date' is required.")
        if not self.ca_status:
            frappe.throw("Field 'Status' is required.")
        if self.ca_status and self.ca_status not in ['Open', 'In Progress', 'Pending Verification', 'Closed', 'Cancelled']:
            frappe.throw("Field 'Status' must be one of ['Open', 'In Progress', 'Pending Verification', 'Closed', 'Cancelled'].")
        if not self.problem_description:
            frappe.throw("Field 'Problem Description' is required.")
        if self.problem_category and self.problem_category not in ['Quality Issue', 'Process Deviation', 'Equipment Failure', 'Human Error', 'Material Defect', 'Environmental', 'Other']:
            frappe.throw("Field 'Problem Category' must be one of ['Quality Issue', 'Process Deviation', 'Equipment Failure', 'Human Error', 'Material Defect', 'Environmental', 'Other'].")
        if self.impact_assessment and self.impact_assessment not in ['Low - Local impact', 'Medium - Department impact', 'High - Plant impact', 'Critical - Company impact']:
            frappe.throw("Field 'Impact Assessment' must be one of ['Low - Local impact', 'Medium - Department impact', 'High - Plant impact', 'Critical - Company impact'].")
        if self.occurrence_frequency and self.occurrence_frequency not in ['First Time', 'Occasional', 'Frequent', 'Continuous']:
            frappe.throw("Field 'Occurrence Frequency' must be one of ['First Time', 'Occasional', 'Frequent', 'Continuous'].")
        if self.customer_impact and self.customer_impact not in ['None', 'Potential', 'Actual', 'Critical']:
            frappe.throw("Field 'Customer Impact' must be one of ['None', 'Potential', 'Actual', 'Critical'].")
        if self.analysis_method and self.analysis_method not in ['5 Why', 'Fishbone Diagram', 'Fault Tree', 'Pareto Analysis', 'FMEA', 'Other']:
            frappe.throw("Field 'Analysis Method' must be one of ['5 Why', 'Fishbone Diagram', 'Fault Tree', 'Pareto Analysis', 'FMEA', 'Other'].")
        if not self.corrective_actions:
            frappe.throw("Field 'Corrective Actions' is required.")
        if not self.overall_responsible_person:
            frappe.throw("Field 'Overall Responsible Person' is required.")
        if not self.target_completion_date:
            frappe.throw("Field 'Target Completion Date' is required.")
        if self.verification_method and self.verification_method not in ['Data Analysis', 'Audit', 'Inspection', 'Testing', 'Monitoring', 'Customer Feedback']:
            frappe.throw("Field 'Verification Method' must be one of ['Data Analysis', 'Audit', 'Inspection', 'Testing', 'Monitoring', 'Customer Feedback'].")
        if self.verification_results and self.verification_results not in ['Effective', 'Partially Effective', 'Ineffective', 'Pending']:
            frappe.throw("Field 'Verification Results' must be one of ['Effective', 'Partially Effective', 'Ineffective', 'Pending'].")
