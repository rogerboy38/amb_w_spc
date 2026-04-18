# -*- coding: utf-8 -*-
"""
PH13.2.0 Sensor Skill API
=========================

Authoritative server-side weight ingestion for RPi / scale devices.

Design rules:
- Device is authoritative only for measured gross_weight, device_id, operator_id, timestamp, mode
- ERPNext is authoritative for locating the barrel row, resolving tara_weight, calculating net_weight,
  updating child rows, and recalculating Batch AMB totals
- batch_name is optional as a narrowing hint, not the primary lookup key
"""

import json
import frappe
from frappe import _
from frappe.utils import now, flt


def _normalize_timestamp(timestamp: str = None) -> str:
    if not timestamp:
        return now()
    try:
        return timestamp.replace("Z", "").replace("T", " ").split(".")[0]
    except Exception:
        return now()


def _resolve_event_type(mode: str = None) -> str:
    event_type_map = {
        "production": "Weight Capture",
        "audit": "Weight Capture",
        "keyboard": "Weight Capture",
        "sensor_skill": "Weight Capture",
        "scale": "Weight Capture",
        "tare": "Tare Reset",
        "calibration": "Calibration",
        "zero": "Zero Reset",
    }
    return event_type_map.get((mode or "").strip().lower(), "Weight Capture")


def _find_container_row(barrel_serial: str, batch_name: str = None) -> dict:
    rows = frappe.get_all(
        "Container Barrels",
        filters={"barrel_serial_number": barrel_serial},
        fields=[
            "name",
            "parent",
            "parenttype",
            "parentfield",
            "barrel_serial_number",
            "packaging_type",
            "tara_weight",
            "gross_weight",
            "net_weight",
            "weight_validated",
            "scan_timestamp",
        ],
        limit=20,
    )

    if batch_name:
        narrowed = [r for r in rows if r.get("parent") == batch_name]
        if narrowed:
            rows = narrowed

    if not rows:
        return None

    if len(rows) > 1:
        frappe.throw(
            _("Barrel serial {0} matched multiple container rows; please disambiguate with batch_name").format(barrel_serial)
        )

    return rows[0]


def _resolve_tara_weight(row: dict, request_tara) -> float:
    row_tara = flt(row.get("tara_weight"))
    if row_tara > 0:
        return row_tara

    packaging_type = row.get("packaging_type")
    if packaging_type:
        item_tara = flt(frappe.db.get_value("Item", packaging_type, "weightperunit"))
        if item_tara > 0:
            return item_tara

    req_tara = flt(request_tara)
    if req_tara > 0:
        return req_tara

    return 0.0


