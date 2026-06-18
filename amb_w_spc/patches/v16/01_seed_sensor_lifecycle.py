# Copyright (c) 2026, AMB-Wellness and contributors
# PR #23 — Sensor Skill Lifecycle State Machine seed patch
#
# Seeds 4 Sensor Skill templates + 8 Sensor Configuration instances at
# lifecycle_state=1 (Provisioned). SANDBOX-FIRST: runs only when site
# matches the sandbox URL. TEST and PROD get separate manual fixture
# imports after VM3 smoke passes.
#
# Idempotent: re-runnable; updates in place if drift detected, skips if unchanged.

import frappe

SANDBOX_SITES = {"v2.sysmayal.cloud", "vm3.sysmayal.cloud"}

TEMPLATES = [
	{
		"skill_id": "scale_modbus_rtu_500kg",
		"skill_name": "Plant Fleet Scale (ModbusRTU 500kg)",
		"sensor_type": "Scale",
		"template_version": "0.1.0",
		"gamp5_category": "5",
		"template_lifecycle_state": "Released",
		"enabled": 1,
		"python_config": '{"driver":"ModbusRTU","max_kg":500,"precision_kg":0.010}',
		"wiring_instructions": "Modbus RTU over RS485, 9600 8N1, slave addr per station map.",
		"calibration_procedure": "Reference weights 0, 100, 250, 500 kg. Tolerance ±0.5 kg full scale.",
	},
	{
		"skill_id": "scale_serial_lab_30kg",
		"skill_name": "Laboratory Precision Scale (Serial 30kg)",
		"sensor_type": "Scale",
		"template_version": "0.2.0",
		"gamp5_category": "5",
		"template_lifecycle_state": "Released",
		"enabled": 1,
		"python_config": '{"driver":"SerialCommand","max_kg":30,"precision_kg":0.001}',
		"wiring_instructions": "RS232 DB9, 9600 8N1, ASCII command protocol.",
		"calibration_procedure": "Reference weights 0, 5, 15, 30 kg. Tolerance ±0.001 kg.",
	},
	{
		"skill_id": "ntc_thermistor_nano",
		"skill_name": "NTC Thermistor over Arduino Nano",
		"sensor_type": "Temperature",
		"template_version": "0.1.0",
		"gamp5_category": "5",
		"template_lifecycle_state": "Released",
		"enabled": 1,
		"python_config": '{"driver":"ArduinoSerial","format":"JSON","sensor_class":"NTC","emitted_keys":["id","s","raw","mv","n"]}',
		"wiring_instructions": "Arduino Nano on /dev/raven-port-*, 5V, 10k pull-up. JSON over serial.",
		"calibration_procedure": "Ice bath 0°C and boiling water 100°C reference points. Tolerance ±0.5°C.",
	},
	{
		"skill_id": "soil_moisture_capacitive",
		"skill_name": "Capacitive Soil Moisture Sensor",
		"sensor_type": "Humidity",
		"template_version": "0.1.0",
		"gamp5_category": "5",
		"template_lifecycle_state": "Draft",
		"enabled": 0,
		"python_config": '{"driver":"ArduinoSerial","format":"JSON","sensor_class":"SoilMoisture","emitted_keys":["id","s","sm","sd"]}',
		"wiring_instructions": "Arduino Nano on /dev/raven-port-*, 3.3V analog. Capacitive probe.",
		"calibration_procedure": "Dry soil baseline + saturated soil endpoint. Confirm raw_dry vs raw_in_water diverge by >50 counts.",
	},
]

