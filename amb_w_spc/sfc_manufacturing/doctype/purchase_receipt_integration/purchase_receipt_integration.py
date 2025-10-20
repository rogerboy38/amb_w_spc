import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import nowdate, now_datetime, flt, cint, now
import json
from typing import Dict, List, Any, Optional

# Main hook function to be called from hooks.py on Purchase Receipt submission
def process_purchase_receipt_integration(doc, method):
	"""
	Main function triggered on Purchase Receipt submission.
	Handles warehouse automation, quality routing, and batch integration.
	"""
	try:
		# Log the integration start
		frappe.logger().info(f"Starting Purchase Receipt integration for {doc.name}")
		
		# Create integration record to track the process
		integration_doc = frappe.new_doc("Purchase Receipt Integration")
		integration_doc.update({
			"purchase_receipt": doc.name,
			"supplier": doc.supplier,
			"posting_date": doc.posting_date,
			"company": doc.company,
			"status": "Processing"
		})
		
		# Copy items for processing
		for item in doc.items:
			if item.qty > 0:  # Only process items with positive quantity
				integration_doc.append("items", {
					"item_code": item.item_code,
					"item_name": item.item_name,
					"qty": item.qty,
					"rate": item.rate,
					"warehouse": item.warehouse,
					"uom": item.uom,
					"batch_no": getattr(item, 'batch_no', None),
					"purchase_receipt_item": item.name
				})
		
		# Save and submit the integration document to trigger all workflows
		integration_doc.insert(ignore_permissions=True)
		integration_doc.submit()
		
		# Update the original Purchase Receipt with integration status
		frappe.db.set_value("Purchase Receipt", doc.name, "custom_warehouse_integration_status", "Completed")
		frappe.db.set_value("Purchase Receipt", doc.name, "custom_integration_datetime", now())
		frappe.db.set_value("Purchase Receipt", doc.name, "custom_integration_reference", integration_doc.name)
		
		frappe.logger().info(f"Successfully completed Purchase Receipt integration for {doc.name}")
		
	except Exception as e:
		frappe.logger().error(f"Error in Purchase Receipt integration for {doc.name}: {str(e)}")
		# Update status to failed
		frappe.db.set_value("Purchase Receipt", doc.name, "custom_warehouse_integration_status", "Failed")
		frappe.db.set_value("Purchase Receipt", doc.name, "custom_integration_error", str(e))
		
		# Don't throw error to avoid blocking Purchase Receipt submission
		frappe.log_error(f"Purchase Receipt integration failed for {doc.name}: {str(e)}", "Purchase Receipt Integration Error")

