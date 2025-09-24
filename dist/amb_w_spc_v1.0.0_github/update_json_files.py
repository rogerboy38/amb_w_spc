#!/usr/bin/env python3
import os
import json
import re

# Mapping of old names to new names
doctype_mapping = {
    # Quality Management module DocTypes
    "Corrective Action": "SPC Corrective Action",
    "Corrective Action Factor": "SPC Corrective Action Factor", 
    "Corrective Action Item": "SPC Corrective Action Item",
    "Corrective Action Workflow": "SPC Corrective Action Workflow",
    "Corrective Action - Due Date Reminder": "SPC Corrective Action - Due Date Reminder",
    "Corrective Action - New CA": "SPC Corrective Action - New CA",
    "Process Capability": "SPC Process Capability",
    "Process Capability Measurement": "SPC Process Capability Measurement",
    "Process Capability Workflow": "SPC Process Capability Workflow",
    "Process Capability - Study Completed": "SPC Process Capability - Study Completed",
    # Plant Equipment module DocTypes
    "Workstation": "SPC Workstation",
    # FDA Compliance module DocTypes
    "Deviation": "SPC Deviation",
    "Electronic Signature": "SPC Electronic Signature"
}

# Module mapping
module_mapping = {
    "Quality Management": "SPC Quality Management"
}

def update_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Update DocType names in the content
        for old_name, new_name in doctype_mapping.items():
            # Update name field
            content = re.sub(
                r'"name":\s*"' + re.escape(old_name) + '"',
                f'"name": "{new_name}"',
                content
            )
            # Update options field (for link fields)
            content = re.sub(
                r'"options":\s*"' + re.escape(old_name) + '"',
                f'"options": "{new_name}"',
                content
            )
        
        # Update module references
        for old_module, new_module in module_mapping.items():
            content = re.sub(
                r'"module":\s*"' + re.escape(old_module) + '"',
                f'"module": "{new_module}"',
                content
            )
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {file_path}")
        else:
            print(f"No changes needed: {file_path}")
            
    except Exception as e:
        print(f"Error updating {file_path}: {e}")

# Find and update all JSON files
def update_all_json_files():
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                update_json_file(file_path)

if __name__ == "__main__":
    update_all_json_files()
