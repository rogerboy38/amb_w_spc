# Copyright (c) 2026, AMB-Wellness and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class SensorSkillCalibrationEvent(Document):
	"""ISO/IEC 17025 §7.8 compliant calibration event record.

	Child of Sensor Configuration. Captures As-Found / As-Left measurements
	against a traceable reference standard, environmental conditions, and
	pass/fail determination per the configured decision rule.
	"""
	pass
