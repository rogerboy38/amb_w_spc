import frappe
from frappe import _
from frappe.utils import flt, now_datetime, nowdate
import json

class WarehouseIntegration:
    """Integration class for connecting warehouse management with existing systems"""
    
    @staticmethod
    def integrate_with_batch_amb(erpnext_batch_id, stock_entry_name):
        """Integrate warehouse operations with Batch AMB system"""
        try:
            # Import here to avoid circular imports
            from amb_w_spc.sfc_manufacturing.warehouse_management.warehouse_batch_integration import WarehouseBatchIntegration
            
            # Get batch_amb from erpnext batch
            batch_amb_name = WarehouseBatchIntegration.get_batch_amb_from_batch(erpnext_batch_id)
            if not batch_amb_name:
                return False
                
            batch_doc = frappe.get_doc("Batch AMB", batch_amb_name)
            stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
            
            # Create batch processing history entry
            WarehouseBatchIntegration.create_stock_entry_batch_history(stock_entry)
            
            # Update warehouse bins with batch tracking
            WarehouseBatchIntegration.update_warehouse_bin_batch_tracking(stock_entry)
            
            # Sync zone status with batch quality
            if stock_entry.custom_work_order_reference:
                WarehouseBatchIntegration.sync_warehouse_zone_status_with_batch_quality(
                    stock_entry.custom_work_order_reference
                )
            
            return True
            
        except Exception as e:
            frappe.log_error(f"Batch AMB integration failed: {str(e)}")
            return False
    
    @staticmethod
    def integrate_with_mrp_planning(work_order_name):
        """Integrate warehouse zone status with MRP Planning"""
        try:
            work_order = frappe.get_doc("Work Order", work_order_name)
            
            # Find related MRP Planning entries
            mrp_plannings = frappe.get_all(
                "MRP Planning",
                filters={"sales_order": work_order.sales_order},
                fields=["name"]
            )
            
            for mrp in mrp_plannings:
                mrp_doc = frappe.get_doc("MRP Planning", mrp.name)
                
                # Update MRP with warehouse status
                if hasattr(mrp_doc, 'custom_warehouse_status'):
                    warehouse_status = json.loads(mrp_doc.custom_warehouse_status or "{}")
                else:
                    warehouse_status = {}
                
                warehouse_status[work_order_name] = {
                    "zone_status": work_order.custom_current_zone_status,
                    "completion_percentage": work_order.custom_material_completion_percentage,
                    "last_update": work_order.custom_last_zone_update
                }
                
                frappe.db.set_value(
                    "MRP Planning",
                    mrp.name,
                    "custom_warehouse_status",
                    json.dumps(warehouse_status)
                )
            
            return True
            
        except Exception as e:
            frappe.log_error(f"MRP Planning integration failed: {str(e)}")
            return False
    
    @staticmethod
    def create_warehouse_pick_request(work_order_name):
        """Create warehouse pick request based on Work Order requirements"""
        try:
            work_order = frappe.get_doc("Work Order", work_order_name)
            
            if not work_order.bom_no:
                return None
            
            # Get BOM items
            bom_items = frappe.get_all(
                "BOM Item",
                filters={"parent": work_order.bom_no},
                fields=["item_code", "qty", "warehouse", "item_name"]
            )
            
            # Create pick request document
            pick_request = frappe.get_doc({
                "doctype": "Warehouse Pick Request",
                "work_order": work_order_name,
                "requested_by": frappe.session.user,
                "request_date": nowdate(),
                "status": "Pending",
                "zone_status": work_order.custom_current_zone_status,
                "items": []
            })
            
            for bom_item in bom_items:
                required_qty = flt(bom_item.qty * work_order.qty)
                available_qty = get_available_qty(bom_item.item_code, bom_item.warehouse)
                
                pick_request.append("items", {
                    "item_code": bom_item.item_code,
                    "item_name": bom_item.item_name,
                    "required_qty": required_qty,
                    "available_qty": available_qty,
                    "warehouse": bom_item.warehouse,
                    "pick_qty": min(required_qty, available_qty)
                })
            
            try:
                pick_request.insert()
                return pick_request.name
            except:
                # If custom DocType doesn't exist, just log the requirement
                frappe.log_error(f"Warehouse Pick Request DocType not found for Work Order {work_order_name}")
                return None
                
        except Exception as e:
            frappe.log_error(f"Pick request creation failed: {str(e)}")
            return None
    
    @staticmethod
    def sync_with_quality_systems(stock_entry_name):
        """Sync warehouse operations with quality management systems"""
        try:
            stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
            
            # Check if quality inspection is required
            for item in stock_entry.items:
                if item.quality_inspection:
                    # Update quality inspection with warehouse details
                    qi_doc = frappe.get_doc("Quality Inspection", item.quality_inspection)
                    
                    # Add warehouse context to quality inspection
                    if hasattr(qi_doc, 'custom_warehouse_context'):
                        warehouse_context = {
                            "sap_movement_type": stock_entry.custom_sap_movement_type,
                            "zone_status": stock_entry.custom_zone_status,
                            "gi_gt_slip": stock_entry.custom_gi_gt_slip_number,
                            "supervisor_signature": bool(stock_entry.custom_warehouse_supervisor_signature)
                        }
                        
                        frappe.db.set_value(
                            "Quality Inspection",
                            item.quality_inspection,
                            "custom_warehouse_context",
                            json.dumps(warehouse_context)
                        )
            
            return True
            
        except Exception as e:
            frappe.log_error(f"Quality system sync failed: {str(e)}")
            return False
    
    @staticmethod
    def update_fda_compliance_records(stock_entry_name):
        """Update FDA compliance records with warehouse operation details"""
        try:
            stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
            
            # Create audit trail entry for FDA compliance
            audit_trail = frappe.get_doc({
                "doctype": "SPC Audit Trail",
                "reference_doctype": "Stock Entry",
                "reference_name": stock_entry_name,
                "event_type": "Warehouse Operation",
                "event_description": f"SAP Movement {stock_entry.custom_sap_movement_type} executed",
                "event_datetime": now_datetime(),
                "user": frappe.session.user,
                "details": json.dumps({
                    "sap_movement_type": stock_entry.custom_sap_movement_type,
                    "zone_status": stock_entry.custom_zone_status,
                    "warehouse_supervisor": bool(stock_entry.custom_warehouse_supervisor_signature),
                    "kitting_supervisor": bool(stock_entry.custom_kitting_supervisor_signature),
                    "gi_gt_slip": stock_entry.custom_gi_gt_slip_number
                })
            })
            
            try:
                audit_trail.insert(ignore_permissions=True)
                return True
            except:
                # If audit trail DocType doesn't exist, just log
                frappe.log_error(f"SPC Audit Trail DocType not found for Stock Entry {stock_entry_name}")
                return False
                
        except Exception as e:
            frappe.log_error(f"FDA compliance update failed: {str(e)}")
            return False

