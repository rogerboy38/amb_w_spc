import frappe
import json
import os

def run():
    """
    Post-installation script to create workflows after the app's core components are installed.
    This solves the installation order dependency issue where workflows reference DocTypes
    that haven't been created yet during the standard installation process.
    """
    workflows_to_install = [
        'spc_corrective_action_workflow.json',
        'spc_alert_workflow.json',
        'spc_process_capability_workflow.json'
    ]
    
    # Path where we stored the workflow JSONs
    workflows_dir = '/tmp/workflows'

    for wf_json in workflows_to_install:
        json_path = os.path.join(workflows_dir, wf_json)
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    
                    # Ensure workflow is active
                    data['is_active'] = 1
                    
                    # Check if workflow already exists
                    if not frappe.db.exists('Workflow', data['name']):
                        doc = frappe.get_doc(data)
                        doc.insert()
                        frappe.db.commit()
                        print(f"Successfully installed workflow: {data['name']}")
                    else:
                        print(f"Workflow {data['name']} already exists.")
                        
            except Exception as e:
                print(f"Error installing workflow {wf_json}: {str(e)}")
        else:
            print(f"Workflow file not found: {json_path}")
    
    print("Post-installation workflow setup completed.")
