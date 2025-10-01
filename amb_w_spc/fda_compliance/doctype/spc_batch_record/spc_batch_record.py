import frappe
from frappe.model.document import Document

class SpcBatchRecord(Document):
    def validate(self):
        if not self.batch_number:
            frappe.throw("Field 'Batch Number' is required.")
        if not self.product_code:
            frappe.throw("Field 'Product Code' is required.")
        if not self.plant:
            frappe.throw("Field 'Plant' is required.")
        if not self.production_date:
            frappe.throw("Field 'Production Date' is required.")
        if not self.batch_size:
            frappe.throw("Field 'Batch Size' is required.")
        if self.batch_size is not None and not isinstance(self.batch_size, float):
            frappe.throw("Field 'Batch Size' must be a float.")
        if not self.production_supervisor:
            frappe.throw("Field 'Production Supervisor' is required.")
        if not self.quality_inspector:
            frappe.throw("Field 'Quality Inspector' is required.")
        if not self.raw_materials_used:
            frappe.throw("Field 'Raw Materials Used' is required.")
        if not self.equipment_used:
            frappe.throw("Field 'Equipment Used' is required.")
        if not self.batch_status:
            frappe.throw("Field 'Batch Status' is required.")
        if self.batch_status and self.batch_status not in ['In Process', 'Complete', 'Approved', 'Released', 'Rejected', 'Hold']:
            frappe.throw("Field 'Batch Status' must be one of ['In Process', 'Complete', 'Approved', 'Released', 'Rejected', 'Hold'].")
        if self.shelf_life is not None and not isinstance(self.shelf_life, int):
            frappe.throw("Field 'Shelf Life (Months)' must be an integer.")
