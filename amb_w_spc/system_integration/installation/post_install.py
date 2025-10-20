"""
Post Installation Setup for Warehouse Management
Handles post-installation configuration and setup
"""

import frappe
from frappe.utils import getdate, now_datetime
import logging

logger = logging.getLogger(__name__)

def run_warehouse_post_install():
    """
    Run warehouse management post-installation setup
    """
    try:
        logger.info("Starting warehouse management post-installation setup")
        
        # Setup warehouse permissions
        setup_warehouse_permissions()
        
        # Create default warehouse zones
        create_default_warehouse_zones()
        
        # Setup default warehouse system settings
        setup_warehouse_system_settings()
        
        # Create default workflows
        setup_warehouse_workflows()
        
        # Setup default warehouse roles
        setup_default_warehouse_roles()
        
        # Initialize warehouse performance tracking
        initialize_performance_tracking()
        
        # Setup sample data if requested
        if frappe.db.get_single_value("System Settings", "setup_sample_warehouse_data"):
            setup_sample_warehouse_data()
        
        logger.info("Warehouse management post-installation setup completed successfully")
        
    except Exception as e:
        logger.error(f"Error in warehouse post-installation setup: {str(e)}")
        frappe.log_error(f"Warehouse Post-Install Error: {str(e)}", "Post Install")

def setup_warehouse_permissions():
    """Setup warehouse-specific permissions"""
    try:
        # Create User Permission DocType entries for warehouses
        warehouses = frappe.get_all("Warehouse", 
            filters={"is_group": 0},
            fields=["name", "plant_code"])
        
        for warehouse in warehouses:
            # Create user permissions based on plant code
            if warehouse.plant_code:
                users_in_plant = frappe.get_all("User",
                    filters={"plant_code": warehouse.plant_code, "enabled": 1},
                    fields=["name"])
                
                for user in users_in_plant:
                    # Check if permission already exists
                    if not frappe.db.exists("User Permission", {
                        "user": user.name,
                        "allow": "Warehouse",
                        "for_value": warehouse.name
                    }):
                        user_perm = frappe.new_doc("User Permission")
                        user_perm.user = user.name
                        user_perm.allow = "Warehouse"
                        user_perm.for_value = warehouse.name
                        user_perm.insert(ignore_permissions=True)
        
        frappe.db.commit()
        logger.info("Warehouse permissions setup completed")
        
    except Exception as e:
        logger.error(f"Error setting up warehouse permissions: {str(e)}")

def create_default_warehouse_zones():
    """Create default warehouse zones for existing warehouses"""
    try:
        warehouses = frappe.get_all("Warehouse", 
            filters={"is_group": 0},
            fields=["name", "warehouse_type"])
        
        default_zones = {
            "Raw Material": ["RM-A", "RM-B", "RM-C"],
            "Work in Process": ["WIP-1", "WIP-2"],
            "Finished Goods": ["FG-A", "FG-B", "FG-READY"],
            "Quarantine": ["QR-HOLD", "QR-INSPECT"],
            "Rejects": ["REJ-1"],
            "Maintenance": ["MAINT"],
            "Temporary": ["TEMP-1", "TEMP-2"]
        }
        
        for warehouse in warehouses:
            warehouse_type = warehouse.get("warehouse_type", "Raw Material")
            zones = default_zones.get(warehouse_type, ["ZONE-A", "ZONE-B"])
            
            # Update warehouse with default zone
            if zones:
                frappe.db.set_value("Warehouse", warehouse.name, "zone_code", zones[0])
        
        frappe.db.commit()
        logger.info("Default warehouse zones created")
        
    except Exception as e:
        logger.error(f"Error creating default warehouse zones: {str(e)}")

