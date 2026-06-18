import frappe
from frappe.model.document import Document

# Lifecycle state machine — see CALIBRATION_LIFECYCLE_RESEARCH.md (PR #23)
LIFECYCLE_STATE_LABELS = {
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

# Allowed forward transitions: keep linear 0→...→6, plus terminal/reserved exits
ALLOWED_FORWARD = {
	(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
	(6, 9),  # Certified → Retired (planned EOL)
	# Reserved branches reachable from multiple states
	(1, 7), (2, 7), (3, 7), (4, 7), (5, 7), (6, 7),  # → Suspended
	(1, 8), (2, 8), (3, 8), (4, 8),                  # → Failed (terminal)
	(7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6),  # Suspended → back to qualifying states (with e-sig)
}
# Allowed reverse transitions (demotions) — all require e-sig in lifecycle transition log
ALLOWED_REVERSE = {
	(6, 5), (6, 4), (6, 3), (6, 2), (6, 1),  # Certified → demotion
	(5, 4), (5, 3), (5, 2),
	(4, 3), (4, 2),
	(3, 2),
	(2, 1),
}


class SensorConfiguration(Document):
	"""Sensor Configuration — instance-level lifecycle state machine.

	Lifecycle is the per-instance qualification track for a sensor (linked to
	a Sensor Skill template). State transitions are validated; the legibility
	label is kept in sync with the numeric ID, which drives code logic.
	"""

	def before_save(self):
		self._sync_lifecycle_label()

	def _sync_lifecycle_label(self):
		"""Keep lifecycle_state_label in sync with the numeric lifecycle_state."""
		try:
			state_int = int(self.lifecycle_state) if self.lifecycle_state is not None else 0
		except (TypeError, ValueError):
			state_int = 0
		label = LIFECYCLE_STATE_LABELS.get(state_int)
		if label is None:
			frappe.throw(
				f"Invalid lifecycle_state={state_int}. Must be 0..9 — see Sensor Configuration docs."
			)
		self.lifecycle_state_label = label

	def validate(self):
		self._validate_lifecycle_transition()

	def _validate_lifecycle_transition(self):
		"""Block illegal state transitions. Reverse transitions allowed but require e-sig record."""
		if self.is_new():
			return
		try:
			old = self.get_doc_before_save()
		except Exception:
			old = None
		if not old:
			return
		try:
			old_state = int(old.lifecycle_state) if old.lifecycle_state is not None else 0
			new_state = int(self.lifecycle_state) if self.lifecycle_state is not None else 0
		except (TypeError, ValueError):
			return
		if old_state == new_state:
			return
		transition = (old_state, new_state)
		if transition in ALLOWED_FORWARD or transition in ALLOWED_REVERSE:
			# Demotion from Certified should bump qualification_cycle_number
			if old_state == 6 and new_state < 6:
				self.qualification_cycle_number = (self.qualification_cycle_number or 0) + 1
			return
		frappe.throw(
			f"Lifecycle transition {old_state} ({LIFECYCLE_STATE_LABELS.get(old_state)}) "
			f"→ {new_state} ({LIFECYCLE_STATE_LABELS.get(new_state)}) is not permitted. "
			f"See ALLOWED_FORWARD / ALLOWED_REVERSE in sensor_configuration.py."
		)
