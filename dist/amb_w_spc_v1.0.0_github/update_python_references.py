#!/usr/bin/env python3
import os
import re

# Mapping of old DocType names to new DocType names for Python files
doctype_mapping = {
    # Exact string matches in Python code
    '"Corrective Action"': '"SPC Corrective Action"',
    "'Corrective Action'": "'SPC Corrective Action'",
    '"Process Capability"': '"SPC Process Capability"',
    "'Process Capability'": "'SPC Process Capability'",
    '"Workstation"': '"SPC Workstation"',
    "'Workstation'": "'SPC Workstation'",
    '"Deviation"': '"SPC Deviation"',
    "'Deviation'": "'SPC Deviation'", 
    '"Electronic Signature"': '"SPC Electronic Signature"',
    "'Electronic Signature'": "'SPC Electronic Signature'",
    
    # Workflow references
    '"Process Capability Workflow"': '"SPC Process Capability Workflow"',
    "'Process Capability Workflow'": "'SPC Process Capability Workflow'",
}

def update_python_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Update DocType references
        for old_ref, new_ref in doctype_mapping.items():
            content = content.replace(old_ref, new_ref)
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {file_path}")
            
            # Show what was changed
            lines_old = original_content.splitlines()
            lines_new = content.splitlines()
            for i, (old_line, new_line) in enumerate(zip(lines_old, lines_new)):
                if old_line != new_line:
                    print(f"  Line {i+1}: {old_line.strip()}")
                    print(f"  ->     : {new_line.strip()}")
        else:
            print(f"No changes needed: {file_path}")
            
    except Exception as e:
        print(f"Error updating {file_path}: {e}")

def update_all_python_files():
    updated_files = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.py') and not file.startswith('update_'):
                file_path = os.path.join(root, file)
                # Check if file contains any of our target DocTypes
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if any(old_ref.strip('"\'') in content for old_ref in doctype_mapping.keys()):
                            update_python_file(file_path)
                            updated_files.append(file_path)
                except:
                    pass
    
    print(f"\nSummary: Updated {len(updated_files)} Python files")
    return updated_files

if __name__ == "__main__":
    print("Updating Python file references...")
    updated_files = update_all_python_files()