def _recalculate_container_totals(batch_name: str):
    if not batch_name or not frappe.db.exists("Batch AMB", batch_name):
        return

    batch_doc = frappe.get_doc("Batch AMB", batch_name)

    total_gross = 0.0
    total_tara = 0.0
    total_net = 0.0
    barrel_count = 0

    rows = getattr(batch_doc, "containerbarrels", None) or getattr(batch_doc, "container_barrels", None) or []

    for row in rows:
        if getattr(row, "gross_weight", None) is not None:
            total_gross += flt(row.gross_weight)
        if getattr(row, "tara_weight", None) is not None:
            total_tara += flt(row.tara_weight)
        if getattr(row, "net_weight", None) is not None:
            total_net += flt(row.net_weight)
        if (getattr(row, "barrel_serial_number", None) or "").strip():
            barrel_count += 1

    frappe.db.set_value("Batch AMB", batch_name, {
        "total_gross_weight": total_gross,
        "total_tara_weight": total_tara,
        "total_net_weight": total_net,
        "barrel_count": barrel_count,
    }, update_modified=True)


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
    operator_id: str = None,
    source: str = None,
) -> dict:
    """
    Receive and process weight event from a scale device.

    Contract:
    - barrel_serial: required
    - gross_weight: required
    - device_id: required
    - batch_name: optional hint
    - tara_weight: optional hint only; authoritative tara is resolved server-side
    - net_weight from client is ignored; server always recalculates
    """
    try:
        errors = []
        if not device_id:
            errors.append("device_id is required")
        if not barrel_serial:
            errors.append("barrel_serial is required")
        if gross_weight is None:
            errors.append("gross_weight is required")

        if errors:
            return {
                "status": "error",
                "code": "missing_fields",
                "message": "; ".join(errors),
                "context": {"missing_fields": errors},
            }

        barrel_serial = (barrel_serial or "").strip().upper()
        gross_weight = flt(gross_weight)
        event_time = _normalize_timestamp(timestamp)
        event_type = _resolve_event_type(mode)

        if gross_weight <= 0:
            return {
                "status": "error",
                "code": "invalid_weight",
                "message": "gross_weight must be greater than zero",
                "context": {"gross_weight": gross_weight},
            }

        row = _find_container_row(barrel_serial, batch_name=batch_name)
        if not row:
            return {
                "status": "error",
                "code": "serial_not_found",
                "message": f"Barrel serial '{barrel_serial}' not found in container rows",
                "context": {
                    "batch_name": batch_name,
                    "barrel_serial": barrel_serial,
                },
            }

        resolved_batch_name = row.get("parent")
        resolved_tara = _resolve_tara_weight(row, tara_weight)

        if resolved_tara <= 0:
            return {
                "status": "error",
                "code": "tara_not_resolved",
                "message": f"No valid tara weight resolved for barrel '{barrel_serial}'",
                "context": {
                    "batch_name": resolved_batch_name,
                    "barrel_serial": barrel_serial,
                    "packaging_type": row.get("packaging_type"),
                    "request_tara": tara_weight,
                },
            }

        resolved_net = flt(gross_weight) - flt(resolved_tara)
        if resolved_net <= 0:
            return {
                "status": "error",
                "code": "invalid_net_weight",
                "message": f"Net weight must be positive for barrel '{barrel_serial}'",
                "context": {
                    "gross_weight": gross_weight,
                    "tara_weight": resolved_tara,
                    "net_weight": resolved_net,
                },
            }

        frappe.db.sql("""
            UPDATE `tabContainer Barrels`
            SET gross_weight = %s,
                tara_weight = %s,
                net_weight = %s,
                weight_validated = 1,
                scan_timestamp = %s,
                modified = NOW()
            WHERE name = %s
        """, (gross_weight, resolved_tara, resolved_net, event_time, row["name"]))

        weight_event_id = None
        if frappe.db.exists("DocType", "Weight Event"):
            evt = frappe.get_doc({
                "doctype": "Weight Event",
                "device_id": device_id,
                "event_type": event_type,
                "batch_name": resolved_batch_name,
                "barrel_serial": barrel_serial,
                "gross_weight": gross_weight,
                "tara_weight": resolved_tara,
                "net_weight": resolved_net,
                "unit_of_measure": unit or "kg",
                "tolerance_profile": tolerance_profile,
                "event_timestamp": event_time,
                "operator_id": operator_id,
                "status": "Completed",
            })
            evt.insert(ignore_permissions=True)
            weight_event_id = evt.name

        _recalculate_container_totals(resolved_batch_name)
        frappe.db.commit()

        return {
                "status": "success",
                "code": "updated",
                "message": "Weight recorded and Batch AMB updated",
                "weight_event_id": weight_event_id,
                "batch_name": resolved_batch_name,
                "container_name": resolved_batch_name,
                "row_name": row["name"],
                "barrel_serial": barrel_serial,
                "gross_weight": gross_weight,
                "tara_weight": resolved_tara,
                "net_weight": resolved_net,
                "unit": unit or "kg",
                "timestamp": event_time,
                "operator_id": operator_id,
                "device_id": device_id,
                "mode": mode,
                "source": source,
                "weight_validated": 1,
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "receive_weight_event failed")
        return {
                "status": "error",
                "code": "exception",
                "message": str(e),
                "context": {},
        }


@frappe.whitelist()
def get_sensor_skill_config(skill_id: str = "scale_plant") -> dict:
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