class PurchaseReceiptIntegration(Document):
    """
    Enhanced Purchase Receipt Integration with Warehouse Management and Quality Systems.
    Handles raw material receiving workflows with automatic warehouse placement,
    quality inspection routing, and batch tracking integration.
    """
    
    def validate(self):
        self.validate_plant_code_routing()
        self.validate_temperature_requirements()
        self.validate_quality_inspection_requirements()
        
    def before_save(self):
        self.set_warehouse_placement_strategy()
        self.calculate_inspection_requirements()
        
    def on_submit(self):
        self.create_warehouse_put_away_tasks()
        self.create_quality_inspection_workflows()
        self.update_batch_processing_history()
        self.create_sap_movement_entries()
        
    def after_submit(self):
        self.trigger_warehouse_integration()
        self.notify_quality_systems()
        
    def validate_plant_code_routing(self):
        """Validate plant code routing for incoming materials"""
        for item in self.items:
            item_code = item.item_code
            plant_code = self.get_item_plant_code(item_code)
            
            # Validate warehouse assignment based on plant code
            if not self.validate_warehouse_plant_assignment(item.warehouse, plant_code):
                frappe.throw(_("Warehouse {0} is not configured for plant code {1} items")
                    .format(item.warehouse, plant_code))
                    
    def get_item_plant_code(self, item_code):
        """Determine plant code from item code pattern"""
        if item_code.startswith('M033'):
            return 'juice'  # Raw leaf materials
        elif item_code.startswith('0227'):
            return 'dry'    # Concentrated materials
        elif item_code.startswith('0303'):
            return 'dry'    # Powder materials  
        elif item_code.startswith('0334'):
            return 'mix'    # Mix materials
        else:
            return 'default'
            
    def validate_warehouse_plant_assignment(self, warehouse, plant_code):
        """Validate warehouse can accept items from specific plant"""
        warehouse_plant = frappe.db.get_value("Warehouse", warehouse, "custom_plant_code")
        
        if not warehouse_plant:
            # Extract from warehouse name
            if ' - ' in warehouse:
                warehouse_plant = warehouse.split(' - ')[-1].lower()
                
        # Allow flexible assignment for now, but log warnings
        if warehouse_plant and warehouse_plant != plant_code:
            frappe.msgprint(_("Warning: Item {0} (plant: {1}) being received in {2} warehouse (plant: {3})") 
                .format(item_code, plant_code, warehouse, warehouse_plant), alert=True)
                
        return True  # Allow with warning for now
        
    def validate_temperature_requirements(self):
        """Validate temperature requirements for incoming materials"""
        for item in self.items:
            # Check if item requires temperature control
            item_group = frappe.db.get_value("Item", item.item_code, "item_group")
            
            if item_group in ["Finished Goods", "Temperature Sensitive"]:
                warehouse_temp_control = frappe.db.get_value(
                    "Warehouse", item.warehouse, "custom_temperature_control"
                )
                
                if not warehouse_temp_control:
                    frappe.msgprint(_("Warning: Temperature sensitive item {0} assigned to non-temperature controlled warehouse {1}")
                        .format(item.item_code, item.warehouse), alert=True)
                        
    def validate_quality_inspection_requirements(self):
        """Validate quality inspection requirements"""
        for item in self.items:
            # Check if item requires quality inspection
            requires_inspection = frappe.db.get_value(
                "Item", item.item_code, "inspection_required_before_delivery"
            )
            
            if requires_inspection and not item.quality_inspection:
                # Auto-create quality inspection requirement
                item.quality_inspection_required = 1
                
    def set_warehouse_placement_strategy(self):
        """Set warehouse placement strategy based on quality requirements"""
        for item in self.items:
            if item.quality_inspection_required:
                # Route to quarantine/inspection warehouse
                item.initial_warehouse = self.get_quarantine_warehouse(item.item_code)
                item.final_warehouse = item.warehouse  # Store target warehouse
                item.warehouse = item.initial_warehouse  # Set to quarantine first
            else:
                # Direct to production warehouse
                item.initial_warehouse = item.warehouse
                item.final_warehouse = item.warehouse
                
    def get_quarantine_warehouse(self, item_code):
        """Get appropriate quarantine warehouse for item"""
        plant_code = self.get_item_plant_code(item_code)
        
        # Map to quarantine warehouses by plant
        quarantine_mapping = {
            'juice': 'Raw Material Quarantine Juice - AMB-W',
            'dry': 'Raw Material Quarantine Dry - AMB-W', 
            'mix': 'Raw Material Quarantine Mix - AMB-W',
            'default': 'Raw Material Quarantine - AMB-W'
        }
        
        quarantine_warehouse = quarantine_mapping.get(plant_code, quarantine_mapping['default'])
        
        # Check if warehouse exists, create if needed
        if not frappe.db.exists("Warehouse", quarantine_warehouse):
            self.create_quarantine_warehouse(quarantine_warehouse, plant_code)
            
        return quarantine_warehouse
        
    def create_quarantine_warehouse(self, warehouse_name, plant_code):
        """Create quarantine warehouse if it doesn't exist"""
        try:
            quarantine_wh = frappe.get_doc({
                "doctype": "Warehouse",
                "warehouse_name": warehouse_name,
                "warehouse_type": "Raw Material",
                "company": self.company,
                "custom_plant_code": plant_code,
                "custom_temperature_control": 1,
                "custom_target_temperature": 15,
                "is_group": 0
            })
            quarantine_wh.insert(ignore_permissions=True)
            frappe.msgprint(_("Created quarantine warehouse: {0}").format(warehouse_name), alert=True)
        except Exception as e:
            frappe.log_error(f"Error creating quarantine warehouse: {str(e)}")
            
    def calculate_inspection_requirements(self):
        """Calculate and set inspection requirements"""
        total_items = len(self.items)
        inspection_required = sum(1 for item in self.items if item.quality_inspection_required)
        
        self.total_items_count = total_items
        self.inspection_required_count = inspection_required
        self.direct_placement_count = total_items - inspection_required
        
    def create_warehouse_put_away_tasks(self):
        """Create warehouse put-away tasks for received materials"""
        try:
            for item in self.items:
                put_away_task = {
                    "doctype": "Warehouse Put Away Task",
                    "purchase_receipt": self.name,
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "received_qty": item.qty,
                    "source_warehouse": "Goods Receipt - AMB-W",  # Default receiving dock
                    "target_warehouse": item.warehouse,
                    "plant_code": self.get_item_plant_code(item.item_code),
                    "priority": "High" if item.quality_inspection_required else "Normal",
                    "sap_movement_type": "101",  # Goods Receipt
                    "quality_inspection_required": item.quality_inspection_required,
                    "temperature_controlled": self.is_temperature_sensitive(item.item_code),
                    "assigned_to": self.get_warehouse_operator(),
                    "status": "Pending",
                    "created_from": "Purchase Receipt Integration"
                }
                
                # Create put-away task document
                try:
                    task_doc = frappe.get_doc(put_away_task)
                    task_doc.insert(ignore_permissions=True)
                    
                    # Link back to purchase receipt item
                    item.put_away_task = task_doc.name
                    
                except Exception:
                    # If custom DocType doesn't exist, log the requirement
                    frappe.log_error(f"Warehouse Put Away Task DocType not found. Task details: {json.dumps(put_away_task)}")
                    
        except Exception as e:
            frappe.log_error(f"Error creating put-away tasks: {str(e)}")
            
    def is_temperature_sensitive(self, item_code):
        """Check if item is temperature sensitive"""
        item_group = frappe.db.get_value("Item", item_code, "item_group")
        return item_group in ["Finished Goods", "Temperature Sensitive", "Biological"]
        
    def get_warehouse_operator(self):
        """Get available warehouse operator for assignment"""
        # Try to find available warehouse operator
        operators = frappe.get_all(
            "SFC Operator",
            filters={
                "operator_status": "Active",
                "operator_type": "Warehouse"
            },
            fields=["name", "user_id"],
            limit=1
        )
        
        if operators:
            return operators[0].user_id
        else:
            return frappe.session.user
            
    def create_quality_inspection_workflows(self):
        """Create quality inspection workflows for items requiring inspection"""
        for item in self.items:
            if item.quality_inspection_required:
                self.create_quality_inspection_record(item)
                
    def create_quality_inspection_record(self, item):
        """Create quality inspection record for incoming material"""
        try:
            # Get TDS specification for item if available
            tds_spec = frappe.db.get_value(
                "TDS Product Specification", 
                {"item_code": item.item_code}, 
                "name"
            )
            
            qi_doc = {
                "doctype": "Quality Inspection",
                "inspection_type": "Incoming",
                "reference_type": "Purchase Receipt",
                "reference_name": self.name,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "sample_size": self.calculate_sample_size(item.qty),
                "report_date": nowdate(),
                "status": "Submitted",
                "supplier": self.supplier,
                "batch_no": item.batch_no if hasattr(item, 'batch_no') else None,
                "warehouse": item.warehouse,
                "custom_tds_specification": tds_spec,
                "custom_purchase_receipt_integration": self.name,
                "custom_plant_code": self.get_item_plant_code(item.item_code),
                "custom_inspection_priority": "High",
                "remarks": f"Auto-generated from Purchase Receipt {self.name}"
            }
            
            qi = frappe.get_doc(qi_doc)
            qi.insert(ignore_permissions=True)
            
            # Link back to item
            item.quality_inspection = qi.name
            
        except Exception as e:
            frappe.log_error(f"Error creating quality inspection: {str(e)}")
            
    def calculate_sample_size(self, total_qty):
        """Calculate sample size for quality inspection"""
        if total_qty <= 10:
            return 1
        elif total_qty <= 100:
            return 3
        elif total_qty <= 1000:
            return 5
        else:
            return 10
            
    def create_sap_movement_entries(self):
        """Create SAP movement entries for receiving"""
        for item in self.items:
            movement_entry = {
                "doctype": "SAP Movement Entry", 
                "movement_type": "101",  # Goods Receipt
                "purchase_receipt": self.name,
                "item_code": item.item_code,
                "quantity": item.qty,
                "warehouse": item.warehouse,
                "plant_code": self.get_item_plant_code(item.item_code),
                "posting_date": self.posting_date,
                "reference_document": self.name,
                "movement_reason": "Purchase Receipt - Raw Material Receiving",
                "created_by": frappe.session.user,
                "workflow_state": "Draft"
            }
            
            try:
                sap_entry = frappe.get_doc(movement_entry)
                sap_entry.insert(ignore_permissions=True)
                
                # Link back to item  
                item.sap_movement_entry = sap_entry.name
                
            except Exception:
                # Log SAP movement requirement if DocType doesn't exist
                frappe.log_error(f"SAP Movement Entry DocType not found. Entry details: {json.dumps(movement_entry)}")
                
    def update_batch_processing_history(self):
        """Update batch processing history for received materials"""
        for item in self.items:
            if hasattr(item, 'batch_no') and item.batch_no:
                self.create_batch_receiving_history(item)
                
    def create_batch_receiving_history(self, item):
        """Create batch processing history entry for material receiving"""
        try:
            # Get or create Batch AMB record
            batch_amb = self.get_or_create_batch_amb(item)
            
            if batch_amb:
                # Import warehouse batch integration
                from amb_w_spc.sfc_manufacturing.warehouse_management.warehouse_batch_integration import WarehouseBatchIntegration
                
                # Create receiving history entry
                history_entry = {
                    "batch_reference": batch_amb,
                    "date": self.posting_date,
                    "plant": self.get_item_plant_code(item.item_code),
                    "item_code": item.item_code,
                    "quality_status": "Pending",
                    "processing_action": "Material Received",
                    "previous_value": "Supplier",
                    "new_value": item.warehouse,
                    "work_order_reference": None,
                    "changed_by": frappe.session.user,
                    "comments": f"Purchase Receipt: {self.name} - Material received from {self.supplier}",
                    "system_generated": 1
                }
                
                # Update batch processing history
                batch_doc = frappe.get_doc("Batch AMB", batch_amb)
                if batch_doc.batch_processing_history:
                    history_doc = frappe.get_doc("Batch Processing History", batch_doc.batch_processing_history)
                    history_doc.update(history_entry)
                    history_doc.save(ignore_permissions=True)
                    
        except Exception as e:
            frappe.log_error(f"Error updating batch processing history: {str(e)}")
            
    def get_or_create_batch_amb(self, item):
        """Get existing or create new Batch AMB record for incoming material"""
        try:
            # Check if Batch AMB exists for this ERPNext batch
            existing_batch = frappe.db.get_value(
                "Batch AMB", 
                {"erpnext_batch_reference": item.batch_no}, 
                "name"
            )
            
            if existing_batch:
                return existing_batch
                
            # Create new Batch AMB for incoming material
            batch_amb = {
                "doctype": "Batch AMB",
                "item_to_manufacture": item.item_code,
                "batch_qty": item.qty,
                "custom_batch_level": "1",  # Level 1 for raw materials
                "erpnext_batch_reference": item.batch_no,
                "manufacturing_date": nowdate(),
                "expiry_date": frappe.utils.add_months(nowdate(), 24),  # Default 24 months
                "custom_plant_code": self.get_item_plant_code(item.item_code),
                "supplier": self.supplier,
                "purchase_receipt_reference": self.name,
                "workflow_state": "Draft",
                "custom_received_from_supplier": 1
            }
            
            batch_doc = frappe.get_doc(batch_amb)
            batch_doc.insert(ignore_permissions=True)
            
            return batch_doc.name
            
        except Exception as e:
            frappe.log_error(f"Error creating Batch AMB: {str(e)}")
            return None
            
    def trigger_warehouse_integration(self):
        """Trigger all warehouse management integrations"""
        try:
            # Import integration class
            from amb_w_spc.sfc_manufacturing.warehouse_management.integration import WarehouseIntegration
            
            # Create stock entry for received materials
            stock_entry = self.create_stock_entry_for_receipt()
            
            if stock_entry:
                # Trigger warehouse integration workflows
                WarehouseIntegration.integrate_with_batch_amb(None, stock_entry.name)
                WarehouseIntegration.sync_with_quality_systems(stock_entry.name)
                WarehouseIntegration.update_fda_compliance_records(stock_entry.name)
                
        except Exception as e:
            frappe.log_error(f"Error triggering warehouse integration: {str(e)}")
            
    def create_stock_entry_for_receipt(self):
        """Create stock entry for purchase receipt"""
        try:
            stock_entry = {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "purpose": "Material Receipt",
                "posting_date": self.posting_date,
                "custom_sap_movement_type": "101",
                "custom_purchase_receipt_reference": self.name,
                "custom_zone_status": "Red Zone",  # Default to Red Zone until quality approved
                "items": []
            }
            
            for item in self.items:
                stock_entry["items"].append({
                    "item_code": item.item_code,
                    "qty": item.qty,
                    "t_warehouse": item.warehouse,
                    "batch_no": item.batch_no if hasattr(item, 'batch_no') else None,
                    "rate": item.rate,
                    "amount": item.amount
                })
                
            se_doc = frappe.get_doc(stock_entry)
            se_doc.insert(ignore_permissions=True)
            se_doc.submit()
            
            return se_doc
            
        except Exception as e:
            frappe.log_error(f"Error creating stock entry: {str(e)}")
            return None
            
    def notify_quality_systems(self):
        """Notify quality management systems of new receipts"""
        try:
            # Create SPC Alert for new material receipts requiring inspection
            inspection_items = [item for item in self.items if item.quality_inspection_required]
            
            if inspection_items:
                alert_doc = {
                    "doctype": "SPC Alert",
                    "alert_type": "Quality Inspection Required",
                    "priority": "High",
                    "description": f"Purchase Receipt {self.name} contains {len(inspection_items)} items requiring quality inspection",
                    "reference_doctype": "Purchase Receipt Integration",
                    "reference_name": self.name,
                    "alert_date": nowdate(),
                    "status": "Open",
                    "assigned_to": self.get_quality_inspector(),
                    "plant_code": self.get_primary_plant_code(),
                    "escalation_required": 0
                }
                
                try:
                    alert = frappe.get_doc(alert_doc)
                    alert.insert(ignore_permissions=True)
                except Exception:
                    frappe.log_error(f"SPC Alert DocType not found. Alert details: {json.dumps(alert_doc)}")
                    
        except Exception as e:
            frappe.log_error(f"Error notifying quality systems: {str(e)}")
            
    def get_quality_inspector(self):
        """Get available quality inspector"""
        inspectors = frappe.get_all(
            "SFC Operator",
            filters={
                "operator_status": "Active",
                "operator_type": "Quality Inspector"
            },
            fields=["user_id"],
            limit=1
        )
        
        if inspectors:
            return inspectors[0].user_id
        else:
            return frappe.session.user
            
    def get_primary_plant_code(self):
        """Get primary plant code for this receipt"""
        plant_codes = [self.get_item_plant_code(item.item_code) for item in self.items]
        
        # Return most common plant code
        from collections import Counter
        return Counter(plant_codes).most_common(1)[0][0] if plant_codes else 'default'

