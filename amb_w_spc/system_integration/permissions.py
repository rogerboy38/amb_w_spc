"""
Warehouse Management Permissions System
Handles user permissions and access control for warehouse operations
"""

import frappe
from frappe.utils import getdate, now_datetime
import logging

logger = logging.getLogger(__name__)

@frappe.whitelist()
def setup_user_warehouse_context():
    """
    Setup warehouse context for user sessions
    Called during session creation
    """
    try:
        user = frappe.session.user
        
        if user == "Administrator" or user == "Guest":
            return
        
        # Get user's warehouse permissions
        user_warehouses = get_user_warehouse_context(user)
        
        # Store in session
        frappe.local.session_obj.data.warehouse_context = user_warehouses
        
        # Setup user-specific defaults
        setup_user_warehouse_defaults(user, user_warehouses)
        
    except Exception as e:
        logger.error(f"Error setting up user warehouse context: {str(e)}")

def get_user_warehouse_context(user):
    """Get warehouse context for a specific user"""
    try:
        user_doc = frappe.get_doc("User", user)
        user_roles = frappe.get_roles(user)
        
        # System Manager has access to all warehouses
        if "System Manager" in user_roles:
            warehouses = frappe.get_all("Warehouse",
                filters={"is_group": 0},
                fields=["name", "warehouse_name", "plant_code", "warehouse_type"])
            
            return {
                "warehouses": warehouses,
                "plant_code": None,
                "access_level": "all",
                "roles": user_roles
            }
        
        # Get user's plant code
        user_plant_code = getattr(user_doc, "plant_code", None)
        
        # Get warehouses based on plant code
        filters = {"is_group": 0}
        if user_plant_code:
            filters["plant_code"] = user_plant_code
        
        warehouses = frappe.get_all("Warehouse",
            filters=filters,
            fields=["name", "warehouse_name", "plant_code", "warehouse_type"])
        
        # Determine access level based on roles
        access_level = "restricted"
        if "Warehouse Manager" in user_roles:
            access_level = "manager"
        elif "Production Manager" in user_roles:
            access_level = "production"
        elif "Plant Supervisor" in user_roles:
            access_level = "supervisor"
        elif "Warehouse Operator" in user_roles:
            access_level = "operator"
        elif "Quality Inspector" in user_roles:
            access_level = "quality"
        
        return {
            "warehouses": warehouses,
            "plant_code": user_plant_code,
            "access_level": access_level,
            "roles": user_roles
        }
        
    except Exception as e:
        logger.error(f"Error getting user warehouse context: {str(e)}")
        return {"warehouses": [], "plant_code": None, "access_level": "none", "roles": []}

def setup_user_warehouse_defaults(user, warehouse_context):
    """Setup user-specific warehouse defaults"""
    try:
        if not warehouse_context.get("warehouses"):
            return
        
        user_doc = frappe.get_doc("User", user)
        
        # Set default warehouse if not already set
        if not getattr(user_doc, "default_warehouse", None) and warehouse_context["warehouses"]:
            # Use first warehouse as default
            default_warehouse = warehouse_context["warehouses"][0]["name"]
            frappe.db.set_value("User", user, "default_warehouse", default_warehouse)
        
        # Setup user permissions for warehouses
        setup_user_warehouse_permissions(user, warehouse_context)
        
    except Exception as e:
        logger.error(f"Error setting up user warehouse defaults: {str(e)}")

def setup_user_warehouse_permissions(user, warehouse_context):
    """Setup user permissions for warehouses"""
    try:
        warehouses = warehouse_context.get("warehouses", [])
        
        for warehouse in warehouses:
            # Check if permission already exists
            if not frappe.db.exists("User Permission", {
                "user": user,
                "allow": "Warehouse",
                "for_value": warehouse["name"]
            }):
                # Create user permission
                user_perm = frappe.new_doc("User Permission")
                user_perm.user = user
                user_perm.allow = "Warehouse"
                user_perm.for_value = warehouse["name"]
                user_perm.insert(ignore_permissions=True)
        
    except Exception as e:
        logger.error(f"Error setting up user warehouse permissions: {str(e)}")

