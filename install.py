import frappe

def create_modules_v15():
    """Create modules using direct SQL to avoid v16 field issues"""
    modules = [
        "core_spc", "spc_quality_management", "sfc_manufacturing", 
        "operator_management", "shop_floor_control", "plant_equipment",
        "real_time_monitoring", "sensor_management", "system_integration", "fda_compliance"
    ]
    
    for module in modules:
        if not frappe.db.exists("Module Def", module):
            print(f"Creating module: {module}")
            frappe.db.sql("""
                INSERT INTO `tabModule Def` 
                (`name`, `creation`, `modified`, `modified_by`, `owner`, 
                 `docstatus`, `idx`, `module_name`, `custom`, `app_name`)
                VALUES (%s, NOW(), NOW(), %s, %s, %s, %s, %s, %s, %s)
            """, (module, "Administrator", "Administrator", 0, 0, module, 0, "amb_w_spc"))
    
    frappe.db.commit()
    print("✅ All modules created successfully!")
