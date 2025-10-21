"""
AMB W SPC Installation Script - Clean Version
Version: 2.0.4
"""

import frappe
import os

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

def before_install():
    """Run before app installation"""
    print("🔧 Preparing AMB W SPC installation...")
    pass

def before_uninstall():
    """Cleanup before uninstalling"""
    print("🧹 Cleaning up AMB W SPC before uninstall...")
    pass

def before_tests():
    """Run before tests"""
    print("🧪 Preparing tests for AMB W SPC...")
    pass

if __name__ == "__main__":
    after_install()
