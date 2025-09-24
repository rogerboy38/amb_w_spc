# Server-side Python validation for SPC DocTypes
# Add these methods to your custom app's hooks.py or create custom methods

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
import statistics
import math

class SPCValidationError(frappe.ValidationError):
    pass

def validate_spc_parameter_master(doc, method):
    """Server-side validation for SPC Parameter Master"""
    
    # Validate parameter code format
    if doc.parameter_code:
        import re
        if not re.match(r'^[A-Za-z0-9_-]+$', doc.parameter_code):
            frappe.throw(_("Parameter Code must contain only letters, numbers, hyphens, and underscores"),
                        SPCValidationError)
    
    # Check for duplicate parameter codes within company
    existing = frappe.get_all("SPC Parameter Master", 
                             filters={
                                 "parameter_code": doc.parameter_code,
                                 "company": doc.company,
                                 "name": ["!=", doc.name]
                             })
    if existing:
        frappe.throw(_("Parameter Code {0} already exists for company {1}").format(
            doc.parameter_code, doc.company), SPCValidationError)
    
    # Validate precision for numeric types
    if doc.data_type == "Numeric":
        if not doc.default_precision or doc.default_precision < 0:
            frappe.throw(_("Default Precision must be specified and >= 0 for Numeric data types"),
                        SPCValidationError)

def validate_spc_data_point(doc, method):
    """Server-side validation for SPC Data Point"""
    
    # Validate measurement value
    if doc.measured_value is None:
        frappe.throw(_("Measured Value is required"), SPCValidationError)
    
    # Validate control limits
    if doc.upper_control_limit and doc.lower_control_limit:
        if flt(doc.upper_control_limit) <= flt(doc.lower_control_limit):
            frappe.throw(_("Upper Control Limit must be greater than Lower Control Limit"),
                        SPCValidationError)
    
    # Validate specification limits
    if doc.upper_spec_limit and doc.lower_spec_limit:
        if flt(doc.upper_spec_limit) <= flt(doc.lower_spec_limit):
            frappe.throw(_("Upper Specification Limit must be greater than Lower Specification Limit"),
                        SPCValidationError)
    
    # Auto-calculate statistical values
    calculate_statistical_values(doc)
    
    # Auto-validate status
    auto_validate_data_point_status(doc)
    
    # Check for alerts
    check_spc_alerts(doc)

def validate_spc_specification(doc, method):
    """Server-side validation for SPC Specification"""
    
    # Validate tolerance values
    if doc.tolerance_plus and doc.tolerance_minus:
        if flt(doc.tolerance_plus) <= 0 or flt(doc.tolerance_minus) <= 0:
            frappe.throw(_("Tolerance values must be positive"), SPCValidationError)
    
    # Calculate specification limits from target and tolerance
    if doc.target_value and doc.tolerance_plus and doc.tolerance_minus:
        doc.upper_spec_limit = flt(doc.target_value) + flt(doc.tolerance_plus)
        doc.lower_spec_limit = flt(doc.target_value) - flt(doc.tolerance_minus)
    
    # Validate specification limits
    if doc.upper_spec_limit and doc.lower_spec_limit:
        if flt(doc.upper_spec_limit) <= flt(doc.lower_spec_limit):
            frappe.throw(_("Upper Specification Limit must be greater than Lower Specification Limit"),
                        SPCValidationError)
    
    # Validate control limits are within spec limits
    if doc.upper_control_limit and doc.upper_spec_limit:
        if flt(doc.upper_control_limit) > flt(doc.upper_spec_limit):
            frappe.throw(_("Upper Control Limit cannot exceed Upper Specification Limit"),
                        SPCValidationError)
    
    if doc.lower_control_limit and doc.lower_spec_limit:
        if flt(doc.lower_control_limit) < flt(doc.lower_spec_limit):
            frappe.throw(_("Lower Control Limit cannot be below Lower Specification Limit"),
                        SPCValidationError)
    
    # Validate date ranges
    if doc.valid_from and doc.valid_to:
        if getdate(doc.valid_to) < getdate(doc.valid_from):
            frappe.throw(_("Valid To date cannot be earlier than Valid From date"),
                        SPCValidationError)
    
    # Check for overlapping active specifications
    check_overlapping_specifications(doc)

def validate_spc_control_chart(doc, method):
    """Server-side validation for SPC Control Chart"""
    
    # Validate sample size
    if doc.sample_size and doc.sample_size <= 0:
        frappe.throw(_("Sample Size must be greater than 0"), SPCValidationError)
    
    # Validate sigma level
    if doc.sigma_level and (doc.sigma_level <= 0 or doc.sigma_level > 6):
        frappe.throw(_("Sigma Level must be between 0 and 6"), SPCValidationError)
    
    # Validate data points to display
    if doc.data_points_to_display and doc.data_points_to_display <= 0:
        frappe.throw(_("Data Points to Display must be greater than 0"), SPCValidationError)
    
    # Validate refresh interval
    if doc.auto_refresh and doc.refresh_interval and doc.refresh_interval <= 0:
        frappe.throw(_("Refresh Interval must be greater than 0"), SPCValidationError)

