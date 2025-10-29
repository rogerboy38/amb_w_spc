#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPC ERPNext System Installation Script
Copyright (c) 2025 SPC System

Complete installation script for the Statistical Process Control system in ERPNext.
Handles DocTypes, permissions, workflows, fixtures, and validation setup.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
import argparse
from datetime import datetime

# Add the workspace path to Python path
sys.path.insert(0, '/workspace')

class SPCInstaller:
    def __init__(self, site_name, base_path='/workspace/erpnext_doctypes'):
        self.site_name = site_name
        self.base_path = Path(base_path)
        self.log_file = "spc_installation_{0}.log".format(datetime.now().strftime('%Y%m%d_%H%M%S'))
        self.errors = []
        self.warnings = []
        
    def log(self, message, level='INFO'):
        """Log installation progress"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = "[{0}] [{1}] {2}".format(timestamp, level, message)
        print(log_message)
        
        with open(self.log_file, 'a') as f:
            f.write(log_message + '\n')
    
    def run_command(self, command, check_output=True):
        """Execute a command and handle errors"""
        try:
            self.log("Executing: {0}".format(command))
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                check=check_output
            )
            
            if result.stdout:
                self.log("Output: {0}".format(result.stdout.strip()))
            if result.stderr and check_output:
                self.log("Error: {0}".format(result.stderr.strip()), 'ERROR')
                self.errors.append("Command failed: {0}\nError: {1}".format(command, result.stderr))
                
            return result
            
        except subprocess.CalledProcessError as e:
            self.log("Command failed: {0}".format(command), 'ERROR')
            self.log("Error: {0}".format(e.stderr), 'ERROR')
            self.errors.append("Command failed: {0}\nError: {1}".format(command, e.stderr))
            return None
    
    def verify_prerequisites(self):
        """Verify ERPNext installation and requirements"""
        self.log("Verifying prerequisites...")
        
        # Check if site exists
        result = self.run_command("bench --site {0} version".format(self.site_name))
        if not result or result.returncode != 0:
            self.errors.append("Site {0} not found or not accessible".format(self.site_name))
            return False
            
        # Check ERPNext version
        result = self.run_command("bench --site {0} execute 'import erpnext; print(erpnext.__version__)'".format(self.site_name))
        if result and result.returncode == 0:
            erpnext_version = result.stdout.strip().split('\n')[-1]
            self.log("ERPNext version: {0}".format(erpnext_version))
        else:
            self.warnings.append("Could not determine ERPNext version")
            
        # Check required Python packages
        required_packages = ['statistics', 'dateutil']
        for package in required_packages:
            result = self.run_command("python -c 'import {0}'".format(package))
            if result and result.returncode != 0:
                self.warnings.append("Python package {0} not found".format(package))
                
        return len(self.errors) == 0
    
    def install_doctypes(self):
        """Install all DocTypes in correct order"""
        self.log("Installing DocTypes...")
        
        # Load master installation file
        master_file = self.base_path / 'system_integration' / 'installation' / 'master_installation.json'
        with open(master_file, 'r') as f:
            master_config = json.load(f)
        
        installation_order = master_config['master_installation']['doctypes_installation_order']
        
        # Map DocType names to their file locations
        doctype_files = self.find_doctype_files()
        
        for doctype_name in installation_order:
            if doctype_name in doctype_files:
                file_path = doctype_files[doctype_name]
                self.install_single_doctype(doctype_name, file_path)
            else:
                self.warnings.append("DocType file not found: {0}".format(doctype_name))
    
    def find_doctype_files(self):
        """Find all DocType JSON files"""
        doctype_files = {}
        
        # Search in all subdirectories
        for module_dir in ['core', 'core_spc', 'fda_compliance', 'plant_equipment', 'quality_management']:
            module_path = self.base_path / module_dir
            if module_path.exists():
                for json_file in module_path.glob('*.json'):
                    # Extract DocType name from file
                    with open(json_file, 'r') as f:
                        try:
                            data = json.load(f)
                            if 'name' in data:
                                doctype_files[data['name']] = json_file
                        except:
                            pass
        
        return doctype_files
    
    def install_single_doctype(self, doctype_name, file_path):
        """Install a single DocType"""
        self.log("Installing DocType: {0}".format(doctype_name))
        
        # Copy file to site directory for import
        temp_file = "/tmp/{0}.json".format(doctype_name.lower().replace(' ', '_'))
        
        try:
            # Copy file
            subprocess.run("cp '{0}' '{1}'".format(file_path, temp_file), shell=True, check=True)
            
            # Import DocType
            result = self.run_command(
                "bench --site {0} data-import --type 'DocType' --file '{1}'".format(self.site_name, temp_file)
            )
            
            if result and result.returncode == 0:
                self.log("Successfully installed: {0}".format(doctype_name))
            else:
                self.errors.append("Failed to install DocType: {0}".format(doctype_name))
                
            # Clean up temp file
            os.remove(temp_file)
            
        except Exception as e:
            self.errors.append("Error installing {0}: {1}".format(doctype_name, str(e)))
    
    def setup_roles_and_permissions(self):
        """Set up roles and permissions"""
        self.log("Setting up roles and permissions...")
        
        # Load permission configuration
        perm_file = self.base_path / 'system_integration' / 'permissions' / 'role_permissions.json'
        with open(perm_file, 'r') as f:
            permissions = json.load(f)
        
        # Create roles
        for role_name, role_config in permissions['permission_structure']['roles'].items():
            self.create_role(role_name, role_config)
            
        # Apply permissions
        for role_name, role_config in permissions['permission_structure']['roles'].items():
            if 'permissions' in role_config:
                for doctype, perms in role_config['permissions'].items():
                    self.apply_permissions(role_name, doctype, perms)
    
    def create_role(self, role_name, role_config):
        """Create a role"""
        self.log("Creating role: {0}".format(role_name))
        
        # Check if role exists
        result = self.run_command(
            "bench --site {0} execute 'import frappe; print(frappe.db.exists(\"Role\", \"{1}\"))'".format(self.site_name, role_name)
        )
        
        if result and 'True' not in result.stdout:
            # Create role
            script = """
