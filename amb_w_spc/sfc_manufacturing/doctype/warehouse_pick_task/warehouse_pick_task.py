# -*- coding: utf-8 -*-
# Copyright (c) 2025, AMB Wellness & Spa and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import nowdate, now_datetime, flt

class WarehousePickTask(Document):
    def validate(self):
        """Validate pick task before saving"""
        self.validate_assignment()
        self.calculate_totals()
        self.validate_batch_requirements()
        
    def before_save(self):
        """Update calculations before saving"""
        self.update_remaining_quantities()
        self.calculate_estimated_time()
        
    def on_submit(self):
        """Process pick task completion"""
        self.validate_pick_completion()
        self.create_stock_entries()
        self.update_batch_tracking()
        self.update_fulfillment_status()
        
    def validate_assignment(self):
        """Validate task assignment"""
        if self.pick_task_status == "Assigned" and not self.assigned_to:
            frappe.throw(_("Assigned user is required when status is Assigned"))
            
        if self.assigned_to and not self.assigned_date:
            self.assigned_date = now_datetime()
    
    def calculate_totals(self):
        """Calculate total quantities and validate items"""
        total_items = 0
        total_qty = 0
        
        for item in self.pick_task_items:
            total_items += 1
            total_qty += flt(item.qty_to_pick)
            
            # Validate warehouse availability
            if not self.validate_item_availability(item):
                frappe.msgprint(_("Insufficient stock for item {0} in warehouse {1}")
                              .format(item.item_code, item.warehouse), alert=True)
        
        self.total_items = total_items
        self.total_qty = total_qty
        
    def validate_item_availability(self, item):
        """Validate item availability in warehouse"""
        filters = {
            "item_code": item.item_code,
            "warehouse": item.warehouse,
            "is_cancelled": 0
        }
        
        if item.batch_no:
            filters["batch_no"] = item.batch_no
            
        available_qty = frappe.db.sql("""
            SELECT SUM(actual_qty) as available
            FROM `tabStock Ledger Entry`
            WHERE item_code = %(item_code)s
            AND warehouse = %(warehouse)s
            AND is_cancelled = 0
            {batch_filter}
        """.format(
            batch_filter="AND batch_no = %(batch_no)s" if item.batch_no else ""
        ), filters, as_dict=True)
        
        available = available_qty[0].available if available_qty and available_qty[0].available else 0
        return available >= flt(item.qty_to_pick)
    
    def validate_batch_requirements(self):
        """Validate batch requirements for items"""
        for item in self.pick_task_items:
            # Check if item requires batch and batch is provided
            item_doc = frappe.get_doc("Item", item.item_code)
            if getattr(item_doc, 'has_batch_no', 0) and not item.batch_no:
                frappe.throw(_("Batch number is required for item {0}").format(item.item_code))
                
            # Validate batch expiry for specific batches
            if item.batch_no:
                batch_doc = frappe.get_doc("Batch", item.batch_no)
                if batch_doc.expiry_date and batch_doc.expiry_date < frappe.utils.getdate():
                    frappe.throw(_("Batch {0} for item {1} has expired").format(item.batch_no, item.item_code))
    
    def update_remaining_quantities(self):
        """Update remaining quantities for all items"""
        for item in self.pick_task_items:
            item.remaining_qty = flt(item.qty_to_pick) - flt(item.picked_qty)
    
    def calculate_estimated_time(self):
        """Calculate estimated pick time based on items and warehouse layout"""
        if self.estimated_time:
            return  # Don't override manual estimates
            
        # Basic calculation: 5 minutes per item + 2 minutes per warehouse zone
        base_time = len(self.pick_task_items) * 0.083  # 5 minutes in hours
        zone_time = 0.033  # 2 minutes for zone setup
        
        self.estimated_time = base_time + zone_time
    
    def validate_pick_completion(self):
        """Validate that pick task is ready for completion"""
        if self.pick_task_status != "Completed":
            frappe.throw(_("Pick task must be completed before submission"))
            
        incomplete_items = []
        for item in self.pick_task_items:
            if item.pick_status not in ["Picked", "Short Pick"]:
                incomplete_items.append(item.item_code)
                
        if incomplete_items:
            frappe.throw(_("Following items are not picked: {0}").format(", ".join(incomplete_items)))
            
        if self.verification_required and not self.verified_by:
            frappe.throw(_("Pick task verification is required but not completed"))
    
    def create_stock_entries(self):
        """Create stock entries for picked items"""
        try:
            # Create goods issue stock entry
            stock_entry = frappe.get_doc({
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Issue",
                "purpose": "Material Issue",
                "posting_date": self.posting_date or nowdate(),
                "company": frappe.defaults.get_user_default("Company"),
                "custom_sap_movement_type": self.sap_movement_type,
                "custom_warehouse_pick_task": self.name,
                "custom_sales_order_reference": self.sales_order,
                "items": []
            })
            
            for item in self.pick_task_items:
                if flt(item.picked_qty) <= 0:
                    continue
                    
                stock_entry.append("items", {
                    "item_code": item.item_code,
                    "s_warehouse": item.warehouse,
                    "qty": item.picked_qty,
                    "batch_no": item.batch_no,
                    "basic_rate": frappe.db.get_value("Item Price", 
                                                     {"item_code": item.item_code}, 
                                                     "price_list_rate") or 0
                })
            
            if stock_entry.items:
                stock_entry.insert()
                stock_entry.submit()
                
                # Link stock entry to pick task
                self.db_set("custom_stock_entry_reference", stock_entry.name)
                
                frappe.msgprint(_("Stock Entry {0} created for pick task").format(stock_entry.name))
                
        except Exception as e:
            frappe.log_error(f"Failed to create stock entry for pick task {self.name}: {str(e)}")
            frappe.throw(_("Failed to create stock entry: {0}").format(str(e)))
    
    def update_batch_tracking(self):
        """Update batch tracking with pick information"""
        for item in self.pick_task_items:
            if not item.batch_no or flt(item.picked_qty) <= 0:
                continue
                
            try:
                # Get Batch AMB record
                batch_amb = frappe.db.get_value("Batch AMB", 
                                               {"erpnext_batch_reference": item.batch_no}, 
                                               "name")
                
                if batch_amb:
                    self.update_batch_amb_shipping_info(batch_amb, item)
                    
            except Exception as e:
                frappe.log_error(f"Failed to update batch tracking for {item.batch_no}: {str(e)}")
    
    def update_batch_amb_shipping_info(self, batch_amb, item):
        """Update Batch AMB with shipping information"""
        try:
            batch_doc = frappe.get_doc("Batch AMB", batch_amb)
            
            # Update batch processing history if exists
            if hasattr(batch_doc, 'batch_processing_history') and batch_doc.batch_processing_history:
                history_doc = frappe.get_doc("Batch Processing History", batch_doc.batch_processing_history)
                
                # Add warehouse pick step
                history_doc.append("processing_steps", {
                    "step_name": "Warehouse Pick",
                    "step_type": "Warehouse Operation",
                    "start_time": self.start_time or now_datetime(),
                    "end_time": self.completion_time or now_datetime(),
                    "status": "Completed",
                    "operator": self.picked_by or frappe.session.user,
                    "notes": f"Picked {item.picked_qty} units for sales order {self.sales_order}",
                    "warehouse_reference": item.warehouse,
                    "pick_task_reference": self.name
                })
                
                history_doc.save(ignore_permissions=True)
                
        except Exception as e:
            frappe.log_error(f"Failed to update batch AMB shipping info: {str(e)}")
    
    def update_fulfillment_status(self):
        """Update sales order fulfillment status"""
        if not self.sales_order_fulfillment:
            return
            
        try:
            fulfillment_doc = frappe.get_doc("Sales Order Fulfillment", self.sales_order_fulfillment)
            
            # Update pick task status in fulfillment
            for pick_task in fulfillment_doc.warehouse_pick_tasks:
                if pick_task.pick_task_reference == self.name:
                    pick_task.status = self.pick_task_status
                    pick_task.completion_date = self.completion_time
                    break
            
            # Update overall fulfillment status
            fulfillment_doc.update_fulfillment_status()
            fulfillment_doc.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to update fulfillment status: {str(e)}")
    
    # Status update methods
    def start_picking(self):
        """Start the picking process"""
        self.pick_task_status = "In Progress"
        self.start_time = now_datetime()
        self.picked_by = frappe.session.user
        self.save()
    
    def complete_picking(self):
        """Complete the picking process"""
        # Validate all items are processed
        for item in self.pick_task_items:
            if item.pick_status == "Pending":
                frappe.throw(_("Item {0} is still pending pick").format(item.item_code))
        
        self.pick_task_status = "Picked"
        self.completion_time = now_datetime()
        
        # Calculate actual time
        if self.start_time:
            time_diff = now_datetime() - self.start_time
            self.actual_time = time_diff.total_seconds() / 3600  # Convert to hours
        
        self.save()
    
    def verify_picks(self):
        """Verify picked items"""
        if not self.verification_required:
            frappe.throw(_("Verification is not required for this pick task"))
            
        self.pick_task_status = "Verified"
        self.verified_by = frappe.session.user
        self.verification_time = now_datetime()
        self.save()
    
    def complete_task(self):
        """Complete the entire pick task"""
        if self.verification_required and not self.verified_by:
            frappe.throw(_("Pick task must be verified before completion"))
            
        self.pick_task_status = "Completed"
        self.save()
        self.submit()

