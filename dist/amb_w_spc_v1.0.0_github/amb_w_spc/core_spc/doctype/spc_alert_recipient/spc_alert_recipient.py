import frappe
from frappe.model.document import Document

class SpcAlertRecipient(Document):
    def validate(self):
        if not self.user:
            frappe.throw("Field 'User / Usuario' is required.")
        if not self.alert_method:
            frappe.throw("Field 'Alert Method / Método de Alerta' is required.")
        if self.alert_method and self.alert_method not in ['Email', 'SMS', 'Push Notification', 'All Methods']:
            frappe.throw("Field 'Alert Method / Método de Alerta' must be one of ['Email', 'SMS', 'Push Notification', 'All Methods'].")
        if not self.alert_types:
            frappe.throw("Field 'Alert Types / Tipos de Alerta' is required.")
        if not self.priority_level:
            frappe.throw("Field 'Priority Level / Nivel de Prioridad' is required.")
        if self.priority_level and self.priority_level not in ['Critical', 'High', 'Normal', 'Low']:
            frappe.throw("Field 'Priority Level / Nivel de Prioridad' must be one of ['Critical', 'High', 'Normal', 'Low'].")
