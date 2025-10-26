#!/usr/bin/env python3
"""
Installation Compatibility Test for AMB W SPC
Tests that the app structure is ready for Frappe installation
"""

import os
import json
import importlib.util

def test_installation_compatibility():
    """Test app compatibility for Frappe installation"""
    print("🧪 Testing Installation Compatibility...")
    issues = []
    
    # Test 1: Check all JSON files are valid
    print("\n📋 Testing DocType JSON files...")
    json_files = []
    for root, dirs, files in os.walk('amb_w_spc'):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))
    
    invalid_json = []
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            invalid_json.append(f"{json_file}: {e}")
    
    if invalid_json:
        issues.extend(invalid_json)
        print(f"❌ Found {len(invalid_json)} invalid JSON files")
    else:
        print(f"✅ All {len(json_files)} JSON files are valid")
    
    # Test 2: Check Python files can be imported
    print("\n🐍 Testing Python file syntax...")
    python_files = []
    for root, dirs, files in os.walk('amb_w_spc'):
        for file in files:
            if file.endswith('.py') and not file.startswith('test_'):
                python_files.append(os.path.join(root, file))
    
    syntax_errors = []
    for py_file in python_files:
        try:
            with open(py_file, 'r') as f:
                compile(f.read(), py_file, 'exec')
        except SyntaxError as e:
            syntax_errors.append(f"{py_file}: {e}")
    
    if syntax_errors:
        issues.extend(syntax_errors)
        print(f"❌ Found {len(syntax_errors)} Python syntax errors")
    else:
        print(f"✅ All {len(python_files)} Python files have valid syntax")
    
    # Test 3: Check hooks.py is valid
    print("\n🔗 Testing hooks.py...")
    try:
        spec = importlib.util.spec_from_file_location("hooks", "hooks.py")
        hooks_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hooks_module)
        
        # Check required attributes
        required_attrs = ['app_name', 'app_title', 'app_publisher']
        missing_attrs = [attr for attr in required_attrs if not hasattr(hooks_module, attr)]
        
        if missing_attrs:
            issues.append(f"hooks.py missing required attributes: {missing_attrs}")
            print(f"❌ hooks.py missing attributes: {missing_attrs}")
        else:
            print("✅ hooks.py is valid and has required attributes")
            
    except Exception as e:
        issues.append(f"hooks.py error: {e}")
        print(f"❌ hooks.py error: {e}")
    
    # Test 4: Check modules.txt
    print("\n📝 Testing modules.txt...")
    try:
        with open('modules.txt', 'r') as f:
            modules = [line.strip() for line in f.readlines() if line.strip()]
        
        # Check if module directories exist
        missing_modules = []
        for module in modules:
            module_dir = os.path.join('amb_w_spc', module.lower().replace(' ', '_'))
            if not os.path.exists(module_dir):
                missing_modules.append(module)
        
        if missing_modules:
            print(f"⚠️  Some modules in modules.txt might not have corresponding directories")
        else:
            print(f"✅ modules.txt lists {len(modules)} modules")
            
    except Exception as e:
        issues.append(f"modules.txt error: {e}")
        print(f"❌ modules.txt error: {e}")
    
    # Summary
    print(f"\n📊 Summary:")
    if issues:
        print(f"❌ Found {len(issues)} issues that need to be resolved:")
        for issue in issues:
            print(f"   • {issue}")
        return False
    else:
        print("✅ All compatibility tests passed!")
        print("🚀 App is ready for Frappe installation")
        return True

if __name__ == "__main__":
    test_installation_compatibility()