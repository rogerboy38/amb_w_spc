import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
import json
import os

def execute():
    """Install warehouse-batch integration custom fields and setup"""
    print("Installing Warehouse-Batch Integration...")
    
    try:
        # Install custom fields
        install_warehouse_batch_custom_fields()
        
        # Setup warehouse batch tracking
        setup_warehouse_batch_tracking()
        
        # Create default warehouse batch configuration
        create_default_warehouse_batch_config()
        
        # Setup batch processing history integration
        setup_batch_processing_history_integration()
        
        print("Warehouse-Batch Integration installed successfully")
        
    except Exception as e:
        print(f"Error installing Warehouse-Batch Integration: {str(e)}")
        frappe.log_error(f"Warehouse-Batch Integration installation failed: {str(e)}")

def install_warehouse_batch_custom_fields():
    """Install custom fields for warehouse-batch integration"""
    print("Installing warehouse-batch custom fields...")
    
    # List of custom field files to process
    custom_field_files = [
        "custom_field_warehouse_batch.json",
        "custom_field_material_assessment_batch.json",
        "custom_field_work_order_batch.json"
    ]
    
    app_path = frappe.get_app_path("amb_w_spc")
    fixtures_path = os.path.join(app_path, "sfc_manufacturing", "fixtures")
    
    for file_name in custom_field_files:
        file_path = os.path.join(fixtures_path, file_name)
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    custom_fields = json.load(f)
                
                # Group custom fields by doctype
                doctype_fields = {}
                for field in custom_fields:
                    dt = field.get('dt')
                    if dt not in doctype_fields:
                        doctype_fields[dt] = []
                    doctype_fields[dt].append(field)
                
                # Create custom fields for each doctype
                for doctype, fields in doctype_fields.items():
                    if not frappe.db.exists("DocType", doctype):
                        print(f"DocType {doctype} does not exist, skipping...")
                        continue
                        
                    print(f"Creating custom fields for {doctype}...")
                    
                    # Convert to the format expected by create_custom_fields
                    custom_fields_dict = {doctype: []}
                    
                    for field in fields:
                        field_dict = {
                            'fieldname': field['fieldname'],
                            'label': field['label'],
                            'fieldtype': field['fieldtype'],
                            'insert_after': field.get('insert_after'),
                            'options': field.get('options'),
                            'default': field.get('default'),
                            'reqd': field.get('reqd', 0),
                            'read_only': field.get('read_only', 0),
                            'hidden': field.get('hidden', 0),
                            'description': field.get('description'),
                            'depends_on': field.get('depends_on'),
                            'collapsible': field.get('collapsible', 0),
                            'collapsed': field.get('collapsed', 0),
                            'in_list_view': field.get('in_list_view', 0),
                            'in_standard_filter': field.get('in_standard_filter', 0),
                            'precision': field.get('precision'),
                            'unique': field.get('unique', 0)
                        }
                        
                        # Remove None values
                        field_dict = {k: v for k, v in field_dict.items() if v is not None}
                        
                        custom_fields_dict[doctype].append(field_dict)
                    
                    # Create the custom fields
                    create_custom_fields(custom_fields_dict, update=True)
                    
                print(f"Successfully processed {file_name}")
                
            except Exception as e:
                print(f"Error processing {file_name}: {str(e)}")
                frappe.log_error(f"Error processing custom fields file {file_name}: {str(e)}")
        else:
            print(f"Custom fields file not found: {file_path}")