import frappe
role = frappe.get_doc({{
    'doctype': 'Role',
    'role_name': '{0}',
    'desk_access': {1},
    'is_custom': 1
}})
role.insert()
frappe.db.commit()
print("Created role: {0}")
""".format(role_name, 1 if role_config.get('user_type') == 'System User' else 0)
            
            result = self.run_command(
                "bench --site {0} execute '{1}'".format(self.site_name, script)
            )
    
    def apply_permissions(self, role_name, doctype, permissions):
        """Apply permissions for a role and doctype"""
        self.log("Applying permissions: {0} -> {1}".format(role_name, doctype))
        
        # Convert permissions to script
        perm_dict = {
            'role': role_name,
            'for_doctype': doctype,
            **permissions
        }
        
        script = """
import frappe
from frappe.permissions import add_permission

# Remove existing permissions
existing = frappe.get_all('Custom DocPerm', filters={{
    'role': '{0}',
    'parent': '{1}'
}})
for perm in existing:
    frappe.delete_doc('Custom DocPerm', perm.name)

# Add new permissions
add_permission('{1}', '{0}', {2}, 
               write={3}, create={4},
               delete={5}, submit={6},
               cancel={7}, amend={8})
               
frappe.db.commit()
print("Applied permissions for {0} on {1}")
""".format(
    role_name, doctype,
    perm_dict.get('read', 0),
    perm_dict.get('write', 0),
    perm_dict.get('create', 0),
    perm_dict.get('delete', 0),
    perm_dict.get('submit', 0),
    perm_dict.get('cancel', 0),
    perm_dict.get('amend', 0)
)
        
        result = self.run_command(
            "bench --site {0} execute '{1}'".format(self.site_name, script)
        )
    
    def install_workflows(self):
        """Install workflow configurations"""
        self.log("Installing workflows...")
        
        workflow_file = self.base_path / 'system_integration' / 'workflows' / 'workflow_configurations.json'
        with open(workflow_file, 'r') as f:
            workflows = json.load(f)
        
        for workflow_name, workflow_config in workflows['workflows']['workflow_definitions'].items():
            self.install_single_workflow(workflow_name, workflow_config)
    
    def install_single_workflow(self, workflow_name, workflow_config):
        """Install a single workflow"""
        self.log("Installing workflow: {0}".format(workflow_name))
        
        script = """
