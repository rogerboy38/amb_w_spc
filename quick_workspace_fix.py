# quick_workspace_fix.py
import json

# Fix the workspace.json in fixtures to match the working one in workspaces/
workspace_path = "amb_w_spc/fixtures/workspace.json"

with open(workspace_path, 'r') as f:
    data = json.load(f)

# Add title field to each workspace item using the name as title
for item in data:
    item['title'] = item['name']  # Use the name as title like in your working example

with open(workspace_path, 'w') as f:
    json.dump(data, f, indent=2)

print("Fixed workspace titles:")
for item in data:
    print(f"  {item['name']} -> title: '{item['title']}'")
