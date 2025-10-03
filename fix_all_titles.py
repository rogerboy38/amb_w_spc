# fix_titles_correctly.py
import json
import os
import glob

def fix_workspace_titles():
    """Fix missing titles in workspace fixtures - add the actual title text"""
    workspace_path = "amb_w_spc/fixtures/workspace.json"
    
    if os.path.exists(workspace_path):
        print(f"Fixing {workspace_path}")
        with open(workspace_path, 'r') as f:
            data = json.load(f)
        
        # Add missing title TEXT to workspace items
        for item in data:
            if 'title' not in item:
                # Use the name as title (like in your working example)
                item['title'] = item.get('name', 'Untitled')
                print(f"  Added title '{item['title']}' to workspace {item.get('name')}")
        
        # Write back the fixed file
        with open(workspace_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print("✓ Workspace titles fixed!\n")

def fix_doctype_title_fields():
    """Fix title_field in doctypes to point to correct field names"""
    doctype_files = glob.glob("amb_w_spc/**/doctype/**/*.json", recursive=True)
    
    for file_path in doctype_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Only process main doctype files
            if isinstance(data, dict) and data.get('doctype') == 'DocType':
                doctype_name = data.get('name', 'Unknown')
                fields = data.get('fields', [])
                
                # Get all field names
                field_names = [f['fieldname'] for f in fields]
                
                # Check if we need to add a title field
                needs_title_field = False
                
                # If this is a main doctype (not child table) and doesn't have good title options
                if not data.get('istable'):
                    if 'title' not in field_names:
                        # Add a title field
                        title_field = {
                            "fieldname": "title", 
                            "fieldtype": "Data",
                            "label": "Title",
                            "reqd": 1,
                            "in_list_view": 1
                        }
                        fields.insert(1, title_field)  # Insert after name field
                        data['fields'] = fields
                        needs_title_field = True
                        print(f"✓ Added 'title' field to {doctype_name}")
                
                # Set the title_field property
                if 'title' in [f['fieldname'] for f in data.get('fields', [])]:
                    data['title_field'] = 'title'
                elif 'name' in [f['fieldname'] for f in data.get('fields', [])]:
                    data['title_field'] = 'name'
                
                if needs_title_field or data.get('title_field'):
                    with open(file_path, 'w') as f:
                        json.dump(data, f, indent=2)
                    if data.get('title_field'):
                        print(f"  Set title_field = '{data['title_field']}'")
                        
        except Exception as e:
            print(f"⚠️  Could not process {file_path}: {e}")

def main():
    print("🔧 Correctly fixing titles...\n")
    
    if not os.path.exists("amb_w_spc"):
        print("❌ Please run this script from the apps directory")
        return
    
    # 1. Fix workspace titles (add the actual title text)
    fix_workspace_titles()
    
    # 2. Fix doctype title_fields (point to correct field names)
    print("Fixing doctype title_field references...")
    fix_doctype_title_fields()
    
    print("\n✅ All fixes completed!")
    print("\nNow try installing the app again:")
    print("cd ~/frappe-bench")
    print("bench --site sysmayal.v.frappe.cloud install-app amb_w_spc --force")

if __name__ == "__main__":
    main()
