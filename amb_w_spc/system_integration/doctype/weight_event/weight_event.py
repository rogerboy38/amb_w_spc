# -*- coding: utf-8 -*-
# Copyright (c) 2026, AMB Solutions and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
import json
from frappe.model.document import Document
from frappe.utils import now, now_datetime
from frappe import _


class WeightEvent(Document):
    """Weight Event Document for capturing scale weight measurements.

    This doctype implements the Weight Event Contract for IoT scale integration
    with ERPNext manufacturing workflows.
    """

    def before_insert(self):
        """Set default values before insert."""
        if not self.event_timestamp:
            self.event_timestamp = now()

        if not self.event_id:
            self.event_id = self.name

        # Calculate net weight
        if self.gross_weight and self.tara_weight:
            self.net_weight = self.gross_weight - self.tara_weight
        elif self.gross_weight:
            self.net_weight = self.gross_weight

    def validate(self):
        """Validate weight event data."""
        self.validate_weight_range()
        self.validate_barrel_format()
        self.validate_quality()

    def validate_weight_range(self):
        """Check if weight is within device limits."""
        if not self.gross_weight or self.gross_weight <= 0:
            frappe.throw(_("Gross weight must be positive"))

        # Default limits
        min_weight = 0.5
        max_weight = 500

        # Try to get limits from device
        if self.device_id:
            try:
                device = frappe.get_doc("Sensor Configuration", self.device_id)
                min_weight = getattr(device, "min_weight", min_weight)
                max_weight = getattr(device, "max_weight", max_weight)
            except:
                pass

        if self.gross_weight < min_weight or self.gross_weight > max_weight:
            self.weight_range_status = "Alarm"
            frappe.msgprint(
                _("Weight {0} is outside device limits ({1} - {2} kg)").format(
                    self.gross_weight, min_weight, max_weight
                ),
                alert=True
            )
        else:
            self.weight_range_status = "Normal"

    def validate_barrel_format(self):
        """Validate barrel serial format."""
        import re

        if self.barrel_serial:
            pattern = r'^[A-Z]{3}[0-9]+-[0-9]+-C[0-9]+-[0-9]+$'
            if not re.match(pattern, self.barrel_serial.upper()):
                frappe.throw(
                    _("Invalid barrel serial format. Expected: JAR0001261-1-C1-001"),
                    frappe.ValidationError
                )

    def validate_quality(self):
        """Determine quality status based on limits."""
        if self.upper_limit and self.lower_limit and self.net_weight:
            if self.net_weight > self.upper_limit or self.net_weight < self.lower_limit:
                self.within_spec = 0
                self.quality_status = "Fail"

                # Calculate deviation
                target = (self.upper_limit + self.lower_limit) / 2
                if target > 0:
                    self.deviation_percentage = (
                        (self.net_weight - target) / target * 100
                    )
            else:
                self.within_spec = 1
                self.quality_status = "Pass"
                self.deviation_percentage = 0

    def after_insert(self):
        """Actions after successful insert."""
        # Create Real Time Process Data record
        self.create_rtd_record()

        # Try to sync to ERPNext
        self.sync_to_erpnext()

    def create_rtd_record(self):
        """Create a Real Time Process Data record for SPC tracking."""
        try:
            rtd_doc = frappe.get_doc({
                "doctype": "Real Time Process Data",
                "timestamp": self.event_timestamp,
                "station": self.station,
                "sensor": self.device_id,
                "parameter_name": "weight",
                "value": self.net_weight or self.gross_weight,
                "unit_of_measure": self.weight_unit or "kg",
                "data_type": "Float",
                "status": self.weight_range_status,
                "upper_limit": self.upper_limit,
                "lower_limit": self.lower_limit,
                "work_order": self.work_order,
                "item": self.production_item,
                "batch_no": self.batch_no,
                "operation": self.operation,
                "control_chart_point": 1
            })
            rtd_doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Failed to create RTD record: {e}", "Weight Event RTD")

    def sync_to_erpnext(self):
        """Sync weight event to ERPNext batch/container."""
        try:
            if self.sync_status == "Synced":
                return

            # Try to sync to Container Barrels via amb_w_tds
            if self.barrel_serial:
                try:
                    result = frappe.call(
                        'amb_w_tds.api.batch_api.receive_weight',
                        barrel_serial=self.barrel_serial,
                        gross_weight=self.gross_weight,
                        device_id=self.device_id,
                        tara_weight=self.tara_weight
                    )
                    self.sync_status = "Synced"
                    self.synced_to = "amb_w_tds"
                    self.save(ignore_permissions=True)
                    frappe.db.commit()
                except Exception as e:
                    self.sync_status = "Failed"
                    self.sync_error = str(e)
                    self.save(ignore_permissions=True)
                    frappe.db.commit()
            else:
                self.sync_status = "Skipped"
                self.sync_error = "No barrel serial"
                self.save(ignore_permissions=True)
                frappe.db.commit()

        except Exception as e:
            frappe.log_error(f"Sync failed: {e}", "Weight Event Sync")


