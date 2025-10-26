import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt, cint
import json

def purchase_receipt_on_submit(doc, method):
    """
    Hook: Called when Purchase Receipt is submitted
    Automatically creates Purchase Receipt Integration and triggers warehouse workflows
    """
    try:
        # Create Purchase Receipt Integration automatically
        create_automatic_integration(doc)
        
        # Trigger immediate warehouse placement for non-inspection items
        process_direct_placement_items(doc)
        
        # Create batch records for received materials
        create_batch_records_for_receipt(doc)
        
        # Update inventory status
        update_inventory_status(doc)
        
    except Exception as e:
        frappe.log_error(f"Error in purchase receipt submission hooks: {str(e)}")

def create_automatic_integration(purchase_receipt_doc):
    """Create Purchase Receipt Integration automatically when PR is submitted"""
    try:
        # Check if integration already exists
        existing_integration = frappe.db.exists(
            "Purchase Receipt Integration",
            {"purchase_receipt_reference": purchase_receipt_doc.name}
        )
        
        if existing_integration:
            return existing_integration
            
        # Create new integration
        from amb_w_spc.sfc_manufacturing.doctype.purchase_receipt_integration.purchase_receipt_integration import create_purchase_receipt_integration
        
        result = create_purchase_receipt_integration(purchase_receipt_doc.name)
        
        if result.get("success"):
            frappe.msgprint(
                _("Purchase Receipt Integration {0} created automatically").format(result["integration_name"]),
                alert=True
            )
            return result["integration_name"]
        else:
            frappe.log_error(f"Failed to create automatic integration: {result.get('error')}")
            
    except Exception as e:
        frappe.log_error(f"Error creating automatic integration: {str(e)}")

def process_direct_placement_items(purchase_receipt_doc):
    """Process items that don't require quality inspection for direct warehouse placement"""
    try:
        for item in purchase_receipt_doc.items:
            # Check if item requires quality inspection
            requires_inspection = frappe.db.get_value(
                "Item", item.item_code, "inspection_required_before_delivery"
            )
            
            if not requires_inspection:
                # Create direct stock entry for immediate placement
                create_direct_placement_stock_entry(purchase_receipt_doc, item)
                
    except Exception as e:
        frappe.log_error(f"Error processing direct placement items: {str(e)}")

def create_direct_placement_stock_entry(purchase_receipt_doc, item):
    """Create stock entry for direct warehouse placement (no inspection required)"""
    try:
        # Determine plant code and appropriate warehouse
        plant_code = get_item_plant_code(item.item_code)
        target_warehouse = get_production_warehouse_for_plant(plant_code, item.warehouse)
        
        stock_entry = {
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "purpose": "Material Receipt",
            "posting_date": purchase_receipt_doc.posting_date,
            "custom_sap_movement_type": "101",  # Goods Receipt
            "custom_purchase_receipt_reference": purchase_receipt_doc.name,
            "custom_zone_status": "Green Zone",  # Direct to green zone (no inspection)
            "custom_direct_placement": 1,
            "items": [{
                "item_code": item.item_code,
                "qty": item.qty,
                "t_warehouse": target_warehouse,
                "batch_no": item.batch_no if hasattr(item, 'batch_no') else None,
                "rate": item.rate,
                "amount": item.amount
            }]
        }
        
        se_doc = frappe.get_doc(stock_entry)
        se_doc.insert(ignore_permissions=True)
        se_doc.submit()
        
        # Link back to purchase receipt item
        item.db_set("custom_direct_placement_stock_entry", se_doc.name)
        
        frappe.msgprint(
            _("Item {0} placed directly in warehouse {1} (no inspection required)").format(
                item.item_code, target_warehouse
            ),
            alert=True
        )
        
        return se_doc.name
        
    except Exception as e:
        frappe.log_error(f"Error creating direct placement stock entry: {str(e)}")

def create_batch_records_for_receipt(purchase_receipt_doc):
    """Create or update Batch AMB records for received materials"""
    try:
        for item in purchase_receipt_doc.items:
            if hasattr(item, 'batch_no') and item.batch_no:
                create_or_update_batch_amb(purchase_receipt_doc, item)
                
    except Exception as e:
        frappe.log_error(f"Error creating batch records: {str(e)}")

