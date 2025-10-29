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
        self.log_file = f"spc_installation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.errors = []
        self.warnings = []
        
    def log(self, message, level='INFO'):
        """Log installation progress"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        
        with open(self.log_file, 'a') as f:
            f.write(log_message + '\n')
    
    def run_command(self, command, check_output=True):
        """Execute a command and handle errors"""
        try:
            self.log(f"Executing: {command}")
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                check=check_output
            )
            
            if result.stdout:
                self.log(f"Output: {result.stdout.strip()}")
            if result.stderr and check_output:
                self.log(f"Error: {result.stderr.strip()}", 'ERROR')
                self.errors.append(fr"Command failed: {command}\nError: {result.stderr}")
                
            return result
            
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {command}", 'ERROR')
            self.log(f"Error: {e.stderr}", 'ERROR')
            self.errors.append(fr"Command failed: {command}\nError: {e.stderr}")
            return None
    
    def verify_prerequisites(self):
        """Verify ERPNext installation and requirements"""
        self.log("Verifying prerequisites...")
        
        # Check if site exists
        result = self.run_command(f"bench --site {self.site_name} version")
        if not result or result.returncode != 0:
            self.errors.append(f"Site {self.site_name} not found or not accessible")
            return False
            
        # Check ERPNext version
        result = self.run_command(f"bench --site {self.site_name} execute 'import erpnext; print(erpnext.__version__)'")
        if result and result.returncode == 0:
            erpnext_version = result.stdout.strip().split('\n')[-1]
            self.log(f"ERPNext version: {erpnext_version}")
        else:
            self.warnings.append("Could not determine ERPNext version")
            
        # Check required Python packages
        required_packages = ['statistics', 'dateutil']
        for package in required_packages:
            result = self.run_command(f"python -c 'import {package}'")
            if result and result.returncode != 0:
                self.warnings.append(f"Python package {package} not found")
                
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
                self.warnings.append(f"DocType file not found: {doctype_name}")
    
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
        self.log(f"Installing DocType: {doctype_name}")
        
        # Copy file to site directory for import
        temp_file = f"/tmp/{doctype_name.lower().replace(' ', '_')}.json"
        
        try:
            # Copy file
            subprocess.run(f"cp '{file_path}' '{temp_file}'", shell=True, check=True)
            
            # Import DocType
            result = self.run_command(
                f"bench --site {self.site_name} data-import --type 'DocType' --file '{temp_file}'"
            )
            
            if result and result.returncode == 0:
                self.log(f"Successfully installed: {doctype_name}")
            else:
                self.errors.append(f"Failed to install DocType: {doctype_name}")
                
            # Clean up temp file
            os.remove(temp_file)
            
        except Exception as e:
            self.errors.append(f"Error installing {doctype_name}: {str(e)}")
    
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
        self.log(f"Creating role: {role_name}")
        
        # Check if role exists
        result = self.run_command(
            fr"bench --site {self.site_name} execute 'import frappe; print(frappe.db.exists(\"Role\", \"{role_name}\"))'"
        )
        
        if result and 'True' not in result.stdout:
            # Create role
            script = f"""
import frappe
role = frappe.get_doc({{
    'doctype': 'Role',
    'role_name': '{role_name}',
    'desk_access': {1 if role_config.get('user_type') == 'System User' else 0},
    'is_custom': 1
}})
role.insert()
frappe.db.commit()
print(f'Created role: {role_name}')
"""
            
            result = self.run_command(
                f"bench --site {self.site_name} execute '{script}'"
            )
    
    def apply_permissions(self, role_name, doctype, permissions):
        """Apply permissions for a role and doctype"""
        self.log(f"Applying permissions: {role_name} -> {doctype}")
        
        # Convert permissions to script
        perm_dict = {
            'role': role_name,
            'for_doctype': doctype,
            **permissions
        }
        
        script = f"""
import frappe
from frappe.permissions import add_permission

# Remove existing permissions
existing = frappe.get_all('Custom DocPerm', filters={{
    'role': '{role_name}',
    'parent': '{doctype}'
}})
for perm in existing:
    frappe.delete_doc('Custom DocPerm', perm.name)

# Add new permissions
add_permission('{doctype}', '{role_name}', {perm_dict.get('read', 0)}, 
               write={perm_dict.get('write', 0)}, create={perm_dict.get('create', 0)},
               delete={perm_dict.get('delete', 0)}, submit={perm_dict.get('submit', 0)},
               cancel={perm_dict.get('cancel', 0)}, amend={perm_dict.get('amend', 0)})
               
frappe.db.commit()
print(f'Applied permissions for {role_name} on {doctype}')
"""
        
        result = self.run_command(
            f"bench --site {self.site_name} execute '{script}'"
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
        self.log(f"Installing workflow: {workflow_name}")
        
        script = f"""
import frappe
import json

# Create workflow document
workflow_config = {json.dumps(workflow_config)}

# Check if workflow exists
if frappe.db.exists('Workflow', '{workflow_name}'):
    workflow = frappe.get_doc('Workflow', '{workflow_name}')
else:
    workflow = frappe.new_doc('Workflow')
    workflow.workflow_name = '{workflow_name}'

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
print(f'Installed workflow: {workflow_name}')
"""
        
        result = self.run_command(
            f"bench --site {self.site_name} execute '{script}'"
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
        script = f"""
import frappe
role_data = {json.dumps(role_data)}

if not frappe.db.exists('Role', role_data['name']):
    role = frappe.get_doc(role_data)
    role.insert()
    frappe.db.commit()
    print(f'Created fixture role: {{role_data["name"]}}')
