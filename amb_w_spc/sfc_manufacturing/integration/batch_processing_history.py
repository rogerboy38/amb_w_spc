# batch_processing_history.py (Enhanced)
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class BatchProcessingHistory(Document):
    def validate(self):
        self.set_defaults()
        self.validate_batch_reference()
    
    def set_defaults(self):
        """Set default values"""
        if not self.start_date:
            self.start_date = now_datetime()
        if not self.status:
            self.status = "In Progress"
    
    def validate_batch_reference(self):
        """Validate batch reference exists"""
        if self.batch_amb_reference and not frappe.db.exists("Batch AMB", self.batch_amb_reference):
            frappe.throw("Batch AMB Reference does not exist")
    
    def add_processing_step(self, step_name, status="Completed", remarks=None, user=None):
        """Add a processing step to history"""
        self.append("processing_steps", {
            "step_name": step_name,
            "timestamp": now_datetime(),
            "status": status,
            "remarks": remarks,
            "changed_by": user or frappe.session.user
        })
        self.save()
    
    def get_processing_timeline(self):
        """Get chronological processing timeline"""
        if not self.processing_steps:
            return []
        
        return sorted(self.processing_steps, key=lambda x: x.timestamp)