import frappe
import json

# Create workflow document
workflow_config = {0}

# Check if workflow exists
if frappe.db.exists('Workflow', '{1}'):
    workflow = frappe.get_doc('Workflow', '{1}')
else:
    workflow = frappe.new_doc('Workflow')
    workflow.workflow_name = '{1}'

workflow.document_type = workflow_config['document_type']
workflow.is_active = workflow_config.get('is_active', 1)

# Clear existing states and transitions
workflow.states = []
workflow.transitions = []

# Add states
for state in workflow_config.get('states', []):
    workflow.append('states', state)

# Add transitions  
for transition in workflow_config.get('transitions', []):
    workflow.append('transitions', transition)

workflow.save()
frappe.db.commit()
print("Installed workflow: {1}")
""".format(json.dumps(workflow_config), workflow_name)
        
        result = self.run_command(
            "bench --site {0} execute '{1}'".format(self.site_name, script)
        )
    
    def setup_fixtures(self):
        """Set up initial data fixtures"""
        self.log("Setting up fixtures...")
        
        master_file = self.base_path / 'system_integration' / 'installation' / 'master_installation.json'
        with open(master_file, 'r') as f:
            master_config = json.load(f)
        
        fixtures = master_config['master_installation']['fixtures']
        
        # Install roles
        for role_data in fixtures.get('roles', []):
            self.install_fixture_role(role_data)
            
        # Install UOMs
        for uom_data in fixtures.get('uoms', []):
            self.install_fixture_uom(uom_data)
            
        # Install parameter types
        for param_data in fixtures.get('parameter_types', []):
            self.install_fixture_parameter(param_data)
    
    def install_fixture_role(self, role_data):
        """Install role fixture"""
        script = """
import frappe
role_data = {0}

if not frappe.db.exists('Role', role_data['name']):
    role = frappe.get_doc(role_data)
    role.insert()
    frappe.db.commit()
    print("Created fixture role: {1}")
else:
    print("Role already exists: {1}")
""".format(json.dumps(role_data), role_data["name"])
        
        self.run_command("bench --site {0} execute '{1}'".format(self.site_name, script))
    
    def install_fixture_uom(self, uom_data):
        """Install UOM fixture"""
        script = """
import frappe
uom_data = {0}

if not frappe.db.exists('UOM', uom_data['uom_name']):
    uom = frappe.get_doc(uom_data)
    uom.insert()
    frappe.db.commit()
    print("Created UOM: {1}")
else:
    print("UOM already exists: {1}")
""".format(json.dumps(uom_data), uom_data["uom_name"])
        
        self.run_command("bench --site {0} execute '{1}'".format(self.site_name, script))
    
    def install_fixture_parameter(self, param_data):
        """Install parameter fixture"""
        script = """
import frappe
param_data = {0}

# Create parameter if it doesn't exist
if not frappe.db.exists('SPC Parameter Master', param_data['parameter_name']):
    param = frappe.get_doc(param_data)
    param.insert()
    frappe.db.commit()
    print("Created parameter: {1}")
else:
    print("Parameter already exists: {1}")
""".format(json.dumps(param_data), param_data["parameter_name"])
        
        self.run_command("bench --site {0} execute '{1}'".format(self.site_name, script))
    
    def install_validations(self):
        """Install validation scripts"""
        self.log("Installing validation scripts...")
        
        validation_file = self.base_path / 'system_integration' / 'validations' / 'spc_validation_rules.py'
        
        if validation_file.exists():
            # Copy validation file to site hooks
            target_path = "sites/{0}/hooks/spc_validation_rules.py".format(self.site_name)
            
            script = """
