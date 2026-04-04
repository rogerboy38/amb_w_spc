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
from frappe.utils import now_datetime, now
import json


@frappe.whitelist()
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

    Args:
        device_id: Scale device identifier (e.g., 'SCALE-L01', 'scale_plant')
        mode: Operation mode (production, audit, keyboard, etc.)
        batch_name: Batch identifier for the production batch
        barrel_serial: Serial number of the barrel/container
        gross_weight: Gross weight measurement in kg
        tara_weight: Tare weight in kg (optional)
        net_weight: Net weight (gross - tara) in kg
        unit: Unit of measurement (default: 'kg')
        tolerance_profile: Tolerance profile name (e.g., 'PLANT', 'LAB')
        timestamp: Event timestamp ISO format (optional, defaults to now)
        operator_id: Operator identifier (optional)

    Returns:
        dict with status and message
    """
    try:
        # Validate required fields
        if not device_id:
            return {"status": "error", "message": "device_id is required"}

        if gross_weight is None:
            return {"status": "error", "message": "gross_weight is required"}

        if not barrel_serial:
            return {"status": "error", "message": "barrel_serial is required"}

        # Calculate net weight if not provided
        if net_weight is None:
            net_weight = float(gross_weight) - (float(tara_weight) if tara_weight else 0)

        # Get timestamp
        event_time = timestamp if timestamp else now()

        # Create Weight Event document
        if frappe.db.exists("DocType", "Weight Event"):
            doc = frappe.get_doc({
                "doctype": "Weight Event",
                "device_id": device_id,
                "event_type": mode or "production",
                "batch_name": batch_name,
                "barrel_serial": barrel_serial,
                "gross_weight": float(gross_weight),
                "tara_weight": float(tara_weight) if tara_weight else 0,
                "net_weight": float(net_weight),
                "unit_of_measure": unit,
                "tolerance_profile": tolerance_profile,
                "event_timestamp": event_time,
                "operator_id": operator_id,
                "status": "Completed"
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()

            return {
                "status": "success",
                "message": "Weight event recorded",
                "weight_event_id": doc.name,
                "device_id": device_id,
                "barrel_serial": barrel_serial,
                "gross_weight": gross_weight,
                "net_weight": net_weight,
                "unit": unit
            }
        else:
            # Fallback: Log to console if DocType not found
            frappe.logger().info(
                f"Weight Event: device={device_id}, barrel={barrel_serial}, "
                f"weight={gross_weight}kg"
            )
            return {
                "status": "success",
                "message": "Weight event logged (DocType not found)",
                "device_id": device_id,
                "barrel_serial": barrel_serial,
                "gross_weight": gross_weight,
                "net_weight": net_weight
            }

    except Exception as e:
        frappe.logger().error(f"Error processing weight event: {e}")
        return {"status": "error", "message": str(e)}


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