# API Functions for Purchase Receipt Integration

@frappe.whitelist()
def create_purchase_receipt_integration(purchase_receipt_name):
    """Create Purchase Receipt Integration from standard Purchase Receipt"""
    try:
        # Get the original Purchase Receipt
        pr = frappe.get_doc("Purchase Receipt", purchase_receipt_name)
        
        # Create Purchase Receipt Integration
        pr_integration = {
            "doctype": "Purchase Receipt Integration",
            "purchase_receipt_reference": purchase_receipt_name,
            "supplier": pr.supplier,
            "company": pr.company,
            "posting_date": pr.posting_date,
            "posting_time": pr.posting_time,
            "total_amount": pr.grand_total,
            "currency": pr.currency,
            "items": []
        }
        
        # Copy items with enhancements
        for pr_item in pr.items:
            item_data = {
                "item_code": pr_item.item_code,
                "item_name": pr_item.item_name,
                "description": pr_item.description,
                "qty": pr_item.qty,
                "rate": pr_item.rate,
                "amount": pr_item.amount,
                "warehouse": pr_item.warehouse,
                "quality_inspection_required": frappe.db.get_value(
                    "Item", pr_item.item_code, "inspection_required_before_delivery"
                ) or 0
            }
            
            # Add batch information if available
            if hasattr(pr_item, 'batch_no') and pr_item.batch_no:
                item_data["batch_no"] = pr_item.batch_no
                
            pr_integration["items"].append(item_data)
            
        # Create and submit the integration document
        integration_doc = frappe.get_doc(pr_integration)
        integration_doc.insert(ignore_permissions=True)
        integration_doc.submit()
        
        return {
            "success": True,
            "integration_name": integration_doc.name,
            "message": f"Purchase Receipt Integration {integration_doc.name} created successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating Purchase Receipt Integration: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_receiving_dashboard_data():
    """Get dashboard data for receiving operations"""
    try:
        # Get recent receipts with integration status
        recent_receipts = frappe.db.sql("""
            SELECT 
                pr.name,
                pr.supplier,
                pr.posting_date,
                pr.grand_total,
                COUNT(pri.name) as integration_count,
                COUNT(CASE WHEN pri.docstatus = 1 THEN 1 END) as submitted_integrations
            FROM `tabPurchase Receipt` pr
            LEFT JOIN `tabPurchase Receipt Integration` pri ON pr.name = pri.purchase_receipt_reference
            WHERE pr.posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY pr.name
            ORDER BY pr.posting_date DESC
            LIMIT 20
        """, as_dict=True)
        
        # Get summary statistics
        summary = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_receipts,
                SUM(grand_total) as total_value,
                COUNT(CASE WHEN docstatus = 1 THEN 1 END) as submitted_receipts
            FROM `tabPurchase Receipt`
            WHERE posting_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        """, as_dict=True)[0]
        
        return {
            "success": True,
            "recent_receipts": recent_receipts,
            "summary": summary
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting receiving dashboard data: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def process_quality_inspection_result(quality_inspection_name, result):
    """Process quality inspection result and route materials accordingly"""
    try:
        qi = frappe.get_doc("Quality Inspection", quality_inspection_name)
        
        # Get related Purchase Receipt Integration
        pr_integration_name = qi.custom_purchase_receipt_integration
        
        if not pr_integration_name:
            return {"success": False, "error": "No Purchase Receipt Integration found"}
            
        pr_integration = frappe.get_doc("Purchase Receipt Integration", pr_integration_name)
        
        # Find the related item
        related_item = None
        for item in pr_integration.items:
            if item.quality_inspection == quality_inspection_name:
                related_item = item
                break
                
        if not related_item:
            return {"success": False, "error": "Related item not found"}
            
        # Route based on inspection result
        if result == "Pass":
            # Move to production warehouse
            target_warehouse = related_item.final_warehouse
            
            # Create stock entry for movement
            stock_entry = {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Transfer",
                "purpose": "Material Transfer",
                "posting_date": nowdate(),
                "custom_sap_movement_type": "311",
                "custom_quality_inspection_reference": quality_inspection_name,
                "items": [{
                    "item_code": related_item.item_code,
                    "qty": related_item.qty,
                    "s_warehouse": related_item.initial_warehouse,  # From quarantine
                    "t_warehouse": target_warehouse,              # To production
                    "batch_no": related_item.batch_no if hasattr(related_item, 'batch_no') else None
                }]
            }
            
            se_doc = frappe.get_doc(stock_entry)
            se_doc.insert(ignore_permissions=True)
            se_doc.submit()
            
            # Update zone status to Green Zone
            related_item.current_zone_status = "Green Zone"
            
        else:
            # Move to rejection warehouse
            rejection_warehouse = f"Raw Material Rejected {pr_integration.get_item_plant_code(related_item.item_code).title()} - AMB-W"
            
            # Create stock entry for rejection
            stock_entry = {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Transfer",
                "purpose": "Material Transfer",
                "posting_date": nowdate(),
                "custom_sap_movement_type": "321",  # Quality rejection
                "custom_quality_inspection_reference": quality_inspection_name,
                "items": [{
                    "item_code": related_item.item_code,
                    "qty": related_item.qty,
                    "s_warehouse": related_item.initial_warehouse,
                    "t_warehouse": rejection_warehouse,
                    "batch_no": related_item.batch_no if hasattr(related_item, 'batch_no') else None
                }]
            }
            
            se_doc = frappe.get_doc(stock_entry)
            se_doc.insert(ignore_permissions=True)
            se_doc.submit()
            
            # Update zone status to Red Zone
            related_item.current_zone_status = "Red Zone"
            
        # Save the integration document
        pr_integration.save(ignore_permissions=True)
        
        return {
            "success": True,
            "message": f"Material routed based on quality result: {result}",
            "stock_entry": se_doc.name
        }
        
    except Exception as e:
        frappe.log_error(f"Error processing quality inspection result: {str(e)}")
        return {"success": False, "error": str(e)}
