# -*- coding: utf-8 -*-
"""
PH13.2.0 Hardening - Idempotent Sensor Skill Patch
===================================================
This patch replaces raw SQL INSERT with Frappe ORM for:
- scale_plant: Plant Production Scale (max 500kg, ModbusRTU)
- scale_lab: Laboratory Precision Scale (max 30kg, SerialCommand)

This approach is IDEMPOTENT:
- If record exists with matching values: No change
- If record exists with different values: Update to match
- If record doesn't exist: Create new record

Run: bench --site v2.sysmayal.cloud execute amb_w_spc.patches.v15.create_sensor_skills_idempotent.execute
"""
import frappe
from frappe import _


SKILLS = [
    {
        'name': 'scale_plant',
        'skill_id': 'scale_plant',
        'skill_name': 'Plant Production Scale',
        'sensor_type': 'Scale',
        'version': '1.0.0',
        'min_value': 0,
        'max_value': 500,
        'unit_of_measure': 'kg',
        'port': '/dev/ttyUSB0',
        'baud_rate': 9600,
        'python_config': '{"driver":"ModbusRTU","slave_id":1,"scale_factor":0.01}',
        'wiring_instructions': 'RS485 to USB converter. Connect A+ to Data+, B- to Data-. Use 120ohm termination if cable >100m.',
        'calibration_procedure': '1. Zero the scale with no load. 2. Place certified 100kg weight. 3. Adjust scale_factor until reading matches. 4. Verify with 50kg and 200kg test weights.',
        'enabled': 1,
    },
    {
        'name': 'scale_lab',
        'skill_id': 'scale_lab',
        'skill_name': 'Laboratory Precision Scale',
        'sensor_type': 'Scale',
        'version': '1.0.0',
        'min_value': 0,
        'max_value': 30,
        'unit_of_measure': 'kg',
        'port': '/dev/ttyUSB1',
        'baud_rate': 115200,
        'python_config': '{"driver":"SerialCommand","command":"W","response_format":"DECIMAL","timeout":5}',
        'wiring_instructions': 'USB-Serial to precision balance. Connect TX to RX, RX to TX. Verify COM port in Device Manager.',
        'calibration_procedure': '1. Warm up balance for 30 minutes. 2. Zero the balance. 3. Place 20kg certified weight. 4. Use calibration function per manufacturer instructions. 5. Verify with 10kg test weight.',
        'enabled': 1,
    },
]


def execute():
    """Idempotent Sensor Skill creation/update using Frappe ORM."""
    print("=" * 60)
    print("PH13.2.0 Hardening - Idempotent Sensor Skill Patch")
    print("=" * 60)

    # Check if Sensor Skill DocType exists
    if not frappe.db.exists("DocType", "Sensor Skill"):
        print("ERROR: Sensor Skill DocType not found!")
        print("Please run 'bench install-app amb_w_spc --force' first")
        return

    created = 0
    updated = 0
    unchanged = 0

    for data in SKILLS:
        name = data['name']

        if frappe.db.exists('Sensor Skill', name):
            # Record exists - check if update needed
            doc = frappe.get_doc('Sensor Skill', name)
            changed = False

            for k, v in data.items():
                if k == 'name':
                    continue  # Skip primary key
                if doc.get(k) != v:
                    doc.set(k, v)
                    changed = True

            if changed:
                doc.save(ignore_permissions=True)
                frappe.db.commit()
                updated += 1
                print(f"  UPDATED: {name}")
            else:
                unchanged += 1
                print(f"  UNCHANGED: {name}")
        else:
            # Create new record using Frappe ORM
            try:
                doc = frappe.get_doc({'doctype': 'Sensor Skill', **data})
                doc.insert(ignore_permissions=True)
                frappe.db.commit()
                created += 1
                print(f"  CREATED: {name}")
            except Exception as e:
                print(f"  ERROR: Failed to create {name}: {e}")

    print("-" * 60)
    print(f"Summary: Created={created}, Updated={updated}, Unchanged={unchanged}")
    print("=" * 60)

    # Verify
    print("\nVerification:")
    for name in ['scale_plant', 'scale_lab']:
        if frappe.db.exists('Sensor Skill', name):
            doc = frappe.get_doc('Sensor Skill', name)
            print(f"  OK: {name} | {doc.sensor_type} | {doc.port} | {doc.baud_rate} | enabled={doc.enabled}")
        else:
            print(f"  FAIL: {name} not found!")


if __name__ == "__main__":
    execute()
