import frappe
from frappe.model.document import Document

class BatchAMB(Document):
    def before_save(self):
        # Auto-populate item_name if item_code is provided
        if self.item_code and not self.item_name:
            item = frappe.get_value("Item", self.item_code, "item_name")
            if item:
                self.item_name = item
                
    def validate(self):
        self.validate_dates()
        self.validate_quantity()
        
    def validate_dates(self):
        if self.production_date and self.expiry_date:
            if self.expiry_date < self.production_date:
                frappe.throw("Expiry Date cannot be before Production Date")
                
    def validate_quantity(self):
        if self.quantity and self.quantity < 0:
            frappe.throw("Quantity cannot be negative")

@frappe.whitelist()
def create_spc_data_point(source_name, target_doc=None):
    from frappe.model.mapper import get_mapped_doc
    
    def set_missing_values(source, target):
        target.measurement_time = frappe.utils.now_datetime()
        target.batch_reference = source.name
        target.quality_status = "Pending"
    
    doc = get_mapped_doc("Batch AMB", source_name, {
        "Batch AMB": {
            "doctype": "SPC Data Point"
        }
    }, target_doc, set_missing_values)
    
    return doc

@frappe.whitelist()
def create_multiple_batches(count, item_code):
    created_count = 0
    for i in range(int(count)):
        try:
            batch = frappe.get_doc({
                "doctype": "Batch AMB",
                "batch_id": f"AMB-BATCH-{frappe.utils.nowdate()}-{i+1:03d}",
                "item_code": item_code,
                "production_date": frappe.utils.nowdate(),
                "quality_status": "Pending"
            })
            batch.insert()
            created_count += 1
        except Exception:
            continue
    
    frappe.db.commit()
    return created_count

@frappe.whitelist()
def bulk_approve_batches(batches):
    approved_count = 0
    for batch_name in batches:
        try:
            batch = frappe.get_doc("Batch AMB", batch_name)
            batch.quality_status = "Approved"
            batch.save()
            approved_count += 1
        except Exception:
            continue
    
    frappe.db.commit()
    return approved_count