def get_available_qty(item_code, warehouse):
    """Get available quantity for an item in a warehouse"""
    return frappe.db.get_value(
        "Bin",
        {"item_code": item_code, "warehouse": warehouse},
        "actual_qty"
    ) or 0

@frappe.whitelist()
def get_integration_status(work_order_name):
    """API endpoint to get integration status for a Work Order"""
    try:
        integration_status = {
            "work_order": work_order_name,
            "batch_integration": False,
            "mrp_integration": False,
            "quality_integration": False,
            "fda_compliance": False,
            "pick_requests": []
        }
        
        # Check batch integration
        work_order = frappe.get_doc("Work Order", work_order_name)
        if work_order.batch_no:
            batch_exists = frappe.db.exists("Batch AMB", work_order.batch_no)
            integration_status["batch_integration"] = bool(batch_exists)
        
        # Check MRP integration
        if work_order.sales_order:
            mrp_exists = frappe.db.exists("MRP Planning", {"sales_order": work_order.sales_order})
            integration_status["mrp_integration"] = bool(mrp_exists)
        
        # Check quality integration
        quality_inspections = frappe.get_all(
            "Quality Inspection",
            filters={"reference_name": work_order_name},
            fields=["name"]
        )
        integration_status["quality_integration"] = len(quality_inspections) > 0
        
        # Check FDA compliance
        audit_entries = frappe.get_all(
            "SPC Audit Trail",
            filters={
                "reference_doctype": "Work Order",
                "reference_name": work_order_name
            },
            fields=["name"]
        )
        integration_status["fda_compliance"] = len(audit_entries) > 0
        
        return integration_status
        
    except Exception as e:
        frappe.log_error(f"Integration status check failed: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def trigger_warehouse_integration(stock_entry_name):
    """API endpoint to trigger all warehouse integrations"""
    try:
        stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
        results = {
            "stock_entry": stock_entry_name,
            "integrations": {}
        }
        
        # Batch integration
        if stock_entry.batch_no:
            results["integrations"]["batch"] = WarehouseIntegration.integrate_with_batch_amb(
                stock_entry.batch_no, stock_entry_name
            )
        
        # Work Order integration
        if stock_entry.custom_work_order_reference:
            results["integrations"]["mrp"] = WarehouseIntegration.integrate_with_mrp_planning(
                stock_entry.custom_work_order_reference
            )
            
            # Create pick request
            pick_request = WarehouseIntegration.create_warehouse_pick_request(
                stock_entry.custom_work_order_reference
            )
            results["integrations"]["pick_request"] = pick_request
        
        # Quality system integration
        results["integrations"]["quality"] = WarehouseIntegration.sync_with_quality_systems(
            stock_entry_name
        )
        
        # FDA compliance integration
        results["integrations"]["fda"] = WarehouseIntegration.update_fda_compliance_records(
            stock_entry_name
        )
        
        return results
        
    except Exception as e:
        frappe.log_error(f"Warehouse integration trigger failed: {str(e)}")
        return {"status": "error", "message": str(e)}
