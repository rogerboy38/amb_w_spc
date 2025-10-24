import frappe
from frappe.model.document import Document

class SPCProcessCapability(Document):
    def validate(self):
        # Auto-set completion date when study is completed
        if self.study_status == "Completed" and not self.completion_date:
            self.completion_date = frappe.utils.nowdate()
            
        # Calculate Cp and Cpk if we have data points (simplified)
        if self.data_points and len(self.data_points) > 0:
            self.calculate_capability_indices()
            
    def calculate_capability_indices(self):
        # This is a simplified calculation
        # In a real system, you would use proper statistical formulas
        data_values = [dp.data_value for dp in self.data_points if dp.data_value]
        if len(data_values) > 1:
            # Simplified calculation for demonstration
            self.cp_value = 1.5  # Example value
            self.cpk_value = 1.3  # Example value
