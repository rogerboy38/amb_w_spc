import frappe
from frappe import _
from frappe.utils import getdate, now_datetime
import json

def execute():
    """Install warehouse management functionality for AMB W SPC"""
    
    try:
        # Install custom fields
        install_custom_fields()
        
        # Install Material Assessment Log DocType
        install_material_assessment_log()
        
        # Create warehouse hierarchy if needed
        create_default_warehouses()
        
        # Setup permissions
        setup_permissions()
        
        frappe.msgprint(_("Warehouse management functionality installed successfully"))
        
    except Exception as e:
        frappe.log_error(f"Warehouse management installation failed: {str(e)}")
        print(f"Error: {str(e)}")

def install_custom_fields():
    """Install custom fields for Stock Entry, Warehouse, and Work Order"""
    
    # Stock Entry Custom Fields
    stock_entry_fields = [
        {
            "doctype": "Custom Field",
            "dt": "Stock Entry",
            "fieldname": "custom_sap_movement_type",
            "label": "SAP Movement Type",
            "fieldtype": "Select",
            "options": "\n261 (FrontFlush - Goods Issue for Production)\n311 (BackFlush - Transfer for Kitting)",
            "insert_after": "purpose",
            "in_list_view": 1,
            "in_standard_filter": 1,
            "description": "SAP-style movement type for warehouse operations"
        },
        {
            "doctype": "Custom Field",
            "dt": "Stock Entry",
            "fieldname": "custom_work_order_reference",
            "label": "Work Order Reference",
            "fieldtype": "Link",
            "options": "Work Order",
            "insert_after": "custom_sap_movement_type",
            "in_list_view": 1,
            "description": "Link to related Work Order for zone status tracking"
        },
        {
            "doctype": "Custom Field",
            "dt": "Stock Entry",
            "fieldname": "section_break_zone_status",
            "label": "Zone Status Information",
            "fieldtype": "Section Break",
            "insert_after": "custom_work_order_reference",
            "collapsible": 1
        },
        {
            "doctype": "Custom Field",
            "dt": "Stock Entry",
            "fieldname": "custom_zone_status",
            "label": "Zone Status",
            "fieldtype": "Select",
            "options": "\nRed Zone\nGreen Zone",
            "insert_after": "section_break_zone_status",
            "in_list_view": 1,
            "read_only": 1,
            "description": "Red Zone = Incomplete materials, Green Zone = Complete materials"
        }
    ]
    
    # Install Stock Entry fields
    for field_config in stock_entry_fields:
        if not frappe.db.exists("Custom Field", {"dt": field_config["dt"], "fieldname": field_config["fieldname"]}):
            try:
                custom_field = frappe.get_doc(field_config)
                custom_field.insert(ignore_permissions=True)
                print(f"Created custom field: {field_config['fieldname']}")
            except Exception as e:
                print(f"Failed to create custom field {field_config['fieldname']}: {str(e)}")
    
    # Warehouse Custom Fields
    warehouse_fields = [
        {
            "doctype": "Custom Field",
            "dt": "Warehouse",
            "fieldname": "custom_temperature_control",
            "label": "Temperature Control",
            "fieldtype": "Check",
            "insert_after": "is_rejected_warehouse",
            "description": "Enable if this warehouse requires temperature monitoring"
        },
        {
            "doctype": "Custom Field",
            "dt": "Warehouse",
            "fieldname": "custom_warehouse_code",
            "label": "Warehouse Code",
            "fieldtype": "Data",
            "insert_after": "custom_temperature_control",
            "unique": 1,
            "description": "Unique warehouse identification code"
        }
    ]
    
    # Install Warehouse fields
    for field_config in warehouse_fields:
        if not frappe.db.exists("Custom Field", {"dt": field_config["dt"], "fieldname": field_config["fieldname"]}):
            try:
                custom_field = frappe.get_doc(field_config)
                custom_field.insert(ignore_permissions=True)
                print(f"Created custom field: {field_config['fieldname']}")
            except Exception as e:
                print(f"Failed to create custom field {field_config['fieldname']}: {str(e)}")
    
    # Work Order Custom Fields
    work_order_fields = [
        {
            "doctype": "Custom Field",
            "dt": "Work Order",
            "fieldname": "section_break_zone_tracking",
            "label": "Zone Status Tracking",
            "fieldtype": "Section Break",
            "insert_after": "required_items",
            "collapsible": 1
        },
        {
            "doctype": "Custom Field",
            "dt": "Work Order",
            "fieldname": "custom_current_zone_status",
            "label": "Current Zone Status",
            "fieldtype": "Select",
            "options": "\nRed Zone\nGreen Zone",
            "insert_after": "section_break_zone_tracking",
            "in_list_view": 1,
            "read_only": 1,
            "default": "Red Zone",
            "description": "Red Zone = Incomplete materials, Green Zone = All materials available"
        }
    ]
    
    # Install Work Order fields
    for field_config in work_order_fields:
        if not frappe.db.exists("Custom Field", {"dt": field_config["dt"], "fieldname": field_config["fieldname"]}):
            try:
                custom_field = frappe.get_doc(field_config)
                custom_field.insert(ignore_permissions=True)
                print(f"Created custom field: {field_config['fieldname']}")
            except Exception as e:
                print(f"Failed to create custom field {field_config['fieldname']}: {str(e)}")

def install_material_assessment_log():
    """Install Material Assessment Log DocType if it doesn't exist"""
    
    if not frappe.db.exists("DocType", "Material Assessment Log"):
        try:
            # The DocType should be created by the standard installation process
            print("Material Assessment Log DocType will be created by standard installation")
        except Exception as e:
            print(f"Material Assessment Log installation note: {str(e)}")

def create_default_warehouses():
    """Create default warehouse hierarchy for warehouse management"""
    
    try:
        # Get default company
        company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            company = frappe.get_all("Company", limit=1, pluck="name")
            company = company[0] if company else "AMB-Wellness"
        
        # Create warehouse hierarchy
        from amb_w_spc.sfc_manufacturing.warehouse_management.warehouse import create_warehouse_hierarchy
        
        result = create_warehouse_hierarchy(company, ["AMB-W"])
        if result.get("status") == "success":
            print(f"Created warehouse hierarchy: {len(result.get('created_warehouses', []))} warehouses")
        
    except Exception as e:
        print(f"Warehouse hierarchy creation info: {str(e)}")

def setup_permissions():
    """Setup permissions for warehouse management"""
    
    try:
        # Material Assessment Log permissions
        if frappe.db.exists("DocType", "Material Assessment Log"):
            # Manufacturing Manager - full access
            if not frappe.db.exists("Custom DocPerm", {
                "parent": "Material Assessment Log",
                "role": "Manufacturing Manager"
            }):
                frappe.get_doc({
                    "doctype": "Custom DocPerm",
                    "parent": "Material Assessment Log",
                    "parenttype": "DocType",
                    "parentfield": "permissions",
                    "role": "Manufacturing Manager",
                    "read": 1,
                    "write": 1,
                    "create": 1,
                    "delete": 1,
                    "submit": 0,
                    "cancel": 0,
                    "amend": 0
                }).insert(ignore_permissions=True)
        
        print("Permissions setup completed")
        
    except Exception as e:
        print(f"Permission setup info: {str(e)}")

if __name__ == "__main__":
    execute()
