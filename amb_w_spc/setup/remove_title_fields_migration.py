# remove_title_fields_migration.py
import json
import os
import glob

def remove_title_fields_from_doctypes():
    """Remove title_field from doctypes that don't have title columns"""
    doctype_files = glob.glob("amb_w_spc/**/doctype/**/*.json", recursive=True)
    
    for file_path in doctype_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Only process main doctype files
            if isinstance(data, dict) and data.get('doctype') == 'DocType':
                doctype_name = data.get('name', 'Unknown')
                fields = data.get('fields', [])
                
                # Check if this doctype actually has a title field
                has_title_field = any(f.get('fieldname') == 'title' for f in fields)
                
                # If no title field exists, remove title_field property
                if not has_title_field and 'title_field' in data:
                    del data['title_field']
                    print(f"✓ Removed title_field from {doctype_name}")
                elif has_title_field:
                    print(f"✓ {doctype_name} has title field, keeping title_field")
                
                # Write back the fixed file
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                        
        except Exception as e:
            print(f"⚠️  Could not process {file_path}: {e}")

def main():
    print("🔧 Removing title_field from doctypes without title columns...\n")
    
    if not os.path.exists("amb_w_spc"):
        print("❌ Please run this script from the apps directory")
        return
    
    remove_title_fields_from_doctypes()
    
    print("\n✅ Title fields removed from doctypes without title columns!")
    print("\nNow try migration again:")
    print("cd ~/frappe-bench")
    print("bench migrate")

if __name__ == "__main__":
    main()
