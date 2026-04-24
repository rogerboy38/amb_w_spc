"""
V13.6.0 P3 Migration: Create Sample Request from Lead
Original Server Script: Create Sample Request from Lead
Type: Whitelisted API
"""

import frappe
from frappe.utils import today


import frappe
from frappe.utils import today

@frappe.whitelist()
def create_sample_request_from_lead(lead_name):
    lead = frappe.get_doc("Lead", lead_name)
    
    sr = frappe.get_doc({
        "doctype": "Sample Request AMB",
        "party_type": "Lead",
        "party": lead_name,
        "request_date": today(),
        "samples": [
            {
                "doctype": "Sample Request AMB Item",
                "item": "0307"
            }
        ]
    })
    sr.insert(ignore_permissions=True)
    frappe.db.commit()
    
    return sr.name
    