def create_or_update_batch_amb(purchase_receipt_doc, item):
    """Create or update Batch AMB record for received material"""
    try:
        # Check if Batch AMB already exists for this ERPNext batch
        existing_batch = frappe.db.get_value(
            "Batch AMB",
            {"erpnext_batch_reference": item.batch_no},
            "name"
        )
        
        if existing_batch:
            # Update existing batch with receipt information
            batch_doc = frappe.get_doc("Batch AMB", existing_batch)
            batch_doc.db_set("purchase_receipt_reference", purchase_receipt_doc.name)
            batch_doc.db_set("supplier", purchase_receipt_doc.supplier)
            batch_doc.db_set("custom_received_from_supplier", 1)
            return existing_batch
            
        # Create new Batch AMB record
        plant_code = get_item_plant_code(item.item_code)
        
        batch_amb = {
            "doctype": "Batch AMB",
            "item_to_manufacture": item.item_code,
            "batch_qty": item.qty,
            "custom_batch_level": "1",  # Level 1 for raw materials
            "erpnext_batch_reference": item.batch_no,
            "manufacturing_date": purchase_receipt_doc.posting_date,
            "expiry_date": frappe.utils.add_months(purchase_receipt_doc.posting_date, 24),  # Default 24 months
            "custom_plant_code": plant_code,
            "supplier": purchase_receipt_doc.supplier,
            "purchase_receipt_reference": purchase_receipt_doc.name,
            "workflow_state": "Draft",
            "custom_received_from_supplier": 1
        }
        
        batch_doc = frappe.get_doc(batch_amb)
        batch_doc.insert(ignore_permissions=True)
        
        # Create batch processing history
        create_batch_receiving_history(batch_doc, purchase_receipt_doc, item)
        
        return batch_doc.name
        
    except Exception as e:
        frappe.log_error(f"Error creating Batch AMB: {str(e)}")

def create_batch_receiving_history(batch_doc, purchase_receipt_doc, item):
    """Create batch processing history for material receiving"""
    try:
        # Import warehouse batch integration
        from amb_w_spc.sfc_manufacturing.warehouse_management.warehouse_batch_integration import WarehouseBatchIntegration
        
        # Create receiving history entry
        WarehouseBatchIntegration.create_batch_processing_history(
            batch_doc, 
            "Material Received",
            f"Purchase Receipt: {purchase_receipt_doc.name} - Material received from {purchase_receipt_doc.supplier}"
        )
        
    except Exception as e:
        frappe.log_error(f"Error creating batch receiving history: {str(e)}")

def update_inventory_status(purchase_receipt_doc):
    """Update inventory status and create alerts"""
    try:
        # Count items by type
        inspection_required = 0
        direct_placement = 0
        total_value = 0
        
        for item in purchase_receipt_doc.items:
            total_value += item.amount
            
            requires_inspection = frappe.db.get_value(
                "Item", item.item_code, "inspection_required_before_delivery"
            )
            
            if requires_inspection:
                inspection_required += 1
            else:
                direct_placement += 1
                
        # Create inventory status update
        status_update = {
            "doctype": "Inventory Status Update",
            "reference_doctype": "Purchase Receipt",
            "reference_name": purchase_receipt_doc.name,
            "update_type": "Material Receipt",
            "total_items": len(purchase_receipt_doc.items),
            "inspection_required_items": inspection_required,
            "direct_placement_items": direct_placement,
            "total_value": total_value,
            "supplier": purchase_receipt_doc.supplier,
            "posting_date": purchase_receipt_doc.posting_date,
            "status": "Completed"
        }
        
        try:
            status_doc = frappe.get_doc(status_update)
            status_doc.insert(ignore_permissions=True)
        except Exception:
            # If DocType doesn't exist, log the status
            frappe.log_error(f"Inventory Status Update DocType not found. Status: {json.dumps(status_update)}")
            
    except Exception as e:
        frappe.log_error(f"Error updating inventory status: {str(e)}")

def get_item_plant_code(item_code):
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

def get_production_warehouse_for_plant(plant_code, fallback_warehouse):
    """Get appropriate production warehouse based on plant code"""
    # Define warehouse mapping for each plant
    warehouse_mapping = {
        'juice': 'Raw Material Juice Production - AMB-W',
        'dry': 'Raw Material Dry Production - AMB-W',
        'mix': 'Raw Material Mix Production - AMB-W',
        'default': 'Raw Material Main - AMB-W'
    }
    
    target_warehouse = warehouse_mapping.get(plant_code, warehouse_mapping['default'])
    
    # Check if warehouse exists, fallback to original if not
    if not frappe.db.exists("Warehouse", target_warehouse):
        return fallback_warehouse
        
    return target_warehouse

