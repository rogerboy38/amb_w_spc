# batch_migration_controller.py
import frappe
from frappe import _
from frappe.utils import cstr, now_datetime
import json

class BatchMigrationController:
    """Controller for managing Batch AMB migrations"""
    
    @staticmethod
    @frappe.whitelist()
    def get_migration_status():
        """Get current migration status"""
        try:
            status = {
                'total_batches': frappe.db.count("Batch AMB"),
                'migrated_batches': frappe.db.count("Batch AMB", {"integration_status": "Completed"}),
                'pending_batches': frappe.db.count("Batch AMB", {"integration_status": "Pending"}),
                'error_batches': frappe.db.count("Batch AMB", {"integration_status": "Error"}),
                'level1_batches': frappe.db.count("Batch AMB", {"custom_batch_level": "1"}),
                'level1_with_erpnext': frappe.db.count("Batch AMB", {
                    "custom_batch_level": "1", 
                    "erpnext_batch_reference": ["!=", ""]
                }),
                'level1_with_spc': frappe.db.count("Batch AMB", {
                    "custom_batch_level": "1", 
                    "spc_batch_record": ["!=", ""]
                })
            }
            
            # Calculate percentages
            total = status['total_batches'] or 1
            status['migration_progress'] = round((status['migrated_batches'] / total) * 100, 2)
            status['level1_erpnext_progress'] = round((status['level1_with_erpnext'] / (status['level1_batches'] or 1)) * 100, 2)
            status['level1_spc_progress'] = round((status['level1_with_spc'] / (status['level1_batches'] or 1)) * 100, 2)
            
            return status
        except Exception as e:
            frappe.log_error(f"Error getting migration status: {str(e)}")
            return {"error": str(e)}
    
    @staticmethod
    @frappe.whitelist()
    def run_targeted_migration(batch_names=None):
        """Run migration for specific batches"""
        try:
            from amb_w_spc.sfc_manufacturing.migration.batch_amb_migration import create_integration_records_for_batches
            
            if not batch_names:
                return {"success": False, "message": "No batch names provided"}
            
            if isinstance(batch_names, str):
                batch_names = json.loads(batch_names)
            
            if not isinstance(batch_names, list) or len(batch_names) == 0:
                return {"success": False, "message": "Invalid batch names provided"}
            
            frappe.enqueue(
                _run_targeted_migration_async,
                batch_names=batch_names,
                job_name=f"Targeted Batch Migration for {len(batch_names)} batches",
                queue="long",
                timeout=3600,
                now=False
            )
            
            return {
                "success": True, 
                "message": f"Migration started for {len(batch_names)} batches. Check background jobs for progress."
            }
            
        except Exception as e:
            frappe.log_error(f"Error in targeted migration: {str(e)}")
            return {"success": False, "message": str(e)}
    
    @staticmethod
    @frappe.whitelist()
    def fix_migration_errors():
        """Attempt to fix migration errors"""
        try:
            error_batches = frappe.get_all("Batch AMB",
                filters={"integration_status": "Error"},
                fields=["name", "sync_errors"]
            )
            
            if not error_batches:
                return {"success": True, "message": "No batches with errors found", "fixed_count": 0}
            
            frappe.enqueue(
                _fix_migration_errors_async,
                job_name="Fix Batch Migration Errors",
                queue="long",
                timeout=3600,
                now=False
            )
            
            return {
                "success": True, 
                "message": f"Error fixing started for {len(error_batches)} batches. Check background jobs for progress."
            }
            
        except Exception as e:
            frappe.log_error(f"Error in fix_migration_errors: {str(e)}")
            return {"success": False, "message": str(e)}
    
    @staticmethod
    @frappe.whitelist()
    def migrate_all_pending():
        """Migrate all pending batches"""
        try:
            pending_batches = frappe.get_all("Batch AMB",
                filters={"integration_status": "Pending"},
                fields=["name"]
            )
            
            if not pending_batches:
                return {"success": True, "message": "No pending batches found", "migrated_count": 0}
            
            batch_names = [batch["name"] for batch in pending_batches]
            
            frappe.enqueue(
                _run_targeted_migration_async,
                batch_names=batch_names,
                job_name=f"Migrate All Pending Batches - {len(batch_names)} total",
                queue="long",
                timeout=7200,
                now=False
            )
            
            return {
                "success": True, 
                "message": f"Migration started for {len(batch_names)} pending batches. Check background jobs for progress."
            }
            
        except Exception as e:
            frappe.log_error(f"Error in migrate_all_pending: {str(e)}")
            return {"success": False, "message": str(e)}
    
    @staticmethod
    @frappe.whitelist()
    def get_batch_details(batch_name):
        """Get detailed information about a specific batch"""
        try:
            batch = frappe.get_doc("Batch AMB", batch_name)
            
            details = {
                "name": batch.name,
                "item_to_manufacture": batch.item_to_manufacture,
                "batch_level": batch.custom_batch_level,
                "integration_status": batch.integration_status,
                "erpnext_batch_reference": batch.erpnext_batch_reference,
                "spc_batch_record": batch.spc_batch_record,
                "batch_processing_history": batch.batch_processing_history,
                "sync_errors": batch.sync_errors,
                "last_sync_date": batch.last_sync_date,
                "manufacturing_date": batch.manufacturing_date,
                "batch_qty": batch.batch_qty
            }
            
            return {"success": True, "details": details}
        except Exception as e:
            return {"success": False, "message": str(e)}

