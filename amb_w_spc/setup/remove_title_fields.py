# remove_title_fields.py
import json
import os
import glob

def remove_title_fields_from_doctypes():
    """Remove title fields that were incorrectly added and reset title_field to name"""
    doctype_files = glob.glob("amb_w_spc/**/doctype/**/*.json", recursive=True)
    
    for file_path in doctype_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Only process main doctype files
            if isinstance(data, dict) and data.get('doctype') == 'DocType':
                doctype_name = data.get('name', 'Unknown')
                fields = data.get('fields', [])
                
                # Remove any title fields we added
                original_field_count = len(fields)
                fields = [f for f in fields if f.get('fieldname') != 'title']
                
                # If we removed fields, update the data
                if len(fields) != original_field_count:
                    data['fields'] = fields
                    print(f"✓ Removed 'title' field from {doctype_name}")
                
                # Always set title_field to 'name' for now
                data['title_field'] = 'name'
                
                # Write back the fixed file
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                    
                print(f"  Set title_field = 'name' for {doctype_name}")
                        
        except Exception as e:
            print(f"⚠️  Could not process {file_path}: {e}")

def main():
    print("🔧 Removing incorrectly added title fields...\n")
    
    if not os.path.exists("amb_w_spc"):
        print("❌ Please run this script from the apps directory")
        return
    
    # Remove title fields and reset title_field to name
    remove_title_fields_from_doctypes()
    
    print("\n✅ Title fields removed!")
    print("\nNow try installing the app again:")
    print("cd ~/frappe-bench")
    print("bench --site sysmayal.v.frappe.cloud install-app amb_w_spc --force")

if __name__ == "__main__":
    main()
