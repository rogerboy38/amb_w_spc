"""
Warehouse Management Boot
"""

import frappe

def get_warehouse_boot_session(bootinfo=None):
    """
    Get warehouse boot session data
    This function is called by Frappe's boot process
    """
    try:
        warehouse_data = {
            'warehouse_ready': frappe.db.exists('DocType', 'Warehouse'),
            'pick_tasks_ready': frappe.db.exists('DocType', 'Warehouse Pick Task'),
            'zones_ready': frappe.db.exists('DocType', 'Warehouse Zone')
        }
        
        # Add to bootinfo if provided
        if bootinfo and isinstance(bootinfo, dict):
            if 'amb_w_spc' not in bootinfo:
                bootinfo['amb_w_spc'] = {}
            bootinfo['amb_w_spc']['warehouse'] = warehouse_data
            return bootinfo
        else:
            return warehouse_data
            
    except Exception as e:
        frappe.log_error(f"Error in warehouse boot session: {str(e)}")
        
        if bootinfo and isinstance(bootinfo, dict):
            if 'amb_w_spc' not in bootinfo:
                bootinfo['amb_w_spc'] = {}
            bootinfo['amb_w_spc']['warehouse'] = {'error': str(e)}
            return bootinfo
        else:
            return {'error': str(e)}
