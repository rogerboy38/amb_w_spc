# Copyright (c) 2026, AMB-Wellness and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

STATE_LABELS = {
	0: "Template",
	1: "Provisioned",
	2: "Configured",
	3: "Calibrated",
	4: "Tested",
	5: "Approved",
	6: "Certified",
	7: "Suspended",
	8: "Failed",
	9: "Retired",
}

# Transitions that MUST have an electronic signature attached (21 CFR Part 11 §11.50)
SIGNATURE_REQUIRED_FORWARD = {(4, 5), (5, 6)}


class SensorSkillLifecycleTransition(Document):
	"""Immutable lifecycle transition log for Sensor Configuration instances.

	Supplements SPC Audit Trail with a narrow, denormalized view that
	SkillRouter can query without joining the full audit table. Every
	transition is recorded as a separate document — no batch signing.
	"""

	def before_insert(self):
		self.from_state_label = STATE_LABELS.get(self.from_state, "Unknown")
		self.to_state_label = STATE_LABELS.get(self.to_state, "Unknown")
		self.is_reverse_transition = 1 if (self.to_state is not None and self.from_state is not None and self.to_state < self.from_state) else 0

	def validate(self):
		needs_sig = (self.from_state, self.to_state) in SIGNATURE_REQUIRED_FORWARD or self.is_reverse_transition
		if needs_sig and not self.e_signature:
			frappe.throw(
				f"Transition {self.from_state}→{self.to_state} requires an electronic signature (21 CFR Part 11 §11.50)."
			)

	def on_trash(self):
		# Lifecycle transitions are immutable evidence — block deletion unless explicit admin override.
		if not frappe.session.user == "Administrator":
			frappe.throw("Lifecycle transitions are immutable. Deletion requires Administrator role.")