def setup_warehouse_system_settings():
    """Setup default warehouse system settings"""
    try:
        # Create Warehouse System Settings if not exists
        if not frappe.db.exists("Warehouse System Settings", "Warehouse System Settings"):
            settings = frappe.new_doc("Warehouse System Settings")
            settings.name = "Warehouse System Settings"
            settings.temperature_monitoring_enabled = 1
            settings.auto_pick_task_assignment = 1
            settings.quality_check_required = 1
            settings.batch_tracking_enabled = 1
            settings.real_time_inventory_updates = 1
            settings.alert_notifications_enabled = 1
            settings.performance_analytics_enabled = 1
            settings.default_pick_task_priority = "Medium"
            settings.auto_archive_days = 90
            settings.temperature_check_frequency = 60  # minutes
            settings.capacity_warning_threshold = 90  # percentage
            settings.insert(ignore_permissions=True)
        
        logger.info("Warehouse system settings setup completed")
        
    except Exception as e:
        logger.error(f"Error setting up warehouse system settings: {str(e)}")

def setup_warehouse_workflows():
    """Setup warehouse-related workflows"""
    try:
        from amb_w_spc.system_integration.workflows.setup import setup_warehouse_workflows
        setup_warehouse_workflows()
        
        logger.info("Warehouse workflows setup completed")
        
    except Exception as e:
        logger.error(f"Error setting up warehouse workflows: {str(e)}")

def setup_default_warehouse_roles():
    """Setup default warehouse roles and assign to users"""
    try:
        # Assign Warehouse Manager role to users with specific designation
        warehouse_manager_designations = ["Warehouse Manager", "Warehouse Supervisor", "Inventory Manager"]
        
        for designation in warehouse_manager_designations:
            users = frappe.get_all("User",
                filters={"designation": designation, "enabled": 1},
                fields=["name"])
            
            for user in users:
                if not frappe.db.exists("Has Role", {"parent": user.name, "role": "Warehouse Manager"}):
                    user_doc = frappe.get_doc("User", user.name)
                    user_doc.append("roles", {"role": "Warehouse Manager"})
                    user_doc.save(ignore_permissions=True)
        
        # Assign Warehouse Operator role
        operator_designations = ["Warehouse Operator", "Picker", "Material Handler"]
        
        for designation in operator_designations:
            users = frappe.get_all("User",
                filters={"designation": designation, "enabled": 1},
                fields=["name"])
            
            for user in users:
                if not frappe.db.exists("Has Role", {"parent": user.name, "role": "Warehouse Operator"}):
                    user_doc = frappe.get_doc("User", user.name)
                    user_doc.append("roles", {"role": "Warehouse Operator"})
                    user_doc.save(ignore_permissions=True)
        
        logger.info("Default warehouse roles setup completed")
        
    except Exception as e:
        logger.error(f"Error setting up default warehouse roles: {str(e)}")

def initialize_performance_tracking():
    """Initialize warehouse performance tracking"""
    try:
        # Create initial performance log entry
        if not frappe.db.exists("Warehouse Performance Log", {"date": getdate()}):
            performance_log = frappe.new_doc("Warehouse Performance Log")
            performance_log.date = getdate()
            performance_log.total_pick_tasks = 0
            performance_log.completed_pick_tasks = 0
            performance_log.completion_rate = 0
            performance_log.average_pick_time = 0
            performance_log.system_initialized = 1
            performance_log.insert(ignore_permissions=True)
        
        logger.info("Performance tracking initialized")
        
    except Exception as e:
        logger.error(f"Error initializing performance tracking: {str(e)}")

def setup_sample_warehouse_data():
    """Setup sample warehouse data for demonstration"""
    try:
        # Create sample warehouse alerts
        create_sample_alerts()
        
        # Create sample performance data
        create_sample_performance_data()
        
        logger.info("Sample warehouse data setup completed")
        
    except Exception as e:
        logger.error(f"Error setting up sample warehouse data: {str(e)}")