@frappe.whitelist(allow_guest=True)
def receive_weight_event(**kwargs):
    """API endpoint to receive weight events from IoT devices.

    This is the main entry point for the Weight Event Contract.

    Args (via kwargs or JSON body):
        barrel_serial (str): Barrel serial number
        gross_weight (float): Weight in kg
        device_id (str): Device identifier
        tara_weight (float, optional): Tara weight
        work_order (str, optional): Work Order reference
        batch_no (str, optional): Batch number
        operation (str, optional): Operation name
        station (str, optional): Manufacturing station
        event_timestamp (str, optional): ISO timestamp

    Returns:
        dict: Status with event details
    """
    # Get data from kwargs or request
    data = frappe.request.data if hasattr(frappe, 'request') else kwargs

    if isinstance(data, (bytes, str)):
        try:
            data = json.loads(data)
        except:
            data = kwargs

    # Extract fields
    barrel_serial = data.get('barrel_serial', '')
    gross_weight = data.get('gross_weight', 0)
    device_id = data.get('device_id', 'UNKNOWN')
    tara_weight = data.get('tara_weight')
    work_order = data.get('work_order')
    batch_no = data.get('batch_no')
    operation = data.get('operation')
    station = data.get('station')
    event_timestamp = data.get('event_timestamp')

    # Validate required fields
    if not barrel_serial:
        return {
            'status': 'error',
            'message': 'barrel_serial is required'
        }

    if not gross_weight or float(gross_weight) <= 0:
        return {
            'status': 'error',
            'message': 'gross_weight must be positive'
        }

    try:
        # Create Weight Event document
        doc = frappe.get_doc({
            'doctype': 'Weight Event',
            'event_type': 'Weight Capture',
            'event_timestamp': event_timestamp or now(),
            'device_id': device_id,
            'station': station,
            'barrel_serial': barrel_serial.upper(),
            'gross_weight': float(gross_weight),
            'tara_weight': float(tara_weight) if tara_weight else None,
            'work_order': work_order,
            'batch_no': batch_no,
            'operation': operation,
            'weight_unit': 'kg',
            'sync_status': 'Pending',
            'raw_payload': json.dumps(data, indent=2)
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            'status': 'success',
            'event_id': doc.name,
            'barrel_serial': doc.barrel_serial,
            'weight': doc.net_weight or doc.gross_weight,
            'quality_status': doc.quality_status,
            'message': 'Weight event recorded'
        }

    except frappe.ValidationError as e:
        return {
            'status': 'error',
            'message': str(e)
        }
    except Exception as e:
        frappe.log_error(f"receive_weight_event error: {e}", "Weight Event API")
        return {
            'status': 'error',
            'message': 'Internal error processing weight event'
        }


@frappe.whitelist()
def bulk_receive_weight_events(events):
    """Receive multiple weight events in bulk.

    Args:
        events: List of weight event dictionaries

    Returns:
        dict: Summary of processed events
    """
    if isinstance(events, str):
        events = json.loads(events)

    results = {
        'total': len(events),
        'success': 0,
        'failed': 0,
        'errors': []
    }

    for i, event in enumerate(events):
        try:
            result = receive_weight_event(**event)
            if result.get('status') == 'success':
                results['success'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({
                    'index': i,
                    'error': result.get('message')
                })
        except Exception as e:
            results['failed'] += 1
            results['errors'].append({
                'index': i,
                'error': str(e)
            })

    return results


@frappe.whitelist()
def get_weight_events_by_barrel(barrel_serial, limit=50):
    """Get weight event history for a barrel.

    Args:
        barrel_serial (str): Barrel serial
        limit (int): Maximum records

    Returns:
        list: Weight events
    """
    return frappe.get_all(
        'Weight Event',
        filters={'barrel_serial': barrel_serial},
        fields=['name', 'event_timestamp', 'gross_weight', 'tara_weight',
                'net_weight', 'quality_status', 'work_order', 'batch_no'],
        order_by='event_timestamp desc',
        limit=limit
    )


@frappe.whitelist()
def get_weight_stats_by_batch(batch_no):
    """Get weight statistics for a batch.

    Args:
        batch_no (str): Batch number

    Returns:
        dict: Statistics
    """
    events = frappe.get_all(
        'Weight Event',
        filters={'batch_no': batch_no, 'sync_status': 'Synced'},
        fields=['net_weight', 'within_spec', 'quality_status']
    )

    if not events:
        return None

    weights = [e.net_weight for e in events if e.net_weight]
    total = len(weights)
    passed = len([e for e in events if e.within_spec])
    failed = total - passed

    return {
        'batch_no': batch_no,
        'total_events': total,
        'total_weight': sum(weights),
        'avg_weight': sum(weights) / total if total else 0,
        'min_weight': min(weights) if weights else 0,
        'max_weight': max(weights) if weights else 0,
        'pass_count': passed,
        'fail_count': failed,
        'pass_rate': (passed / total * 100) if total else 0
    }
