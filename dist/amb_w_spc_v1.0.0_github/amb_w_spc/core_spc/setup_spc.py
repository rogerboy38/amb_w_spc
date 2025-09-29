# SPC DocTypes Installation Script
# Run this script after importing the DocTypes to set up additional configurations

import frappe
import json
from frappe.utils import nowdate

def setup_spc_doctypes():
    """Setup SPC DocTypes with default configurations"""
    
    print("Setting up SPC DocTypes...")
    
    # 1. Create default SPC Parameter Masters for common measurements
    create_default_parameters()
    
    # 2. Set up default roles and permissions
    setup_default_permissions()
    
    # 3. Create sample specifications
    create_sample_specifications()
    
    # 4. Set up number series
    setup_number_series()
    
    print("SPC DocTypes setup completed successfully!")

def create_default_parameters():
    """Create common SPC parameters"""
    
    default_params = [
        {
            "parameter_name": "Diameter",
            "parameter_code": "DIA",
            "unit_of_measurement": "Millimeter",
            "data_type": "Numeric",
            "default_precision": 3,
            "description": "Diameter measurement for cylindrical components"
        },
        {
            "parameter_name": "Length",
            "parameter_code": "LEN",
            "unit_of_measurement": "Millimeter",
            "data_type": "Numeric",
            "default_precision": 2,
            "description": "Length measurement"
        },
        {
            "parameter_name": "Weight",
            "parameter_code": "WT",
            "unit_of_measurement": "Gram",
            "data_type": "Numeric",
            "default_precision": 2,
            "description": "Weight measurement"
        },
        {
            "parameter_name": "Temperature",
            "parameter_code": "TEMP",
            "unit_of_measurement": "Degree Celsius",
            "data_type": "Numeric",
            "default_precision": 1,
            "description": "Temperature measurement"
        },
        {
            "parameter_name": "Pressure",
            "parameter_code": "PRESS",
            "unit_of_measurement": "Bar",
            "data_type": "Numeric",
            "default_precision": 2,
            "description": "Pressure measurement"
        }
    ]
    
    company = frappe.get_all("Company", limit=1)
    if not company:
        print("Warning: No company found. Please create a company first.")
        return
    
    company_name = company[0].name
    
    for param_data in default_params:
        if not frappe.db.exists("SPC Parameter Master", param_data["parameter_name"]):
            param_doc = frappe.get_doc({
                "doctype": "SPC Parameter Master",
                "company": company_name,
                **param_data
            })
            param_doc.insert(ignore_permissions=True)
            print(f"Created parameter: {param_data['parameter_name']}")

def setup_default_permissions():
    """Set up role-based permissions for SPC DocTypes"""
    
    # Define roles if they don't exist
    roles_to_create = [
        {
            "role_name": "SPC Manager",
            "desk_access": 1,
            "description": "Full access to SPC system"
        },
        {
            "role_name": "SPC User",
            "desk_access": 1,
            "description": "Data entry and viewing access for SPC"
        }
    ]
    
    for role_data in roles_to_create:
        if not frappe.db.exists("Role", role_data["role_name"]):
            role_doc = frappe.get_doc({
                "doctype": "Role",
                **role_data
            })
            role_doc.insert(ignore_permissions=True)
            print(f"Created role: {role_data['role_name']}")

def create_sample_specifications():
    """Create sample specifications for default parameters"""
    
    # Get default company
    company = frappe.get_all("Company", limit=1)
    if not company:
        return
    company_name = company[0].name
    
    sample_specs = [
        {
            "specification_name": "Standard Diameter Spec",
            "parameter": "Diameter",
            "target_value": 25.0,
            "tolerance_plus": 0.05,
            "tolerance_minus": 0.05,
            "upper_spec_limit": 25.05,
            "lower_spec_limit": 24.95,
            "upper_control_limit": 25.03,
            "lower_control_limit": 24.97,
            "cpk_target": 1.33,
            "ppk_target": 1.33
        },
        {
            "specification_name": "Standard Temperature Spec",
            "parameter": "Temperature",
            "target_value": 180.0,
            "tolerance_plus": 5.0,
            "tolerance_minus": 5.0,
            "upper_spec_limit": 185.0,
            "lower_spec_limit": 175.0,
            "upper_control_limit": 183.0,
            "lower_control_limit": 177.0,
            "cpk_target": 1.67,
            "ppk_target": 1.67
        }
    ]
    
    for spec_data in sample_specs:
        # Check if parameter exists
        if frappe.db.exists("SPC Parameter Master", spec_data["parameter"]):
            if not frappe.db.exists("SPC Specification", spec_data["specification_name"]):
                spec_doc = frappe.get_doc({
                    "doctype": "SPC Specification",
                    "company": company_name,
                    "valid_from": nowdate(),
                    "unit_of_measurement": get_param_uom(spec_data["parameter"]),
                    **spec_data
                })
                spec_doc.insert(ignore_permissions=True)
                print(f"Created specification: {spec_data['specification_name']}")

def get_param_uom(parameter_name):
    """Get UOM for a parameter"""
    param = frappe.get_doc("SPC Parameter Master", parameter_name)
    return param.unit_of_measurement if param else "Unit"

def setup_number_series():
    """Set up number series for SPC DocTypes"""
    
    series_to_create = [
        {
            "name": "SPC-DATA-.YYYY.-.#####",
            "current": 1
        },
        {
            "name": "SPC-SPEC-.YYYY.-.#####",
            "current": 1
        }
    ]
    
    for series in series_to_create:
        if not frappe.db.exists("Number Series", series["name"]):
            series_doc = frappe.get_doc({
                "doctype": "Number Series",
                **series
            })
            series_doc.insert(ignore_permissions=True)
            print(f"Created number series: {series['name']}")

if __name__ == "__main__":
    # Run the setup
    setup_spc_doctypes()