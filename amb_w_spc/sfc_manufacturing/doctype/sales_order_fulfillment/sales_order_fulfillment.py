# -*- coding: utf-8 -*-
# Copyright (c) 2025, AMB Wellness & Spa and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import nowdate, now_datetime, flt
import json

class SalesOrderFulfillment(Document):
    def validate(self):
        """Validate the Sales Order Fulfillment document"""
        self.validate_sales_order()
        self.load_sales_order_items()
        self.check_warehouse_availability()
        self.validate_customer_requirements()
        self.update_compliance_flags()
        
    def before_save(self):
        """Update totals and status before saving"""
        self.update_totals()
        self.update_fulfillment_status()
        self.last_updated = now_datetime()
        
    def on_submit(self):
        """Create warehouse pick tasks and initiate fulfillment"""
        try:
            self.create_warehouse_pick_tasks()
            self.generate_quality_certificates()
            self.create_batch_tracking_entries()
            self.update_audit_trail("Sales Order Fulfillment Submitted")
            frappe.msgprint(_("Sales Order Fulfillment submitted successfully. Pick tasks created."))
        except Exception as e:
            frappe.log_error(f"Sales Order Fulfillment submission failed: {str(e)}")
            frappe.throw(_("Failed to submit fulfillment: {0}").format(str(e)))
    
    def validate_sales_order(self):
        """Validate sales order exists and is confirmed"""
        if not self.sales_order:
            frappe.throw(_("Sales Order is mandatory"))
            
        if not frappe.db.exists("Sales Order", self.sales_order):
            frappe.throw(_("Sales Order {0} does not exist").format(self.sales_order))
            
        so_status = frappe.db.get_value("Sales Order", self.sales_order, "status")
        if so_status not in ["To Deliver and Bill", "To Deliver", "Completed"]:
            frappe.throw(_("Sales Order must be confirmed to create fulfillment"))
    
    def load_sales_order_items(self):
        """Load items from sales order if not already loaded"""
        if self.fulfillment_items:
            return  # Items already loaded
            
        so_items = frappe.get_all(
            "Sales Order Item",
            filters={"parent": self.sales_order},
            fields=["item_code", "item_name", "qty", "warehouse", "delivery_date"]
        )
        
        for item in so_items:
            # Check if item requires batch tracking
            item_doc = frappe.get_doc("Item", item.item_code)
            has_batch_no = getattr(item_doc, 'has_batch_no', 0)
            is_stock_item = getattr(item_doc, 'is_stock_item', 0)
            
            fulfillment_item = {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": item.qty,
                "warehouse": item.warehouse or self.warehouse,
                "batch_required": has_batch_no,
                "fulfillment_status": "Pending",
                "quality_check_required": self.requires_quality_check(item.item_code),
                "temperature_controlled": self.requires_temperature_control(item.item_code),
                "expiry_date_check": has_batch_no
            }
            
            self.append("fulfillment_items", fulfillment_item)
    
    def check_warehouse_availability(self):
        """Check warehouse availability and update item status"""
        for item in self.fulfillment_items:
            if not item.warehouse:
                continue
                
            # Get available quantity
            available_qty = self.get_available_stock(item.item_code, item.warehouse, item.specific_batch)
            allocated_qty = min(available_qty, item.qty)
            pending_qty = item.qty - allocated_qty
            
            item.available_qty = available_qty
            item.allocated_qty = allocated_qty
            item.pending_qty = pending_qty
            
            # Update status based on availability
            if allocated_qty >= item.qty:
                item.fulfillment_status = "Available"
            elif allocated_qty > 0:
                item.fulfillment_status = "Partial"
            else:
                item.fulfillment_status = "Unavailable"
    
    def get_available_stock(self, item_code, warehouse, batch_no=None):
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
    
    def create_warehouse_pick_tasks(self):
        """Create warehouse pick tasks for available items"""
        pick_tasks_created = 0
        
        # Group items by warehouse/zone for efficient picking
        warehouse_groups = self.group_items_by_warehouse()
        
        for warehouse, items in warehouse_groups.items():
            if not items:
                continue
                
            pick_task = self.create_pick_task_for_warehouse(warehouse, items)
            if pick_task:
                pick_tasks_created += 1
                
                # Update fulfillment items
                for item in items:
                    for fulfillment_item in self.fulfillment_items:
                        if (fulfillment_item.item_code == item["item_code"] and 
                            fulfillment_item.warehouse == warehouse):
                            fulfillment_item.pick_task_created = 1
                            fulfillment_item.fulfillment_status = "Pick Task Created"
        
        if pick_tasks_created:
            frappe.msgprint(_("Created {0} warehouse pick tasks").format(pick_tasks_created))
    
    def group_items_by_warehouse(self):
        """Group fulfillment items by warehouse for efficient picking"""
        warehouse_groups = {}
        
        for item in self.fulfillment_items:
            if item.allocated_qty <= 0:
                continue  # Skip unavailable items
                
            warehouse = item.warehouse or self.warehouse
            if warehouse not in warehouse_groups:
                warehouse_groups[warehouse] = []
                
            warehouse_groups[warehouse].append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty_to_pick": item.allocated_qty,
                "batch_required": item.batch_required,
                "specific_batch": item.specific_batch,
                "temperature_controlled": item.temperature_controlled,
                "quality_check_required": item.quality_check_required,
                "customer_specification": item.customer_specification
            })
            
        return warehouse_groups
    
    def create_pick_task_for_warehouse(self, warehouse, items):
        """Create a pick task for specific warehouse"""
        try:
            # Determine plant code and zone
            plant_code = self.get_plant_code_for_warehouse(warehouse)
            zone_assignment = self.get_warehouse_zone(warehouse)
            
            pick_task_data = {
                "doctype": "Warehouse Pick Task",
                "sales_order_fulfillment": self.name,
                "sales_order": self.sales_order,
                "pick_task_status": "Open",
                "priority": self.get_pick_priority(),
                "zone_assignment": zone_assignment,
                "plant_code": plant_code,
                "sap_movement_type": "601",  # Goods Issue to Customer
                "movement_reason": "Sales Order Fulfillment",
                "posting_date": nowdate(),
                "batch_selection_criteria": self.get_batch_selection_criteria(),
                "temperature_zone": self.get_temperature_zone_for_items(items),
                "verification_required": 1,
                "pick_task_items": []
            }
            
            # Add items to pick task
            for item in items:
                # Get optimal batch for this item
                batch_no = self.get_optimal_batch_for_item(
                    item["item_code"], 
                    warehouse, 
                    item["qty_to_pick"],
                    item["specific_batch"]
                )
                
                pick_item = {
                    "item_code": item["item_code"],
                    "item_name": item["item_name"],
                    "qty_to_pick": item["qty_to_pick"],
                    "warehouse": warehouse,
                    "batch_no": batch_no,
                    "bin_location": self.get_bin_location(item["item_code"], warehouse, batch_no),
                    "pick_status": "Pending",
                    "quality_status": "Released"  # Assume released unless check required
                }
                
                pick_task_data["pick_task_items"].append(pick_item)
            
            # Create the pick task
            pick_task = frappe.get_doc(pick_task_data)
            pick_task.insert()
            
            # Add to warehouse pick tasks table
            self.append("warehouse_pick_tasks", {
                "pick_task_reference": pick_task.name,
                "warehouse": warehouse,
                "total_items": len(items),
                "status": "Open",
                "assigned_to": self.get_default_picker_for_zone(zone_assignment)
            })
            
            return pick_task.name
            
        except Exception as e:
            frappe.log_error(f"Failed to create pick task for warehouse {warehouse}: {str(e)}")
            return None
    
    def get_optimal_batch_for_item(self, item_code, warehouse, qty_needed, specific_batch=None):
        """Get optimal batch based on FEFO/FIFO or specific requirements"""
        if specific_batch:
            return specific_batch
            
        # Get available batches sorted by expiry date (FEFO)
        batches = frappe.db.sql("""
            SELECT sle.batch_no, b.expiry_date, SUM(sle.actual_qty) as available_qty
            FROM `tabStock Ledger Entry` sle
            INNER JOIN `tabBatch` b ON sle.batch_no = b.name
            WHERE sle.item_code = %s 
            AND sle.warehouse = %s 
            AND sle.is_cancelled = 0
            AND b.expiry_date > CURDATE()
            GROUP BY sle.batch_no, b.expiry_date
            HAVING available_qty > 0
            ORDER BY b.expiry_date ASC
            LIMIT 1
        """, (item_code, warehouse), as_dict=True)
        
        return batches[0].batch_no if batches else None
    
    def generate_quality_certificates(self):
        """Generate quality certificates for shipped batches"""
        for item in self.fulfillment_items:
            if not item.quality_check_required:
                continue
                
            batch_no = item.specific_batch or self.get_batch_for_item(item.item_code, item.warehouse)
            if not batch_no:
                continue
                
            # Check if certificates already exist
            existing_coa = frappe.db.exists("COA AMB", {"batch_no": batch_no})
            existing_tds = frappe.db.exists("TDS Product Specification", {"item_code": item.item_code})
            
            if existing_coa:
                self.append("quality_certificates", {
                    "certificate_type": "COA",
                    "certificate_reference": existing_coa,
                    "batch_no": batch_no,
                    "generation_status": "Generated",
                    "generated_date": now_datetime()
                })
            
            if existing_tds:
                self.append("quality_certificates", {
                    "certificate_type": "TDS",
                    "certificate_reference": existing_tds,
                    "batch_no": batch_no,
                    "generation_status": "Generated",
                    "generated_date": now_datetime()
                })
    
    def create_batch_tracking_entries(self):
        """Create batch tracking entries for shipments"""
        for item in self.fulfillment_items:
            if not item.batch_required:
                continue
                
            batch_no = item.specific_batch or self.get_batch_for_item(item.item_code, item.warehouse)
            if not batch_no:
                continue
                
            # Update batch processing history
            self.update_batch_processing_history(batch_no, item.item_code, item.allocated_qty)
    
    def update_batch_processing_history(self, batch_no, item_code, qty_shipped):
        """Update batch processing history with shipment information"""
        try:
            # Get associated Batch AMB record
            batch_amb = frappe.db.get_value("Batch AMB", {"erpnext_batch_reference": batch_no}, "name")
            
            if batch_amb and frappe.db.exists("Batch AMB", batch_amb):
                batch_doc = frappe.get_doc("Batch AMB", batch_amb)
                
                if hasattr(batch_doc, 'batch_processing_history') and batch_doc.batch_processing_history:
                    history_doc = frappe.get_doc("Batch Processing History", batch_doc.batch_processing_history)
                    
                    # Add shipment step
                    history_doc.append("processing_steps", {
                        "step_name": "Customer Shipment",
                        "step_type": "Shipment",
                        "start_time": now_datetime(),
                        "status": "Completed",
                        "operator": frappe.session.user,
                        "notes": f"Shipped {qty_shipped} units to customer via Sales Order {self.sales_order}",
                        "customer_reference": self.customer,
                        "sales_order_reference": self.sales_order
                    })
                    
                    history_doc.save(ignore_permissions=True)
                    
        except Exception as e:
            frappe.log_error(f"Failed to update batch processing history: {str(e)}")
    
    # Helper methods
    def requires_quality_check(self, item_code):
        """Check if item requires quality check"""
        item_doc = frappe.get_doc("Item", item_code)
        return getattr(item_doc, 'inspection_required_before_delivery', 0)
    
    def requires_temperature_control(self, item_code):
        """Check if item requires temperature control"""
        # Check item custom fields for temperature requirements
        return frappe.db.get_value("Item", item_code, "custom_temperature_controlled") or 0
    
    def get_plant_code_for_warehouse(self, warehouse):
        """Get plant code for warehouse"""
        return frappe.db.get_value("Warehouse", warehouse, "custom_warehouse_code") or "0334"
    
    def get_warehouse_zone(self, warehouse):
        """Get warehouse zone assignment"""
        zone_type = frappe.db.get_value("Warehouse", warehouse, "custom_zone_type")
        return warehouse if zone_type else None
    
    def get_pick_priority(self):
        """Determine pick priority based on delivery date"""
        from datetime import datetime, timedelta
        
        if self.delivery_date:
            days_until_delivery = (self.delivery_date - datetime.now().date()).days
            if days_until_delivery <= 1:
                return "High"
            elif days_until_delivery <= 3:
                return "Medium"
        return "Low"
    
    def get_batch_selection_criteria(self):
        """Get batch selection criteria"""
        return "FEFO"  # First Expired, First Out by default
    
    def get_temperature_zone_for_items(self, items):
        """Determine temperature zone for items"""
        temp_controlled = any(item.get("temperature_controlled") for item in items)
        return "Refrigerated" if temp_controlled else "Ambient"
    
    def get_bin_location(self, item_code, warehouse, batch_no):
        """Get bin location for item"""
        # This could be enhanced to get actual bin locations from warehouse management
        return f"{warehouse}-{item_code[:4]}"
    
    def get_default_picker_for_zone(self, zone):
        """Get default picker for warehouse zone"""
        # This could be enhanced to get actual user assignments
        return None
    
    def get_batch_for_item(self, item_code, warehouse):
        """Get any available batch for item"""
        batch = frappe.db.sql("""
            SELECT batch_no 
            FROM `tabStock Ledger Entry` 
            WHERE item_code = %s AND warehouse = %s 
            AND actual_qty > 0 AND is_cancelled = 0
            LIMIT 1
        """, (item_code, warehouse))
        
        return batch[0][0] if batch else None
    
    def validate_customer_requirements(self):
        """Validate customer-specific requirements"""
        for item in self.fulfillment_items:
            if item.lot_specific_requirement:
                # Validate lot/batch availability
                if item.specific_batch:
                    if not frappe.db.exists("Batch", item.specific_batch):
                        frappe.throw(_("Specified batch {0} does not exist for item {1}")
                                   .format(item.specific_batch, item.item_code))
    
    def update_compliance_flags(self):
        """Update compliance requirement flags"""
        # Check if any items require FDA compliance
        self.fda_compliance_required = any(
            self.requires_fda_compliance(item.item_code) for item in self.fulfillment_items
        )
        
        # Check if any items require cold chain
        self.cold_chain_compliance = any(
            item.temperature_controlled for item in self.fulfillment_items
        )
        
        # Check if any items require batch tracking
        self.batch_tracking_required = any(
            item.batch_required for item in self.fulfillment_items
        )
        
        # Update compliance status
        if self.fda_compliance_required or self.cold_chain_compliance or self.batch_tracking_required:
            self.compliance_status = "Under Review"
        else:
            self.compliance_status = "Compliant"
    
    def requires_fda_compliance(self, item_code):
        """Check if item requires FDA compliance"""
        # Check if item is in FDA regulated categories
        return frappe.db.get_value("Item", item_code, "custom_fda_regulated") or 0
    
    def update_totals(self):
        """Update total counts"""
        self.total_items = len(self.fulfillment_items)
    
    def update_fulfillment_status(self):
        """Update overall fulfillment status"""
        if not self.fulfillment_items:
            self.fulfillment_status = "Draft"
            return
            
        statuses = [item.fulfillment_status for item in self.fulfillment_items]
        
        if all(status == "Delivered" for status in statuses):
            self.fulfillment_status = "Completed"
        elif any(status == "Shipped" for status in statuses):
            self.fulfillment_status = "Shipped"
        elif all(status in ["Available", "Pick Task Created"] for status in statuses):
            self.fulfillment_status = "Ready to Ship"
        elif any(status == "Pick Task Created" for status in statuses):
            self.fulfillment_status = "Pick Tasks Created"
        elif any(status in ["Available", "Partial"] for status in statuses):
            self.fulfillment_status = "Warehouse Check"
        else:
            self.fulfillment_status = "Draft"
    
    def update_audit_trail(self, action):
        """Update audit trail with action"""
        timestamp = now_datetime()
        user = frappe.session.user
        
        audit_entry = f"[{timestamp}] {user}: {action}\n"
        
        if self.audit_trail:
            self.audit_trail += audit_entry
        else:
            self.audit_trail = audit_entry

