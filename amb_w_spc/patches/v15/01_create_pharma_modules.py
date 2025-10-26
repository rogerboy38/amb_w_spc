import frappe

def execute():
    """Create pharmaceutical modules"""
    
    modules_to_create = [
        {
            "module_name": "Pharma Warehouse",
            "app_name": "amb_w_spc",
            "custom": 0
        }
    ]
    
    for module_data in modules_to_create:
        if not frappe.db.exists("Module Def", module_data["module_name"]):
            module = frappe.new_doc("Module Def")
            module.module_name = module_data["module_name"]
            module.app_name = module_data["app_name"]
            module.custom = module_data["custom"]
            module.insert()
            print(f"✅ Created module: {module_data['module_name']}")
        else:
            print(f"✅ Module already exists: {module_data['module_name']}")
    
    frappe.db.commit()
