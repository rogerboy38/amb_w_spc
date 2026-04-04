# -*- coding: utf-8 -*-
"""
PH13.2.0 - Create Sensor Skill Records via Raw SQL
===================================================
Bypasses Frappe's DocType.insert() to avoid schema sync hang at 82%.

This patch creates:
- scale_plant: Plant Production Scale (max 500kg, ModbusRTU)
- scale_lab: Laboratory Precision Scale (max 30kg, SerialCommand)

Run: bench --site v2.sysmayal.cloud execute amb_w_spc.patches.v15.create_sensor_skill_records.execute
"""
import frappe
from frappe import _


def execute():
    """Create Sensor Skill records for plant and lab scales via raw SQL.

    This approach bypasses frappe.get_doc().insert() which triggers
    schema sync and hangs at 82% during install-app.
    """
    print("=" * 60)
    print("PH13.2.0 - Creating Sensor Skill Records via SQL")
    print("=" * 60)

    # Check if Sensor Skill DocType exists
    if not frappe.db.exists("DocType", "Sensor Skill"):
        print("ERROR: Sensor Skill DocType not found!")
        print("Please run 'bench install-app amb_w_spc --force' first")
        return

    # Define sensor skill records
    skills = [
        {
            "name": "scale_plant",
            "skill_id": "scale_plant",
            "skill_name": "Plant Production Scale",
            "sensor_type": "Scale",
            "version": "1.0.0",
            "min_value": 0,
            "max_value": 500,
            "unit_of_measure": "kg",
            "port": "/dev/ttyUSB0",
            "baud_rate": 9600,
            "python_config": '{"driver": "ModbusRTU", "slave_id": 1, "scale_factor": 0.01}',
            "wiring_instructions": "RS485 to USB converter. Connect A+ to Data+, B- to Data-. Use 120ohm termination if cable >100m.",
            "calibration_procedure": "1. Zero the scale with no load. 2. Place certified 100kg weight. 3. Adjust scale_factor until reading matches. 4. Verify with 50kg and 200kg test weights.",
            "enabled": 1,
        },
        {
            "name": "scale_lab",
            "skill_id": "scale_lab",
            "skill_name": "Laboratory Precision Scale",
            "sensor_type": "Scale",
            "version": "1.0.0",
            "min_value": 0,
            "max_value": 30,
            "unit_of_measure": "kg",
            "port": "/dev/ttyUSB1",
            "baud_rate": 115200,
            "python_config": '{"driver": "SerialCommand", "command": "W", "response_format": "DECIMAL", "timeout": 5}',
            "wiring_instructions": "USB-Serial to precision balance. Connect TX to RX, RX to TX. Verify COM port in Device Manager.",
            "calibration_procedure": "1. Warm up balance for 30 minutes. 2. Zero the balance. 3. Place 20kg certified weight. 4. Use calibration function per manufacturer instructions. 5. Verify with 10kg test weight.",
            "enabled": 1,
        },
    ]

    for skill in skills:
        skill_id = skill["skill_id"]

        # Check if record already exists
        exists = frappe.db.exists("Sensor Skill", skill_id)

        if exists:
            print(f"  SKIP: {skill_id} already exists")
            continue

        # Insert via raw SQL to bypass schema sync
        try:
            frappe.db.sql("""
                INSERT INTO `tabSensor Skill` (
                    name, skill_id, skill_name, sensor_type, version,
                    min_value, max_value, unit_of_measure, port, baud_rate,
                    python_config, wiring_instructions, calibration_procedure,
                    enabled, owner, modified_by, creation, modified
                ) VALUES (
                    %(name)s, %(skill_id)s, %(skill_name)s, %(sensor_type)s, %(version)s,
                    %(min_value)s, %(max_value)s, %(unit_of_measure)s, %(port)s, %(baud_rate)s,
                    %(python_config)s, %(wiring_instructions)s, %(calibration_procedure)s,
                    %(enabled)s, 'Administrator', 'Administrator', NOW(), NOW()
                )
            """, skill, auto_commit=True)

            print(f"  CREATE: {skill_id} - {skill['skill_name']}")

        except Exception as e:
            print(f"  ERROR: Failed to create {skill_id}: {e}")

    print("=" * 60)
    print("PH13.2.0 - Sensor Skill Records Complete")
    print("=" * 60)

    # Verify
    for skill_id in ["scale_plant", "scale_lab"]:
        if frappe.db.exists("Sensor Skill", skill_id):
            print(f"  OK: {skill_id}")
        else:
            print(f"  FAIL: {skill_id} not created!")


if __name__ == "__main__":
    execute()
