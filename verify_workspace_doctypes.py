# verify_workspace_doctypes.py
import json

workspace_path = "amb_w_spc/fixtures/workspace.json"

with open(workspace_path, 'r') as f:
    data = json.load(f)

print("Workspace shortcuts verification:")
for workspace in data:
    print(f"\n{workspace['name']}:")
    for shortcut in workspace.get('shortcuts', []):
        doctype = shortcut.get('link_to')
        print(f"  - {shortcut.get('label')} -> {doctype}")

print("\nIf any of these doctypes don't exist yet, the installation might fail.")
print("We might need to create empty placeholder doctypes or remove the shortcuts.")