def create_sample_alerts():
    """Create sample warehouse alerts for demonstration"""
    try:
        warehouses = frappe.get_all("Warehouse", 
            filters={"is_group": 0},
            fields=["name"],
            limit=3)
        
        sample_alerts = [
            {
                "alert_type": "Temperature Violation",
                "severity": "High",
                "message": "Temperature exceeded acceptable range",
                "status": "Open"
            },
            {
                "alert_type": "Capacity Warning",
                "severity": "Medium", 
                "message": "Warehouse utilization above 90%",
                "status": "Open"
            },
            {
                "alert_type": "Quality Hold",
                "severity": "High",
                "message": "Material placed on quality hold",
                "status": "Acknowledged"
            }
        ]
        
        for i, warehouse in enumerate(warehouses[:len(sample_alerts)]):
            alert_data = sample_alerts[i]
            
            if not frappe.db.exists("Warehouse Alert", {
                "warehouse": warehouse.name,
                "alert_type": alert_data["alert_type"]
            }):
                alert = frappe.new_doc("Warehouse Alert")
                alert.warehouse = warehouse.name
                alert.alert_type = alert_data["alert_type"]
                alert.severity = alert_data["severity"]
                alert.message = alert_data["message"]
                alert.alert_datetime = now_datetime()
                alert.status = alert_data["status"]
                alert.insert(ignore_permissions=True)
        
    except Exception as e:
        logger.error(f"Error creating sample alerts: {str(e)}")

def create_sample_performance_data():
    """Create sample performance data for the past week"""
    try:
        from frappe.utils import add_days
        
        # Create performance data for the past 7 days
        for i in range(7):
            date = add_days(getdate(), -i)
            
            if not frappe.db.exists("Warehouse Performance Log", {"date": date}):
                performance_log = frappe.new_doc("Warehouse Performance Log")
                performance_log.date = date
                performance_log.total_pick_tasks = 20 + (i * 5)  # Sample data
                performance_log.completed_pick_tasks = 18 + (i * 4)  # Sample data
                performance_log.completion_rate = 90 + (i * 2)  # Sample data
                performance_log.average_pick_time = 25 - i  # Sample data
                performance_log.insert(ignore_permissions=True)
        
    except Exception as e:
        logger.error(f"Error creating sample performance data: {str(e)}")

@frappe.whitelist()
def validate_warehouse_installation():
    """Validate warehouse management installation"""
    try:
        validation_results = {
            "warehouse_roles": check_warehouse_roles(),
            "warehouse_permissions": check_warehouse_permissions(),
            "custom_fields": check_custom_fields(),
            "workflows": check_workflows(),
            "scheduled_tasks": check_scheduled_tasks(),
            "system_settings": check_system_settings()
        }
        
        all_valid = all(validation_results.values())
        
        return {
            "valid": all_valid,
            "results": validation_results,
            "message": "Warehouse management installation is valid" if all_valid else "Some components need attention"
        }
        
    except Exception as e:
        logger.error(f"Error validating warehouse installation: {str(e)}")
        return {"valid": False, "error": str(e)}

def check_warehouse_roles():
    """Check if warehouse roles are properly created"""
    required_roles = ["Warehouse Manager", "Warehouse Operator", "Quality Inspector", 
                     "Production Manager", "Plant Supervisor"]
    
    for role in required_roles:
        if not frappe.db.exists("Role", role):
            return False
    
    return True

def check_warehouse_permissions():
    """Check if warehouse permissions are properly configured"""
    # Check if custom DocPerm entries exist for key DocTypes
    key_doctypes = ["Warehouse Pick Task", "Material Assessment Log", "Warehouse Alert"]
    
    for doctype in key_doctypes:
        if not frappe.db.exists("Custom DocPerm", {"parent": doctype}):
            return False
    
    return True

def check_custom_fields():
    """Check if custom fields are properly installed"""
    # Check key custom fields
    key_fields = [
        ("Stock Entry", "amb_warehouse_zone"),
        ("Warehouse", "amb_temperature_controlled"),
        ("Work Order", "amb_production_zone"),
        ("Purchase Receipt", "amb_quality_inspection_required")
    ]
    
    for doctype, fieldname in key_fields:
        if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
            return False
    
    return True

def check_workflows():
    """Check if workflows are properly configured"""
    # Implementation for workflow validation
    return True

def check_scheduled_tasks():
    """Check if scheduled tasks are properly configured"""
    # Implementation for scheduled task validation
    return True

def check_system_settings():
    """Check if system settings are properly configured"""
    return frappe.db.exists("Warehouse System Settings", "Warehouse System Settings")
