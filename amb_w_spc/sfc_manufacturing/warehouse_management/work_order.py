import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt

def before_save(doc, method=None):
	"""Hook: Before saving Work Order"""
	set_initial_zone_status(doc)
	update_material_requirements(doc)

def on_submit(doc, method=None):
	"""Hook: After submitting Work Order"""
	create_initial_material_assessment(doc)

def set_initial_zone_status(doc):
	"""Set initial zone status for new Work Orders"""
	if not doc.custom_current_zone_status:
		doc.custom_current_zone_status = "Red Zone"  # Default to Red Zone (incomplete)
		doc.custom_zone_status_color = "#dc3545"     # Red color
		doc.custom_material_completion_percentage = 0
		doc.custom_last_zone_update = now_datetime()

def update_material_requirements(doc):
	"""Update material requirements and availability"""
	if not doc.bom_no:
		return
	
	# Get BOM items
	bom_items = frappe.get_all(
		"BOM Item",
		filters={"parent": doc.bom_no},
		fields=["item_code", "qty", "warehouse", "item_name"]
	)
	
	# Calculate total required vs available
	total_items = len(bom_items)
	available_items = 0
	missing_materials = []
	
	for bom_item in bom_items:
		required_qty = flt(bom_item.qty * doc.qty)
		available_qty = get_available_qty(bom_item.item_code, bom_item.warehouse)
		
		if available_qty >= required_qty:
			available_items += 1
		else:
			missing_qty = required_qty - available_qty
			missing_materials.append({
				"item_code": bom_item.item_code,
				"item_name": bom_item.item_name,
				"required_qty": required_qty,
				"available_qty": available_qty,
				"missing_qty": missing_qty,
				"warehouse": bom_item.warehouse
			})
	
	# Update completion percentage
	completion_percentage = (available_items / total_items * 100) if total_items > 0 else 0
	doc.custom_material_completion_percentage = completion_percentage
	
	# Update zone status based on completion
	if completion_percentage >= 100:
		doc.custom_current_zone_status = "Green Zone"
		doc.custom_zone_status_color = "#28a745"  # Green
	else:
		doc.custom_current_zone_status = "Red Zone"
		doc.custom_zone_status_color = "#dc3545"  # Red
	
	# Store missing materials info
	doc.custom_missing_materials_json = frappe.as_json(missing_materials)

def get_available_qty(item_code, warehouse):
	"""Get available quantity for an item in a warehouse"""
	return frappe.db.get_value(
		"Bin",
		{"item_code": item_code, "warehouse": warehouse},
		"actual_qty"
	) or 0

def create_initial_material_assessment(doc):
	"""Create initial material assessment record"""
	# Create a material assessment log
	assessment = frappe.get_doc({
		"doctype": "Material Assessment Log",
		"work_order": doc.name,
		"assessment_date": now_datetime(),
		"zone_status": doc.custom_current_zone_status,
		"completion_percentage": doc.custom_material_completion_percentage,
		"missing_materials": doc.custom_missing_materials_json,
		"assessed_by": frappe.session.user
	})
	
	try:
		assessment.insert(ignore_permissions=True)
	except Exception as e:
		# If custom DocType doesn't exist, just log the assessment
		frappe.log_error(f"Material Assessment Log creation failed: {str(e)}")

def update_batch_context(doc):
	"""Update work order with batch context information"""
	try:
		# Find related batches
		related_batches = frappe.get_all(
			"Batch AMB",
			filters={"work_order_ref": doc.name},
			fields=["name", "workflow_state", "custom_batch_level", "custom_plant_code"]
		)
		
		if related_batches:
			# Update work order with batch information
			batch_info = {
				"batch_count": len(related_batches),
				"batch_levels": list(set(b["custom_batch_level"] for b in related_batches if b["custom_batch_level"])),
				"batch_states": list(set(b["workflow_state"] for b in related_batches if b["workflow_state"])),
				"plant_codes": list(set(b["custom_plant_code"] for b in related_batches if b["custom_plant_code"]))
			}
			
			doc.custom_batch_context = frappe.as_json(batch_info)
			
			# Determine batch quality impact on zone status
			if any(state in ["SPC Hold", "Rejected"] for state in batch_info["batch_states"]):
				doc.custom_current_zone_status = "Red Zone"
				doc.custom_zone_status_color = "#dc3545"
			
	except Exception as e:
		frappe.log_error(f"Batch context update failed: {str(e)}")

