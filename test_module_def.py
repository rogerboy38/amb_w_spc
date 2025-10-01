import frappe

def test_module_def_structure():
    print("=== Testing Module Def Structure ===")
    
    # Method 1: Direct SQL
    print("1. Direct SQL describe:")
    result = frappe.db.sql("DESCRIBE `tabModule Def`")
    for row in result:
        print(f"   {row}")
    
    # Method 2: Frappe schema
    print("\n2. Frappe schema:")
    from frappe.model.db_schema import DbSchema
    db_schema = DbSchema(frappe.local.site)
    columns = db_schema.get_table_columns("tabModule Def")
    print(f"   Columns: {columns}")
    
    # Method 3: Try to create a minimal module
    print("\n3. Testing minimal module creation:")
    try:
        frappe.db.sql("""
            INSERT INTO `tabModule Def` 
            (`name`, `module_name`, `app_name`) 
            VALUES (%s, %s, %s)
        """, ("test_module", "Test Module", "frappe"))
        print("   SUCCESS: Minimal insert worked")
        # Clean up
        frappe.db.sql("DELETE FROM `tabModule Def` WHERE name='test_module'")
        frappe.db.commit()
    except Exception as e:
        print(f"   FAILED: {e}")

if __name__ == "__main__":
    test_module_def_structure()
