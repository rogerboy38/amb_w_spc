"""
Compatibility layer for Frappe v15-v16 compatibility
"""
import frappe
from datetime import datetime, timedelta

# For Frappe v15 compatibility - add functions that were removed in v16
def add_minutes(timestamp, minutes):
    """
    Compatibility function for Frappe v15
    In v16, this was removed and replaced with frappe.utils.add_to_date
    """
    if isinstance(timestamp, str):
        timestamp = frappe.utils.get_datetime(timestamp)
    return timestamp + timedelta(minutes=minutes)

def add_to_date(date, days=0, hours=0, minutes=0, seconds=0):
    """
    Compatibility function that works in both v15 and v16
    """
    if isinstance(date, str):
        date = frappe.utils.get_datetime(date)
    return date + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

# Make these functions available in frappe.utils
def patch_frappe_utils():
    """Patch frappe.utils with missing v16 functions"""
    if not hasattr(frappe.utils, 'add_minutes'):
        frappe.utils.add_minutes = add_minutes
    if not hasattr(frappe.utils, 'add_to_date'):
        frappe.utils.add_to_date = add_to_date
    
    print("✅ Applied Frappe v15-v16 compatibility patch")

# Apply the patch when this module is imported
patch_frappe_utils()
