# fix_workspace_content_json.py
import json

def fix_workspace_content():
    """Fix workspace content to be JSON strings instead of Python lists"""
    workspace_path = "amb_w_spc/fixtures/workspace.json"
    
    with open(workspace_path, 'r') as f:
        data = json.load(f)
    
    # Define proper content as JSON strings for each workspace
    workspace_content = {
        "SPC Dashboard": json.dumps([
            {
                "type": "header",
                "data": {
                    "text": "SPC Dashboard",
                    "level": 1
                }
            },
            {
                "type": "paragraph",
                "data": {
                    "text": "Statistical Process Control Dashboard for monitoring manufacturing processes."
                }
            }
        ]),
        "SPC Quality Management": json.dumps([
            {
                "type": "header", 
                "data": {
                    "text": "SPC Quality Management",
                    "level": 1
                }
            },
            {
                "type": "paragraph",
                "data": {
                    "text": "Quality management tools for SPC alerts and corrective actions."
                }
            }
        ]),
        "Manufacturing Control": json.dumps([
            {
                "type": "header",
                "data": {
                    "text": "Manufacturing Control", 
                    "level": 1
                }
            },
            {
                "type": "paragraph",
                "data": {
                    "text": "Shop floor control and manufacturing operations management."
                }
            }
        ])
    }
    
    # Update each workspace with proper JSON string content
    for workspace in data:
        name = workspace.get('name')
        if name in workspace_content:
            workspace['content'] = workspace_content[name]
        else:
            # Default empty content as JSON string
            workspace['content'] = "[]"
        
        # Ensure sequence_id is unique (already fixed)
        # Ensure shortcuts have doctype
        for shortcut in workspace.get('shortcuts', []):
            if 'doctype' not in shortcut:
                shortcut['doctype'] = 'Workspace Shortcut'
    
    # Write back the fixed file
    with open(workspace_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print("✓ Fixed workspace content as JSON strings")
    for workspace in data:
        content_preview = workspace['content'][:50] + "..." if len(workspace['content']) > 50 else workspace['content']
        print(f"  - {workspace['name']}: content = '{content_preview}'")

# Run the fix
fix_workspace_content()
