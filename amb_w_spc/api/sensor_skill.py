# -*- coding: utf-8 -*-
"""
PH13.2.0 Sensor Skill API
=========================
API endpoint for receiving weight events from raven_ai_agent (V12.7.0).

This module provides:
- receive_weight_event(): Direct Python function for weight event processing
- Whitelisted REST endpoint for HTTP POST requests
"""
import frappe
from frappe import _
from frappe.utils import now_datetime, now, get_datetime
import json
from datetime import datetime


@frappe.whitelist(allow_guest=True)
def receive_weight_event(
    device_id: str = None,
    mode: str = None,
    batch_name: str = None,
    barrel_serial: str = None,
    gross_weight: float = None,
    tara_weight: float = None,
    net_weight: float = None,
    unit: str = "kg",
    tolerance_profile: str = None,
    timestamp: str = None,
    operator_id: str = None
) -> dict:
    """
    Receive and process weight event from scale device.
    FIX: BUG 97 - Now updates Batch AMB container_barrels child table.
    """
    try:
        # STEP 1: Validate required fields
        validation_errors = []
        if not device_id:
            validation_errors.append("device_id is required")
        if not barrel_serial:
            validation_errors.append("barrel_serial is required")
        if gross_weight is None:
            validation_errors.append("gross_weight is required")
        if not batch_name:
            validation_errors.append("batch_name is required")

        if validation_errors:
            return {
                "status": "error",
                "code": "missing_fields",
                "message": "; ".join(validation_errors),
                "context": {"missing_fields": validation_errors}
            }

        # STEP 2: Parse and validate weights
        gross_weight = float(gross_weight)
        tara_weight = float(tara_weight) if tara_weight else 0.0
        calculated_net = gross_weight - tara_weight
        
        if net_weight is None:
            net_weight = calculated_net
        else:
            net_weight = float(net_weight)

        # Validate net_weight consistency (10g tolerance)
        if abs(net_weight - calculated_net) > 0.01:
            return {
                "status": "error",
                "code": "validation_failed",
                "message": f"net_weight mismatch: expected {calculated_net}, got {net_weight}",
                "context": {
                    "gross_weight": gross_weight,
                    "tara_weight": tara_weight,
                    "calculated_net": calculated_net,
                    "provided_net": net_weight
                }
            }

        # STEP 3: Parse timestamp
        if timestamp:
            try:
                ts = timestamp.replace('Z', '').replace('T', ' ').split('.')[0]
                event_time = ts
            except Exception:
                event_time = now()
        else:
            event_time = now()

        # STEP 4: Check if Batch AMB exists
        if batch_name and not frappe.db.exists("Batch AMB", batch_name):
            return {
                "status": "error",
                "code": "batch_not_found",
                "message": f"Batch AMB '{batch_name}' not found",
                "context": {"batch_name": batch_name}
            }

        # STEP 5: Update Container Barrels child row (BUG 97 FIX)
        child_row_name = None
        if batch_name:
            batch_doc = frappe.get_doc("Batch AMB", batch_name)
            if hasattr(batch_doc, 'container_barrels'):
                for row in batch_doc.container_barrels:
                    if (row.barrel_serial_number or "").strip() == barrel_serial:
                        child_row_name = row.name
                        break
            
            if not child_row_name:
                return {
                    "status": "error",
                    "code": "serial_not_found",
                    "message": f"Barrel serial '{barrel_serial}' not found in Batch AMB",
                    "context": {
                        "batch_name": batch_name,
                        "barrel_serial": barrel_serial
                    }
                }
            
            # Use SQL update to bypass validation (packaging_type requirement)
            frappe.db.sql("""
                UPDATE `tabContainer Barrels`
                SET gross_weight = %s,
                    tara_weight = %s,
                    net_weight = %s,
                    weight_validated = 1,
                    scan_timestamp = %s,
                    modified = NOW()
                WHERE name = %s
            """, (gross_weight, tara_weight, net_weight, event_time, child_row_name))
            frappe.db.commit()

        # STEP 6: Map mode to valid event_type
        EVENT_TYPE_MAP = {
            "production": "Weight Capture",
            "audit": "Weight Capture",
            "keyboard": "Weight Capture",
            "sensor_skill": "Weight Capture",
            "tare": "Tare Reset",
            "calibration": "Calibration",
            "zero": "Zero Reset",
        }
        event_type = EVENT_TYPE_MAP.get(mode, "Weight Capture") if mode else "Weight Capture"

        # STEP 7: Create Weight Event document
        weight_event_id = None
        if frappe.db.exists("DocType", "Weight Event"):
            doc = frappe.get_doc({
                "doctype": "Weight Event",
                "device_id": device_id,
                "event_type": event_type,
                "batch_name": batch_name,
                "barrel_serial": barrel_serial,
                "gross_weight": gross_weight,
                "tara_weight": tara_weight,
                "net_weight": net_weight,
                "unit_of_measure": unit,
                "tolerance_profile": tolerance_profile,
                "event_timestamp": event_time,
                "operator_id": operator_id,
                "status": "Completed"
            })
            doc.insert(ignore_permissions=True)
            weight_event_id = doc.name
            frappe.db.commit()

        # STEP 8: Return structured success response
        return {
            "status": "ok",
            "code": "updated",
            "message": "Weight recorded and Batch AMB updated",
            "context": {
                "weight_event_id": weight_event_id,
                "batch_name": batch_name,
                "barrel_serial": barrel_serial,
                "gross_weight": gross_weight,
                "tara_weight": tara_weight,
                "net_weight": net_weight,
                "unit": unit,
                "timestamp": event_time,
                "operator_id": operator_id
            }
        }

    except Exception as e:
        frappe.logger().error(f"Error processing weight event: {e}")
        return {
            "status": "error",
            "code": "exception",
            "message": str(e),
            "context": {}
        }



@frappe.whitelist()
def get_sensor_skill_config(skill_id: str = "scale_plant") -> dict:
    """
    Get Sensor Skill configuration for a given skill ID.

    Args:
        skill_id: The Sensor Skill identifier (e.g., 'scale_plant', 'scale_lab')

    Returns:
        dict with skill configuration or error
    """
    try:
        if not frappe.db.exists("DocType", "Sensor Skill"):
            return {"status": "error", "message": "Sensor Skill DocType not found"}

        if not frappe.db.exists("Sensor Skill", skill_id):
            return {"status": "error", "message": f"Sensor Skill '{skill_id}' not found"}

        doc = frappe.get_doc("Sensor Skill", skill_id)

        return {
            "status": "success",
            "skill_id": doc.skill_id,
            "skill_name": doc.skill_name,
            "sensor_type": doc.sensor_type,
            "port": doc.port,
            "baud_rate": doc.baud_rate,
            "min_value": doc.min_value,
            "max_value": doc.max_value,
            "unit_of_measure": doc.unit_of_measure,
            "python_config": json.loads(doc.python_config) if doc.python_config else {},
            "enabled": doc.enabled
        }

    except Exception as e:
        frappe.logger().error(f"Error getting sensor skill config: {e}")
        return {"status": "error", "message": str(e)}