def purchase_receipt_before_submit(doc, method):
    """
    Hook: Called before Purchase Receipt is submitted
    Validates warehouse assignments and prepares integration data
    """
    try:
        # Validate plant code assignments
        validate_plant_code_assignments(doc)
        
        # Validate temperature requirements
        validate_temperature_requirements(doc)
        
        # Prepare batch creation requirements
        prepare_batch_requirements(doc)
        
    except Exception as e:
        frappe.throw(_("Purchase Receipt validation failed: {0}").format(str(e)))

def validate_plant_code_assignments(purchase_receipt_doc):
    """Validate that warehouse assignments are appropriate for item plant codes"""
    validation_errors = []
    
    for item in purchase_receipt_doc.items:
        plant_code = get_item_plant_code(item.item_code)
        
        # Get warehouse plant code
        warehouse_plant = frappe.db.get_value("Warehouse", item.warehouse, "custom_plant_code")
        
        if not warehouse_plant and ' - ' in item.warehouse:
            warehouse_plant = item.warehouse.split(' - ')[-1].lower()
            
        # Check compatibility
        if warehouse_plant and warehouse_plant != plant_code and warehouse_plant != 'default':
            validation_errors.append(
                _("Item {0} (plant: {1}) assigned to incompatible warehouse {2} (plant: {3})").format(
                    item.item_code, plant_code, item.warehouse, warehouse_plant
                )
            )
            
    if validation_errors:
        frappe.msgprint(
            _("Warehouse Assignment Warnings:<br>{0}").format("<br>".join(validation_errors)),
            alert=True,
            indicator="orange"
        )

def validate_temperature_requirements(purchase_receipt_doc):
    """Validate temperature requirements for incoming materials"""
    temperature_warnings = []
    
    for item in purchase_receipt_doc.items:
        # Check if item requires temperature control
        item_group = frappe.db.get_value("Item", item.item_code, "item_group")
        
        if item_group in ["Finished Goods", "Temperature Sensitive", "Biological"]:
            warehouse_temp_control = frappe.db.get_value(
                "Warehouse", item.warehouse, "custom_temperature_control"
            )
            
            if not warehouse_temp_control:
                temperature_warnings.append(
                    _("Temperature sensitive item {0} assigned to non-temperature controlled warehouse {1}").format(
                        item.item_code, item.warehouse
                    )
                )
                
    if temperature_warnings:
        frappe.msgprint(
            _("Temperature Control Warnings:<br>{0}").format("<br>".join(temperature_warnings)),
            alert=True,
            indicator="yellow"
        )

def prepare_batch_requirements(purchase_receipt_doc):
    """Prepare batch creation requirements"""
    batch_items = []
    
    for item in purchase_receipt_doc.items:
        if hasattr(item, 'batch_no') and item.batch_no:
            batch_items.append({
                "item_code": item.item_code,
                "batch_no": item.batch_no,
                "qty": item.qty,
                "plant_code": get_item_plant_code(item.item_code)
            })
            
    if batch_items:
        frappe.msgprint(
            _("Will create {0} batch records for received materials").format(len(batch_items)),
            alert=True,
            indicator="blue"
        )

# API Functions for enhanced Purchase Receipt workflows

