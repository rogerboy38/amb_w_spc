# fix_workspace_content.py
import json

def fix_workspace_fixtures():
    """Fix workspace fixtures by adding required content fields"""
    workspace_path = "amb_w_spc/fixtures/workspace.json"
    
    with open(workspace_path, 'r') as f:
        data = json.load(f)
    
    # Define content for each workspace
    workspace_content = {
        "SPC Dashboard": {
            "cards": [
                {
                    "label": "SPC Overview",
                    "type": "Custom",
                    "custom_html": "<div>SPC Dashboard Content</div>"
                }
            ],
            "shortcuts": [
                {
                    "type": "DocType",
                    "link_to": "SPC Control Chart", 
                    "label": "Control Charts"
                },
                {
                    "type": "DocType",
                    "link_to": "SPC Report",
                    "label": "SPC Reports"
                }
            ]
        },
        "SPC Quality Management": {
            "cards": [
                {
                    "label": "Quality Overview", 
                    "type": "Custom",
                    "custom_html": "<div>Quality Management Content</div>"
                }
            ],
            "shortcuts": [
                {
                    "type": "DocType",
                    "link_to": "SPC Alert",
                    "label": "Alerts"
                },
                {
                    "type": "DocType", 
                    "link_to": "SPC Corrective Action",
                    "label": "Corrective Actions"
                }
            ]
        },
        "Manufacturing Control": {
            "cards": [
                {
                    "label": "Manufacturing Overview",
                    "type": "Custom", 
                    "custom_html": "<div>Manufacturing Control Content</div>"
                }
            ],
            "shortcuts": [
                {
                    "type": "DocType",
                    "link_to": "Batch AMB", 
                    "label": "Batches"
                },
                {
                    "type": "DocType",
                    "link_to": "Work Order Routing",
                    "label": "Work Orders"
                }
            ]
        }
    }
    
    # Update each workspace with required fields
    for workspace in data:
        name = workspace.get('name')
        if name in workspace_content:
            workspace.update(workspace_content[name])
        
        # Ensure required fields exist
        if 'content' not in workspace:
            workspace['content'] = []
        if 'cards' not in workspace:
            workspace['cards'] = workspace_content.get(name, {}).get('cards', [])
        if 'shortcuts' not in workspace:
            workspace['shortcuts'] = workspace_content.get(name, {}).get('shortcuts', [])
        if 'sequence_id' not in workspace:
            workspace['sequence_id'] = 1
    
    # Write back the fixed file
    with open(workspace_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print("✓ Workspace fixtures fixed with proper content")
    for workspace in data:
        print(f"  - {workspace['name']}: {len(workspace.get('content', []))} content items, {len(workspace.get('cards', []))} cards, {len(workspace.get('shortcuts', []))} shortcuts")

# Run the fix
fix_workspace_fixtures()