# API Functions
@frappe.whitelist()
def start_pick_task(pick_task_name):
    """Start a pick task"""
    try:
        pick_task = frappe.get_doc("Warehouse Pick Task", pick_task_name)
        pick_task.start_picking()
        return {"success": True, "message": "Pick task started"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def update_item_pick_status(pick_task_name, item_code, picked_qty, pick_status):
    """Update individual item pick status"""
    try:
        pick_task = frappe.get_doc("Warehouse Pick Task", pick_task_name)
        
        for item in pick_task.pick_task_items:
            if item.item_code == item_code:
                item.picked_qty = flt(picked_qty)
                item.pick_status = pick_status
                item.remaining_qty = flt(item.qty_to_pick) - flt(picked_qty)
                break
        
        pick_task.save()
        return {"success": True, "message": "Item status updated"}
        
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def complete_pick_task(pick_task_name):
    """Complete a pick task"""
    try:
        pick_task = frappe.get_doc("Warehouse Pick Task", pick_task_name)
        pick_task.complete_task()
        return {"success": True, "message": "Pick task completed"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def get_optimal_pick_route(warehouse, item_codes):
    """Get optimal pick route for items in warehouse"""
    try:
        # This is a simplified version - could be enhanced with actual warehouse layout
        route = []
        
        for item_code in item_codes:
            # Get bin location for item
            bin_location = frappe.db.get_value("Bin", 
                                             {"item_code": item_code, "warehouse": warehouse}, 
                                             "name")
            if bin_location:
                route.append({
                    "item_code": item_code,
                    "bin_location": bin_location,
                    "sequence": len(route) + 1
                })
        
        return {"success": True, "route": route}
        
    except Exception as e:
        return {"success": False, "message": str(e)}