def setup_warehouse_batch_tracking():
    """Setup warehouse batch tracking configuration"""
    print("Setting up warehouse batch tracking...")
    
    try:
        # Update existing warehouses with batch tracking defaults
        warehouses = frappe.get_all("Warehouse", fields=["name", "warehouse_type"])
        
        for warehouse in warehouses:
            # Set default batch tracking based on warehouse type
            updates = {
                "custom_enable_batch_tracking": 1
            }
            
            # Set plant code based on warehouse name
            if " - " in warehouse.name:
                plant_code = warehouse.name.split(" - ")[-1]
                updates["custom_plant_code"] = plant_code
            
            # Set zone assignment based on warehouse type
            if warehouse.warehouse_type:
                if "finished" in warehouse.warehouse_type.lower():
                    updates["custom_zone_assignment"] = "Green Zone"
                    updates["custom_temperature_control"] = 1
                    updates["custom_target_temperature"] = 20.0
                elif "raw" in warehouse.warehouse_type.lower():
                    updates["custom_zone_assignment"] = "Transit Zone"
                    updates["custom_temperature_control"] = 1
                    updates["custom_target_temperature"] = 15.0
                elif "wip" in warehouse.warehouse_type.lower() or "production" in warehouse.warehouse_type.lower():
                    updates["custom_zone_assignment"] = "Red Zone"
                elif "rejected" in warehouse.warehouse_type.lower():
                    updates["custom_zone_assignment"] = "Quality Zone"
                    updates["custom_allow_expired_batches"] = 1
                    updates["custom_batch_quality_restrictions"] = "Hold,Failed"
            
            # Update warehouse with batch tracking configuration
            frappe.db.set_value("Warehouse", warehouse.name, updates)
        
        frappe.db.commit()
        print(f"Updated {len(warehouses)} warehouses with batch tracking configuration")
        
    except Exception as e:
        print(f"Error setting up warehouse batch tracking: {str(e)}")
        frappe.log_error(f"Warehouse batch tracking setup failed: {str(e)}")

def create_default_warehouse_batch_config():
    """Create default warehouse-batch configuration"""
    print("Creating default warehouse-batch configuration...")
    
    try:
        # Check if we need to create any default configurations
        # This could include default temperature settings, batch capacity limits, etc.
        
        # Set default batch capacity for all warehouses
        frappe.db.sql("""
            UPDATE `tabWarehouse` 
            SET custom_max_batch_capacity = 100
            WHERE custom_max_batch_capacity IS NULL OR custom_max_batch_capacity = 0
        """)
        
        # Set default temperature tolerance
        frappe.db.sql("""
            UPDATE `tabWarehouse` 
            SET custom_temperature_tolerance = 2.0
            WHERE custom_temperature_control = 1 
            AND (custom_temperature_tolerance IS NULL OR custom_temperature_tolerance = 0)
        """)
        
        frappe.db.commit()
        print("Default warehouse-batch configuration created")
        
    except Exception as e:
        print(f"Error creating default configuration: {str(e)}")
        frappe.log_error(f"Default warehouse-batch configuration failed: {str(e)}")

def setup_batch_processing_history_integration():
    """Setup integration with batch processing history"""
    print("Setting up batch processing history integration...")
    
    try:
        # Update existing Batch AMB records to ensure they have processing history
        batch_ambs = frappe.get_all(
            "Batch AMB", 
            filters={"batch_processing_history": ["", "is", "not set"]},
            fields=["name"]
        )
        
        for batch_amb in batch_ambs:
            try:
                # Create batch processing history if not exists
                batch_doc = frappe.get_doc("Batch AMB", batch_amb.name)
                
                if not batch_doc.batch_processing_history:
                    history_doc = frappe.get_doc({
                        "doctype": "Batch Processing History",
                        "batch_reference": batch_doc.name,
                        "date": batch_doc.creation,
                        "plant": batch_doc.custom_plant_code or "DEFAULT",
                        "item_code": batch_doc.item_to_manufacture,
                        "quality_status": "Pending",
                        "processing_action": "Batch Created",
                        "changed_by": batch_doc.owner,
                        "comments": "Initial processing history created during warehouse-batch integration setup",
                        "system_generated": 1
                    })
                    
                    history_doc.insert(ignore_permissions=True)
                    
                    # Link back to batch
                    batch_doc.batch_processing_history = history_doc.name
                    batch_doc.save(ignore_permissions=True)
                    
            except Exception as batch_error:
                print(f"Error setting up history for batch {batch_amb.name}: {str(batch_error)}")
                continue
        
        frappe.db.commit()
        print(f"Set up batch processing history for {len(batch_ambs)} batches")
        
    except Exception as e:
        print(f"Error setting up batch processing history integration: {str(e)}")
        frappe.log_error(f"Batch processing history integration setup failed: {str(e)}")
