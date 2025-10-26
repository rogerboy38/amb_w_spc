# Copyright (c) 2024, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MrpPlanningMaterial(Document):
	def before_save(self):
		"""Calculate shortage quantity"""
		if self.required_qty and self.available_qty:
			self.shortage_qty = max(0, self.required_qty - self.available_qty)
		else:
			self.shortage_qty = self.required_qty or 0
	
	def validate(self):
		"""Validate material planning data"""
		if self.required_qty and self.required_qty < 0:
			frappe.throw("Required quantity cannot be negative")
		
		if self.available_qty and self.available_qty < 0:
			frappe.throw("Available quantity cannot be negative")