import frappe
from frappe.utils import cstr
import shutil

# Copy validation file
shutil.copy('{0}', '{1}')

# Add hooks for validations
hooks_content = '''
# SPC Validation Hooks
doc_events = {{
    "SPC Data Point": {{
        "validate": "spc_validation_rules.validate_spc_data_point"
    }},
    "SPC Specification": {{
        "validate": "spc_validation_rules.validate_spc_specification"
    }},
    "SPC Alert": {{
        "validate": "spc_validation_rules.validate_spc_alert"
    }},
    "SPC Electronic Signature": {{
        "validate": "spc_validation_rules.validate_electronic_signature"
    }},
    "SPC Deviation": {{
        "validate": "spc_validation_rules.validate_deviation"
    }}
}}
'''

with open("sites/{2}/hooks.py", 'a') as f:
    f.write(hooks_content)

print('Installed validation scripts')
""".format(str(validation_file), target_path, self.site_name)
            
            self.run_command("bench --site {0} execute '{1}'".format(self.site_name, script))
    
    def configure_automation(self):
        """Configure automation scripts and scheduled jobs"""
        self.log("Configuring automation...")
        
        automation_file = self.base_path / 'system_integration' / 'scripts' / 'automation_scripts.py'
        
        if automation_file.exists():
            # Copy automation scripts
            target_path = "sites/{0}/hooks/automation_scripts.py".format(self.site_name)
            
            script = """
import shutil
shutil.copy('{0}', '{1}')

# Set up scheduled tasks
from frappe import get_doc

# Daily SPC maintenance task
if not frappe.db.exists('Scheduled Job Type', 'daily_spc_maintenance'):
    job = get_doc({{
        'doctype': 'Scheduled Job Type',
        'method': 'automation_scripts.daily_spc_maintenance',
        'frequency': 'Daily',
        'create_log': 1
    }})
    job.insert()

# Hourly SPC checks
if not frappe.db.exists('Scheduled Job Type', 'hourly_spc_checks'):
    job = get_doc({{
        'doctype': 'Scheduled Job Type', 
        'method': 'automation_scripts.hourly_spc_checks',
        'frequency': 'Hourly',
        'create_log': 1
    }})
    job.insert()

frappe.db.commit()
print('Configured automation scripts')
""".format(str(automation_file), target_path)
            
            self.run_command("bench --site {0} execute '{1}'".format(self.site_name, script))
    
    def verify_installation(self):
        """Verify installation was successful"""
        self.log("Verifying installation...")
        
        verification_script = """
import frappe

# Check key DocTypes
key_doctypes = [
    'Plant Configuration', 'SPC Workstation', 'SPC Parameter Master', 
    'SPC Specification', 'SPC Data Point', 'SPC Alert', 
    'SPC Process Capability', 'SPC Report', 'SPC Corrective Action', 
    'SPC Deviation', 'SPC Electronic Signature', 'SPC Audit Trail'
]

missing_doctypes = []
for doctype in key_doctypes:
    if not frappe.db.exists('DocType', doctype):
        missing_doctypes.append(doctype)

if missing_doctypes:
    print("Missing DocTypes: {0}".format(missing_doctypes))
else:
    print('All key DocTypes installed successfully')

# Check roles
key_roles = ['Quality User', 'Inspector User', 'Manufacturing User']
missing_roles = []
for role in key_roles:
    if not frappe.db.exists('Role', role):
        missing_roles.append(role)

if missing_roles:
    print("Missing Roles: {0}".format(missing_roles))
else:
    print('All key Roles created successfully')

# Check workflows
key_workflows = ['SPC Alert Workflow', 'SPC Process Capability Workflow']
missing_workflows = []
for workflow in key_workflows:
    if not frappe.db.exists('Workflow', workflow):
        missing_workflows.append(workflow)

