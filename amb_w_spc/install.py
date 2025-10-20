"""
AMB W SPC Installation Script
Version: 2.0.3
"""

import frappe
import os
import json

def after_install():
    """
    Post-installation setup for AMB W SPC
    """
    try:
        print("🚀 Starting AMB W SPC installation...")
        
        # Create required directories
        create_required_directories()
        
        # Setup default settings
        setup_default_settings()
        
        # Create standard workspace
        create_standard_workspace()
        
        print("✅ AMB W SPC installation completed successfully!")
        
    except Exception as e:
        print(f"❌ Installation error: {str(e)}")
        frappe.log_error(f"AMB W SPC Installation Failed: {str(e)}")

def create_required_directories():
    """Create necessary directories"""
    directories = [
        "private/files/amb_w_spc",
        "public/files/amb_w_spc"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"📁 Created directory: {directory}")

def setup_default_settings():
    """Setup default application settings"""
    try:
        # Create Operator Management Settings if doesn't exist
        if not frappe.db.exists("Operator Management Settings", "Operator Management Settings"):
            doc = frappe.get_doc({
                "doctype": "Operator Management Settings",
                "shift_duration": 8,
                "overtime_threshold": 2,
                "auto_attendance": 1
            })
            doc.insert(ignore_permissions=True)
            print("✅ Created Operator Management Settings")
            
    except Exception as e:
        print(f"⚠️  Could not create settings: {str(e)}")

def create_standard_workspace():
    """Create standard workspace for the app"""
    try:
        workspace_data = {
            "doctype": "Workspace",
            "label": "AMB W SPC",
            "title": "AMB W SPC",
            "sequence_id": 1,
            "public": 1,
            "is_hidden": 0,
            "extends": "Manufacturing",
            "shortcuts": [
                {
                    "type": "Dashboard",
                    "link_to": "SPC Control Chart",
                    "format_type": "Link"
                }
            ]
        }
        
        if not frappe.db.exists("Workspace", "AMB W SPC"):
            workspace = frappe.get_doc(workspace_data)
            workspace.insert(ignore_permissions=True)
            print("✅ Created AMB W SPC Workspace")
            
    except Exception as e:
        print(f"⚠️  Could not create workspace: {str(e)}")
# Add the missing functions to install.py

def before_install():
    """Run before app installation - minimal implementation"""
    print("🔧 Preparing AMB W SPC installation...")
    pass


def before_uninstall():
    """
    Cleanup before uninstalling the app
    """
    print("🧹 Cleaning up AMB W SPC before uninstall...")
    # Add any cleanup logic here

def before_tests():
    """Run before tests - minimal implementation"""
    print("🧪 Preparing tests for AMB W SPC...")
    pass

# Main execution block
if __name__ == "__main__":
    after_install()
