import frappe
from frappe.model.document import Document

class SPCDeviationTeamMember(Document):
    def validate(self):
        if not self.team_member:
            frappe.throw("Field 'Team Member' is required.")
        if not self.role_in_investigation:
            frappe.throw("Field 'Role in Investigation' is required.")
        if self.role_in_investigation and self.role_in_investigation not in ['Lead Investigator', 'Subject Matter Expert', 'Quality Representative', 'Production Representative', 'Technical Expert', 'Witness']:
            frappe.throw("Field 'Role in Investigation' must be one of ['Lead Investigator', 'Subject Matter Expert', 'Quality Representative', 'Production Representative', 'Technical Expert', 'Witness'].")
