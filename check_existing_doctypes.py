# check_existing_doctypes.py
import os
import json
import glob

def find_existing_doctypes():
    """Find all doctypes that actually exist in the app"""
    doctype_paths = glob.glob("amb_w_spc/**/doctype/**/*.json", recursive=True)
    existing_doctypes = []
    
    for path in doctype_paths:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'doctype' in data and data['doctype'] == 'DocType':
                    existing_doctypes.append(data.get('name'))
        except:
            continue
    
    return existing_doctypes

print("🔍 Checking which doctypes exist in your app...")
existing_doctypes = find_existing_doctypes()

print("\n📋 Existing doctypes:")
for doctype in sorted(existing_doctypes):
    print(f"  ✓ {doctype}")

# Check workspace shortcuts against existing doctypes
workspace_path = "amb_w_spc/fixtures/workspace.json"
with open(workspace_path, 'r') as f:
    workspaces = json.load(f)

print("\n🔗 Workspace shortcut validation:")
all_shortcuts_exist = True
for workspace in workspaces:
    print(f"\n{workspace['name']}:")
    for shortcut in workspace.get('shortcuts', []):
        doctype = shortcut.get('link_to')
        if doctype in existing_doctypes:
            print(f"  ✓ {shortcut.get('label')} -> {doctype}")
        else:
            print(f"  ❌ {shortcut.get('label')} -> {doctype} (MISSING)")
            all_shortcuts_exist = False

if all_shortcuts_exist:
    print("\n✅ All workspace shortcuts point to existing doctypes!")
else:
    print("\n❌ Some shortcuts point to missing doctypes")
