# -*- coding: utf-8 -*-
# Sales Order Integration with Warehouse Operations
# Copyright (c) 2025, AMB Wellness & Spa and contributors

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt
import json

class SalesOrderIntegration:
    """Integration layer between Sales Orders and Warehouse Operations"""
    
    @staticmethod
    def on_sales_order_submit(doc, method):
        """Handle sales order submission - create fulfillment and check availability"""
        try:
            # Create Sales Order Fulfillment
            fulfillment = SalesOrderIntegration.create_fulfillment_from_sales_order(doc)
            
            if fulfillment:
                frappe.msgprint(_("Sales Order Fulfillment {0} created").format(fulfillment.name))
                
                # Link MRP Planning if exists
                SalesOrderIntegration.link_mrp_planning(doc.name, fulfillment.name)
                
        except Exception as e:
            frappe.log_error(f"Sales Order Integration Error: {str(e)}")
            # Don't fail sales order submission due to integration issues
    
    @staticmethod
    def create_fulfillment_from_sales_order(sales_order_doc):
        """Create fulfillment document from sales order"""
        try:
            # Check if fulfillment already exists
            existing = frappe.db.exists("Sales Order Fulfillment", {"sales_order": sales_order_doc.name})
            if existing:
                return frappe.get_doc("Sales Order Fulfillment", existing)
            
            fulfillment = frappe.get_doc({
                "doctype": "Sales Order Fulfillment",
                "sales_order": sales_order_doc.name,
                "customer": sales_order_doc.customer,
                "delivery_date": sales_order_doc.delivery_date,
                "fulfillment_status": "Draft",
                "warehouse": sales_order_doc.set_warehouse,
                "plant_code": SalesOrderIntegration.determine_plant_code(sales_order_doc)
            })
            
            fulfillment.insert()
            return fulfillment
            
        except Exception as e:
            frappe.log_error(f"Failed to create fulfillment: {str(e)}")
            return None
    
    @staticmethod
    def determine_plant_code(sales_order_doc):
        """Determine plant code based on items in sales order"""
        plant_codes = set()
        
        for item in sales_order_doc.items:
            item_code = item.item_code
            
            # Get plant code based on item code patterns
            if item_code.startswith('M'):
                plant_codes.add('juice')
            elif item_code.startswith('02'):
                plant_codes.add('dry')
            elif item_code.startswith('0334'):
                plant_codes.add('0334')  # Mix plant
            elif item_code.startswith('03'):
                plant_codes.add('dry')
            else:
                plant_codes.add('0334')  # Default to mix plant
        
        # Return primary plant code (could be enhanced for multi-plant orders)
        return list(plant_codes)[0] if plant_codes else '0334'
    
    @staticmethod
    def link_mrp_planning(sales_order, fulfillment_name):
        """Link existing MRP Planning with fulfillment"""
        try:
            mrp_planning = frappe.db.get_value("MRP Planning", {"sales_order": sales_order}, "name")
            
            if mrp_planning:
                mrp_doc = frappe.get_doc("MRP Planning", mrp_planning)
                mrp_doc.db_set("custom_sales_order_fulfillment", fulfillment_name)
                
                # Update work orders created by MRP with fulfillment reference
                work_orders = frappe.get_all("Work Order", 
                                           filters={"mrp_planning": mrp_planning},
                                           fields=["name"])
                
                for wo in work_orders:
                    frappe.db.set_value("Work Order", wo.name, "custom_sales_order_fulfillment", fulfillment_name)
                
        except Exception as e:
            frappe.log_error(f"Failed to link MRP Planning: {str(e)}")
    
    @staticmethod
    def check_warehouse_availability(sales_order_doc):
        """Check warehouse availability for sales order items"""
        availability_status = []
        
        for item in sales_order_doc.items:
            warehouse = item.warehouse or sales_order_doc.set_warehouse
            if not warehouse:
                continue
                
            available_qty = SalesOrderIntegration.get_available_stock(item.item_code, warehouse)
            required_qty = flt(item.qty)
            
            status = {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "required_qty": required_qty,
                "available_qty": available_qty,
                "shortage_qty": max(0, required_qty - available_qty),
                "availability_status": "Available" if available_qty >= required_qty else "Shortage"
            }
            
            availability_status.append(status)
        
        return availability_status
    
    @staticmethod
    def get_available_stock(item_code, warehouse, batch_no=None):
        """Get available stock for item in warehouse"""
        filters = {
            "item_code": item_code,
            "warehouse": warehouse,
            "is_cancelled": 0
        }
        
        if batch_no:
            filters["batch_no"] = batch_no
            
        stock_entries = frappe.db.sql("""
            SELECT SUM(actual_qty) as available_qty
            FROM `tabStock Ledger Entry`
            WHERE item_code = %(item_code)s
            AND warehouse = %(warehouse)s
            AND is_cancelled = 0
            {batch_filter}
        """.format(
            batch_filter="AND batch_no = %(batch_no)s" if batch_no else ""
        ), filters, as_dict=True)
        
        return stock_entries[0].available_qty if stock_entries and stock_entries[0].available_qty else 0
    
    @staticmethod
    def create_delivery_note_integration(delivery_note_doc, method):
        """Handle delivery note creation with warehouse integration"""
        try:
            # Validate warehouse pick completion
            SalesOrderIntegration.validate_pick_completion(delivery_note_doc)
            
            # Generate quality certificates
            SalesOrderIntegration.generate_delivery_certificates(delivery_note_doc)
            
            # Update batch tracking
            SalesOrderIntegration.update_delivery_batch_tracking(delivery_note_doc)
            
            # Create FDA compliance records if required
            SalesOrderIntegration.create_fda_compliance_records(delivery_note_doc)
            
        except Exception as e:
            frappe.log_error(f"Delivery Note Integration Error: {str(e)}")
            # Don't fail delivery note due to integration issues
    
    @staticmethod
    def validate_pick_completion(delivery_note_doc):
        """Validate that all warehouse pick tasks are completed"""
        for item in delivery_note_doc.items:
            sales_order = item.against_sales_order
            
            if sales_order:
                # Check if fulfillment exists
                fulfillment = frappe.db.get_value("Sales Order Fulfillment", 
                                                {"sales_order": sales_order}, "name")
                
                if fulfillment:
                    # Check pick task completion
                    incomplete_tasks = frappe.get_all("Warehouse Pick Task",
                                                     filters={
                                                         "sales_order_fulfillment": fulfillment,
                                                         "pick_task_status": ["not in", ["Completed", "Cancelled"]]
                                                     },
                                                     fields=["name", "pick_task_status"])
                    
                    if incomplete_tasks:
                        task_list = ", ".join([task.name for task in incomplete_tasks])
                        frappe.msgprint(_("Warning: Incomplete pick tasks found: {0}").format(task_list), 
                                      alert=True)
    
    @staticmethod
    def generate_delivery_certificates(delivery_note_doc):
        """Generate quality certificates for delivery"""
        for item in delivery_note_doc.items:
            if not item.batch_no:
                continue
                
            try:
                # Check if COA exists for batch
                coa_exists = frappe.db.exists("COA AMB", {"batch_no": item.batch_no})
                
                if not coa_exists:
                    # Create COA for batch if required
                    SalesOrderIntegration.create_coa_for_batch(item.batch_no, item.item_code)
                
                # Check if TDS exists for item
                tds_exists = frappe.db.exists("TDS Product Specification", {"item_code": item.item_code})
                
                if not tds_exists:
                    frappe.msgprint(_("TDS not found for item {0}").format(item.item_code), alert=True)
                
            except Exception as e:
                frappe.log_error(f"Failed to generate certificates for {item.item_code}: {str(e)}")
    
    @staticmethod
    def create_coa_for_batch(batch_no, item_code):
        """Create COA for batch automatically"""
        try:
            # Get TDS for item
            tds = frappe.db.get_value("TDS Product Specification", {"item_code": item_code}, "name")
            
            if tds:
                coa = frappe.get_doc({
                    "doctype": "COA AMB",
                    "batch_no": batch_no,
                    "item_code": item_code,
                    "linked_tds": tds,
                    "coa_date": nowdate(),
                    "validation_status": "Pending Review",
                    "overall_compliance_status": "PENDING"
                })
                
                coa.insert()
                frappe.msgprint(_("COA {0} created for batch {1}").format(coa.name, batch_no))
                
        except Exception as e:
            frappe.log_error(f"Failed to create COA for batch {batch_no}: {str(e)}")
    
    @staticmethod
    def update_delivery_batch_tracking(delivery_note_doc):
        """Update batch tracking with delivery information"""
        for item in delivery_note_doc.items:
            if not item.batch_no:
                continue
                
            try:
                # Get Batch AMB record
                batch_amb = frappe.db.get_value("Batch AMB", 
                                               {"erpnext_batch_reference": item.batch_no}, 
                                               "name")
                
                if batch_amb:
                    SalesOrderIntegration.update_batch_delivery_info(batch_amb, delivery_note_doc, item)
                    
            except Exception as e:
                frappe.log_error(f"Failed to update batch tracking for {item.batch_no}: {str(e)}")
    
    @staticmethod
    def update_batch_delivery_info(batch_amb, delivery_note_doc, item):
        """Update Batch AMB with delivery information"""
        try:
            batch_doc = frappe.get_doc("Batch AMB", batch_amb)
            
            # Update batch processing history
            if hasattr(batch_doc, 'batch_processing_history') and batch_doc.batch_processing_history:
                history_doc = frappe.get_doc("Batch Processing History", batch_doc.batch_processing_history)
                
                # Add delivery step
                history_doc.append("processing_steps", {
                    "step_name": "Customer Delivery",
                    "step_type": "Delivery",
                    "start_time": now_datetime(),
                    "status": "Completed",
                    "operator": frappe.session.user,
                    "notes": f"Delivered {item.qty} units via delivery note {delivery_note_doc.name}",
                    "customer_reference": delivery_note_doc.customer,
                    "delivery_note_reference": delivery_note_doc.name,
                    "tracking_number": delivery_note_doc.lr_no if hasattr(delivery_note_doc, 'lr_no') else None
                })
                
                history_doc.save(ignore_permissions=True)
                
        except Exception as e:
            frappe.log_error(f"Failed to update batch delivery info: {str(e)}")
    
    @staticmethod
    def create_fda_compliance_records(delivery_note_doc):
        """Create FDA compliance records for delivery"""
        try:
            # Check if any items require FDA compliance
            fda_items = []
            
            for item in delivery_note_doc.items:
                is_fda_regulated = frappe.db.get_value("Item", item.item_code, "custom_fda_regulated")
                if is_fda_regulated:
                    fda_items.append(item)
            
            if fda_items:
                # Create FDA compliance record
                compliance_doc = frappe.get_doc({
                    "doctype": "FDA Compliance Record",
                    "document_type": "Delivery Note",
                    "document_reference": delivery_note_doc.name,
                    "compliance_date": nowdate(),
                    "customer": delivery_note_doc.customer,
                    "status": "Compliant",
                    "items": [{"item_code": item.item_code, "batch_no": item.batch_no} for item in fda_items]
                })
                
                compliance_doc.insert()
                
        except Exception as e:
            frappe.log_error(f"Failed to create FDA compliance records: {str(e)}")

