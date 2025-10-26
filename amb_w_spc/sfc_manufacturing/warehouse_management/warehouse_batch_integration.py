import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt, cint
from typing import Dict, List, Any, Optional
import json

class WarehouseBatchIntegration:
    """
    Main integration controller for Warehouse-Batch operations.
    Provides seamless integration between warehouse operations and batch tracking
    without modifying existing batch DocTypes.
    """
    
    @staticmethod
    def create_stock_entry_batch_history(stock_entry_doc, method=None):
        """
        Create batch processing history entries for stock movements.
        Called as hook from Stock Entry submission.
        """
        try:
            if not stock_entry_doc.items:
                return
                
            for item in stock_entry_doc.items:
                if item.batch_no:
                    # Get batch_amb reference
                    batch_amb = WarehouseBatchIntegration.get_batch_amb_from_batch(item.batch_no)
                    if batch_amb:
                        WarehouseBatchIntegration.create_batch_processing_entry(
                            stock_entry_doc, item, batch_amb
                        )
                        
        except Exception as e:
            frappe.log_error(f"Error creating batch history for Stock Entry {stock_entry_doc.name}: {str(e)}")
    
    @staticmethod
    def get_batch_amb_from_batch(erpnext_batch_id):
        """
        Get Batch AMB reference from ERPNext Batch ID.
        """
        return frappe.db.get_value(
            "Batch AMB", 
            {"erpnext_batch_reference": erpnext_batch_id}, 
            "name"
        )
    
    @staticmethod
    def create_batch_processing_entry(stock_entry_doc, item, batch_amb_name):
        """
        Create a batch processing history entry for warehouse movement.
        """
        try:
            # Determine processing action based on SAP movement type
            processing_action = WarehouseBatchIntegration.get_processing_action_from_sap_movement(
                stock_entry_doc.custom_sap_movement_type,
                stock_entry_doc.purpose
            )
            
            # Get plant codes from warehouse locations
            source_plant = WarehouseBatchIntegration.get_plant_code_from_warehouse(
                item.s_warehouse
            ) if item.s_warehouse else None
            
            target_plant = WarehouseBatchIntegration.get_plant_code_from_warehouse(
                item.t_warehouse
            ) if item.t_warehouse else None
            
            # Create batch processing history entry
            history_entry = {
                "batch_reference": batch_amb_name,
                "date": stock_entry_doc.posting_date or nowdate(),
                "plant": target_plant or source_plant,
                "item_code": item.item_code,
                "quality_status": WarehouseBatchIntegration.get_batch_quality_status(batch_amb_name),
                "processing_action": processing_action,
                "previous_value": source_plant,
                "new_value": target_plant,
                "work_order_reference": stock_entry_doc.custom_work_order_reference,
                "changed_by": frappe.session.user,
                "comments": f"Stock Entry: {stock_entry_doc.name} - {processing_action}",
                "system_generated": 1
            }
            
            # Add to batch_amb processing history table
            batch_amb_doc = frappe.get_doc("Batch AMB", batch_amb_name)
            if not batch_amb_doc.batch_processing_history:
                # Create new batch processing history document if none exists
                WarehouseBatchIntegration.create_batch_processing_history_doc(batch_amb_doc)
            
            # Add entry to processing history
            batch_processing_history_doc = frappe.get_doc(
                "Batch Processing History", 
                batch_amb_doc.batch_processing_history
            )
            
            # Update the existing fields rather than appending to table
            batch_processing_history_doc.update(history_entry)
            batch_processing_history_doc.save(ignore_permissions=True)
            
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(f"Error creating batch processing entry: {str(e)}")
    
    @staticmethod
    def create_batch_processing_history_doc(batch_amb_doc):
        """
        Create a new Batch Processing History document for the batch.
        """
        try:
            history_doc = frappe.get_doc({
                "doctype": "Batch Processing History",
                "batch_reference": batch_amb_doc.name,
                "date": nowdate(),
                "plant": batch_amb_doc.custom_plant_code,
                "item_code": batch_amb_doc.item_to_manufacture,
                "quality_status": "Pending",
                "processing_action": "Batch Created",
                "changed_by": frappe.session.user,
                "comments": "Initial batch processing history created",
                "system_generated": 1
            })
            
            history_doc.insert(ignore_permissions=True)
            
            # Link back to batch_amb
            batch_amb_doc.batch_processing_history = history_doc.name
            batch_amb_doc.save(ignore_permissions=True)
            
            return history_doc.name
            
        except Exception as e:
            frappe.log_error(f"Error creating batch processing history document: {str(e)}")
            return None
    
    @staticmethod
    def get_processing_action_from_sap_movement(sap_movement_type, purpose):
        """
        Map SAP movement type to processing action.
        """
        mapping = {
            "261": "Plant Transfer",  # FrontFlush
            "311": "Plant Transfer",  # BackFlush
        }
        
        if sap_movement_type in mapping:
            return mapping[sap_movement_type]
        
        # Fallback to purpose-based mapping
        purpose_mapping = {
            "Material Issue": "Item Code Change",
            "Material Transfer": "Plant Transfer",
            "Material Receipt": "Plant Transfer",
            "Repack": "Item Code Change"
        }
        
        return purpose_mapping.get(purpose, "Plant Transfer")
    
    @staticmethod
    def get_plant_code_from_warehouse(warehouse_name):
        """
        Extract plant code from warehouse name or custom field.
        """
        if not warehouse_name:
            return None
            
        # Try to get from warehouse custom field first
        plant_code = frappe.db.get_value(
            "Warehouse", warehouse_name, "custom_plant_code"
        )
        
        if plant_code:
            return plant_code
            
        # Extract from warehouse name pattern
        # Expected pattern: "Warehouse Name - PLANT_CODE"
        if " - " in warehouse_name:
            return warehouse_name.split(" - ")[-1]
            
        # Default plant code extraction logic
        if "AMB-W" in warehouse_name:
            return "AMB-W"
        elif "Red Zone" in warehouse_name:
            return "RZ"
        elif "Green Zone" in warehouse_name:
            return "GZ"
        else:
            return "DEFAULT"
    
    @staticmethod
    def get_batch_quality_status(batch_amb_name):
        """
        Get current quality status from SPC systems.
        """
        try:
            # Get SPC Batch Record
            spc_record = frappe.db.get_value(
                "Batch AMB", batch_amb_name, "spc_batch_record"
            )
            
            if spc_record:
                status = frappe.db.get_value(
                    "SPC Batch Record", spc_record, "batch_status"
                )
                if status:
                    return status
                    
            # Get from workflow state
            workflow_state = frappe.db.get_value(
                "Batch AMB", batch_amb_name, "workflow_state"
            )
            
            # Map workflow states to quality states
            state_mapping = {
                "Draft": "Pending",
                "Pending QC Review": "Pending",
                "Quality Approved": "Passed",
                "SPC Hold": "Hold",
                "Rejected": "Failed"
            }
            
            return state_mapping.get(workflow_state, "Pending")
            
        except Exception:
            return "Pending"
    
    @staticmethod
    def update_warehouse_bin_batch_tracking(stock_entry_doc, method=None):
        """
        Update warehouse bin locations with batch tracking information.
        """
        try:
            for item in stock_entry_doc.items:
                if item.batch_no and item.t_warehouse:
                    WarehouseBatchIntegration.update_bin_batch_info(
                        item.t_warehouse, item.item_code, item.batch_no, item.qty
                    )
                    
        except Exception as e:
            frappe.log_error(f"Error updating bin batch tracking: {str(e)}")
    
    @staticmethod
    def update_bin_batch_info(warehouse, item_code, batch_no, qty):
        """
        Update bin with batch information and container details.
        """
        try:
            # Get or create bin record
            bin_name = frappe.db.get_value(
                "Bin", 
                {"warehouse": warehouse, "item_code": item_code}, 
                "name"
            )
            
            if bin_name:
                # Get batch_amb details
                batch_amb = WarehouseBatchIntegration.get_batch_amb_from_batch(batch_no)
                if batch_amb:
                    batch_details = frappe.get_doc("Batch AMB", batch_amb)
                    
                    # Update bin with batch context
                    frappe.db.set_value("Bin", bin_name, {
                        "custom_current_batch": batch_no,
                        "custom_batch_amb_reference": batch_amb,
                        "custom_batch_level": batch_details.custom_batch_level,
                        "custom_batch_expiry_date": batch_details.expiry_date,
                        "custom_batch_quality_status": WarehouseBatchIntegration.get_batch_quality_status(batch_amb),
                        "custom_container_count": batch_details.barrel_count if batch_details.custom_batch_level == "3" else 0,
                        "custom_last_batch_movement": now_datetime()
                    })
                    
                    frappe.db.commit()
                    
        except Exception as e:
            frappe.log_error(f"Error updating bin batch info: {str(e)}")
    
    @staticmethod
    def validate_batch_warehouse_movement(stock_entry_doc, method=None):
        """
        Validate warehouse movements respect batch constraints.
        """
        try:
            for item in stock_entry_doc.items:
                if item.batch_no:
                    WarehouseBatchIntegration.validate_batch_constraints(
                        item.batch_no, item.s_warehouse, item.t_warehouse
                    )
                    
        except Exception as e:
            frappe.throw(_("Batch validation failed: {0}").format(str(e)))
    
    @staticmethod
    def validate_batch_constraints(batch_no, source_warehouse, target_warehouse):
        """
        Validate batch movement constraints.
        """
        # Get batch_amb details
        batch_amb = WarehouseBatchIntegration.get_batch_amb_from_batch(batch_no)
        if not batch_amb:
            return  # Skip validation if no batch_amb found
            
        batch_doc = frappe.get_doc("Batch AMB", batch_amb)
        
        # Validate expiry date
        if batch_doc.expiry_date and batch_doc.expiry_date <= nowdate():
            frappe.throw(_("Cannot move expired batch {0}").format(batch_no))
        
        # Validate quality status
        quality_status = WarehouseBatchIntegration.get_batch_quality_status(batch_amb)
        if quality_status in ["Failed", "Hold"]:
            # Check if target warehouse allows rejected/hold batches
            target_warehouse_type = frappe.db.get_value(
                "Warehouse", target_warehouse, "warehouse_type"
            )
            
            if target_warehouse_type != "Rejected":
                frappe.throw(_("Batch {0} with quality status '{1}' can only be moved to Rejected warehouses")
                    .format(batch_no, quality_status))
        
        # Validate temperature requirements
        if target_warehouse:
            WarehouseBatchIntegration.validate_temperature_compatibility(
                batch_doc, target_warehouse
            )
    
    @staticmethod
    def validate_temperature_compatibility(batch_doc, warehouse):
        """
        Validate temperature requirements for batch storage.
        """
        warehouse_temp_control = frappe.db.get_value(
            "Warehouse", warehouse, "custom_temperature_control"
        )
        
        # For finished goods batches, ensure temperature controlled warehouse
        if (batch_doc.custom_batch_level == "1" and 
            frappe.db.get_value("Item", batch_doc.item_to_manufacture, "item_group") == "Finished Goods"):
            
            if not warehouse_temp_control:
                frappe.msgprint(
                    _("Warning: Finished goods batch {0} should be stored in temperature controlled warehouse")
                    .format(batch_doc.name), 
                    alert=True
                )
    
    @staticmethod
    def sync_warehouse_zone_status_with_batch_quality(work_order_name=None):
        """
        Sync warehouse zone status with batch quality status.
        """
        try:
            if work_order_name:
                # Get all batches related to work order
                batches = frappe.get_all(
                    "Batch AMB",
                    filters={"work_order_ref": work_order_name},
                    fields=["name", "workflow_state", "custom_plant_code"]
                )
                
                # Determine overall zone status
                zone_status = WarehouseBatchIntegration.calculate_zone_status_from_batches(batches)
                
                # Update work order zone status
                frappe.db.set_value("Work Order", work_order_name, {
                    "custom_current_zone_status": zone_status,
                    "custom_last_zone_update": now_datetime()
                })
                
                frappe.db.commit()
                
        except Exception as e:
            frappe.log_error(f"Error syncing zone status with batch quality: {str(e)}")
    
    @staticmethod
    def calculate_zone_status_from_batches(batches):
        """
        Calculate zone status based on batch quality states.
        """
        if not batches:
            return "Red Zone"
            
        failed_count = 0
        hold_count = 0
        approved_count = 0
        
        for batch in batches:
            quality_status = WarehouseBatchIntegration.get_batch_quality_status(batch["name"])
            
            if quality_status in ["Failed", "Rejected"]:
                failed_count += 1
            elif quality_status == "Hold":
                hold_count += 1
            elif quality_status in ["Passed", "Approved"]:
                approved_count += 1
        
        total_batches = len(batches)
        
        # All batches approved = Green Zone
        if approved_count == total_batches:
            return "Green Zone"
        
        # Any failures or majority in hold = Red Zone
        if failed_count > 0 or hold_count > (total_batches / 2):
            return "Red Zone"
        
        # Default to Red Zone for safety
        return "Red Zone"
    
    @staticmethod
    def get_batch_location_tracking_info(batch_amb_name):
        """
        Get comprehensive location tracking information for a batch.
        """
        try:
            # Get current bin locations
            bin_locations = frappe.db.sql("""
                SELECT 
                    b.warehouse,
                    b.actual_qty,
                    w.warehouse_type,
                    w.custom_temperature_control,
                    w.custom_target_temperature,
                    b.custom_current_batch,
                    b.custom_last_batch_movement
                FROM `tabBin` b
                INNER JOIN `tabWarehouse` w ON b.warehouse = w.name
                WHERE b.custom_batch_amb_reference = %s
                AND b.actual_qty > 0
            """, batch_amb_name, as_dict=True)
            
            # Get movement history
            movement_history = frappe.db.sql("""
                SELECT 
                    se.name as stock_entry,
                    se.posting_date,
                    se.purpose,
                    se.custom_sap_movement_type,
                    sei.s_warehouse,
                    sei.t_warehouse,
                    sei.qty,
                    sei.batch_no
                FROM `tabStock Entry` se
                INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
                WHERE sei.batch_no IN (
                    SELECT erpnext_batch_reference 
                    FROM `tabBatch AMB` 
                    WHERE name = %s
                )
                ORDER BY se.posting_date DESC, se.posting_time DESC
                LIMIT 10
            """, batch_amb_name, as_dict=True)
            
            return {
                "current_locations": bin_locations,
                "movement_history": movement_history,
                "total_locations": len(bin_locations),
                "total_quantity": sum(loc["actual_qty"] for loc in bin_locations)
            }
            
        except Exception as e:
            frappe.log_error(f"Error getting batch location tracking info: {str(e)}")
            return {"error": str(e)}
    
    @staticmethod
    def create_warehouse_batch_dashboard_data():
        """
        Generate dashboard data combining warehouse and batch information.
        """
        try:
            # Get warehouse statistics with batch context
            warehouse_batch_stats = frappe.db.sql("""
                SELECT 
                    w.name as warehouse,
                    w.warehouse_type,
                    w.custom_temperature_control,
                    COUNT(DISTINCT b.custom_batch_amb_reference) as unique_batches,
                    COUNT(DISTINCT b.item_code) as unique_items,
                    SUM(b.actual_qty) as total_quantity,
                    COUNT(CASE WHEN b.custom_batch_quality_status = 'Passed' THEN 1 END) as passed_batches,
                    COUNT(CASE WHEN b.custom_batch_quality_status = 'Failed' THEN 1 END) as failed_batches,
                    COUNT(CASE WHEN b.custom_batch_quality_status = 'Hold' THEN 1 END) as hold_batches,
                    COUNT(CASE WHEN b.custom_batch_quality_status = 'Pending' THEN 1 END) as pending_batches
                FROM `tabWarehouse` w
                LEFT JOIN `tabBin` b ON w.name = b.warehouse AND b.actual_qty > 0
                WHERE w.is_group = 0
                GROUP BY w.name, w.warehouse_type, w.custom_temperature_control
                ORDER BY w.warehouse_type, w.name
            """, as_dict=True)
            
            return warehouse_batch_stats
            
        except Exception as e:
            frappe.log_error(f"Error creating warehouse batch dashboard data: {str(e)}")
            return []

