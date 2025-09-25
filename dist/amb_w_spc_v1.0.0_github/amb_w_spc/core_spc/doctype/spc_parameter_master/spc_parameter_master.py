import frappe
from frappe.model.document import Document

class SpcParameterMaster(Document):
    def validate(self):
        if not self.parameter_name:
            frappe.throw("Field 'Parameter Name / Nombre del Parámetro' is required.")
        if not self.parameter_code:
            frappe.throw("Field 'Parameter Code / Código del Parámetro' is required.")
        if self.status and self.status not in ['Active', 'Inactive']:
            frappe.throw("Field 'Status / Estado' must be one of ['Active', 'Inactive'].")
        if self.parameter_type and self.parameter_type not in ['Temperature', 'Brix', 'Total Solids', 'pH', 'Viscosity', 'Density', 'Moisture', 'Protein', 'Fat', 'Ash']:
            frappe.throw("Field 'Parameter Type / Tipo de Parámetro' must be one of ['Temperature', 'Brix', 'Total Solids', 'pH', 'Viscosity', 'Density', 'Moisture', 'Protein', 'Fat', 'Ash'].")
        if self.data_type and self.data_type not in ['Numeric', 'Text']:
            frappe.throw("Field 'Data Type / Tipo de Dato' must be one of ['Numeric', 'Text'].")
        if self.default_precision is not None and not isinstance(self.default_precision, int):
            frappe.throw("Field 'Default Precision / Precisión por Defecto' must be an integer.")
