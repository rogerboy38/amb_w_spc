import frappe
from frappe.model.document import Document

class BatchProcessingHistory(Document):
    def before_save(self):
        """Custom validation for Batch Processing History"""
        self.validate_limits()
    
    def validate_limits(self):
        """Validate parameter limits if applicable"""
        if hasattr(self, 'actual_value') and hasattr(self, 'upper_limit') and hasattr(self, 'lower_limit'):
            if self.actual_value and self.upper_limit and self.lower_limit:
                if self.actual_value > self.upper_limit or self.actual_value < self.lower_limit:
                    frappe.msgprint(
                        f'Value {self.actual_value} is outside control limits ({self.lower_limit} - {self.upper_limit})',
                        alert=True
                    )