def integrate_with_batch_system(doc):
	"""Integrate work order with batch management system"""
	try:
		from amb_w_spc.sfc_manufacturing.warehouse_management.warehouse_batch_integration import WarehouseBatchIntegration
		
		# Sync zone status with batch quality
		WarehouseBatchIntegration.sync_warehouse_zone_status_with_batch_quality(doc.name)
		
		# Create batch processing history entries for work order start
		related_batches = frappe.get_all(
			"Batch AMB",
			filters={"work_order_ref": doc.name},
			fields=["name"]
		)
		
		for batch in related_batches:
			try:
				# Create mock stock entry for history
				stock_entry_mock = type('obj', (object,), {
					'name': f"WO-START-{doc.name}",
					'posting_date': doc.creation,
					'custom_sap_movement_type': None,
					'purpose': "Work Order Start",
					'custom_work_order_reference': doc.name
				})
				
				item_mock = type('obj', (object,), {
					'item_code': doc.production_item,
					'batch_no': None,  # Will be set if batch exists
					's_warehouse': None,
					't_warehouse': doc.fg_warehouse
				})
				
				WarehouseBatchIntegration.create_batch_processing_entry(
					stock_entry_mock, item_mock, batch["name"]
				)
				
			except Exception as batch_error:
				frappe.log_error(f"Batch integration failed for batch {batch['name']}: {str(batch_error)}")
			
	except Exception as e:
		frappe.log_error(f"Work Order batch system integration failed: {str(e)}")

def get_permission_query_conditions(user):
	"""Permission query conditions for Work Order"""
	if not user:
		user = frappe.session.user
	
	user_roles = frappe.get_roles(user)
	
	# Define role-based access
	role_access = {
		"Production Manager": "1=1",  # Access to all
		"Warehouse Manager": "1=1",   # Access to all
		"Manufacturing User": "(`tabWork Order`.owner = '{user}' OR `tabWork Order`.docstatus = 1)".format(user=user),
		"Stock User": "(`tabWork Order`.docstatus = 1)"  # Only submitted Work Orders
	}
	
	conditions = []
	for role in user_roles:
		if role in role_access:
			conditions.append(role_access[role])
	
	return " OR ".join(conditions) if conditions else "0=1"

@frappe.whitelist()
def update_work_order_zone_status(work_order_name):
	"""API endpoint to manually update Work Order zone status"""
	try:
		work_order = frappe.get_doc("Work Order", work_order_name)
		update_material_requirements(work_order)
		work_order.save(ignore_permissions=True)
		
		return {
			"status": "success",
			"zone_status": work_order.custom_current_zone_status,
			"completion_percentage": work_order.custom_material_completion_percentage,
			"last_updated": work_order.custom_last_zone_update
		}
	except Exception as e:
		frappe.log_error(f"Work Order zone status update failed: {str(e)}")
		return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_work_order_material_status(work_order_name):
	"""API endpoint to get detailed material status for a Work Order"""
	try:
		work_order = frappe.get_doc("Work Order", work_order_name)
		
		if not work_order.bom_no:
			return {"status": "error", "message": "No BOM associated with this Work Order"}
		
		# Get BOM items with availability
		bom_items = frappe.get_all(
			"BOM Item",
			filters={"parent": work_order.bom_no},
			fields=["item_code", "qty", "warehouse", "item_name", "description"]
		)
		
		material_status = []
		for bom_item in bom_items:
			required_qty = flt(bom_item.qty * work_order.qty)
			available_qty = get_available_qty(bom_item.item_code, bom_item.warehouse)
			
			material_status.append({
				"item_code": bom_item.item_code,
				"item_name": bom_item.item_name,
				"description": bom_item.description,
				"required_qty": required_qty,
				"available_qty": available_qty,
				"shortage": max(0, required_qty - available_qty),
				"warehouse": bom_item.warehouse,
				"status": "Available" if available_qty >= required_qty else "Shortage"
			})
		
		return {
			"status": "success",
			"work_order": work_order_name,
			"zone_status": work_order.custom_current_zone_status,
			"completion_percentage": work_order.custom_material_completion_percentage,
			"material_status": material_status
		}
	except Exception as e:
		frappe.log_error(f"Work Order material status check failed: {str(e)}")
		return {"status": "error", "message": str(e)}
