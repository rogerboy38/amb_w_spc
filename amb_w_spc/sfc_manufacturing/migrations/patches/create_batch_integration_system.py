# patches/create_batch_integration_system.py
import frappe

def execute():
    """Patch to create Batch Integration System"""
    print("Creating Batch Integration System...")
    
    # Run the migration
    from amb_w_spc.sfc_manufacturing.migration.batch_amb_migration import execute_batch_amb_migration
    result = execute_batch_amb_migration()
    
    if result.get("success"):
        print("Batch Integration System created successfully!")
    else:
        print(f"Batch Integration System creation failed: {result.get('message')}")