def calculate_statistical_values(doc):
    """Calculate statistical values for SPC Data Point"""
    
    if not doc.parameter:
        return
    
    # Get recent data points for the same parameter (last 30 points)
    recent_points = frappe.get_all("SPC Data Point",
                                  filters={
                                      "parameter": doc.parameter,
                                      "status": "Valid",
                                      "name": ["!=", doc.name or ""]
                                  },
                                  fields=["measured_value", "timestamp"],
                                  order_by="timestamp desc",
                                  limit=29)  # Get 29 + current = 30 total
    
    values = [flt(point.measured_value) for point in recent_points]
    values.append(flt(doc.measured_value))  # Add current value
    
    if len(values) >= 2:
        # Calculate X-bar (mean)
        doc.x_bar = statistics.mean(values)
        
        # Calculate Range (if we have subgroups)
        if len(values) >= 5:
            # Take last 5 values as subgroup
            subgroup = values[-5:]
            doc.range_value = max(subgroup) - min(subgroup)
        
        # Calculate Moving Range
        if len(values) >= 2:
            moving_ranges = [abs(values[i] - values[i-1]) for i in range(1, len(values))]
            doc.moving_range = moving_ranges[-1] if moving_ranges else 0

def auto_validate_data_point_status(doc):
    """Auto-validate SPC Data Point status based on limits"""
    
    status = "Valid"
    notes = []
    
    measured_val = flt(doc.measured_value)
    
    # Check control limits
    if doc.upper_control_limit and measured_val > flt(doc.upper_control_limit):
        status = "Invalid"
        notes.append("Above Upper Control Limit")
    
    if doc.lower_control_limit and measured_val < flt(doc.lower_control_limit):
        status = "Invalid"
        notes.append("Below Lower Control Limit")
    
    # Check specification limits
    if doc.upper_spec_limit and measured_val > flt(doc.upper_spec_limit):
        status = "Invalid"
        notes.append("Above Upper Specification Limit")
    
    if doc.lower_spec_limit and measured_val < flt(doc.lower_spec_limit):
        status = "Invalid"
        notes.append("Below Lower Specification Limit")
    
    # Update status and notes
    doc.status = status
    if notes and status == "Invalid":
        doc.validation_notes = ", ".join(notes)

def check_overlapping_specifications(doc):
    """Check for overlapping active specifications"""
    
    if doc.status != "Active":
        return
    
    # Find overlapping specifications
    filters = {
        "parameter": doc.parameter,
        "status": "Active",
        "name": ["!=", doc.name or ""]
    }
    
    if doc.valid_from:
        filters["valid_from"] = ["<=", doc.valid_to or "2099-12-31"]
    
    if doc.valid_to:
        filters["valid_to"] = [">=", doc.valid_from]
    
    overlapping = frappe.get_all("SPC Specification", filters=filters)
    
    if overlapping:
        frappe.throw(_("An active specification already exists for parameter {0} in the specified date range").format(
            doc.parameter), SPCValidationError)

def check_spc_alerts(doc):
    """Check if SPC alerts need to be triggered"""
    
    if doc.status != "Invalid":
        return
    
    # Get control charts for this parameter
    charts = frappe.get_all("SPC Control Chart",
                           filters={
                               "parameter": doc.parameter,
                               "status": "Active",
                               "enable_alerts": 1
                           },
                           fields=["name", "chart_name"])
    
    # For each chart, check alert conditions and send notifications
    for chart in charts:
        send_spc_alert(chart.name, doc)

def send_spc_alert(chart_name, data_point):
    """Send SPC alert notifications"""
    
    # Get alert recipients for the chart
    chart_doc = frappe.get_doc("SPC Control Chart", chart_name)
    
    if not chart_doc.alert_recipients:
        return
    
    # Prepare alert message
    subject = f"SPC Alert: {data_point.parameter} Out of Control"
    message = f"""
    SPC Alert Notification
    
    Parameter: {data_point.parameter}
    Measured Value: {data_point.measured_value}
    Timestamp: {data_point.timestamp}
    Status: {data_point.status}
    Notes: {data_point.validation_notes or 'N/A'}
    Workstation: {data_point.workstation or 'N/A'}
    Batch: {data_point.batch_number or 'N/A'}
    Operator: {data_point.operator or 'N/A'}
    
    Please investigate and take corrective action.
    """
    
    # Send notifications to recipients
    for recipient in chart_doc.alert_recipients:
        if recipient.alert_method in ["Email", "All Methods"]:
            frappe.sendmail(
                recipients=[recipient.email or recipient.user],
                subject=subject,
                message=message,
                reference_doctype="SPC Data Point",
                reference_name=data_point.name
            )
        
        # Add notification to ERPNext notification system
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": subject,
            "email_content": message,
            "for_user": recipient.user,
            "type": "Alert",
            "document_type": "SPC Data Point",
            "document_name": data_point.name
        }).insert(ignore_permissions=True)

# Hooks to add to your app's hooks.py file:
"""
doc_events = {
    "SPC Parameter Master": {
        "validate": "your_app.spc_validations.validate_spc_parameter_master"
    },
    "SPC Data Point": {
        "validate": "your_app.spc_validations.validate_spc_data_point"
    },
    "SPC Specification": {
        "validate": "your_app.spc_validations.validate_spc_specification"
    },
    "SPC Control Chart": {
        "validate": "your_app.spc_validations.validate_spc_control_chart"
    }
}
"""