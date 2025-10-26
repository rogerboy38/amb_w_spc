# -*- coding: utf-8 -*-
# Copyright (c) 2025, AMB-Wellness and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class MaterialAssessmentLogItem(Document):
	def validate(self):
		"""Validate the Material Assessment Log Item"""
		if self.item_code:
			# Auto-fetch item name and UOM
			item = frappe.get_doc("Item", self.item_code)
			self.item_name = item.item_name
			self.uom = item.stock_uom
		
		# Calculate shortage quantity
		if self.required_qty and self.available_qty:
			self.shortage_qty = max(0, self.required_qty - self.available_qty)
			
			# Determine status
			if self.available_qty >= self.required_qty:
				self.status = "Available"
			elif self.available_qty > 0:
				self.status = "Partial"
			else:
				self.status = "Shortage"
