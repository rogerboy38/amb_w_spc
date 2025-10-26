"""
System Integration Boot
"""

import frappe

def get_warehouse_boot_session(bootinfo=None):
    """
    Get warehouse data for boot session
    This function is called by Frappe's boot process and receives bootinfo as argument
    """
    try:
        warehouse_data = {
            'warehouse_permissions': {
                'can_view_warehouse': 'Warehouse User' in frappe.get_roles() or 'System Manager' in frappe.get_roles(),
                'can_manage_pick_tasks': 'Warehouse Manager' in frappe.get_roles() or 'System Manager' in frappe.get_roles(),
                'can_manage_assessments': 'Quality Manager' in frappe.get_roles() or 'System Manager' in frappe.get_roles()
            },
            'warehouse_stats': {
                'total_warehouses': frappe.db.count('Warehouse'),
                'active_pick_tasks': frappe.db.count('Warehouse Pick Task', {'status': 'Active'}) if frappe.db.exists('DocType', 'Warehouse Pick Task') else 0,
                'pending_assessments': frappe.db.count('Material Assessment Log', {'status': 'Pending'}) if frappe.db.exists('DocType', 'Material Assessment Log') else 0
            }
        }
        
        # If bootinfo is provided (as it should be), add our data to it
        if bootinfo and isinstance(bootinfo, dict):
            bootinfo['amb_w_spc'] = warehouse_data
            return bootinfo
        else:
            # Fallback: return just our data
            return warehouse_data
            
    except Exception as e:
        # Log error but don't break the boot process
        frappe.log_error(f"Error in get_warehouse_boot_session: {str(e)}")
        
        if bootinfo and isinstance(bootinfo, dict):
            bootinfo['amb_w_spc'] = {'error': str(e)}
            return bootinfo
        else:
            return {'error': str(e)}
