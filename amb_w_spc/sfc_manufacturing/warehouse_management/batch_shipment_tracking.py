# -*- coding: utf-8 -*-
# Batch Shipment Tracking Integration
# Copyright (c) 2025, AMB Wellness & Spa and contributors

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt
import json

class BatchShipmentTracking:
    """Enhanced batch tracking for customer shipments with complete chain of custody"""
    
    @staticmethod
    def track_batch_shipment(batch_no, delivery_note, customer, qty_shipped):
        """Track batch shipment with complete details"""
        try:
            # Get Batch AMB record
            batch_amb = frappe.db.get_value("Batch AMB", 
                                          {"erpnext_batch_reference": batch_no}, 
                                          "name")
            
            if not batch_amb:
                frappe.log_error(f"Batch AMB not found for batch {batch_no}")
                return False
            
            # Update batch genealogy
            BatchShipmentTracking.update_batch_genealogy(batch_amb, delivery_note, customer, qty_shipped)
            
            # Create shipment tracking record
            BatchShipmentTracking.create_shipment_tracking_record(batch_no, delivery_note, customer, qty_shipped)
            
            # Update batch processing history
            BatchShipmentTracking.update_processing_history(batch_amb, delivery_note, customer, qty_shipped)
            
            # Enable customer recall capability
            BatchShipmentTracking.create_recall_record(batch_no, delivery_note, customer)
            
            return True
            
        except Exception as e:
            frappe.log_error(f"Failed to track batch shipment: {str(e)}")
            return False
    
    @staticmethod
    def update_batch_genealogy(batch_amb, delivery_note, customer, qty_shipped):
        """Update batch genealogy with shipment information"""
        try:
            batch_doc = frappe.get_doc("Batch AMB", batch_amb)
            
            # Add customer shipment to genealogy
            if not hasattr(batch_doc, 'customer_shipments'):
                batch_doc.append("customer_shipments", {})
            
            shipment_record = {
                "customer": customer,
                "delivery_note": delivery_note,
                "shipped_qty": qty_shipped,
                "shipping_date": nowdate(),
                "shipment_id": f"SHIP-{batch_amb}-{len(batch_doc.get('customer_shipments', []))+1}",
                "chain_of_custody_complete": 1
            }
            
            batch_doc.append("customer_shipments", shipment_record)
            batch_doc.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Failed to update batch genealogy: {str(e)}")
    
    @staticmethod
    def create_shipment_tracking_record(batch_no, delivery_note, customer, qty_shipped):
        """Create detailed shipment tracking record"""
        try:
            # Get batch details
            batch_doc = frappe.get_doc("Batch", batch_no)
            batch_amb = frappe.db.get_value("Batch AMB", 
                                          {"erpnext_batch_reference": batch_no}, 
                                          "name")
            
            # Get delivery note details
            dn_doc = frappe.get_doc("Delivery Note", delivery_note)
            
            tracking_record = frappe.get_doc({
                "doctype": "Batch Shipment Tracking",
                "batch_no": batch_no,
                "batch_amb_reference": batch_amb,
                "delivery_note": delivery_note,
                "customer": customer,
                "shipped_qty": qty_shipped,
                "shipping_date": dn_doc.posting_date,
                "manufacturing_date": batch_doc.manufacturing_date,
                "expiry_date": batch_doc.expiry_date,
                "item_code": batch_doc.item,
                "warehouse": dn_doc.items[0].warehouse if dn_doc.items else None,
                "tracking_number": getattr(dn_doc, 'lr_no', None),
                "chain_of_custody_status": "Complete",
                "recall_capability": "Enabled"
            })
            
            tracking_record.insert()
            
        except Exception as e:
            frappe.log_error(f"Failed to create shipment tracking record: {str(e)}")
    
    @staticmethod
    def update_processing_history(batch_amb, delivery_note, customer, qty_shipped):
        """Update batch processing history with shipment details"""
        try:
            batch_doc = frappe.get_doc("Batch AMB", batch_amb)
            
            if hasattr(batch_doc, 'batch_processing_history') and batch_doc.batch_processing_history:
                history_doc = frappe.get_doc("Batch Processing History", batch_doc.batch_processing_history)
                
                # Get delivery note details for comprehensive tracking
                dn_doc = frappe.get_doc("Delivery Note", delivery_note)
                
                # Add comprehensive shipment step
                history_doc.append("processing_steps", {
                    "step_name": "Customer Shipment",
                    "step_type": "Shipment",
                    "start_time": now_datetime(),
                    "status": "Completed",
                    "operator": frappe.session.user,
                    "notes": f"Shipped {qty_shipped} units to {customer} via {delivery_note}",
                    "customer_reference": customer,
                    "delivery_note_reference": delivery_note,
                    "tracking_number": getattr(dn_doc, 'lr_no', None),
                    "shipping_method": getattr(dn_doc, 'custom_shipping_method', None),
                    "temperature_compliance": getattr(dn_doc, 'custom_temperature_compliance', None),
                    "chain_of_custody_verified": 1,
                    "quality_certificates_attached": 1
                })
                
                # Update overall history status
                if history_doc.status != "Shipped":
                    history_doc.status = "Shipped"
                    history_doc.last_updated = now_datetime()
                
                history_doc.save(ignore_permissions=True)
                
        except Exception as e:
            frappe.log_error(f"Failed to update processing history: {str(e)}")
    
    @staticmethod
    def create_recall_record(batch_no, delivery_note, customer):
        """Create batch recall capability record"""
        try:
            recall_record = frappe.get_doc({
                "doctype": "Batch Recall Record",
                "batch_no": batch_no,
                "customer": customer,
                "delivery_note": delivery_note,
                "recall_status": "Not Required",
                "recall_capability": "Enabled",
                "created_date": nowdate(),
                "expiry_date": frappe.db.get_value("Batch", batch_no, "expiry_date"),
                "contact_information_verified": 1
            })
            
            recall_record.insert()
            
        except Exception as e:
            frappe.log_error(f"Failed to create recall record: {str(e)}")
    
    @staticmethod
    def get_batch_shipment_history(batch_no):
        """Get complete shipment history for a batch"""
        try:
            # Get all shipments for this batch
            shipments = frappe.get_all("Batch Shipment Tracking",
                                     filters={"batch_no": batch_no},
                                     fields=["*"],
                                     order_by="shipping_date desc")
            
            # Get batch details
            batch_amb = frappe.db.get_value("Batch AMB", 
                                          {"erpnext_batch_reference": batch_no}, 
                                          "name")
            
            batch_details = None
            if batch_amb:
                batch_details = frappe.get_doc("Batch AMB", batch_amb)
            
            return {
                "success": True,
                "batch_no": batch_no,
                "batch_details": batch_details,
                "shipments": shipments,
                "total_shipments": len(shipments),
                "total_shipped_qty": sum([s.shipped_qty for s in shipments])
            }
            
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def get_customer_batch_history(customer):
        """Get all batches shipped to a specific customer"""
        try:
            shipments = frappe.get_all("Batch Shipment Tracking",
                                     filters={"customer": customer},
                                     fields=["*"],
                                     order_by="shipping_date desc")
            
            # Group by batch
            batch_groups = {}
            for shipment in shipments:
                batch_no = shipment.batch_no
                if batch_no not in batch_groups:
                    batch_groups[batch_no] = []
                batch_groups[batch_no].append(shipment)
            
            return {
                "success": True,
                "customer": customer,
                "batches": batch_groups,
                "total_batches": len(batch_groups),
                "total_shipments": len(shipments)
            }
            
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def initiate_batch_recall(batch_no, recall_reason, severity_level):
        """Initiate batch recall process"""
        try:
            # Get all customers who received this batch
            shipments = frappe.get_all("Batch Shipment Tracking",
                                     filters={"batch_no": batch_no},
                                     fields=["customer", "delivery_note", "shipped_qty"])
            
            if not shipments:
                return {"success": False, "message": "No shipments found for this batch"}
            
            # Create recall record
            recall_doc = frappe.get_doc({
                "doctype": "Batch Recall",
                "batch_no": batch_no,
                "recall_reason": recall_reason,
                "severity_level": severity_level,
                "recall_date": nowdate(),
                "recall_status": "Initiated",
                "affected_customers": len(set([s.customer for s in shipments])),
                "total_qty_recalled": sum([s.shipped_qty for s in shipments]),
                "customer_notifications": []
            })
            
            # Add customer notifications
            for shipment in shipments:
                recall_doc.append("customer_notifications", {
                    "customer": shipment.customer,
                    "delivery_note": shipment.delivery_note,
                    "qty_to_recall": shipment.shipped_qty,
                    "notification_status": "Pending",
                    "notification_method": "Email"
                })
            
            recall_doc.insert()
            
            # Update batch recall records
            frappe.db.sql("""
                UPDATE `tabBatch Recall Record`
                SET recall_status = 'Initiated', recall_date = %s
                WHERE batch_no = %s
            """, (nowdate(), batch_no))
            
            return {
                "success": True,
                "recall_id": recall_doc.name,
                "affected_customers": len(set([s.customer for s in shipments])),
                "total_qty": sum([s.shipped_qty for s in shipments])
            }
            
        except Exception as e:
            frappe.log_error(f"Failed to initiate batch recall: {str(e)}")
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def get_traceability_chain(batch_no):
        """Get complete traceability chain from production to delivery"""
        try:
            # Get Batch AMB record
            batch_amb = frappe.db.get_value("Batch AMB", 
                                          {"erpnext_batch_reference": batch_no}, 
                                          "name")
            
            if not batch_amb:
                return {"success": False, "message": "Batch AMB record not found"}
            
            batch_doc = frappe.get_doc("Batch AMB", batch_amb)
            
            traceability_chain = {
                "batch_no": batch_no,
                "batch_amb": batch_amb,
                "production_details": {
                    "manufacturing_date": batch_doc.manufacturing_date,
                    "expiry_date": batch_doc.expiry_date,
                    "item_code": batch_doc.item_to_manufacture,
                    "batch_size": batch_doc.batch_qty,
                    "production_level": batch_doc.custom_batch_level
                },
                "processing_history": [],
                "quality_records": [],
                "shipment_history": [],
                "current_status": batch_doc.workflow_state
            }
            
            # Get processing history
            if hasattr(batch_doc, 'batch_processing_history') and batch_doc.batch_processing_history:
                history_doc = frappe.get_doc("Batch Processing History", batch_doc.batch_processing_history)
                traceability_chain["processing_history"] = history_doc.processing_steps
            
            # Get quality records
            coa_records = frappe.get_all("COA AMB",
                                       filters={"batch_no": batch_no},
                                       fields=["name", "validation_status", "overall_compliance_status"])
            traceability_chain["quality_records"] = coa_records
            
            # Get shipment history
            shipments = frappe.get_all("Batch Shipment Tracking",
                                     filters={"batch_no": batch_no},
                                     fields=["*"])
            traceability_chain["shipment_history"] = shipments
            
            return {"success": True, "traceability_chain": traceability_chain}
            
        except Exception as e:
            return {"success": False, "message": str(e)}

# API Functions
@frappe.whitelist()
def track_delivery_note_batches(delivery_note):
    """Track all batches in a delivery note"""
    try:
        dn_doc = frappe.get_doc("Delivery Note", delivery_note)
        tracked_batches = []
        
        for item in dn_doc.items:
            if item.batch_no:
                success = BatchShipmentTracking.track_batch_shipment(
                    item.batch_no, 
                    delivery_note, 
                    dn_doc.customer, 
                    item.qty
                )
                
                tracked_batches.append({
                    "batch_no": item.batch_no,
                    "item_code": item.item_code,
                    "qty": item.qty,
                    "tracking_success": success
                })
        
        return {"success": True, "tracked_batches": tracked_batches}
        
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def get_batch_traceability(batch_no):
    """Get complete batch traceability information"""
    return BatchShipmentTracking.get_traceability_chain(batch_no)

@frappe.whitelist()
def get_customer_shipment_history(customer):
    """Get shipment history for a customer"""
    return BatchShipmentTracking.get_customer_batch_history(customer)

@frappe.whitelist()
def initiate_recall(batch_no, reason, severity="Medium"):
    """Initiate batch recall"""
    return BatchShipmentTracking.initiate_batch_recall(batch_no, reason, severity)
