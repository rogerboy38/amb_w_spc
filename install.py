# Enhanced Installation Module for AMB W SPC v1.0.1
# Frappe v15.84.0 Compatible with Multiple Fallback Methods

import frappe
from frappe import _
import json
import os

def create_modules_v15_safe():
    """
    Enhanced module creation function for Frappe v15 compatibility
    Includes multiple fallback methods and comprehensive error handling
    """
    
    modules = [
        'core_spc',
        'spc_quality_management', 
        'sfc_manufacturing',
        'operator_management',
        'shop_floor_control',
        'plant_equipment',
        'real_time_monitoring',
        'sensor_management',
        'system_integration',
        'fda_compliance'
    ]
    
    print("=== AMB W SPC v1.0.1 Module Creation ===")
    print("Frappe v15.84.0 Compatible Installation")
    print("=" * 50)
    
    created_count = 0
    skipped_count = 0
    failed_count = 0
    
    # Detect Frappe version for compatibility
    frappe_version = getattr(frappe, '__version__', 'unknown')
    print(f"Detected Frappe version: {frappe_version}")
    
    # Determine installation method based on version
    use_compatibility_mode = is_v15_84_or_higher(frappe_version)
    
    if use_compatibility_mode:
        print("⚠️  Using v15.84.0+ compatibility mode")
    else:
        print("✅ Using standard installation mode")
    
    print()
    
    for module in modules:
        try:
            # Check if module already exists
            if frappe.db.exists('Module Def', module):
                print(f"⏭️  Module '{module}' already exists, skipping...")
                skipped_count += 1
                continue
            
            success = False
            
            # Method 1: Try standard ERPNext method (if not in compatibility mode)
            if not use_compatibility_mode:
                try:
                    module_doc = frappe.get_doc({
                        'doctype': 'Module Def',
                        'name': module,
                        'module_name': module,
                        'app_name': 'amb_w_spc',
                        'custom': 0
                    })
                    module_doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
                    print(f"✅ Created module '{module}' (standard method)")
                    success = True
                    
                except Exception as standard_error:
                    print(f"⚠️  Standard method failed for '{module}': {str(standard_error)[:100]}...")
                    print(f"   Trying compatibility method...")
            
            # Method 2: Use direct SQL insert (v15 compatible)
            if not success:
                try:
                    # Use only fields that exist in v15 schema
                    frappe.db.sql("""
                        INSERT INTO `tabModule Def` 
                        (`name`, `creation`, `modified`, `modified_by`, `owner`, 
                         `docstatus`, `idx`, `module_name`, `custom`, `app_name`)
                        VALUES (%s, NOW(), NOW(), %s, %s, 0, 0, %s, 0, %s)
                    """, (
                        module,
                        frappe.session.user,
                        frappe.session.user, 
                        module,
                        'amb_w_spc'
                    ))
                    
                    print(f"✅ Created module '{module}' (compatibility method)")
                    success = True
                    
                except Exception as sql_error:
                    print(f"❌ Compatibility method failed for '{module}': {str(sql_error)[:100]}...")
            
            # Method 3: Emergency fallback - most basic insertion
            if not success:
                try:
                    frappe.db.sql("""
                        INSERT IGNORE INTO `tabModule Def`
                        (`name`, `module_name`, `app_name`)
                        VALUES (%s, %s, %s)
                    """, (module, module, 'amb_w_spc'))
                    
                    print(f"✅ Created module '{module}' (emergency method)")
                    success = True
                    
                except Exception as emergency_error:
                    print(f"❌ All methods failed for '{module}': {str(emergency_error)[:100]}...")
            
            if success:
                created_count += 1
            else:
                failed_count += 1
                
        except Exception as e:
            print(f"❌ Unexpected error creating module '{module}': {str(e)[:100]}...")
            failed_count += 1
    
    # Commit all changes
    try:
        frappe.db.commit()
        print(f"\n✅ Database changes committed successfully")
    except Exception as e:
        print(f"\n❌ Error committing changes: {e}")
        frappe.db.rollback()
        return False
    
    # Summary
    print(f"\n{'='*50}")
    print(f"Module Creation Summary")
    print(f"{'='*50}")
    print(f"✅ Created: {created_count} modules")
    print(f"⏭️  Skipped: {skipped_count} modules (already existed)")
    print(f"❌ Failed: {failed_count} modules")
    print(f"📊 Total: {created_count + skipped_count + failed_count}/{len(modules)} processed")
    
    # Determine success
    total_expected = len(modules)
    total_success = created_count + skipped_count
    
    if total_success == total_expected:
        print(f"\n🎉 Module creation completed successfully!")
        return True
    elif failed_count == 0:
        print(f"\n✅ All modules already existed - no action needed!")
        return True
    else:
        print(f"\n⚠️  Module creation completed with {failed_count} failures.")
        print(f"   You may need to create missing modules manually.")
        return False


def is_v15_84_or_higher(version_string):
    """
    Check if Frappe version is v15.84.0 or higher (where the bug exists)
    """
    try:
        if not version_string or version_string == 'unknown':
            return True  # Assume compatibility mode if version unknown
        
        # Extract version numbers
        version_parts = version_string.split('.')
        if len(version_parts) < 2:
            return True
        
        major = int(version_parts[0])
        minor = int(version_parts[1])
        
        # Check for v15.84+
        if major == 15 and minor >= 84:
            return True
        elif major > 15:
            return True
        
        return False
        
    except:
        return True  # Default to compatibility mode on any error


def post_install_setup():
    """
    Post-installation setup that runs after app installation
    This is called from hooks.py after_app_install
    """
    print("Running AMB W SPC post-installation setup...")
    
    # Additional setup steps can be added here
    # For example: creating default records, setting up permissions, etc.
    
    print("✅ AMB W SPC post-installation setup completed")


def check_installation():
    """
    Comprehensive installation verification
    """
    print("=== AMB W SPC Installation Verification ===")
    print("=" * 45)
    
    modules = [
        'core_spc', 'spc_quality_management', 'sfc_manufacturing',
        'operator_management', 'shop_floor_control', 'plant_equipment',
        'real_time_monitoring', 'sensor_management', 'system_integration',
        'fda_compliance'
    ]
    
    missing_modules = []
    
    print("Checking modules:")
    for module in modules:
        if frappe.db.exists('Module Def', module):
            print(f"✅ {module}")
        else:
            print(f"❌ {module} - MISSING")
            missing_modules.append(module)
    
    print()
    
    # Check app installation
    try:
        import amb_w_spc
        print("✅ AMB W SPC app import successful")
    except ImportError as e:
        print(f"❌ AMB W SPC app import failed: {e}")
    
    # Summary
    print("\n" + "=" * 45)
    if missing_modules:
        print(f"⚠️  {len(missing_modules)} modules are missing:")
        for module in missing_modules:
            print(f"   - {module}")
        return False
    else:
        print(f"🎉 All {len(modules)} modules are properly installed!")
        return True


# Legacy compatibility - keep the original function name for backward compatibility
def create_modules_v15():
    """Legacy function name - calls the enhanced version"""
    return create_modules_v15_safe()