# API Functions
@frappe.whitelist()
def create_fulfillment_from_sales_order(sales_order):
    """Create Sales Order Fulfillment from Sales Order"""
    try:
        # Check if fulfillment already exists
        existing = frappe.db.exists("Sales Order Fulfillment", {"sales_order": sales_order})
        if existing:
            return {"success": False, "message": "Fulfillment already exists", "fulfillment": existing}
        
        # Get sales order data
        so_doc = frappe.get_doc("Sales Order", sales_order)
        
        # Create fulfillment
        fulfillment = frappe.get_doc({
            "doctype": "Sales Order Fulfillment",
            "sales_order": sales_order,
            "customer": so_doc.customer,
            "delivery_date": so_doc.delivery_date,
            "fulfillment_status": "Draft",
            "warehouse": so_doc.set_warehouse
        })
        
        fulfillment.insert()
        
        return {"success": True, "fulfillment": fulfillment.name}
        
    except Exception as e:
        frappe.log_error(f"Failed to create fulfillment: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def update_pick_task_status(pick_task, new_status):
    """Update pick task status and sync with fulfillment"""
    try:
        pick_task_doc = frappe.get_doc("Warehouse Pick Task", pick_task)
        pick_task_doc.pick_task_status = new_status
        
        if new_status == "Completed":
            pick_task_doc.completion_time = now_datetime()
            pick_task_doc.picked_by = frappe.session.user
        
        pick_task_doc.save()
        
        # Update fulfillment status
        if pick_task_doc.sales_order_fulfillment:
            fulfillment_doc = frappe.get_doc("Sales Order Fulfillment", pick_task_doc.sales_order_fulfillment)
            fulfillment_doc.update_fulfillment_status()
            fulfillment_doc.save()
        
        return {"success": True, "message": "Pick task status updated"}
        
    except Exception as e:
        frappe.log_error(f"Failed to update pick task status: {str(e)}")
        return {"success": False, "message": str(e)}
