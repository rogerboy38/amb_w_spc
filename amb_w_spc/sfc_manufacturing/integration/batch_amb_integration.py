# batch_amb_integration.py

# batch_amb_integration.py
import frappe
from frappe import _
from frappe.utils import nowdate, flt, now_datetime
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class BatchAMBIntegration:
    """Complete integration controller for Batch AMB system"""
    
    @staticmethod
    def create_erpnext_batch(batch_amb_doc):
        """Create corresponding ERPNext Batch when Batch AMB is created"""
        if batch_amb_doc.erpnext_batch_reference:
            return  # Already linked
            
        # Validate required fields
        if not batch_amb_doc.item_to_manufacture:
            frappe.throw(_("Item to Manufacture is required to create ERPNext Batch"))
        
        # Generate batch ID
        batch_id = batch_amb_doc.name
        
        # Create ERPNext Batch
        try:
            erpnext_batch = frappe.new_doc("Batch")
            erpnext_batch.update({
                "batch_id": batch_id,
                "item": batch_amb_doc.item_to_manufacture,
                "item_name": batch_amb_doc.wo_item_name or batch_amb_doc.tds_item_name or frappe.db.get_value("Item", batch_amb_doc.item_to_manufacture, "item_name"),
                "expiry_date": batch_amb_doc.expiry_date,
                "manufacturing_date": batch_amb_doc.manufacturing_date or nowdate(),
                "supplier": getattr(batch_amb_doc, 'supplier', None),
                "reference_doctype": "Batch AMB",
                "reference_name": batch_amb_doc.name
            })
            
            erpnext_batch.insert(ignore_permissions=True)
            batch_amb_doc.db_set("erpnext_batch_reference", erpnext_batch.name)
            
            frappe.msgprint(_("ERPNext Batch {0} created successfully").format(erpnext_batch.name))
            
        except Exception as e:
            frappe.log_error(f"Error creating ERPNext Batch: {str(e)}")
            frappe.throw(_("Failed to create ERPNext Batch: {0}").format(str(e)))
    
    @staticmethod
    def sync_batch_data(batch_amb_doc):
        """Sync data between Batch AMB and ERPNext Batch"""
        if not batch_amb_doc.erpnext_batch_reference:
            return
            
        try:
            erpnext_batch = frappe.get_doc("Batch", batch_amb_doc.erpnext_batch_reference)
            
            # Update ERPNext Batch with AMB data
            updates = {
                "item": batch_amb_doc.item_to_manufacture,
                "item_name": batch_amb_doc.wo_item_name or batch_amb_doc.tds_item_name,
                "expiry_date": batch_amb_doc.expiry_date,
                "manufacturing_date": batch_amb_doc.manufacturing_date
            }
            
            erpnext_batch.update(updates)
            erpnext_batch.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Error syncing Batch data: {str(e)}")
    
    @staticmethod
    def get_stock_balance(batch_amb_name):
        """Get stock balance for Batch AMB via ERPNext Batch"""
        try:
            batch_amb = frappe.get_doc("Batch AMB", batch_amb_name)
            if not batch_amb.erpnext_batch_reference:
                return 0
                
            # Use ERPNext's stock balance calculation
            from erpnext.stock.utils import get_stock_balance
            
            balance = get_stock_balance(
                item_code=batch_amb.item_to_manufacture,
                batch_no=batch_amb.erpnext_batch_reference
            )
            
            return flt(balance)
            
        except Exception as e:
            frappe.log_error(f"Error getting stock balance: {str(e)}")
            return 0
    
    @staticmethod
    def update_batch_qty(batch_amb_name):
        """Update batch quantity from stock balance"""
        try:
            batch_amb = frappe.get_doc("Batch AMB", batch_amb_name)
            stock_balance = BatchAMBIntegration.get_stock_balance(batch_amb_name)
            
            if batch_amb.batch_qty != stock_balance:
                batch_amb.db_set("batch_qty", stock_balance)
                
        except Exception as e:
            frappe.log_error(f"Error updating batch quantity: {str(e)}")
    
    @staticmethod
    def create_spc_batch_record(batch_amb_doc):
        """Create SPC Batch Record for Level 1 batches"""
        if batch_amb_doc.custom_batch_level != "1":
            return
            
        if batch_amb_doc.spc_batch_record:
            return  # Already exists
            
        try:
            spc_record = frappe.new_doc("SPC Batch Record")
            spc_record.update({
                "batch_amb_reference": batch_amb_doc.name,
                "batch_number": batch_amb_doc.name,
                "product_code": batch_amb_doc.item_to_manufacture,
                "plant": batch_amb_doc.production_plant_name,
                "production_date": batch_amb_doc.manufacturing_date or nowdate(),
                "batch_size": batch_amb_doc.batch_qty or 0,
                "batch_status": "In Process"
            })
            
            spc_record.insert()
            batch_amb_doc.db_set("spc_batch_record", spc_record.name)
            
            frappe.msgprint(_("SPC Batch Record {0} created").format(spc_record.name))
            
        except Exception as e:
            frappe.log_error(f"Error creating SPC Batch Record: {str(e)}")
    
    @staticmethod
    def sync_spc_parameters(batch_amb_doc):
        """Sync SPC parameters between systems"""
        if not batch_amb_doc.spc_batch_record:
            return
            
        try:
            spc_record = frappe.get_doc("SPC Batch Record", batch_amb_doc.spc_batch_record)
            
            # Update basic information
            spc_record.update({
                "batch_size": batch_amb_doc.batch_qty or 0,
                "expiry_date": batch_amb_doc.expiry_date
            })
            
            spc_record.save()
            
        except Exception as e:
            frappe.log_error(f"Error syncing SPC parameters: {str(e)}")
    
    @staticmethod
    def create_batch_processing_history(batch_amb_doc, action, remarks=None):
        """Create processing history entry"""
        try:
            if not batch_amb_doc.batch_processing_history:
                # Create main processing history record
                history = frappe.new_doc("Batch Processing History")
                history.update({
                    "batch_amb_reference": batch_amb_doc.name,
                    "batch_code": batch_amb_doc.name,
                    "item_code": batch_amb_doc.item_to_manufacture,
                    "start_date": now_datetime(),
                    "status": "In Progress"
                })
                history.insert()
                batch_amb_doc.db_set("batch_processing_history", history.name)
            
            # Add history entry
            history = frappe.get_doc("Batch Processing History", batch_amb_doc.batch_processing_history)
            history.append("processing_steps", {
                "step_name": action,
                "timestamp": now_datetime(),
                "status": "Completed",
                "remarks": remarks or f"Batch {action}",
                "changed_by": frappe.session.user
            })
            history.save()
            
        except Exception as e:
            frappe.log_error(f"Error creating processing history: {str(e)}")
    
    @staticmethod
    def get_comprehensive_batch_report(filters=None):
        """Get comprehensive batch report across all systems"""
        filters = frappe.parse_json(filters) if filters else {}
        
        # Build base query
        conditions = []
        if filters.get("batch_level"):
            conditions.append(f"b.custom_batch_level = '{filters['batch_level']}'")
        if filters.get("workflow_state"):
            conditions.append(f"b.workflow_state = '{filters['workflow_state']}'")
        if filters.get("item_code"):
            conditions.append(f"b.item_to_manufacture = '{filters['item_code']}'")
        if filters.get("plant"):
            conditions.append(f"b.production_plant_name = '{filters['plant']}'")
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT 
                b.name as batch_amb,
                b.custom_batch_level as batch_level,
                b.workflow_state,
                b.item_to_manufacture as item_code,
                b.item_name,
                b.erpnext_batch_reference,
                b.batch_qty,
                b.total_net_weight,
                b.barrel_count,
                b.spc_batch_record,
                b.spc_batch_deviation,
                b.batch_processing_history,
                b.manufacturing_date,
                b.expiry_date,
                b.production_plant_name as plant,
                eb.batch_id as erpnext_batch_id,
                sbr.batch_status as spc_record_status,
                sbr.specifications_met as spc_specs_met,
                bph.status as processing_status
            FROM `tabBatch AMB` b
            LEFT JOIN `tabBatch` eb ON b.erpnext_batch_reference = eb.name
            LEFT JOIN `tabSPC Batch Record` sbr ON b.spc_batch_record = sbr.name
            LEFT JOIN `tabBatch Processing History` bph ON b.batch_processing_history = bph.name
            WHERE {where_clause}
            ORDER BY b.creation DESC
        """
        
        return frappe.db.sql(query, as_dict=True)
    
    @staticmethod
    def validate_batch_hierarchy_integrity(batch_amb_doc):
        """Validate and maintain batch hierarchy integrity"""
        if batch_amb_doc.custom_batch_level == "1":
            # Level 1 batches should not have parent
            if batch_amb_doc.parent_batch_amb:
                frappe.throw(_("Level 1 batches cannot have a parent batch"))
        else:
            # Sublots must have parent
            if not batch_amb_doc.parent_batch_amb:
                frappe.throw(_("Parent Batch AMB is required for level {0} batches").format(
                    batch_amb_doc.custom_batch_level))
            
            # Validate parent level
            parent_level = frappe.db.get_value("Batch AMB", batch_amb_doc.parent_batch_amb, "custom_batch_level")
            if parent_level and int(parent_level) != int(batch_amb_doc.custom_batch_level) - 1:
                frappe.throw(_("Parent batch must be level {0} for this level {1} batch").format(
                    int(batch_amb_doc.custom_batch_level) - 1, batch_amb_doc.custom_batch_level))
    
    @staticmethod
    def get_batch_tree_data(plant=None):
        """Get batch tree data for widget display"""
        conditions = ["b.custom_batch_level IN ('1', '2', '3')"]
        if plant:
            conditions.append(f"b.production_plant_name = '{plant}'")
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                b.name as batch_code,
                b.custom_generated_batch_name as batch_name,
                b.custom_batch_level,
                b.workflow_state as quality_status,
                b.production_plant_name as plant,
                b.batch_qty as quantity,
                b.item_to_manufacture as item_code
            FROM `tabBatch AMB` b
            WHERE {where_clause}
            ORDER BY b.production_plant_name, b.custom_batch_level, b.creation
        """
        
        batches = frappe.db.sql(query, as_dict=True)
        
        # Group by plant
        plant_data = {}
        for batch in batches:
            plant = batch.pop('plant', 'Unknown Plant')
            if plant not in plant_data:
                plant_data[plant] = []
            plant_data[plant].append(batch)
        
        return plant_data

