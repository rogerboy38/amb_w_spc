import frappe

def execute():
    """Create pharmaceutical roles"""
    
    roles_to_create = [
        {
            "role_name": "Quality Manager",
            "desk_access": 1
        },
        {
            "role_name": "Warehouse Operator", 
            "desk_access": 1
        },
        {
            "role_name": "Pharma Manager",
            "desk_access": 1
        }
    ]
    
    for role_data in roles_to_create:
        if not frappe.db.exists("Role", role_data["role_name"]):
            role = frappe.new_doc("Role")
            role.role_name = role_data["role_name"]
            role.desk_access = role_data["desk_access"]
            role.insert()
            print(f"✅ Created role: {role_data['role_name']}")
        else:
            print(f"✅ Role already exists: {role_data['role_name']}")
    
    frappe.db.commit()
