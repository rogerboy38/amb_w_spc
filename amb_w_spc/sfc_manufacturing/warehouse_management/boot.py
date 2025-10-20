"""
Boot Session Module for Warehouse Management
Provides initial data and permissions for warehouse dashboard
"""

import frappe
from frappe.utils import getdate, now_datetime

@frappe.whitelist()
def get_warehouse_boot_session():
    """
    Get warehouse management boot session data
    Returns initial data for warehouse dashboard and user permissions
    """
    try:
        user = frappe.session.user
        
        # Get user warehouse permissions
        user_warehouses = get_user_warehouse_permissions(user)
        
        # Get warehouse dashboard data
        dashboard_data = get_warehouse_dashboard_data(user_warehouses)
        
        # Get user role-based configurations
        user_config = get_user_warehouse_config(user)
        
        boot_data = {
            "warehouse_management": {
                "user_warehouses": user_warehouses,
                "dashboard_data": dashboard_data,
                "user_config": user_config,
                "system_settings": get_warehouse_system_settings()
            }
        }
        
        return boot_data
        
    except Exception as e:
        frappe.log_error(f"Error in warehouse boot session: {str(e)}", "Warehouse Boot Session")
        return {}

def get_user_warehouse_permissions(user):
    """Get warehouses accessible to the current user"""
    try:
        # Check if user has system manager role (access to all warehouses)
        if "System Manager" in frappe.get_roles(user):
            warehouses = frappe.get_all("Warehouse", 
                filters={"is_group": 0},
                fields=["name", "warehouse_name", "warehouse_type", "plant_code"])
            return warehouses
        
        # Get user-specific warehouse permissions
        user_doc = frappe.get_doc("User", user)
        user_plant_code = getattr(user_doc, "plant_code", None)
        
        filters = {"is_group": 0}
        if user_plant_code:
            filters["plant_code"] = user_plant_code
        
        warehouses = frappe.get_all("Warehouse", 
            filters=filters,
            fields=["name", "warehouse_name", "warehouse_type", "plant_code"])
        
        return warehouses
        
    except Exception as e:
        frappe.log_error(f"Error getting user warehouse permissions: {str(e)}", "Warehouse Permissions")
        return []