if missing_workflows:
    print("Missing Workflows: {0}".format(missing_workflows))
else:
    print('All key Workflows installed successfully')

print('\\nInstallation verification complete')
"""
        
        result = self.run_command("bench --site {0} execute '{1}'".format(self.site_name, verification_script))
        return result and result.returncode == 0
    
    def generate_installation_report(self):
        """Generate installation report"""
        report = """
# SPC ERPNext Installation Report

**Date:** {0}
**Site:** {1}

## Installation Summary

**Status:** {2}
**Errors:** {3}
**Warnings:** {4}

## Errors
{5}

## Warnings
{6}

## Installation Log
Full log available in: {7}

## Next Steps

1. **Configure Plant Settings**
   - Create Plant Configuration records for your facilities
   - Set up Workstations for each plant
   - Define SPC Parameter Masters for your processes

2. **Set Up Users**
   - Assign users to appropriate roles (Quality User, Inspector User, etc.)
   - Configure plant-based permissions for multi-tenant access
   - Set up bot users for automated data collection

3. **Configure Parameters**
   - Set up SPC Specifications with appropriate limits
   - Configure statistical control limits
   - Set up automated alert thresholds

4. **Test System**
   - Create test data points to verify alert generation
   - Test workflow transitions
   - Verify electronic signature functionality

5. **Integration**
   - Configure PLC Integration for automated data collection
   - Set up email notifications
   - Configure report generation schedules

## Support

For support and customization, refer to the documentation in each module directory.
""".format(
    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    self.site_name,
    'SUCCESS' if len(self.errors) == 0 else 'FAILED',
    len(self.errors),
    len(self.warnings),
    '\n'.join(["- {0}".format(error) for error in self.errors]) if self.errors else 'None',
    '\n'.join(["- {0}".format(warning) for warning in self.warnings]) if self.warnings else 'None',
    self.log_file
)
        
        report_file = "spc_installation_report_{0}.md".format(datetime.now().strftime('%Y%m%d_%H%M%S'))
        with open(report_file, 'w') as f:
            f.write(report)
        
        self.log("Installation report generated: {0}".format(report_file))
        return report_file
    
    def run_full_installation(self):
        """Run complete installation process"""
        self.log("Starting SPC ERPNext Installation...")
        
        try:
            # Step 1: Verify prerequisites
            if not self.verify_prerequisites():
                self.log("Prerequisites verification failed", 'ERROR')
                return False
            
            # Step 2: Install DocTypes
            self.install_doctypes()
            
            # Step 3: Set up roles and permissions
            self.setup_roles_and_permissions()
            
            # Step 4: Install workflows
            self.install_workflows()
            
            # Step 5: Set up fixtures
            self.setup_fixtures()
            
            # Step 6: Install validations
            self.install_validations()
            
            # Step 7: Configure automation
            self.configure_automation()
            
            # Step 8: Verify installation
            verification_success = self.verify_installation()
            
            # Step 9: Generate report
            report_file = self.generate_installation_report()
            
            if len(self.errors) == 0:
                self.log("SPC ERPNext Installation completed successfully!")
                self.log("Installation report: {0}".format(report_file))
                return True
            else:
                self.log("Installation completed with {0} errors".format(len(self.errors)), 'ERROR')
                return False
                
        except Exception as e:
            self.log("Installation failed with exception: {0}".format(str(e)), 'ERROR')
            self.errors.append("Installation exception: {0}".format(str(e)))
            self.generate_installation_report()
            return False


def main():
    parser = argparse.ArgumentParser(description='Install SPC ERPNext System')
    parser.add_argument('site_name', help='ERPNext site name')
    parser.add_argument('--base-path', default='/workspace/erpnext_doctypes', 
                       help='Base path to SPC system files')
    
    args = parser.parse_args()
    
    installer = SPCInstaller(args.site_name, args.base_path)
    success = installer.run_full_installation()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
