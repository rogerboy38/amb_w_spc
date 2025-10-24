import frappe
from frappe.model.document import Document

class SPCParameterSpecification(Document):
    def before_save(self):
        # Auto-populate parameter_name if parameter is provided
        if self.parameter and not self.parameter_name:
            param_name = frappe.get_value("SPC Parameter Master", self.parameter, "parameter_name")
            if param_name:
                self.parameter_name = param_name
