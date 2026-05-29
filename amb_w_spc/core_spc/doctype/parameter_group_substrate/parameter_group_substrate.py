import frappe
from frappe.model.document import Document


class ParameterGroupSubstrate(Document):
    """Parameter Group Substrate (child table)

    Wraps a Link → Substrate for Table MultiSelect usage on
    Quality Inspection Parameter Group.applicable_substrates (M3.5 picker
    substrate filter; Task #32 / Task #43 baseline; Task #65 PWD expansion;
    Task #67 ship to git).
    """
    pass
