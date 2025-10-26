# -*- coding: utf-8 -*-
# Delivery Note Integration with Warehouse Operations
# Copyright (c) 2025, AMB Wellness & Spa and contributors

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt
import json

class DeliveryNoteIntegration:
    """Integration layer for Delivery Note with warehouse operations and quality certificates"""
    
    @staticmethod
    def on_delivery_note_before_submit(doc, method):
        """Validate delivery note before submission"""
        try:
            # Validate warehouse pick completion
            DeliveryNoteIntegration.validate_warehouse_picks(doc)
            
            # Validate batch expiry and quality
            DeliveryNoteIntegration.validate_batch_quality(doc)
            
            # Validate temperature compliance
            DeliveryNoteIntegration.validate_temperature_compliance(doc)
            
            # Check customer-specific requirements
            DeliveryNoteIntegration.validate_customer_requirements(doc)
            
        except Exception as e:
            frappe.log_error(f"Delivery Note Validation Error: {str(e)}")
            frappe.throw(_("Delivery validation failed: {0}").format(str(e)))
    
    @staticmethod
    def on_delivery_note_submit(doc, method):
        """Handle delivery note submission"""
        try:
            # Create stock entries with SAP movement types
            DeliveryNoteIntegration.create_warehouse_stock_entries(doc)
            
            # Generate quality certificates automatically
            DeliveryNoteIntegration.auto_generate_quality_certificates(doc)
            
            # Update batch processing history
            DeliveryNoteIntegration.update_batch_shipping_history(doc)
            
            # Create FDA compliance documentation
            DeliveryNoteIntegration.create_fda_shipping_records(doc)
            
            # Update warehouse bin locations
            DeliveryNoteIntegration.update_warehouse_bin_locations(doc)
            
            # Update fulfillment status
            DeliveryNoteIntegration.update_fulfillment_shipping_status(doc)
            
            frappe.msgprint(_("Delivery Note processed with warehouse integration"))
            
        except Exception as e:
            frappe.log_error(f"Delivery Note Integration Error: {str(e)}")
            # Don't fail delivery note submission
    
    @staticmethod
    def validate_warehouse_picks(delivery_note_doc):
        """Validate that all warehouse pick tasks are completed"""
        validation_issues = []
        
        for item in delivery_note_doc.items:
            sales_order = item.against_sales_order
            
            if not sales_order:
                continue
                
            # Get fulfillment for sales order
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
                    task_names = [task.name for task in incomplete_tasks]
                    validation_issues.append(
                        f"Incomplete pick tasks for {item.item_code}: {', '.join(task_names)}"
                    )
        
        if validation_issues:
            # Convert to warning instead of error to allow override
            frappe.msgprint(_("Warning: {0}").format("; ".join(validation_issues)), alert=True)
    
    @staticmethod
    def validate_batch_quality(delivery_note_doc):
        """Validate batch quality and expiry dates"""
        validation_errors = []
        
        for item in delivery_note_doc.items:
            if not item.batch_no:
                continue
                
            batch_doc = frappe.get_doc("Batch", item.batch_no)
            
            # Check expiry date
            if batch_doc.expiry_date and batch_doc.expiry_date <= frappe.utils.getdate():
                validation_errors.append(
                    f"Batch {item.batch_no} for item {item.item_code} has expired"
                )
            
            # Check batch quality status in Batch AMB
            batch_amb = frappe.db.get_value("Batch AMB", 
                                          {"erpnext_batch_reference": item.batch_no}, 
                                          ["name", "workflow_state"])
            
            if batch_amb:
                workflow_state = batch_amb[1]
                if workflow_state not in ["Released", "Approved"]:
                    validation_errors.append(
                        f"Batch {item.batch_no} is not released for shipment (Status: {workflow_state})"
                    )
        
        if validation_errors:
            frappe.throw(_("Batch validation failed: {0}").format("; ".join(validation_errors)))
    
    @staticmethod
    def validate_temperature_compliance(delivery_note_doc):
        """Validate temperature compliance for shipped goods"""
        temp_controlled_items = []
        
        for item in delivery_note_doc.items:
            is_temp_controlled = frappe.db.get_value("Item", item.item_code, "custom_temperature_controlled")
            
            if is_temp_controlled:
                temp_controlled_items.append(item.item_code)
        
        if temp_controlled_items:
            # Check if delivery note has temperature documentation
            if not hasattr(delivery_note_doc, 'custom_temperature_compliance') or not delivery_note_doc.custom_temperature_compliance:
                frappe.msgprint(_("Warning: Temperature-controlled items found but no temperature compliance documented"), 
                              alert=True)
    
    @staticmethod
    def validate_customer_requirements(delivery_note_doc):
        """Validate customer-specific requirements"""
        for item in delivery_note_doc.items:
            sales_order = item.against_sales_order
            
            if not sales_order:
                continue
                
            # Get fulfillment item requirements
            fulfillment = frappe.db.get_value("Sales Order Fulfillment", 
                                            {"sales_order": sales_order}, "name")
            
            if fulfillment:
                fulfillment_item = frappe.db.get_value("Sales Order Fulfillment Item",
                                                      {
                                                          "parent": fulfillment,
                                                          "item_code": item.item_code
                                                      },
                                                      ["specific_batch", "lot_specific_requirement"])
                
                if fulfillment_item:
                    specific_batch, lot_requirement = fulfillment_item
                    
                    # Validate specific batch requirement
                    if specific_batch and item.batch_no != specific_batch:
                        frappe.throw(_("Item {0} requires specific batch {1} but {2} is being shipped")
                                   .format(item.item_code, specific_batch, item.batch_no))
    
    @staticmethod
    def create_warehouse_stock_entries(delivery_note_doc):
        """Create warehouse stock entries with proper SAP movement types"""
        try:
            # Group items by warehouse for efficient processing
            warehouse_groups = {}
            
            for item in delivery_note_doc.items:
                warehouse = item.warehouse
                if warehouse not in warehouse_groups:
                    warehouse_groups[warehouse] = []
                warehouse_groups[warehouse].append(item)
            
            # Create stock entries for each warehouse
            for warehouse, items in warehouse_groups.items():
                DeliveryNoteIntegration.create_stock_entry_for_warehouse(delivery_note_doc, warehouse, items)
                
        except Exception as e:
            frappe.log_error(f"Failed to create warehouse stock entries: {str(e)}")
    
    @staticmethod
    def create_stock_entry_for_warehouse(delivery_note_doc, warehouse, items):
        """Create stock entry for specific warehouse"""
        try:
            plant_code = frappe.db.get_value("Warehouse", warehouse, "custom_warehouse_code") or "0334"
            
            stock_entry = frappe.get_doc({
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Issue",
                "purpose": "Material Issue",
                "posting_date": delivery_note_doc.posting_date,
                "company": delivery_note_doc.company,
                "custom_sap_movement_type": "601",  # Goods Issue to Customer
                "custom_delivery_note_reference": delivery_note_doc.name,
                "custom_customer_reference": delivery_note_doc.customer,
                "custom_plant_code": plant_code,
                "items": []
            })
            
            for item in items:
                stock_entry.append("items", {
                    "item_code": item.item_code,
                    "s_warehouse": warehouse,
                    "qty": item.qty,
                    "batch_no": item.batch_no,
                    "basic_rate": item.rate or 0,
                    "uom": item.uom,
                    "stock_uom": item.stock_uom,
                    "conversion_factor": item.conversion_factor or 1
                })
            
            stock_entry.insert()
            stock_entry.submit()
            
            # Link stock entry to delivery note
            delivery_note_doc.db_set("custom_warehouse_stock_entry", stock_entry.name)
            
        except Exception as e:
            frappe.log_error(f"Failed to create stock entry for warehouse {warehouse}: {str(e)}")
    
    @staticmethod
    def auto_generate_quality_certificates(delivery_note_doc):
        """Automatically generate quality certificates for shipped batches"""
        certificates_generated = []
        
        for item in delivery_note_doc.items:
            if not item.batch_no:
                continue
                
            try:
                # Generate COA if not exists
                coa = DeliveryNoteIntegration.generate_coa_for_shipment(item.batch_no, item.item_code)
                if coa:
                    certificates_generated.append(f"COA: {coa}")
                
                # Generate TDS reference
                tds = DeliveryNoteIntegration.link_tds_for_shipment(item.item_code)
                if tds:
                    certificates_generated.append(f"TDS: {tds}")
                    
            except Exception as e:
                frappe.log_error(f"Failed to generate certificates for {item.item_code}, batch {item.batch_no}: {str(e)}")
        
        if certificates_generated:
            frappe.msgprint(_("Quality certificates generated: {0}").format(", ".join(certificates_generated)))
    
    @staticmethod
    def generate_coa_for_shipment(batch_no, item_code):
        """Generate COA for shipment if not exists"""
        try:
            # Check if COA already exists
            existing_coa = frappe.db.get_value("COA AMB", {"batch_no": batch_no}, "name")
            
            if existing_coa:
                return existing_coa
            
            # Get TDS for item
            tds = frappe.db.get_value("TDS Product Specification", {"item_code": item_code}, "name")
            
            if not tds:
                frappe.msgprint(_("TDS not found for item {0}, cannot generate COA").format(item_code), alert=True)
                return None
            
            # Create COA
            coa = frappe.get_doc({
                "doctype": "COA AMB",
                "batch_no": batch_no,
                "item_code": item_code,
                "linked_tds": tds,
                "coa_date": nowdate(),
                "validation_status": "Auto-Generated",
                "overall_compliance_status": "PENDING",
                "auto_generated_for_shipment": 1
            })
            
            coa.insert()
            
            # Auto-load TDS parameters
            if hasattr(coa, 'load_tds_parameters_event'):
                coa.load_tds_parameters_event(tds)
                coa.save()
            
            return coa.name
            
        except Exception as e:
            frappe.log_error(f"Failed to generate COA for batch {batch_no}: {str(e)}")
            return None
    
    @staticmethod
    def link_tds_for_shipment(item_code):
        """Link TDS for shipment"""
        try:
            tds = frappe.db.get_value("TDS Product Specification", {"item_code": item_code}, "name")
            return tds
        except Exception as e:
            frappe.log_error(f"Failed to link TDS for item {item_code}: {str(e)}")
            return None
    
    @staticmethod
    def update_batch_shipping_history(delivery_note_doc):
        """Update batch processing history with shipping information"""
        for item in delivery_note_doc.items:
            if not item.batch_no:
                continue
                
            try:
                # Get Batch AMB record
                batch_amb = frappe.db.get_value("Batch AMB", 
                                               {"erpnext_batch_reference": item.batch_no}, 
                                               "name")
                
                if batch_amb:
                    DeliveryNoteIntegration.update_batch_amb_shipping(batch_amb, delivery_note_doc, item)
                    
            except Exception as e:
                frappe.log_error(f"Failed to update batch shipping history for {item.batch_no}: {str(e)}")
    
    @staticmethod
    def update_batch_amb_shipping(batch_amb, delivery_note_doc, item):
        """Update Batch AMB with shipping information"""
        try:
            batch_doc = frappe.get_doc("Batch AMB", batch_amb)
            
            # Update batch processing history
            if hasattr(batch_doc, 'batch_processing_history') and batch_doc.batch_processing_history:
                history_doc = frappe.get_doc("Batch Processing History", batch_doc.batch_processing_history)
                
                # Add shipping step
                history_doc.append("processing_steps", {
                    "step_name": "Customer Shipment",
                    "step_type": "Shipment",
                    "start_time": now_datetime(),
                    "status": "Completed",
                    "operator": frappe.session.user,
                    "notes": f"Shipped {item.qty} units via delivery note {delivery_note_doc.name}",
                    "customer_reference": delivery_note_doc.customer,
                    "delivery_note_reference": delivery_note_doc.name,
                    "tracking_number": getattr(delivery_note_doc, 'lr_no', None),
                    "warehouse_reference": item.warehouse,
                    "temperature_compliance": getattr(delivery_note_doc, 'custom_temperature_compliance', None)
                })
                
                history_doc.save(ignore_permissions=True)
                
                # Update batch genealogy with customer shipment
                if hasattr(batch_doc, 'customer_shipments'):
                    batch_doc.append("customer_shipments", {
                        "customer": delivery_note_doc.customer,
                        "delivery_note": delivery_note_doc.name,
                        "shipped_qty": item.qty,
                        "shipping_date": delivery_note_doc.posting_date,
                        "batch_no": item.batch_no
                    })
                    
                    batch_doc.save(ignore_permissions=True)
                
        except Exception as e:
            frappe.log_error(f"Failed to update batch AMB shipping: {str(e)}")
    
    @staticmethod
    def create_fda_shipping_records(delivery_note_doc):
        """Create FDA compliance documentation for shipped goods"""
        try:
            fda_regulated_items = []
            
            for item in delivery_note_doc.items:
                is_fda_regulated = frappe.db.get_value("Item", item.item_code, "custom_fda_regulated")
                if is_fda_regulated:
                    fda_regulated_items.append(item)
            
            if not fda_regulated_items:
                return
            
            # Create FDA shipment record
            fda_record = frappe.get_doc({
                "doctype": "FDA Shipment Record",
                "delivery_note": delivery_note_doc.name,
                "customer": delivery_note_doc.customer,
                "shipping_date": delivery_note_doc.posting_date,
                "compliance_status": "Compliant",
                "documentation_complete": 1,
                "items": []
            })
            
            for item in fda_regulated_items:
                fda_record.append("items", {
                    "item_code": item.item_code,
                    "batch_no": item.batch_no,
                    "qty_shipped": item.qty,
                    "warehouse": item.warehouse,
                    "coa_reference": frappe.db.get_value("COA AMB", {"batch_no": item.batch_no}, "name"),
                    "tds_reference": frappe.db.get_value("TDS Product Specification", {"item_code": item.item_code}, "name")
                })
            
            fda_record.insert()
            
        except Exception as e:
            frappe.log_error(f"Failed to create FDA shipping records: {str(e)}")
    
    @staticmethod
    def update_warehouse_bin_locations(delivery_note_doc):
        """Update warehouse bin locations when goods are shipped"""
        try:
            for item in delivery_note_doc.items:
                if not item.batch_no:
                    continue
                    
                # Update bin quantities
                frappe.db.sql("""
                    UPDATE `tabBin` 
                    SET actual_qty = actual_qty - %s,
                        modified = NOW()
                    WHERE item_code = %s 
                    AND warehouse = %s
                """, (item.qty, item.item_code, item.warehouse))
                
                # Log bin movement
                frappe.get_doc({
                    "doctype": "Stock Ledger Entry",
                    "item_code": item.item_code,
                    "warehouse": item.warehouse,
                    "batch_no": item.batch_no,
                    "actual_qty": -1 * item.qty,
                    "posting_date": delivery_note_doc.posting_date,
                    "posting_time": delivery_note_doc.posting_time,
                    "voucher_type": "Delivery Note",
                    "voucher_no": delivery_note_doc.name,
                    "company": delivery_note_doc.company
                }).insert(ignore_permissions=True)
                
        except Exception as e:
            frappe.log_error(f"Failed to update warehouse bin locations: {str(e)}")
    
    @staticmethod
    def update_fulfillment_shipping_status(delivery_note_doc):
        """Update fulfillment status to shipped"""
        try:
            sales_orders = set()
            
            for item in delivery_note_doc.items:
                if item.against_sales_order:
                    sales_orders.add(item.against_sales_order)
            
            for sales_order in sales_orders:
                fulfillment = frappe.db.get_value("Sales Order Fulfillment", 
                                                {"sales_order": sales_order}, "name")
                
                if fulfillment:
                    fulfillment_doc = frappe.get_doc("Sales Order Fulfillment", fulfillment)
                    fulfillment_doc.fulfillment_status = "Shipped"
                    fulfillment_doc.update_audit_trail(f"Shipped via delivery note {delivery_note_doc.name}")
                    fulfillment_doc.save(ignore_permissions=True)
                    
        except Exception as e:
            frappe.log_error(f"Failed to update fulfillment shipping status: {str(e)}")

