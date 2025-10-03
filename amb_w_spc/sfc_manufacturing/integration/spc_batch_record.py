# spc_batch_record.py (Enhanced)
import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime

class SPCBatchRecord(Document):
    def validate(self):
        self.validate_batch_reference()
        self.calculate_overall_status()
        self.validate_required_fields()
        
    def on_update(self):
        self.update_batch_amb_status()
        
    def validate_batch_reference(self):
        """Validate that batch reference exists and is level 1"""
        if self.batch_amb_reference:
            batch_level = frappe.db.get_value("Batch AMB", self.batch_amb_reference, "custom_batch_level")
            if batch_level != "1":
                frappe.throw("SPC Batch Record can only be created for Level 1 batches")
    
    def validate_required_fields(self):
        """Validate required fields"""
        required_fields = [
            'batch_number', 'product_code', 'plant', 'production_date', 
            'batch_size', 'production_supervisor', 'quality_inspector',
            'raw_materials_used', 'equipment_used', 'batch_status'
        ]
        
        for field in required_fields:
            if not self.get(field):
                frappe.throw(f"Field '{self.meta.get_label(field)}' is required")
    
    def calculate_overall_status(self):
        """Calculate overall status based on parameters"""
        if not self.parameters_tested:
            self.specifications_met = False
            return
            
        # Check if all parameters passed
        all_passed = all(
            param.pass_fail == "Pass" 
            for param in self.parameters_tested 
            if param.pass_fail in ["Pass", "Fail", "Investigate"]
        )
        
        self.specifications_met = all_passed
        
        # Update batch status based on parameters
        if not all_passed and self.batch_status in ["Complete", "Approved"]:
            self.batch_status = "Hold"
    
    def update_batch_amb_status(self):
        """Update related Batch AMB status"""
        if self.batch_amb_reference:
            try:
                batch_amb = frappe.get_doc("Batch AMB", self.batch_amb_reference)
                
                # Map SPC status to Batch AMB workflow state
                status_mapping = {
                    "Approved": "Quality Approved",
                    "Released": "Quality Approved", 
                    "Rejected": "Rejected",
                    "Hold": "SPC Hold",
                    "Complete": "Pending QC Review"
                }
                
                if self.batch_status in status_mapping:
                    new_state = status_mapping[self.batch_status]
                    if batch_amb.workflow_state != new_state:
                        batch_amb.db_set("workflow_state", new_state)
                        
                        # Add to processing history
                        from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import BatchAMBIntegration
                        BatchAMBIntegration.create_batch_processing_history(
                            batch_amb, 
                            f"SPC Status Update: {self.batch_status}",
                            f"Batch status updated via SPC Record {self.name}"
                        )
                
            except Exception as e:
                frappe.log_error(f"Error updating Batch AMB status: {str(e)}")

@frappe.whitelist()
def create_spc_record_for_batch(batch_amb_name):
    """Create SPC Batch Record for a Batch AMB"""
    batch_amb = frappe.get_doc("Batch AMB", batch_amb_name)
    
    if batch_amb.custom_batch_level != "1":
        frappe.throw("SPC Batch Record can only be created for Level 1 batches")
    
    if batch_amb.spc_batch_record:
        frappe.throw("SPC Batch Record already exists for this batch")
    
    spc_record = frappe.new_doc("SPC Batch Record")
    spc_record.update({
        "batch_amb_reference": batch_amb_name,
        "batch_number": batch_amb.name,
        "product_code": batch_amb.item_to_manufacture,
        "plant": batch_amb.production_plant_name,
        "production_date": batch_amb.manufacturing_date or nowdate(),
        "batch_size": batch_amb.batch_qty or 0,
        "expiry_date": batch_amb.expiry_date,
        "batch_status": "In Process"
    })
    
    spc_record.insert()
    
    # Link back to Batch AMB
    batch_amb.db_set("spc_batch_record", spc_record.name)
    
    frappe.msgprint(f"SPC Batch Record {spc_record.name} created successfully")
    return spc_record.name
