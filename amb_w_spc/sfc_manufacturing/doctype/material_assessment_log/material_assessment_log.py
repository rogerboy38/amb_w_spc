# -*- coding: utf-8 -*-
# Copyright (c) 2025, AMB-Wellness and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, now_datetime
import json

class MaterialAssessmentLog(Document):
	def validate(self):
		"""Validate the Material Assessment Log"""
		if not self.assessment_date:
			self.assessment_date = now_datetime()
		
		if not self.assessed_by:
			self.assessed_by = frappe.session.user
		
		# Set default assessment type if not specified
		if not self.assessment_type:
			if self.work_order and not self.mrp_planning:
				self.assessment_type = "Work Order Assessment"
			elif self.mrp_planning and not self.work_order:
				self.assessment_type = "MRP Master Assessment"
			else:
				self.assessment_type = "Warehouse Pick Assessment"
		
		# Calculate completion percentage from items
		if self.items:
			self.calculate_completion_percentage()
		
		# Validate and update batch information
		self.validate_batch_integration()
		
		# Update zone status based on completion
		self.update_zone_status()
	
	def before_save(self):
		"""Update related documents with latest assessment"""
		if self.work_order:
			# Update Work Order with latest zone status
			frappe.db.set_value(
				"Work Order",
				self.work_order,
				{
					"custom_current_zone_status": self.zone_status,
					"custom_material_completion_percentage": self.completion_percentage,
					"custom_last_zone_update": self.assessment_date,
					"custom_missing_materials_json": self.missing_materials
				}
			)
		
		# Update MRP Planning if linked
		if self.mrp_planning:
			self.update_mrp_planning_status()
	
	def calculate_completion_percentage(self):
		"""Calculate completion percentage based on assessment items"""
		if not self.items:
			return
		
		total_items = len(self.items)
		available_items = 0
		
		for item in self.items:
			if flt(item.available_qty) >= flt(item.required_qty):
				available_items += 1
		
		self.completion_percentage = (available_items / total_items * 100) if total_items > 0 else 0
	
	def update_zone_status(self):
		"""Update zone status based on completion percentage"""
		if not hasattr(self, 'completion_percentage') or self.completion_percentage is None:
			return
		
		if self.completion_percentage >= 100:
			self.zone_status = "Green Zone"
		else:
			self.zone_status = "Red Zone"
	
	def update_mrp_planning_status(self):
		"""Update MRP Planning with assessment information"""
		try:
			mrp_doc = frappe.get_doc("MRP Planning", self.mrp_planning)
			
			# Update MRP Planning with warehouse assessment info
			if hasattr(mrp_doc, 'custom_warehouse_assessment_status'):
				assessment_status = json.loads(mrp_doc.custom_warehouse_assessment_status or "{}")
			else:
				assessment_status = {}
			
			# Add this assessment to the status
			key = self.work_order or f"master_{self.name}"
			assessment_status[key] = {
				"assessment_log": self.name,
				"zone_status": self.zone_status,
				"completion_percentage": self.completion_percentage,
				"assessment_date": self.assessment_date,
				"assessment_type": self.assessment_type
			}
			
			frappe.db.set_value(
				"MRP Planning",
				self.mrp_planning,
				"custom_warehouse_assessment_status",
				json.dumps(assessment_status)
			)
			
		except Exception as e:
			frappe.log_error(f"MRP Planning status update failed: {str(e)}")
	
	def validate_batch_integration(self):
		"""Validate and update batch integration fields"""
		try:
			# Update batch reference from work order if available
			if self.work_order and not self.custom_batch_reference:
				batch_ref = frappe.db.get_value(
					"Batch AMB", 
					{"work_order_ref": self.work_order}, 
					"name"
				)
				if batch_ref:
					self.custom_batch_reference = batch_ref
					self.custom_batch_quality_status = self.get_batch_quality_status(batch_ref)
			
			# Update batch information for assessment items
			if self.custom_batch_availability_check and self.items:
				for item in self.items:
					self.update_item_batch_info(item)
					
		except Exception as e:
			frappe.log_error(f"Batch integration validation failed: {str(e)}")
	
	def update_item_batch_info(self, item):
		"""Update individual item with batch information"""
		try:
			# Find best available batch for this item
			best_batch = self.find_best_batch_for_item(
				item.item_code, 
				item.required_qty, 
				item.warehouse
			)
			
			if best_batch:
				item.custom_suggested_batch = best_batch["batch_amb"]
				item.custom_batch_availability_qty = best_batch["available_qty"]
				item.custom_batch_expiry_date = best_batch["expiry_date"]
				item.custom_batch_quality_status = best_batch["quality_status"]
				item.custom_warehouse_location = best_batch["warehouse"]
				
				# Set assessment result
				if best_batch["quality_status"] in ["Failed", "Hold"]:
					item.custom_assessment_result = f"Quality {best_batch['quality_status']}"
				elif best_batch["expiry_date"] and best_batch["expiry_date"] <= frappe.utils.nowdate():
					item.custom_assessment_result = "Expired"
				elif best_batch["available_qty"] >= item.required_qty:
					item.custom_assessment_result = "Available"
				elif best_batch["available_qty"] > 0:
					item.custom_assessment_result = "Partially Available"
				else:
					item.custom_assessment_result = "Not Available"
			else:
				item.custom_assessment_result = "Not Available"
				
		except Exception as e:
			frappe.log_error(f"Item batch info update failed: {str(e)}")
	
	def find_best_batch_for_item(self, item_code, required_qty, warehouse=None):
		"""Find the best available batch for an item"""
		try:
			# Query to find batches with stock
			sql = """
				SELECT 
					ba.name as batch_amb,
					ba.erpnext_batch_reference,
					ba.expiry_date,
					ba.workflow_state,
					b.actual_qty as available_qty,
					b.warehouse
				FROM `tabBatch AMB` ba
				INNER JOIN `tabBin` b ON ba.erpnext_batch_reference = b.custom_current_batch
				WHERE ba.item_to_manufacture = %s
				AND b.actual_qty > 0
			"""
			
			params = [item_code]
			
			if warehouse:
				sql += " AND b.warehouse = %s"
				params.append(warehouse)
			
			sql += " ORDER BY ba.expiry_date ASC, b.actual_qty DESC LIMIT 1"
			
			result = frappe.db.sql(sql, params, as_dict=True)
			
			if result:
				batch = result[0]
				batch["quality_status"] = self.get_batch_quality_status(batch["batch_amb"])
				return batch
				
			return None
			
		except Exception as e:
			frappe.log_error(f"Best batch search failed: {str(e)}")
			return None
	
	def get_batch_quality_status(self, batch_amb_name):
		"""Get quality status for a batch"""
		try:
			from amb_w_spc.sfc_manufacturing.warehouse_management.warehouse_batch_integration import WarehouseBatchIntegration
			return WarehouseBatchIntegration.get_batch_quality_status(batch_amb_name)
		except Exception:
			return "Pending"
	
	def on_submit(self):
		"""Actions after assessment is submitted"""
		try:
			from amb_w_spc.sfc_manufacturing.warehouse_management.integration import WarehouseIntegration
			
			# Trigger warehouse integrations if this is a work order assessment
			if self.work_order and self.assessment_type == "Work Order Assessment":
				# Create or update pick requests based on assessment
				if self.zone_status == "Green Zone":
					# Materials are available, trigger pick process
					WarehouseIntegration.create_warehouse_pick_request(self.work_order)
				
				# Update quality and compliance systems
				WarehouseIntegration.sync_with_quality_systems(self.name)
				WarehouseIntegration.update_fda_compliance_records(self.name)
			
		except Exception as e:
			frappe.log_error(f"Material Assessment Log submission integration failed: {str(e)}")
			# Don't fail the submission due to integration issues

