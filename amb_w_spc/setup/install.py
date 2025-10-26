import frappe

def before_install():
    """Run before app installation"""
    pass

def after_install(app_name=None):
    """Run after app installation - setup navigation and modules"""
    print(f"Setting up navigation for {app_name}...")
    create_modules_v15()
    setup_navigation()
    create_workspaces()
    
def create_workspaces():
    """Create workspaces programmatically"""
    print("Creating workspaces...")
    
    workspaces = [
        {
            "name": "SPC Dashboard",
            "label": "SPC Dashboard", 
            "title": "SPC Dashboard",
            "module": "core_spc",
            "shortcuts": [
                {"type": "DocType", "link_to": "SPC Control Chart", "label": "Control Charts"},
                {"type": "DocType", "link_to": "SPC Data Point", "label": "Data Points"}
            ]
        }
    ]
    
    for ws_config in workspaces:
        if not frappe.db.exists("Workspace", ws_config["name"]):
            workspace = frappe.get_doc({
                "doctype": "Workspace",
                "name": ws_config["name"],
                "label": ws_config["label"],
                "title": ws_config["title"],
                "module": ws_config["module"],
                "is_standard": 1,
                "public": 1,
                "shortcuts": ws_config["shortcuts"]
            })
            workspace.insert()
            print(f"✅ Created {ws_config['name']} workspace")
    
    frappe.db.commit()
    
def setup_navigation():
    """Setup workspaces and desktop icons"""
    print("Setting up navigation...")
    
    # Workspaces will be loaded from fixtures
    # Desktop icons will be auto-created from modules
    
    frappe.db.commit()
    print("✅ Navigation setup completed")

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