INSTANCES = [
	# Production plant fleet — start at state=1 (Provisioned)
	{
		"sensor_id": "scale_juice",
		"sensor_name": "Juice Plant Scale",
		"template_skill_id": "scale_modbus_rtu_500kg",
		"company": "Juice",
		"sensor_type": "Scale",
		"status": "Inactive",
		"lifecycle_state": 1,
	},
	{
		"sensor_id": "scale_dry",
		"sensor_name": "Dry Plant Scale",
		"template_skill_id": "scale_modbus_rtu_500kg",
		"company": "Dry",
		"sensor_type": "Scale",
		"status": "Inactive",
		"lifecycle_state": 1,
	},
	{
		"sensor_id": "scale_mix",
		"sensor_name": "Mix Plant Scale",
		"template_skill_id": "scale_modbus_rtu_500kg",
		"company": "Mix",
		"sensor_type": "Scale",
		"status": "Inactive",
		"lifecycle_state": 1,
	},
	{
		"sensor_id": "scale_formulated",
		"sensor_name": "Formulated Plant Scale",
		"template_skill_id": "scale_modbus_rtu_500kg",
		"company": "Formulated",
		"sensor_type": "Scale",
		"status": "Inactive",
		"lifecycle_state": 1,
	},
	{
		"sensor_id": "scale_lab",
		"sensor_name": "Laboratory Precision Scale",
		"template_skill_id": "scale_serial_lab_30kg",
		"company": "Laboratory",
		"sensor_type": "Scale",
		"status": "Inactive",
		"lifecycle_state": 1,
	},
	# bot-iot-l01 dev sensors — sandbox-only, live data confirmed
	{
		"sensor_id": "dev_l01_ntc_nano_01",
		"sensor_name": "bot-iot-l01 NTC Nano #1",
		"template_skill_id": "ntc_thermistor_nano",
		"company": "AMB-Wellness",
		"sensor_type": "Temperature",
		"status": "Active",
		"lifecycle_state": 1,
		"description": "Live, /dev/raven-port-C, 8 msg/25s verified 2026-06-16.",
	},
	{
		"sensor_id": "dev_l01_ntc_nano_02",
		"sensor_name": "bot-iot-l01 NTC Nano #2",
		"template_skill_id": "ntc_thermistor_nano",
		"company": "AMB-Wellness",
		"sensor_type": "Temperature",
		"status": "Active",
		"lifecycle_state": 1,
		"description": "Live, /dev/raven-port-B, 8 msg/25s verified 2026-06-16.",
	},
	{
		"sensor_id": "dev_l01_soil",
		"sensor_name": "bot-iot-l01 Soil Moisture",
		"template_skill_id": "soil_moisture_capacitive",
		"company": "AMB-Wellness",
		"sensor_type": "Humidity",
		"status": "Maintenance",
		"lifecycle_state": 1,
		"description": "Wiring issue confirmed 2026-06-16 (cables, not hardware). Hold at Provisioned until rewired.",
	},
]


def _get_site_url():
	"""Best-effort site URL detection."""
	try:
		return frappe.local.site
	except Exception:
		return None


def _resolve_default_company():
	"""Resolve a usable Company name, preferring AMB-Wellness, then system default, then first available."""
	for candidate in ("AMB-Wellness", frappe.defaults.get_global_default("company")):
		if candidate and frappe.db.exists("Company", candidate):
			return candidate
	rows = frappe.get_all("Company", fields=["name"], limit=1)
	return rows[0].name if rows else None


def _ensure_template(t):
	"""Create or update Sensor Skill template."""
	name = t["skill_id"]
	exists = frappe.db.exists("Sensor Skill", name)
	if exists:
		doc = frappe.get_doc("Sensor Skill", name)
		dirty = False
		for k, v in t.items():
			if doc.get(k) != v:
				doc.set(k, v)
				dirty = True
		if dirty:
			doc.save(ignore_permissions=True)
			print(f"  [UPDATED] Sensor Skill: {name}")
		else:
			print(f"  [UNCHANGED] Sensor Skill: {name}")
	else:
		doc = frappe.get_doc({"doctype": "Sensor Skill", **t})
		doc.insert(ignore_permissions=True)
		print(f"  [CREATED] Sensor Skill: {name}")


def _ensure_instance(i, fallback_company):
	"""Create or update Sensor Configuration instance."""
	name = i["sensor_id"]
	payload = dict(i)
	template_id = payload.pop("template_skill_id", None)
	# Resolve Company link with fallback
	if not frappe.db.exists("Company", payload.get("company", "")):
		print(f"  [WARN] Company '{payload.get('company')}' missing — falling back to '{fallback_company}'")
		payload["company"] = fallback_company

	exists = frappe.db.exists("Sensor Configuration", name)
	if exists:
		doc = frappe.get_doc("Sensor Configuration", name)
		dirty = False
		for k, v in payload.items():
			if doc.get(k) != v:
				doc.set(k, v)
				dirty = True
		if dirty:
			doc.save(ignore_permissions=True)
			print(f"  [UPDATED] Sensor Configuration: {name} (template={template_id}, state={payload.get('lifecycle_state')})")
		else:
			print(f"  [UNCHANGED] Sensor Configuration: {name}")
	else:
		doc = frappe.get_doc({"doctype": "Sensor Configuration", **payload})
		doc.insert(ignore_permissions=True)
		print(f"  [CREATED] Sensor Configuration: {name} (template={template_id}, state={payload.get('lifecycle_state')})")


def execute():
	site = _get_site_url()
	print(f"\n=== PR #23 lifecycle seed — site: {site} ===")

	if site not in SANDBOX_SITES:
		print(f"  [SKIP] Site '{site}' is not in SANDBOX_SITES {SANDBOX_SITES}.")
		print(f"  [SKIP] TEST and PROD seeds run manually after sandbox smoke passes.")
		return

	fallback_company = _resolve_default_company()
	if not fallback_company:
		print("  [ABORT] No Company exists on this site — create at least one Company first.")
		return
	print(f"  Fallback Company: {fallback_company}")

	print("\n  --- Templates ---")
	for t in TEMPLATES:
		_ensure_template(t)

	print("\n  --- Instances ---")
	for i in INSTANCES:
		_ensure_instance(i, fallback_company)

	frappe.db.commit()
	print("\n=== Lifecycle seed complete ===\n")