@frappe.whitelist()
def create_assessment_from_work_order(work_order_name):
	"""Create a material assessment log from a work order"""
	try:
		work_order = frappe.get_doc("Work Order", work_order_name)
		
		if not work_order.bom_no:
			return {"status": "error", "message": "No BOM associated with Work Order"}
		
		# Create assessment log
		assessment = frappe.get_doc({
			"doctype": "Material Assessment Log",
			"work_order": work_order_name,
			"mrp_planning": work_order.mrp_planning,
			"assessment_date": now_datetime(),
			"assessed_by": frappe.session.user,
			"assessment_type": "Work Order Assessment",
			"plant_code": work_order.plant_code,
			"items": []
		})
		
		# Get BOM items and add to assessment
		bom_items = frappe.get_all(
			"BOM Item",
			filters={"parent": work_order.bom_no},
			fields=["item_code", "qty", "warehouse", "item_name", "uom"]
		)
		
		for bom_item in bom_items:
			required_qty = flt(bom_item.qty * work_order.qty)
			available_qty = get_available_qty(bom_item.item_code, bom_item.warehouse)
			
			assessment.append("items", {
				"item_code": bom_item.item_code,
				"item_name": bom_item.item_name,
				"required_qty": required_qty,
				"available_qty": available_qty,
				"warehouse": bom_item.warehouse,
				"uom": bom_item.uom
			})
		
		assessment.insert()
		return {"status": "success", "assessment_log": assessment.name}
		
	except Exception as e:
		frappe.log_error(f"Assessment creation failed: {str(e)}")
		return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_warehouse_material_status(warehouse, item_codes=None):
	"""Get material status for items in a warehouse"""
	try:
		filters = {"warehouse": warehouse}
		if item_codes:
			if isinstance(item_codes, str):
				item_codes = json.loads(item_codes)
			filters["item_code"] = ["in", item_codes]
		
		bins = frappe.get_all(
			"Bin",
			filters=filters,
			fields=["item_code", "actual_qty", "reserved_qty", "ordered_qty", "projected_qty"]
		)
		
		material_status = []
		for bin_data in bins:
			item = frappe.get_doc("Item", bin_data.item_code)
			material_status.append({
				"item_code": bin_data.item_code,
				"item_name": item.item_name,
				"actual_qty": bin_data.actual_qty,
				"reserved_qty": bin_data.reserved_qty,
				"ordered_qty": bin_data.ordered_qty,
				"projected_qty": bin_data.projected_qty,
				"uom": item.stock_uom
			})
		
		return {"status": "success", "material_status": material_status}
		
	except Exception as e:
		frappe.log_error(f"Warehouse material status check failed: {str(e)}")
		return {"status": "error", "message": str(e)}

def get_available_qty(item_code, warehouse):
	"""Get available quantity for an item in a warehouse"""
	return frappe.db.get_value(
		"Bin",
		{"item_code": item_code, "warehouse": warehouse},
		"actual_qty"
	) or 0
