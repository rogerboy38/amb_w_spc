"""
Frappe v15.84.0 Module Installation Patch
==========================================

This patch fixes the incompatibility between Frappe v15.84.0 installer and v15 database schema.

PROBLEM:
- Frappe v15.84.0 installer tries to use v16 field names (parent, parentfield, parenttype)
- But v15 database schema doesn't have these fields
- Result: "Unknown column 'parent' in 'INSERT INTO'" error

SOLUTION:
- This patch automatically runs during app installation
- Uses v15-compatible module creation methods
- Provides multiple fallback methods for maximum reliability
- Logs all activities for troubleshooting

AUTOMATIC EXECUTION:
- Registered in patches.txt
- Runs automatically when app is installed or updated
- No manual intervention required on Frappe Cloud
"""

import frappe
from frappe import _

def execute():
    """
    Main patch execution function
    
    This function is called automatically by Frappe's patch system
    during app installation or update.
    """
    
    frappe.logger().info("=" * 60)
    frappe.logger().info("STARTING AMB-W SPC v15.84.0 COMPATIBILITY PATCH")
    frappe.logger().info("=" * 60)
    
    try:
        # Log environment information
        frappe_version = getattr(frappe, '__version__', 'unknown')
        frappe.logger().info(f"Detected Frappe version: {frappe_version}")
        
        # Import and run our proven module creation function
        from amb_w_spc.install import create_modules_v15_safe
        
        frappe.logger().info("Executing enhanced module creation function...")
        success = create_modules_v15_safe()
        
        if success:
            frappe.logger().info("✅ AMB-W SPC modules created successfully via compatibility patch")
            frappe.logger().info("Modules created: core_spc, spc_quality_management, sfc_manufacturing, operator_management, shop_floor_control, plant_equipment, real_time_monitoring, sensor_management, system_integration, fda_compliance")
            
            # Log successful completion
            frappe.logger().info("=" * 60)
            frappe.logger().info("PATCH EXECUTION COMPLETED SUCCESSFULLY")
            frappe.logger().info("=" * 60)
            
        else:
            frappe.logger().warning("⚠️ AMB-W SPC module creation completed with some warnings")
            frappe.logger().warning("Check the detailed logs above for specific issues")
            
    except ImportError as e:
        frappe.logger().error(f"❌ Could not import module creation function: {e}")
        frappe.logger().error("Attempting direct module creation as fallback...")
        
        # Fallback to direct module creation if import fails
        try:
            success = create_modules_direct()
            if success:
                frappe.logger().info("✅ Fallback method succeeded")
            else:
                frappe.logger().error("❌ Fallback method also failed")
                raise Exception("All module creation methods failed")
        except Exception as fallback_error:
            frappe.logger().error(f"❌ Fallback method failed: {fallback_error}")
            raise
            
    except Exception as e:
        frappe.logger().error(f"❌ Failed to create AMB-W SPC modules via patch: {e}")
        frappe.logger().error("=" * 60)
        frappe.logger().error("PATCH EXECUTION FAILED")
        frappe.logger().error("=" * 60)
        raise


def create_modules_direct():
    """
    Direct module creation as emergency fallback method
    
    This uses the most basic, proven SQL approach that works
    even when the main install module cannot be imported.
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
    
    frappe.logger().info("Using direct SQL module creation (emergency fallback)")
    
    created_count = 0
    skipped_count = 0
    
    for module in modules:
        try:
            # Check if module already exists
            if frappe.db.exists('Module Def', module):
                frappe.logger().info(f"⏭️ Module '{module}' already exists, skipping")
                skipped_count += 1
                continue
            
            # Use the most compatible SQL method
            frappe.db.sql("""
                INSERT INTO `tabModule Def`
                (`name`, `module_name`, `app_name`, `creation`, `modified`, 
                 `modified_by`, `owner`, `docstatus`, `idx`, `custom`)
                VALUES (%s, %s, %s, NOW(), NOW(), %s, %s, 0, 0, 0)
            """, (
                module,
                module, 
                'amb_w_spc',
                frappe.session.user,
                frappe.session.user
            ))
            
            frappe.logger().info(f"✅ Created module '{module}' using direct SQL")
            created_count += 1
            
        except Exception as e:
            frappe.logger().error(f"❌ Failed to create module '{module}': {e}")
    
    # Commit all changes
    frappe.db.commit()
    
    frappe.logger().info(f"Direct module creation completed. Created: {created_count}, Skipped: {skipped_count}")
    
    return (created_count + skipped_count) == len(modules)