else:
    print(f'Role already exists: {{role_data["name"]}}')
"""
        
        self.run_command(f"bench --site {self.site_name} execute '{script}'")
    
    def install_fixture_uom(self, uom_data):
        """Install UOM fixture"""
        script = f"""
import frappe
uom_data = {json.dumps(uom_data)}

if not frappe.db.exists('UOM', uom_data['uom_name']):
    uom = frappe.get_doc(uom_data)
    uom.insert()
    frappe.db.commit()
    print(f'Created UOM: {{uom_data["uom_name"]}}')
else:
    print(f'UOM already exists: {{uom_data["uom_name"]}}')
"""
        
        self.run_command(f"bench --site {self.site_name} execute '{script}'")
    
    def install_fixture_parameter(self, param_data):
        """Install parameter fixture"""
        script = f"""
import frappe
param_data = {json.dumps(param_data)}

# Create parameter if it doesn't exist
if not frappe.db.exists('SPC Parameter Master', param_data['parameter_name']):
    param = frappe.get_doc(param_data)
    param.insert()
    frappe.db.commit()
    print(f'Created parameter: {{param_data["parameter_name"]}}')
else:
    print(f'Parameter already exists: {{param_data["parameter_name"]}}')
"""
        
        self.run_command(f"bench --site {self.site_name} execute '{script}'")
    
    def install_validations(self):
        """Install validation scripts"""
        self.log("Installing validation scripts...")
        
        validation_file = self.base_path / 'system_integration' / 'validations' / 'spc_validation_rules.py'
        
        if validation_file.exists():
            # Copy validation file to site hooks
            target_path = f"sites/{self.site_name}/hooks/spc_validation_rules.py"
            
            script = f"""
import frappe
from frappe.utils import cstr
import shutil

# Copy validation file
shutil.copy('{validation_file}', '{target_path}')

# Add hooks for validations
hooks_content = '''\n# SPC Validation Hooks\ndoc_events = {{\n    "SPC Data Point": {{\n        "validate": "spc_validation_rules.validate_spc_data_point"\n    }},\n    "SPC Specification": {{\n        "validate": "spc_validation_rules.validate_spc_specification"\n    }},\n    "SPC Alert": {{\n        "validate": "spc_validation_rules.validate_spc_alert"\n    }},\n    "SPC Electronic Signature": {{\n        "validate": "spc_validation_rules.validate_electronic_signature"\n    }},\n    "SPC Deviation": {{\n        "validate": "spc_validation_rules.validate_deviation"\n    }}\n}}\n'''

with open(f'sites/{self.site_name}/hooks.py', 'a') as f:
    f.write(hooks_content)

print('Installed validation scripts')
"""
            
            self.run_command(f"bench --site {self.site_name} execute '{script}'")
    
    def configure_automation(self):
        """Configure automation scripts and scheduled jobs"""
        self.log("Configuring automation...")
        
        automation_file = self.base_path / 'system_integration' / 'scripts' / 'automation_scripts.py'
        
        if automation_file.exists():
            # Copy automation scripts
            target_path = f"sites/{self.site_name}/hooks/automation_scripts.py"
            
            script = f"""
import shutil
shutil.copy('{automation_file}', '{target_path}')

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
"""
            
            self.run_command(f"bench --site {self.site_name} execute '{script}'")
    
    def verify_installation(self):
        """Verify installation was successful"""
        self.log("Verifying installation...")
        
        verification_script = fr"""
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
    print(f'Missing DocTypes: {{missing_doctypes}}')
else:
    print('All key DocTypes installed successfully')

# Check roles
key_roles = ['Quality User', 'Inspector User', 'Manufacturing User']
missing_roles = []
for role in key_roles:
    if not frappe.db.exists('Role', role):
        missing_roles.append(role)

if missing_roles:
    print(f'Missing Roles: {{missing_roles}}')
else:
    print('All key Roles created successfully')

# Check workflows
key_workflows = ['SPC Alert Workflow', 'SPC Process Capability Workflow']
missing_workflows = []
for workflow in key_workflows:
    if not frappe.db.exists('Workflow', workflow):
        missing_workflows.append(workflow)

if missing_workflows:
    print(f'Missing Workflows: {{missing_workflows}}')
else:
    print('All key Workflows installed successfully')

print('\nInstallation verification complete')
"""
        
        result = self.run_command(f"bench --site {self.site_name} execute '{verification_script}'")
        return result and result.returncode == 0
    
    def generate_installation_report(self):
        """Generate installation report"""
        report = fr"""
# SPC ERPNext Installation Report

**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Site:** {self.site_name}

## Installation Summary

**Status:** {'SUCCESS' if len(self.errors) == 0 else 'FAILED'}
**Errors:** {len(self.errors)}
**Warnings:** {len(self.warnings)}

## Errors
{'\n'.join([f'- {error}' for error in self.errors]) if self.errors else 'None'}

## Warnings
{'\n'.join([f'- {warning}' for warning in self.warnings]) if self.warnings else 'None'}

## Installation Log
Full log available in: {self.log_file}

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
"""
        
        report_file = f"spc_installation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, 'w') as f:
            f.write(report)
        
        self.log(f"Installation report generated: {report_file}")
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
                self.log(f"Installation report: {report_file}")
                return True
            else:
                self.log(f"Installation completed with {len(self.errors)} errors", 'ERROR')
                return False
                
        except Exception as e:
            self.log(f"Installation failed with exception: {str(e)}", 'ERROR')
            self.errors.append(f"Installation exception: {str(e)}")
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