# Background job functions
def _run_targeted_migration_async(batch_names):
    """Run targeted migration as background job"""
    from amb_w_spc.sfc_manufacturing.migration.batch_amb_migration import create_integration_records_for_batches
    
    try:
        results = create_integration_records_for_batches(batch_names)
        
        # Log results
        success_count = len([r for r in results if r.get("status") == "Success"])
        failed_count = len([r for r in results if r.get("status") == "Failed"])
        
        frappe.publish_realtime(
            "batch_migration_complete",
            {
                "message": f"Migration completed: {success_count} successful, {failed_count} failed",
                "success_count": success_count,
                "failed_count": failed_count,
                "results": results
            }
        )
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Error in async targeted migration: {str(e)}")
        frappe.db.rollback()

def _fix_migration_errors_async():
    """Fix migration errors as background job"""
    try:
        error_batches = frappe.get_all("Batch AMB",
            filters={"integration_status": "Error"},
            fields=["name", "sync_errors"]
        )
        
        fixed_count = 0
        results = []
        
        for batch in error_batches:
            try:
                batch_doc = frappe.get_doc("Batch AMB", batch.name)
                
                # Clear errors and retry
                batch_doc.db_set('integration_status', 'Pending')
                batch_doc.db_set('sync_errors', '')
                
                # Retry integration
                from amb_w_spc.sfc_manufacturing.migration.batch_amb_migration import create_integration_records_for_batch
                create_integration_records_for_batch(batch_doc)
                
                fixed_count += 1
                results.append({"batch": batch.name, "status": "Fixed"})
                
            except Exception as e:
                results.append({"batch": batch.name, "status": "Failed", "error": str(e)})
                frappe.log_error(f"Error fixing batch {batch.name}: {str(e)}")
                continue
        
        frappe.publish_realtime(
            "batch_migration_fix_complete",
            {
                "message": f"Error fixing completed: {fixed_count} batches fixed",
                "fixed_count": fixed_count,
                "results": results
            }
        )
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Error in async error fixing: {str(e)}")
        frappe.db.rollback()

# Migration helper functions
def create_integration_records_for_batches(batch_names):
    """Create integration records for specific batches"""
    from amb_w_spc.sfc_manufacturing.migration.batch_amb_migration import create_integration_records_for_batch
    
    results = []
    total = len(batch_names)
    
    for index, batch_name in enumerate(batch_names):
        try:
            batch_doc = frappe.get_doc("Batch AMB", batch_name)
            create_integration_records_for_batch(batch_doc)
            results.append({"batch": batch_name, "status": "Success"})
            
            # Update progress
            if index % 10 == 0:  # Update every 10 batches
                frappe.publish_realtime(
                    "batch_migration_progress",
                    {
                        "message": f"Processing batch {index + 1} of {total}",
                        "current": index + 1,
                        "total": total,
                        "percent": round(((index + 1) / total) * 100, 1)
                    }
                )
                
        except Exception as e:
            error_msg = str(e)
            frappe.log_error(f"Error migrating batch {batch_name}: {error_msg}")
            results.append({"batch": batch_name, "status": "Failed", "error": error_msg})
    
    return results

def create_integration_records_for_batch(batch_doc):
    """Create integration records for a single batch"""
    from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import BatchAMBIntegration
    
    try:
        # Create ERPNext Batch for Level 1
        if batch_doc.custom_batch_level == "1" and not batch_doc.erpnext_batch_reference:
            BatchAMBIntegration.create_erpnext_batch(batch_doc)
        
        # Create SPC Record for Level 1
        if batch_doc.custom_batch_level == "1" and not batch_doc.spc_batch_record:
            spc_record = frappe.new_doc("SPC Batch Record")
            spc_record.update({
                "batch_amb_reference": batch_doc.name,
                "batch_number": batch_doc.name,
                "product_code": batch_doc.item_to_manufacture,
                "production_date": batch_doc.manufacturing_date,
                "batch_size": batch_doc.batch_qty or 0,
                "batch_status": "In Process"
            })
            spc_record.insert(ignore_permissions=True)
            batch_doc.db_set("spc_batch_record", spc_record.name)
        
        # Create Processing History
        if not batch_doc.batch_processing_history:
            history = frappe.new_doc("Batch Processing History")
            history.update({
                "batch_amb_reference": batch_doc.name,
                "batch_code": batch_doc.name,
                "item_code": batch_doc.item_to_manufacture,
                "start_date": now_datetime(),
                "status": "Completed"
            })
            history.insert(ignore_permissions=True)
            batch_doc.db_set("batch_processing_history", history.name)
        
        # Update integration status
        batch_doc.db_set('integration_status', 'Completed')
        batch_doc.db_set('last_sync_date', now_datetime())
        batch_doc.db_set('sync_errors', '')
        
        frappe.db.commit()
        
    except Exception as e:
        # Update batch with error
        batch_doc.db_set('integration_status', 'Error')
        batch_doc.db_set('sync_errors', str(e))
        frappe.db.commit()
        raise e
