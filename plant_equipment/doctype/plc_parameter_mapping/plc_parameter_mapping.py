import frappe
from frappe.model.document import Document

class PlcParameterMapping(Document):
    def validate(self):
        if not self.parameter_name:
            frappe.throw("Field 'Parameter Name' is required.")
        if not self.data_type:
            frappe.throw("Field 'Data Type' is required.")
        if self.data_type and self.data_type not in ['Boolean', 'Int16', 'Int32', 'Float', 'Double', 'String']:
            frappe.throw("Field 'Data Type' must be one of ['Boolean', 'Int16', 'Int32', 'Float', 'Double', 'String'].")
        if not self.plc_address:
            frappe.throw("Field 'PLC Address/Tag' is required.")
        if not self.access_type:
            frappe.throw("Field 'Access Type' is required.")
        if self.access_type and self.access_type not in ['Read Only', 'Write Only', 'Read/Write']:
            frappe.throw("Field 'Access Type' must be one of ['Read Only', 'Write Only', 'Read/Write'].")
        if self.scaling_factor is not None and not isinstance(self.scaling_factor, float):
            frappe.throw("Field 'Scaling Factor' must be a float.")
        if self.offset is not None and not isinstance(self.offset, float):
            frappe.throw("Field 'Offset' must be a float.")