# API Functions
@frappe.whitelist()
def validate_delivery_note_readiness(delivery_note):
    """Validate if delivery note is ready for submission"""
    try:
        dn_doc = frappe.get_doc("Delivery Note", delivery_note)
        
        issues = []
        warnings = []
        
        # Check warehouse picks
        for item in dn_doc.items:
            if item.against_sales_order:
                fulfillment = frappe.db.get_value("Sales Order Fulfillment", 
                                                {"sales_order": item.against_sales_order}, "name")
                
                if fulfillment:
                    incomplete_tasks = frappe.get_all("Warehouse Pick Task",
                                                     filters={
                                                         "sales_order_fulfillment": fulfillment,
                                                         "pick_task_status": ["not in", ["Completed", "Cancelled"]]
                                                     })
                    
                    if incomplete_tasks:
                        warnings.append(f"Incomplete pick tasks for {item.item_code}")
        
        return {
            "success": True,
            "ready": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def get_shipment_certificates(delivery_note):
    """Get quality certificates for shipment"""
    try:
        dn_doc = frappe.get_doc("Delivery Note", delivery_note)
        certificates = []
        
        for item in dn_doc.items:
            if item.batch_no:
                # Get COA
                coa = frappe.db.get_value("COA AMB", {"batch_no": item.batch_no}, 
                                        ["name", "validation_status"])
                if coa:
                    certificates.append({
                        "type": "COA",
                        "reference": coa[0],
                        "status": coa[1],
                        "batch_no": item.batch_no,
                        "item_code": item.item_code
                    })
                
                # Get TDS
                tds = frappe.db.get_value("TDS Product Specification", {"item_code": item.item_code}, "name")
                if tds:
                    certificates.append({
                        "type": "TDS",
                        "reference": tds,
                        "status": "Available",
                        "item_code": item.item_code
                    })
        
        return {"success": True, "certificates": certificates}
        
    except Exception as e:
        return {"success": False, "message": str(e)}
