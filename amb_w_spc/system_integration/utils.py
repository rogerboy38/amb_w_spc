"""
System Integration Utilities
"""

import frappe

def get_user_warehouse_permissions(user=None):
    """
    Get user warehouse permissions for Jinja templates
    """
    if not user:
        user = frappe.session.user
    
    user_roles = frappe.get_roles(user)
    
    return {
        'can_view_warehouse': 'Wareprise User' in user_roles or 'System Manager' in user_roles,
        'can_manage_pick_tasks': 'Warehouse Manager' in user_roles or 'System Manager' in user_roles,
        'can_manage_assessments': 'Quality Manager' in user_roles or 'System Manager' in user_roles,
        'can_view_reports': 'Warehouse User' in user_roles or 'System Manager' in user_roles,
        'is_warehouse_manager': 'Warehouse Manager' in user_roles or 'System Manager' in user_roles
    }
