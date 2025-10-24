import frappe
from frappe.model.document import Document

class RealTimeProcessData(Document):
    def before_save(self):
        # Auto-set timestamp if empty
        if not self.timestamp:
            self.timestamp = frappe.utils.now_datetime()
            
        # Auto-assess quality status based on parameter limits
        if self.parameter and self.data_value:
            self.assess_quality_status()
            
    def assess_quality_status(self):
        try:
            param = frappe.get_doc("SPC Parameter Master", self.parameter)
            value = self.data_value
            
            if param.upper_spec_limit and param.lower_spec_limit:
                spec_range = param.upper_spec_limit - param.lower_spec_limit
                warning_margin = spec_range * 0.1  # 10% margin for warning
                
                if value > param.upper_spec_limit or value < param.lower_spec_limit:
                    self.quality_status = "Critical"
                elif (value > param.upper_spec_limit - warning_margin or 
                      value < param.lower_spec_limit + warning_margin):
                    self.quality_status = "Warning"
                else:
                    self.quality_status = "Normal"
        except Exception:
            # If assessment fails, set to normal
            self.quality_status = "Normal"
