# create_placeholder_doctypes.py
import os
import json

# Doctypes that are referenced but might not exist
missing_doctypes = {
    "SPC Control Chart": "core_spc",
    "SPC Report": "core_spc", 
    "SPC Alert": "spc_quality_management",
    "SPC Corrective Action": "spc_quality_management",
    "Batch AMB": "sfc_manufacturing",
    "Work Order Routing": "sfc_manufacturing"
}

for doctype_name, module in missing_doctypes.items():
    # Create directory structure
    dir_path = f"amb_w_spc/{module}/doctype/{doctype_name.lower().replace(' ', '_')}"
    os.makedirs(dir_path, exist_ok=True)
    
    # Create minimal doctype JSON
    doctype_data = {
        "doctype": "DocType",
        "name": doctype_name,
        "module": module,
        "custom": 1,
        "is_submittable": 0,
        "istable": 0,
        "track_changes": 1,
        "fields": [
            {
                "fieldname": "name1",
                "fieldtype": "Data", 
                "label": "Name",
                "reqd": 1
            }
        ],
        "permissions": [
            {
                "role": "System Manager",
                "permlevel": 0,
                "read": 1,
                "write": 1,
                "create": 1,
                "delete": 1,
                "submit": 0,
                "cancel": 0,
                "amend": 0
            }
        ]
    }
    
    # Write doctype file
    with open(f"{dir_path}/{doctype_name.lower().replace(' ', '_')}.json", 'w') as f:
        json.dump(doctype_data, f, indent=2)
    
    print(f"✓ Created placeholder doctype: {doctype_name}")

print("\nNow all referenced doctypes should exist!")