@frappe.whitelist()
def get_user_warehouse_permissions(user=None):
    """Get warehouse permissions for a user"""
    try:
        if not user:
            user = frappe.session.user
        
        # Get from session cache if available
        if hasattr(frappe.local, "session_obj") and frappe.local.session_obj.data.get("warehouse_context"):
            return frappe.local.session_obj.data.warehouse_context
        
        # Generate fresh context
        return get_user_warehouse_context(user)
        
    except Exception as e:
        logger.error(f"Error getting user warehouse permissions: {str(e)}")
        return {"warehouses": [], "plant_code": None, "access_level": "none", "roles": []}

@frappe.whitelist()
def check_warehouse_access(user, warehouse, operation="read"):
    """
    Check if user has access to perform operation on warehouse
    
    Args:
        user: User ID
        warehouse: Warehouse name
        operation: read, write, create, delete, submit, cancel
    """
    try:
        user_context = get_user_warehouse_context(user)
        
        # System Manager has all access
        if "System Manager" in user_context.get("roles", []):
            return True
        
        # Check if user has access to this warehouse
        user_warehouses = [w["name"] for w in user_context.get("warehouses", [])]
        if warehouse not in user_warehouses:
            return False
        
        # Check operation-specific permissions based on access level
        access_level = user_context.get("access_level", "none")
        
        if access_level == "manager":
            return True  # Warehouse Manager has all permissions
        
        elif access_level == "production":
            # Production Manager can read and create but not delete
            return operation in ["read", "write", "create", "submit"]
        
        elif access_level == "supervisor":
            # Plant Supervisor can read and write
            return operation in ["read", "write"]
        
        elif access_level == "operator":
            # Warehouse Operator can read and update assigned tasks
            return operation in ["read", "write"] 
        
        elif access_level == "quality":
            # Quality Inspector can read and update quality-related items
            return operation in ["read", "write", "submit"]
        
        else:
            return operation == "read"  # Default read-only access
        
    except Exception as e:
        logger.error(f"Error checking warehouse access: {str(e)}")
        return False

@frappe.whitelist()
def get_accessible_warehouses(user=None, warehouse_type=None):
    """Get list of warehouses accessible to user"""
    try:
        if not user:
            user = frappe.session.user
        
        user_context = get_user_warehouse_context(user)
        warehouses = user_context.get("warehouses", [])
        
        # Filter by warehouse type if specified
        if warehouse_type:
            warehouses = [w for w in warehouses if w.get("warehouse_type") == warehouse_type]
        
        return warehouses
        
    except Exception as e:
        logger.error(f"Error getting accessible warehouses: {str(e)}")
        return []