# API Endpoints for integration

@frappe.whitelist()
def get_batch_warehouse_locations(batch_amb_name):
    """
    API: Get all warehouse locations for a batch.
    """
    return WarehouseBatchIntegration.get_batch_location_tracking_info(batch_amb_name)

@frappe.whitelist()
def get_warehouse_batch_summary(warehouse=None):
    """
    API: Get batch summary for warehouse(s).
    """
    try:
        filters = {}
        if warehouse:
            filters["warehouse"] = warehouse
            
        data = frappe.db.sql("""
            SELECT 
                warehouse,
                COUNT(DISTINCT custom_batch_amb_reference) as batch_count,
                COUNT(DISTINCT item_code) as item_count,
                SUM(actual_qty) as total_qty,
                GROUP_CONCAT(DISTINCT custom_batch_quality_status) as quality_statuses
            FROM `tabBin`
            WHERE actual_qty > 0 
            {where_clause}
            GROUP BY warehouse
        """.format(
            where_clause=f"AND warehouse = '{warehouse}'" if warehouse else ""
        ), as_dict=True)
        
        return {"status": "success", "data": data}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def sync_batch_warehouse_data(batch_amb_name=None):
    """
    API: Manually sync batch-warehouse data.
    """
    try:
        if batch_amb_name:
            # Sync specific batch
            batch_doc = frappe.get_doc("Batch AMB", batch_amb_name)
            if batch_doc.erpnext_batch_reference:
                # Update all bins with this batch
                bins = frappe.get_all(
                    "Bin",
                    filters={"custom_current_batch": batch_doc.erpnext_batch_reference},
                    fields=["name", "warehouse", "item_code"]
                )
                
                for bin_rec in bins:
                    WarehouseBatchIntegration.update_bin_batch_info(
                        bin_rec.warehouse, bin_rec.item_code, 
                        batch_doc.erpnext_batch_reference, 0  # qty not changed
                    )
        else:
            # Sync all batches
            batches = frappe.get_all(
                "Batch AMB",
                filters={"erpnext_batch_reference": ["!=", ""]},
                fields=["name", "erpnext_batch_reference"]
            )
            
            for batch in batches:
                bins = frappe.get_all(
                    "Bin",
                    filters={"custom_current_batch": batch.erpnext_batch_reference},
                    fields=["name", "warehouse", "item_code"]
                )
                
                for bin_rec in bins:
                    WarehouseBatchIntegration.update_bin_batch_info(
                        bin_rec.warehouse, bin_rec.item_code,
                        batch.erpnext_batch_reference, 0
                    )
        
        return {"status": "success", "message": "Batch-warehouse data synchronized"}
        
    except Exception as e:
        frappe.log_error(f"Error syncing batch-warehouse data: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def create_warehouse_batch_report():
    """
    API: Generate comprehensive warehouse-batch integration report.
    """
    try:
        dashboard_data = WarehouseBatchIntegration.create_warehouse_batch_dashboard_data()
        
        report = {
            "generated_on": now_datetime(),
            "warehouse_statistics": dashboard_data,
            "summary": {
                "total_warehouses": len(dashboard_data),
                "total_unique_batches": sum(row.get("unique_batches", 0) for row in dashboard_data),
                "temperature_controlled_warehouses": len([row for row in dashboard_data if row.get("custom_temperature_control")]),
                "quality_distribution": {
                    "passed": sum(row.get("passed_batches", 0) for row in dashboard_data),
                    "failed": sum(row.get("failed_batches", 0) for row in dashboard_data),
                    "hold": sum(row.get("hold_batches", 0) for row in dashboard_data),
                    "pending": sum(row.get("pending_batches", 0) for row in dashboard_data)
                }
            }
        }
        
        return {"status": "success", "report": report}
        
    except Exception as e:
        frappe.log_error(f"Error creating warehouse batch report: {str(e)}")
        return {"status": "error", "message": str(e)}