# Warehouse Integration API Functions
@frappe.whitelist()
def check_sales_order_availability(sales_order):
    """Check warehouse availability for sales order"""
    try:
        so_doc = frappe.get_doc("Sales Order", sales_order)
        availability = SalesOrderIntegration.check_warehouse_availability(so_doc)
        return {"success": True, "availability": availability}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def create_fulfillment_from_sales_order(sales_order):
    """Create fulfillment from sales order"""
    try:
        so_doc = frappe.get_doc("Sales Order", sales_order)
        fulfillment = SalesOrderIntegration.create_fulfillment_from_sales_order(so_doc)
        
        if fulfillment:
            return {"success": True, "fulfillment": fulfillment.name}
        else:
            return {"success": False, "message": "Failed to create fulfillment"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def get_fulfillment_status(sales_order):
    """Get fulfillment status for sales order"""
    try:
        fulfillment = frappe.db.get_value("Sales Order Fulfillment", 
                                        {"sales_order": sales_order}, 
                                        ["name", "fulfillment_status", "total_items"])
        
        if fulfillment:
            fulfillment_doc = frappe.get_doc("Sales Order Fulfillment", fulfillment[0])
            
            # Get pick task status
            pick_tasks = frappe.get_all("Warehouse Pick Task",
                                      filters={"sales_order_fulfillment": fulfillment[0]},
                                      fields=["name", "pick_task_status", "assigned_to"])
            
            return {
                "success": True,
                "fulfillment": {
                    "name": fulfillment[0],
                    "status": fulfillment[1],
                    "total_items": fulfillment[2],
                    "pick_tasks": pick_tasks
                }
            }
        else:
            return {"success": False, "message": "Fulfillment not found"}
            
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def validate_delivery_readiness(delivery_note):
    """Validate delivery note readiness"""
    try:
        dn_doc = frappe.get_doc("Delivery Note", delivery_note)
        
        issues = []
        warnings = []
        
        for item in dn_doc.items:
            sales_order = item.against_sales_order
            
            if sales_order:
                # Check fulfillment status
                fulfillment = frappe.db.get_value("Sales Order Fulfillment", 
                                                {"sales_order": sales_order}, 
                                                ["name", "fulfillment_status"])
                
                if fulfillment:
                    if fulfillment[1] not in ["Ready to Ship", "Picking Complete"]:
                        warnings.append(f"Fulfillment {fulfillment[0]} status: {fulfillment[1]}")
                    
                    # Check pick task completion
                    incomplete_tasks = frappe.get_all("Warehouse Pick Task",
                                                     filters={
                                                         "sales_order_fulfillment": fulfillment[0],
                                                         "pick_task_status": ["not in", ["Completed", "Cancelled"]]
                                                     },
                                                     fields=["name"])
                    
                    if incomplete_tasks:
                        issues.append(f"Incomplete pick tasks: {len(incomplete_tasks)}")
                else:
                    warnings.append(f"No fulfillment found for sales order {sales_order}")
        
        return {
            "success": True,
            "ready": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}