@frappe.whitelist()
def setup_warehouse_user_permissions(plant_code=None):
    """Setup warehouse user permissions for all users in a plant"""
    try:
        # Get users based on plant code
        filters = {"enabled": 1}
        if plant_code:
            filters["plant_code"] = plant_code
        
        users = frappe.get_all("User", filters=filters, fields=["name", "plant_code"])
        
        for user in users:
            # Skip system users
            if user.name in ["Administrator", "Guest"]:
                continue
            
            # Get user's warehouse context
            user_context = get_user_warehouse_context(user.name)
            
            # Setup permissions
            setup_user_warehouse_permissions(user.name, user_context)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Warehouse permissions setup for {len(users)} users",
            "users_processed": len(users)
        }
        
    except Exception as e:
        logger.error(f"Error setting up warehouse user permissions: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def validate_user_warehouse_permissions(user=None):
    """Validate user's warehouse permissions"""
    try:
        if not user:
            user = frappe.session.user
        
        user_context = get_user_warehouse_context(user)
        
        validation_results = {
            "user": user,
            "has_warehouse_access": len(user_context.get("warehouses", [])) > 0,
            "access_level": user_context.get("access_level", "none"),
            "plant_code": user_context.get("plant_code"),
            "warehouse_count": len(user_context.get("warehouses", [])),
            "roles": user_context.get("roles", []),
            "permissions_valid": True
        }
        
        # Check if user permissions are properly setup
        warehouses = user_context.get("warehouses", [])
        for warehouse in warehouses:
            if not frappe.db.exists("User Permission", {
                "user": user,
                "allow": "Warehouse",
                "for_value": warehouse["name"]
            }):
                validation_results["permissions_valid"] = False
                break
        
        return validation_results
        
    except Exception as e:
        logger.error(f"Error validating user warehouse permissions: {str(e)}")
        return {"user": user, "error": str(e)}

@frappe.whitelist()
def update_user_warehouse_permissions(user, warehouse_list):
    """Update user's warehouse permissions"""
    try:
        # Remove existing warehouse permissions
        existing_perms = frappe.get_all("User Permission",
            filters={"user": user, "allow": "Warehouse"},
            fields=["name"])
        
        for perm in existing_perms:
            frappe.delete_doc("User Permission", perm.name, ignore_permissions=True)
        
        # Add new permissions
        for warehouse in warehouse_list:
            if frappe.db.exists("Warehouse", warehouse):
                user_perm = frappe.new_doc("User Permission")
                user_perm.user = user
                user_perm.allow = "Warehouse"
                user_perm.for_value = warehouse
                user_perm.insert(ignore_permissions=True)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Updated warehouse permissions for {user}",
            "warehouses_added": len(warehouse_list)
        }
        
    except Exception as e:
        logger.error(f"Error updating user warehouse permissions: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_warehouse_permission_matrix():
    """Get comprehensive warehouse permission matrix"""
    try:
        # Get all warehouse-related roles
        warehouse_roles = ["Warehouse Manager", "Warehouse Operator", "Quality Inspector", 
                          "Production Manager", "Plant Supervisor"]
        
        # Get all warehouse-related DocTypes
        warehouse_doctypes = ["Warehouse Pick Task", "Material Assessment Log", "Warehouse Alert",
                             "Warehouse Performance Log", "Stock Entry", "Warehouse", "Batch AMB"]
        
        permission_matrix = {}
        
        for role in warehouse_roles:
            permission_matrix[role] = {}
            
            for doctype in warehouse_doctypes:
                # Get permissions for this role and doctype
                perms = frappe.get_all("Custom DocPerm",
                    filters={"parent": doctype, "role": role},
                    fields=["read", "write", "create", "delete", "submit", "cancel", "report"])
                
                if perms:
                    permission_matrix[role][doctype] = perms[0]
                else:
                    permission_matrix[role][doctype] = {
                        "read": 0, "write": 0, "create": 0, "delete": 0,
                        "submit": 0, "cancel": 0, "report": 0
                    }
        
        return permission_matrix
        
    except Exception as e:
        logger.error(f"Error getting warehouse permission matrix: {str(e)}")
        return {}

def has_warehouse_role(user=None):
    """Check if user has any warehouse-related role"""
    try:
        if not user:
            user = frappe.session.user
        
        warehouse_roles = ["Warehouse Manager", "Warehouse Operator", "Quality Inspector", 
                          "Production Manager", "Plant Supervisor"]
        
        user_roles = frappe.get_roles(user)
        
        return any(role in user_roles for role in warehouse_roles)
        
    except Exception as e:
        logger.error(f"Error checking warehouse role: {str(e)}")
        return False

@frappe.whitelist()
def get_user_warehouse_dashboard_config(user=None):
    """Get user-specific warehouse dashboard configuration"""
    try:
        if not user:
            user = frappe.session.user
        
        user_context = get_user_warehouse_context(user)
        access_level = user_context.get("access_level", "none")
        
        config = {
            "show_analytics": access_level in ["manager", "production", "supervisor"],
            "show_alerts": access_level in ["manager", "supervisor"],
            "show_pick_tasks": access_level in ["manager", "operator"],
            "show_quality_checks": access_level in ["manager", "quality"],
            "show_temperature_monitoring": access_level in ["manager", "supervisor"],
            "show_performance_metrics": access_level in ["manager", "production"],
            "can_create_tasks": access_level in ["manager"],
            "can_assign_tasks": access_level in ["manager"],
            "can_acknowledge_alerts": access_level in ["manager", "supervisor"],
            "default_view": get_default_dashboard_view(access_level)
        }
        
        return config
        
    except Exception as e:
        logger.error(f"Error getting user warehouse dashboard config: {str(e)}")
        return {}

def get_default_dashboard_view(access_level):
    """Get default dashboard view based on access level"""
    view_mapping = {
        "manager": "comprehensive",
        "production": "production_focused",
        "supervisor": "monitoring_focused",
        "operator": "task_focused",
        "quality": "quality_focused",
        "none": "limited"
    }
    
    return view_mapping.get(access_level, "limited")
