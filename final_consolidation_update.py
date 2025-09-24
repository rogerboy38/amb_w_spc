#!/usr/bin/env python3
import os
import re

# DocType mappings
doctype_mapping = {
    '"SPC Corrective Action"': '"SPC Corrective Action"',
    "'SPC Corrective Action'": "'SPC Corrective Action'",
    '"SPC Process Capability"': '"SPC Process Capability"',
    "'SPC Process Capability'": "'SPC Process Capability'",
    '"SPC Workstation"': '"SPC Workstation"',
    "'SPC Workstation'": "'SPC Workstation'",
    '"SPC Deviation"': '"SPC Deviation"',
    "'SPC Deviation'": "'SPC Deviation'",
    '"SPC Electronic Signature"': '"SPC Electronic Signature"',
    "'SPC Electronic Signature'": "'SPC Electronic Signature'",
}

# Class name mappings for Python files
class_mapping = {
    'class CorrectiveAction': 'class SPCCorrectiveAction',
    'class ProcessCapability': 'class SPCProcessCapability', 
    'class Workstation': 'class SPCWorkstation',
    'class Deviation': 'class SPCDeviation',
    'class ElectronicSignature': 'class SPCElectronicSignature',
}

def update_file(file_path, is_js=False):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Update DocType references
        for old_ref, new_ref in doctype_mapping.items():
            content = content.replace(old_ref, new_ref)
        
        # Update class names for Python files
        if not is_js:
            for old_class, new_class in class_mapping.items():
                content = content.replace(old_class, new_class)
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {file_path}")
        
    except Exception as e:
        print(f"Error updating {file_path}: {e}")

def main():
    js_updated = 0
    py_class_updated = 0
    
    print("Updating JavaScript and Python class references...")
    
    for root, dirs, files in os.walk('.'):
        for file in files:
            file_path = os.path.join(root, file)
            
            # Update JS files
            if file.endswith('.js'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if any(old_ref.strip('"\'') in content for old_ref in doctype_mapping.keys()):
                            update_file(file_path, is_js=True)
                            js_updated += 1
                except:
                    pass
            
            # Update Python class definitions
            elif file.endswith('.py') and '/doctype/' in file_path:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if any(old_class in content for old_class in class_mapping.keys()):
                            update_file(file_path, is_js=False)
                            py_class_updated += 1
                except:
                    pass
    
    print(f"Updated {js_updated} JavaScript files")
    print(f"Updated {py_class_updated} Python class files")

if __name__ == "__main__":
    main()
