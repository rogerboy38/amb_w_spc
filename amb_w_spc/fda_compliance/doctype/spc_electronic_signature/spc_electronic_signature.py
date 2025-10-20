import frappe
from frappe.model.document import Document

class SPCElectronicSignature(Document):
    def validate(self):
        if not self.signature_id:
            frappe.throw("Field 'Signature ID' is required.")
        if not self.document_type:
            frappe.throw("Field 'Document Type' is required.")
        if not self.document_name:
            frappe.throw("Field 'Document Name' is required.")
        if not self.signer_name:
            frappe.throw("Field 'Signer Name' is required.")
        if not self.signer_role:
            frappe.throw("Field 'Signer Role' is required.")
        if not self.signature_meaning:
            frappe.throw("Field 'Signature Meaning' is required.")
        if self.signature_meaning and self.signature_meaning not in ['Authored', 'Reviewed', 'Approved', 'Witnessed', 'Responsible', 'Delegate']:
            frappe.throw("Field 'Signature Meaning' must be one of ['Authored', 'Reviewed', 'Approved', 'Witnessed', 'Responsible', 'Delegate'].")
        if not self.signature_date:
            frappe.throw("Field 'Signature Date' is required.")
        if not self.signature_method:
            frappe.throw("Field 'Signature Method' is required.")
        if self.signature_method and self.signature_method not in ['Password', 'Biometric', 'Token', 'Digital Certificate', 'Multi-Factor']:
            frappe.throw("Field 'Signature Method' must be one of ['Password', 'Biometric', 'Token', 'Digital Certificate', 'Multi-Factor'].")
        if not self.user_credentials_verified:
            frappe.throw("Field 'User Credentials Verified' is required.")
        if not self.authorization_level:
            frappe.throw("Field 'Authorization Level' is required.")
        if self.authorization_level and self.authorization_level not in ['Level 1 - Basic', 'Level 2 - Intermediate', 'Level 3 - Advanced', 'Level 4 - Critical']:
            frappe.throw("Field 'Authorization Level' must be one of ['Level 1 - Basic', 'Level 2 - Intermediate', 'Level 3 - Advanced', 'Level 4 - Critical'].")
        if not self.cfr_part11_compliant:
            frappe.throw("Field 'CFR Part 11 Compliant' is required.")
        if self.verification_method and self.verification_method not in ['Digital Certificate', 'Hash Validation', 'Timestamp Verification', 'Biometric Match', 'Database Verification']:
            frappe.throw("Field 'Verification Method' must be one of ['Digital Certificate', 'Hash Validation', 'Timestamp Verification', 'Biometric Match', 'Database Verification'].")
