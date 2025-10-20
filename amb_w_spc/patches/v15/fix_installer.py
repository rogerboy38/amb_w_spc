import frappe

def execute():
    """Patch Frappe's installer to use v15-compatible Module Def insertion"""
    from frappe.installer import add_module_defs as original_add_module_defs
    
    def patched_add_module_defs(app, ignore_if_duplicate=False):
        """Use direct SQL to avoid v16 field names"""
        modules = frappe.get_hooks("modules", app_name=app)
        if not modules:
            return
        
        for module in modules:
            if not frappe.db.exists("Module Def", module):
                print(f"Creating module: {module} for app: {app}")
                # Use direct SQL with only v15-compatible fields
                frappe.db.sql("""
                    INSERT INTO `tabModule Def` 
                    (`name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`, `idx`, `module_name`, `custom`, `app_name`)
                    VALUES (%s, NOW(), NOW(), %s, %s, %s, %s, %s, %s, %s)
                """, (
                    module,
                    "Administrator",
                    "Administrator",
                    0,  # docstatus
                    0,  # idx
                    module,
                    0,  # custom
                    app
                ))
        
        frappe.db.commit()
    
    # Apply the monkey patch
    import frappe.installer
    frappe.installer.add_module_defs = patched_add_module_defs
    print("✅ Applied v15 Module Def compatibility patch")