@frappe.whitelist()
def get_purchase_receipt_integration_status(purchase_receipt_name):
    """Get integration status for a Purchase Receipt"""
    try:
        # Get integration record
        integration = frappe.db.get_value(
            "Purchase Receipt Integration",
            {"purchase_receipt_reference": purchase_receipt_name},
            ["name", "warehouse_integration_status", "quality_system_integration_status", 
             "batch_tracking_integration_status", "overall_status"]
        )
        
        if not integration:
            return {"success": False, "message": "No integration found"}
            
        # Get quality inspections
        quality_inspections = frappe.get_all(
            "Quality Inspection",
            filters={"reference_name": purchase_receipt_name},
            fields=["name", "status", "inspection_type"]
        )
        
        # Get batch records
        batch_records = frappe.get_all(
            "Batch AMB", 
            filters={"purchase_receipt_reference": purchase_receipt_name},
            fields=["name", "workflow_state", "custom_batch_level"]
        )
        
        return {
            "success": True,
            "integration": integration,
            "quality_inspections": quality_inspections,
            "batch_records": batch_records,
            "integration_name": integration[0] if integration else None
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting integration status: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def trigger_quality_inspection_workflow(purchase_receipt_name, item_code):
    """Trigger quality inspection workflow for specific item"""
    try:
        # Get Purchase Receipt and item details
        pr = frappe.get_doc("Purchase Receipt", purchase_receipt_name)
        
        # Find the specific item
        target_item = None
        for item in pr.items:
            if item.item_code == item_code:
                target_item = item
                break
                
        if not target_item:
            return {"success": False, "error": "Item not found in Purchase Receipt"}
            
        # Create quality inspection
        qi_doc = {
            "doctype": "Quality Inspection",
            "inspection_type": "Incoming",
            "reference_type": "Purchase Receipt",
            "reference_name": purchase_receipt_name,
            "item_code": target_item.item_code,
            "item_name": target_item.item_name,
            "sample_size": calculate_sample_size(target_item.qty),
            "report_date": nowdate(),
            "status": "Submitted",
            "supplier": pr.supplier,
            "batch_no": target_item.batch_no if hasattr(target_item, 'batch_no') else None,
            "warehouse": target_item.warehouse,
            "custom_plant_code": get_item_plant_code(target_item.item_code),
            "custom_inspection_priority": "High",
            "remarks": f"Manual trigger from Purchase Receipt {purchase_receipt_name}"
        }
        
        qi = frappe.get_doc(qi_doc)
        qi.insert(ignore_permissions=True)
        
        return {
            "success": True,
            "quality_inspection": qi.name,
            "message": f"Quality Inspection {qi.name} created for item {item_code}"
        }
        
    except Exception as e:
        frappe.log_error(f"Error triggering quality inspection: {str(e)}")
        return {"success": False, "error": str(e)}

def calculate_sample_size(total_qty):
    """Calculate sample size for quality inspection"""
    if total_qty <= 10:
        return 1
    elif total_qty <= 100:
        return 3
    elif total_qty <= 1000:
        return 5
    else:
        return 10

@frappe.whitelist()
def get_receiving_warehouse_recommendations(item_code):
    """Get warehouse recommendations based on item characteristics"""
    try:
        # Get item details
        item_doc = frappe.get_doc("Item", item_code)
        plant_code = get_item_plant_code(item_code)
        
        # Determine warehouse recommendations
        recommendations = {
            "plant_code": plant_code,
            "primary_warehouses": [],
            "quarantine_warehouses": [],
            "temperature_required": False
        }
        
        # Check if temperature sensitive
        if item_doc.item_group in ["Finished Goods", "Temperature Sensitive", "Biological"]:
            recommendations["temperature_required"] = True
            
        # Get appropriate warehouses for plant
        if plant_code == 'juice':
            recommendations["primary_warehouses"] = [
                "Raw Material Juice Production - AMB-W",
                "Raw Material Main - AMB-W"
            ]
            recommendations["quarantine_warehouses"] = [
                "Raw Material Quarantine Juice - AMB-W"
            ]
        elif plant_code == 'dry':
            recommendations["primary_warehouses"] = [
                "Raw Material Dry Production - AMB-W", 
                "Raw Material Main - AMB-W"
            ]
            recommendations["quarantine_warehouses"] = [
                "Raw Material Quarantine Dry - AMB-W"
            ]
        elif plant_code == 'mix':
            recommendations["primary_warehouses"] = [
                "Raw Material Mix Production - AMB-W",
                "Raw Material Main - AMB-W"
            ]
            recommendations["quarantine_warehouses"] = [
                "Raw Material Quarantine Mix - AMB-W"
            ]
        else:
            recommendations["primary_warehouses"] = [
                "Raw Material Main - AMB-W"
            ]
            recommendations["quarantine_warehouses"] = [
                "Raw Material Quarantine - AMB-W"
            ]
            
        # Filter to only existing warehouses
        all_warehouses = frappe.get_all("Warehouse", fields=["name"])
        existing_warehouse_names = [w.name for w in all_warehouses]
        
        recommendations["primary_warehouses"] = [
            w for w in recommendations["primary_warehouses"] if w in existing_warehouse_names
        ]
        recommendations["quarantine_warehouses"] = [
            w for w in recommendations["quarantine_warehouses"] if w in existing_warehouse_names
        ]
        
        return {
            "success": True,
            "recommendations": recommendations
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting warehouse recommendations: {str(e)}")
        return {"success": False, "error": str(e)}
