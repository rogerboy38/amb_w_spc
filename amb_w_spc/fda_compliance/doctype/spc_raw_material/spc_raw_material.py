import frappe
from frappe.model.document import Document

class SpcRawMaterial(Document):
    def validate(self):
        if not self.material_code:
            frappe.throw("Field 'Material Code' is required.")
        if not self.lot_number:
            frappe.throw("Field 'Lot Number' is required.")
        if not self.quantity_used:
            frappe.throw("Field 'Quantity Used' is required.")
        if self.quantity_used is not None and not isinstance(self.quantity_used, float):
            frappe.throw("Field 'Quantity Used' must be a float.")
        if not self.uom:
            frappe.throw("Field 'UOM' is required.")
