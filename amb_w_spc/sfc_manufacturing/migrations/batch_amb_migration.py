# batch_amb_migration.py
import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime
import logging

logger = logging.getLogger(__name__)

def run_batch_amb_migration():
    """Run comprehensive migration for Batch AMB system"""
    try:
        logger.info("Starting Batch AMB Migration...")
        
        # 1. Create missing doctypes if they don't exist
        create_missing_doctypes()
        
        # 2. Update existing Batch AMB doctype schema
        update_batch_amb_schema()
        
        # 3. Migrate existing data
        migrate_existing_batches()
        
        # 4. Create integration records for existing batches
        create_integration_records()
        
        # 5. Validate migration results
        validate_migration()
        
        logger.info("Batch AMB Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        frappe.log_error(f"Batch AMB Migration Error: {str(e)}")
        raise

def create_missing_doctypes():
    """Create missing doctypes required for integration"""
    logger.info("Creating missing doctypes...")
    
    doctypes_to_create = [
        {
            'name': 'SPC Batch Record',
            'module': 'FDA Compliance',
            'custom': 1,
            'is_submittable': 1
        },
        {
            'name': 'SPC Batch Parameter', 
            'module': 'FDA Compliance',
            'custom': 1,
            'istable': 1
        },
        {
            'name': 'SPC Batch Deviation',
            'module': 'FDA Compliance', 
            'custom': 1,
            'istable': 1
        },
        {
            'name': 'Batch Processing History',
            'module': 'SFC Manufacturing',
            'custom': 1
        }
    ]
    
    for doctype_config in doctypes_to_create:
        if not frappe.db.exists("DocType", doctype_config['name']):
            create_doctype(doctype_config)
            logger.info(f"Created doctype: {doctype_config['name']}")

def create_doctype(doctype_config):
    """Create a doctype with basic configuration"""
    doc = frappe.new_doc("DocType")
    doc.update(doctype_config)
    doc.insert()

def update_batch_amb_schema():
    """Update Batch AMB doctype schema with new fields"""
    logger.info("Updating Batch AMB schema...")
    
    batch_amb = frappe.get_doc("DocType", "Batch AMB")
    
    # Add new fields if they don't exist
    new_fields = [
        {
            'fieldname': 'integration_status',
            'fieldtype': 'Select',
            'label': 'Integration Status',
            'options': 'Pending\nIn Progress\nCompleted\nError',
            'default': 'Pending',
            'read_only': 1
        },
        {
            'fieldname': 'last_sync_date',
            'fieldtype': 'Datetime', 
            'label': 'Last Sync Date',
            'read_only': 1
        },
        {
            'fieldname': 'sync_errors',
            'fieldtype': 'Text',
            'label': 'Sync Errors',
            'read_only': 1
        }
    ]
    
    for field_config in new_fields:
        if not any(f.fieldname == field_config['fieldname'] for f in batch_amb.fields):
            batch_amb.append('fields', field_config)
            logger.info(f"Added field: {field_config['fieldname']}")
    
    batch_amb.save()

def migrate_existing_batches():
    """Migrate existing Batch AMB records"""
    logger.info("Migrating existing batches...")
    
    # Get all existing Batch AMB records
    batches = frappe.get_all("Batch AMB", fields=['name', 'custom_batch_level', 'item_to_manufacture'])
    
    for batch in batches:
        try:
            batch_doc = frappe.get_doc("Batch AMB", batch.name)
            
            # Set default workflow state if not set
            if not batch_doc.workflow_state:
                batch_doc.db_set('workflow_state', 'Draft')
            
            # Set manufacturing date if not set for Level 1 batches
            if batch_doc.custom_batch_level == "1" and not batch_doc.manufacturing_date:
                batch_doc.db_set('manufacturing_date', nowdate())
            
            # Update integration status
            batch_doc.db_set('integration_status', 'Pending')
            
            logger.info(f"Migrated batch: {batch.name}")
            
        except Exception as e:
            logger.error(f"Error migrating batch {batch.name}: {str(e)}")
            continue

def create_integration_records():
    """Create integration records for existing batches"""
    logger.info("Creating integration records...")
    
    # Get Level 1 batches that need integration records
    level1_batches = frappe.get_all("Batch AMB", 
        filters={'custom_batch_level': '1'},
        fields=['name', 'item_to_manufacture', 'manufacturing_date', 'expiry_date']
    )
    
    for batch in level1_batches:
        try:
            batch_doc = frappe.get_doc("Batch AMB", batch.name)
            
            # Create ERPNext Batch if not exists
            if not batch_doc.erpnext_batch_reference:
                create_erpnext_batch_for_existing(batch_doc)
            
            # Create SPC Batch Record if not exists  
            if not batch_doc.spc_batch_record:
                create_spc_record_for_existing(batch_doc)
            
            # Create Processing History if not exists
            if not batch_doc.batch_processing_history:
                create_processing_history_for_existing(batch_doc)
            
            # Update integration status
            batch_doc.db_set('integration_status', 'Completed')
            batch_doc.db_set('last_sync_date', now_datetime())
            
            logger.info(f"Created integration records for: {batch.name}")
            
        except Exception as e:
            logger.error(f"Error creating integration records for {batch.name}: {str(e)}")
            batch_doc.db_set('integration_status', 'Error')
            batch_doc.db_set('sync_errors', str(e))
            continue

def create_erpnext_batch_for_existing(batch_doc):
    """Create ERPNext Batch for existing Batch AMB records"""
    try:
        from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import BatchAMBIntegration
        BatchAMBIntegration.create_erpnext_batch(batch_doc)
    except Exception as e:
        logger.error(f"Error creating ERPNext batch for {batch_doc.name}: {str(e)}")
        raise

def create_spc_record_for_existing(batch_doc):
    """Create SPC Batch Record for existing Batch AMB records"""
    try:
        spc_record = frappe.new_doc("SPC Batch Record")
        spc_record.update({
            "batch_amb_reference": batch_doc.name,
            "batch_number": batch_doc.name,
            "product_code": batch_doc.item_to_manufacture,
            "production_date": batch_doc.manufacturing_date or nowdate(),
            "batch_size": batch_doc.batch_qty or 0,
            "batch_status": "In Process"
        })
        spc_record.insert()
        
        batch_doc.db_set("spc_batch_record", spc_record.name)
        
    except Exception as e:
        logger.error(f"Error creating SPC record for {batch_doc.name}: {str(e)}")
        raise

def create_processing_history_for_existing(batch_doc):
    """Create Processing History for existing Batch AMB records"""
    try:
        history = frappe.new_doc("Batch Processing History")
        history.update({
            "batch_amb_reference": batch_doc.name,
            "batch_code": batch_doc.name,
            "item_code": batch_doc.item_to_manufacture,
            "start_date": now_datetime(),
            "status": "Completed"
        })
        history.insert()
        
        batch_doc.db_set("batch_processing_history", history.name)
        
    except Exception as e:
        logger.error(f"Error creating processing history for {batch_doc.name}: {str(e)}")
        raise

def validate_migration():
    """Validate migration results"""
    logger.info("Validating migration...")
    
    # Check total batches
    total_batches = frappe.db.count("Batch AMB")
    migrated_batches = frappe.db.count("Batch AMB", {"integration_status": "Completed"})
    
    logger.info(f"Migration Summary:")
    logger.info(f"Total batches: {total_batches}")
    logger.info(f"Successfully migrated: {migrated_batches}")
    logger.info(f"Pending/Failed: {total_batches - migrated_batches}")
    
    # Check integration records
    level1_with_erpnext = frappe.db.count("Batch AMB", {
        "custom_batch_level": "1", 
        "erpnext_batch_reference": ["!=", ""]
    })
    
    level1_with_spc = frappe.db.count("Batch AMB", {
        "custom_batch_level": "1", 
        "spc_batch_record": ["!=", ""]
    })
    
    logger.info(f"Level 1 batches with ERPNext integration: {level1_with_erpnext}")
    logger.info(f"Level 1 batches with SPC integration: {level1_with_spc}")

# Command to run migration
@frappe.whitelist()
def execute_batch_amb_migration():
    """Execute the Batch AMB migration (call this from UI)"""
    
    # === ADD PERMISSION CHECK HERE ===
    if not frappe.has_permission("Batch AMB", "write"):
        frappe.throw(_("You don't have permission to run migrations. Required: Write permission on Batch AMB"))
    
    # === ADD ADMIN ROLE CHECK (Optional but recommended) ===
    user_roles = frappe.get_roles(frappe.session.user)
    if 'System Manager' not in user_roles and 'Administrator' not in user_roles:
        frappe.throw(_("Only System Managers and Administrators can run migrations"))
    
    try:
        run_batch_amb_migration()
        return {
            "success": True,
            "message": "Batch AMB migration completed successfully!"
        }
    except Exception as e:
        frappe.log_error(f"Migration failed: {str(e)}")
        return {
            "success": False,
            "message": f"Migration failed: {str(e)}"
        }