def get_warehouse_dashboard_data(user_warehouses):
    """Get dashboard data for user's accessible warehouses"""
    try:
        if not user_warehouses:
            return {}
        
        warehouse_names = [w.name for w in user_warehouses]
        
        # Get pending pick tasks
        pending_tasks = frappe.db.count("Warehouse Pick Task", {
            "warehouse": ["in", warehouse_names],
            "status": ["in", ["Pending", "In Progress"]]
        })
        
        # Get today's completed tasks
        completed_today = frappe.db.count("Warehouse Pick Task", {
            "warehouse": ["in", warehouse_names],
            "status": "Completed",
            "completion_date": getdate()
        })
        
        # Get critical alerts
        critical_alerts = frappe.db.count("Warehouse Alert", {
            "warehouse": ["in", warehouse_names],
            "severity": "High",
            "status": "Open"
        })
        
        # Get warehouse utilization summary
        utilization_data = get_warehouse_utilization_summary(warehouse_names)
        
        return {
            "pending_pick_tasks": pending_tasks,
            "completed_tasks_today": completed_today,
            "critical_alerts": critical_alerts,
            "warehouse_utilization": utilization_data,
            "last_updated": now_datetime()
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting warehouse dashboard data: {str(e)}", "Warehouse Dashboard")
        return {}

def get_warehouse_utilization_summary(warehouse_names):
    """Get warehouse utilization summary"""
    try:
        utilization_data = []
        
        for warehouse_name in warehouse_names:
            warehouse_doc = frappe.get_doc("Warehouse", warehouse_name)
            
            capacity = getattr(warehouse_doc, "warehouse_capacity", 0)
            current_utilization = getattr(warehouse_doc, "current_utilization", 0)
            
            if capacity > 0:
                utilization_percentage = (current_utilization / capacity) * 100
            else:
                utilization_percentage = 0
            
            utilization_data.append({
                "warehouse": warehouse_name,
                "capacity": capacity,
                "current_utilization": current_utilization,
                "utilization_percentage": utilization_percentage
            })
        
        return utilization_data
        
    except Exception as e:
        frappe.log_error(f"Error getting warehouse utilization: {str(e)}", "Warehouse Utilization")
        return []

def get_user_warehouse_config(user):
    """Get user-specific warehouse configuration"""
    try:
        user_roles = frappe.get_roles(user)
        
        config = {
            "can_create_pick_tasks": False,
            "can_manage_warehouses": False,
            "can_view_analytics": False,
            "can_manage_zones": False,
            "can_perform_quality_checks": False,
            "default_warehouse": None,
            "preferred_dashboard_view": "summary"
        }
        
        # Configure based on user roles
        if "Warehouse Manager" in user_roles:
            config.update({
                "can_create_pick_tasks": True,
                "can_manage_warehouses": True,
                "can_view_analytics": True,
                "can_manage_zones": True,
                "preferred_dashboard_view": "detailed"
            })
        
        elif "Warehouse Operator" in user_roles:
            config.update({
                "can_create_pick_tasks": False,
                "can_manage_warehouses": False,
                "can_view_analytics": False,
                "can_manage_zones": False,
                "preferred_dashboard_view": "tasks"
            })
        
        elif "Quality Inspector" in user_roles:
            config.update({
                "can_perform_quality_checks": True,
                "preferred_dashboard_view": "quality"
            })
        
        elif "Production Manager" in user_roles:
            config.update({
                "can_view_analytics": True,
                "preferred_dashboard_view": "production"
            })
        
        # Get user's default warehouse if set
        user_doc = frappe.get_doc("User", user)
        config["default_warehouse"] = getattr(user_doc, "default_warehouse", None)
        
        return config
        
    except Exception as e:
        frappe.log_error(f"Error getting user warehouse config: {str(e)}", "User Config")
        return {}

def get_warehouse_system_settings():
    """Get system-wide warehouse settings"""
    try:
        settings = {
            "temperature_monitoring_enabled": True,
            "auto_pick_task_assignment": True,
            "quality_check_required": True,
            "batch_tracking_enabled": True,
            "real_time_inventory_updates": True,
            "alert_notifications_enabled": True,
            "performance_analytics_enabled": True
        }
        
        # Get actual system settings if they exist
        if frappe.db.exists("Warehouse System Settings", "Warehouse System Settings"):
            system_settings_doc = frappe.get_doc("Warehouse System Settings", "Warehouse System Settings")
            
            for key in settings.keys():
                if hasattr(system_settings_doc, key):
                    settings[key] = getattr(system_settings_doc, key)
        
        return settings
        
    except Exception as e:
        frappe.log_error(f"Error getting warehouse system settings: {str(e)}", "System Settings")
        return {}

@frappe.whitelist()
def update_warehouse_dashboard_cache():
    """Update warehouse dashboard cache data"""
    try:
        users_with_warehouse_access = frappe.get_all("User",
            filters={
                "enabled": 1,
                "role_profile_name": ["in", ["Warehouse Manager", "Warehouse Operator", "Production Manager"]]
            },
            fields=["name"])
        
        for user in users_with_warehouse_access:
            # Update cache for each user
            user_warehouses = get_user_warehouse_permissions(user.name)
            dashboard_data = get_warehouse_dashboard_data(user_warehouses)
            
            # Store in cache
            cache_key = f"warehouse_dashboard_{user.name}"
            frappe.cache().set_value(cache_key, dashboard_data, expires_in_sec=300)  # 5 minutes cache
        
        return True
        
    except Exception as e:
        frappe.log_error(f"Error updating warehouse dashboard cache: {str(e)}", "Dashboard Cache")
        return False

@frappe.whitelist()
def get_cached_warehouse_dashboard_data():
    """Get cached warehouse dashboard data for current user"""
    try:
        user = frappe.session.user
        cache_key = f"warehouse_dashboard_{user}"
        
        cached_data = frappe.cache().get_value(cache_key)
        
        if cached_data:
            return cached_data
        
        # If no cache, generate fresh data
        user_warehouses = get_user_warehouse_permissions(user)
        dashboard_data = get_warehouse_dashboard_data(user_warehouses)
        
        # Store in cache
        frappe.cache().set_value(cache_key, dashboard_data, expires_in_sec=300)
        
        return dashboard_data
        
    except Exception as e:
        frappe.log_error(f"Error getting cached warehouse dashboard data: {str(e)}", "Cached Dashboard")
        return {}
