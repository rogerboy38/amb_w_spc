#!/usr/bin/env python3
import os
import json

def validate_frappe_app_structure():
    """Validate that we have a proper Frappe app structure"""
    print("🔍 Validating Frappe App Structure...")
    
    # Required root files
    required_root_files = ['hooks.py', 'setup.py', 'modules.txt', 'requirements.txt']
    app_directory = 'amb_w_spc'
    
    # Check root files
    missing_files = []
    for file in required_root_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing required root files: {missing_files}")
        return False
    else:
        print("✅ All required root files present")
    
    # Check app directory exists
    if not os.path.exists(app_directory):
        print(f"❌ App directory '{app_directory}' missing")
        return False
    else:
        print(f"✅ App directory '{app_directory}' present")
    
    # Count modules and doctypes
    module_count = 0
    doctype_count = 0
    
    for root, dirs, files in os.walk(app_directory):
        if '/doctype/' in root and any(f.endswith('.json') for f in files):
            doctype_count += 1
        
        if root.count(os.sep) == 1 and os.path.basename(root) != '__pycache__':
            module_count += 1
    
    print(f"📊 Found {module_count} modules")
    print(f"📊 Found {doctype_count} doctypes")
    
    return True

if __name__ == "__main__":
    validate_frappe_app_structure()