@frappe.whitelist()
def get_batch_stock_info(batch_amb_name):
    """Get comprehensive stock information for a batch"""
    try:
        batch_amb = frappe.get_doc("Batch AMB", batch_amb_name)
        
        stock_balance = BatchAMBIntegration.get_stock_balance(batch_amb_name)
        
        # Get stock ledger entries
        ledger_entries = frappe.db.sql("""
            SELECT posting_date, voucher_type, voucher_no, actual_qty, qty_after_transaction, warehouse
            FROM `tabStock Ledger Entry`
            WHERE batch_no = %s AND item_code = %s
            ORDER BY posting_date DESC, creation DESC
            LIMIT 50
        """, (batch_amb.erpnext_batch_reference, batch_amb.item_to_manufacture), as_dict=True)
        
        return {
            'batch_amb': batch_amb_name,
            'erpnext_batch': batch_amb.erpnext_batch_reference,
            'item_code': batch_amb.item_to_manufacture,
            'current_stock': stock_balance,
            'ledger_entries': ledger_entries,
            'warehouses': list(set([entry.warehouse for entry in ledger_entries]))
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting batch stock info: {str(e)}")
        return {'error': str(e)}

@frappe.whitelist()
def sync_batch_systems(batch_amb_name):
    """Manual sync of all batch systems"""
    try:
        batch_amb = frappe.get_doc("Batch AMB", batch_amb_name)
        
        # Sync ERPNext Batch
        if not batch_amb.erpnext_batch_reference and batch_amb.custom_batch_level == "1":
            BatchAMBIntegration.create_erpnext_batch(batch_amb)
        else:
            BatchAMBIntegration.sync_batch_data(batch_amb)
        
        # Sync SPC Record
        if batch_amb.custom_batch_level == "1":
            if not batch_amb.spc_batch_record:
                BatchAMBIntegration.create_spc_batch_record(batch_amb)
            else:
                BatchAMBIntegration.sync_spc_parameters(batch_amb)
        
        # Update stock quantity
        BatchAMBIntegration.update_batch_qty(batch_amb_name)
        
        # Add to processing history
        BatchAMBIntegration.create_batch_processing_history(batch_amb, "Manual System Sync")
        
        frappe.msgprint(_("All batch systems synchronized successfully"))
        return {'success': True}
        
    except Exception as e:
        frappe.log_error(f"Error syncing batch systems: {str(e)}")
        return {'success': False, 'error': str(e)}
