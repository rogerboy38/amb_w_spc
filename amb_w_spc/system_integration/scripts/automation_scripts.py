# -*- coding: utf-8 -*-
# Custom Automation Scripts for SPC ERPNext System
# Copyright (c) 2025 SPC System

import frappe
from frappe import _
from frappe.utils import flt, cint, now_datetime, add_days, get_datetime
import statistics
import json
from datetime import datetime, timedelta

# =============================================================================
# SPC ALERT AUTOMATION
# =============================================================================

@frappe.whitelist()
def auto_create_spc_alert(data_point_name):
    """Automatically create SPC Alert when data point exceeds limits"""
    
    data_point = frappe.get_doc("SPC Data Point", data_point_name)
    
    if not data_point.specification:
        return None
    
    spec = frappe.get_doc("SPC Specification", data_point.specification)
    value = flt(data_point.measurement_value)
    alert_type = None
    severity = None
    
    # Determine alert type and severity
    if spec.lower_critical_limit and value < flt(spec.lower_critical_limit):
        alert_type = "Critical Low"
        severity = "Critical"
    elif spec.upper_critical_limit and value > flt(spec.upper_critical_limit):
        alert_type = "Critical High"
        severity = "Critical"
    elif spec.lower_warning_limit and value < flt(spec.lower_warning_limit):
        alert_type = "Warning Low"
        severity = "Warning"
    elif spec.upper_warning_limit and value > flt(spec.upper_warning_limit):
        alert_type = "Warning High"
        severity = "Warning"
    
    if alert_type:
        # Create SPC Alert
        alert = frappe.get_doc({
            "doctype": "SPC Alert",
            "data_point": data_point_name,
            "parameter": data_point.parameter,
            "workstation": data_point.workstation,
            "plant": data_point.plant,
            "alert_type": alert_type,
            "severity": severity,
            "measurement_value": value,
            "limit_violated": get_violated_limit(spec, value, alert_type),
            "deviation_amount": abs(value - flt(spec.target_value)) if spec.target_value else 0,
            "status": "Open",
            "priority": "High" if severity == "Critical" else "Medium",
            "description": f"Parameter {data_point.parameter} exceeded {alert_type.lower()} limit. Value: {value}"
        })
        
        alert.insert(ignore_permissions=True)
        
        # Send notifications
        send_alert_notifications(alert.name)
        
        # Create deviation for critical alerts
        if severity == "Critical":
            create_deviation_from_alert(alert.name)
        
        return alert.name
    
    return None

def get_violated_limit(spec, value, alert_type):
    """Get the specific limit that was violated"""
    
    if alert_type == "Critical Low":
        return flt(spec.lower_critical_limit)
    elif alert_type == "Critical High":
        return flt(spec.upper_critical_limit)
    elif alert_type == "Warning Low":
        return flt(spec.lower_warning_limit)
    elif alert_type == "Warning High":
        return flt(spec.upper_warning_limit)
    
    return 0

def send_alert_notifications(alert_name):
    """Send email and system notifications for SPC alerts"""
    
    alert = frappe.get_doc("SPC Alert", alert_name)
    
    # Get alert recipients
    recipients = frappe.get_all("SPC Alert Recipient",
        filters={
            "parent": alert_name,
            "parenttype": "SPC Alert"
        },
        fields=["recipient", "notification_type"]
    )
    
    if not recipients:
        # Get default recipients based on plant and severity
        recipients = get_default_alert_recipients(alert.plant, alert.severity)
    
    for recipient in recipients:
        if recipient.get("notification_type") == "Email" or not recipient.get("notification_type"):
            send_email_notification(alert, recipient.get("recipient"))
        
        if recipient.get("notification_type") == "System":
            send_system_notification(alert, recipient.get("recipient"))

def get_default_alert_recipients(plant, severity):
    """Get default recipients based on plant and alert severity"""
    
    # Get quality users for this plant
    plant_users = frappe.get_all("User Permission",
        filters={
            "allow": "Plant Configuration",
            "for_value": plant
        },
        fields=["user"]
    )
    
    recipients = []
    for user in plant_users:
        user_roles = frappe.get_roles(user.user)
        if "Quality User" in user_roles or "Inspector User" in user_roles:
            recipients.append({"recipient": user.user, "notification_type": "Email"})
    
    return recipients

# =============================================================================
# STATISTICAL CALCULATIONS
# =============================================================================

@frappe.whitelist()
def calculate_xbar_r_values(parameter, workstation, subgroup_size=5):
    """Calculate X-bar and R chart values"""
    
    # Get recent data points
    data_points = frappe.get_all("SPC Data Point",
        filters={
            "parameter": parameter,
            "workstation": workstation
        },
        fields=["measurement_value", "measurement_datetime"],
        order_by="measurement_datetime desc",
        limit=100
    )
    
    if len(data_points) < subgroup_size:
        frappe.throw(_("Insufficient data for X-bar R chart. Need at least {0} points").format(subgroup_size))
    
    # Group data into subgroups
    subgroups = []
    for i in range(0, len(data_points), subgroup_size):
        subgroup = data_points[i:i+subgroup_size]
        if len(subgroup) == subgroup_size:
            values = [flt(dp.measurement_value) for dp in subgroup]
            subgroups.append({
                "values": values,
                "xbar": statistics.mean(values),
                "range": max(values) - min(values),
                "datetime": subgroup[0].measurement_datetime
            })
    
    if not subgroups:
        return {"error": "No complete subgroups available"}
    
    # Calculate control limits
    grand_mean = statistics.mean([sg["xbar"] for sg in subgroups])
    avg_range = statistics.mean([sg["range"] for sg in subgroups])
    
    # Control limit constants for subgroup size
    constants = get_control_chart_constants(subgroup_size)
    
    # X-bar chart limits
    xbar_ucl = grand_mean + (constants["A2"] * avg_range)
    xbar_lcl = grand_mean - (constants["A2"] * avg_range)
    
    # R chart limits
    r_ucl = constants["D4"] * avg_range
    r_lcl = constants["D3"] * avg_range
    
    return {
        "grand_mean": grand_mean,
        "avg_range": avg_range,
        "xbar_ucl": xbar_ucl,
        "xbar_lcl": xbar_lcl,
        "r_ucl": r_ucl,
        "r_lcl": r_lcl,
        "subgroups": subgroups,
        "subgroup_size": subgroup_size
    }

def get_control_chart_constants(n):
    """Get control chart constants for subgroup size n"""
    
    constants = {
        2: {"A2": 1.880, "D3": 0.000, "D4": 3.267},
        3: {"A2": 1.023, "D3": 0.000, "D4": 2.574},
        4: {"A2": 0.729, "D3": 0.000, "D4": 2.282},
        5: {"A2": 0.577, "D3": 0.000, "D4": 2.114},
        6: {"A2": 0.483, "D3": 0.000, "D4": 2.004},
        7: {"A2": 0.419, "D3": 0.076, "D4": 1.924},
        8: {"A2": 0.373, "D3": 0.136, "D4": 1.864},
        9: {"A2": 0.337, "D3": 0.184, "D4": 1.816},
        10: {"A2": 0.308, "D3": 0.223, "D4": 1.777}
    }
    
    return constants.get(n, constants[5])  # Default to n=5 if not found

@frappe.whitelist()
def auto_calculate_cpk(parameter, workstation, specification):
    """Automatically calculate and update Cpk values"""
    
    try:
        # Get specification limits
        spec = frappe.get_doc("SPC Specification", specification)
        
        if not (spec.upper_specification_limit and spec.lower_specification_limit):
            return {"error": "Specification limits not defined"}
        
        # Get process capability calculation
        capability = calculate_process_capability_detailed(parameter, workstation, specification)
        
        # Update or create process capability record
        existing_capability = frappe.get_all("SPC Process Capability",
            filters={
                "parameter": parameter,
                "workstation": workstation,
                "specification": specification,
                "status": "In Progress"
            },
            limit=1
        )
        
        if existing_capability:
            pc_doc = frappe.get_doc("SPC Process Capability", existing_capability[0].name)
        else:
            pc_doc = frappe.new_doc("SPC Process Capability")
            pc_doc.parameter = parameter
            pc_doc.workstation = workstation
            pc_doc.specification = specification
            pc_doc.study_start_date = now_datetime()
        
        # Update capability values
        pc_doc.cp_value = capability["cp"]
        pc_doc.cpk_value = capability["cpk"]
        pc_doc.cpu_value = capability["cpu"]
        pc_doc.cpl_value = capability["cpl"]
        pc_doc.pp_value = capability["pp"]
        pc_doc.ppk_value = capability["ppk"]
        pc_doc.process_mean = capability["mean"]
        pc_doc.process_std_dev = capability["std_dev"]
        pc_doc.sample_size = capability["sample_size"]
        pc_doc.last_updated = now_datetime()
        
        if capability["cpk"] >= 1.33:
            pc_doc.capability_status = "Capable"
        elif capability["cpk"] >= 1.0:
            pc_doc.capability_status = "Marginal"
        else:
            pc_doc.capability_status = "Not Capable"
        
        pc_doc.save(ignore_permissions=True)
        
        return {
            "process_capability": pc_doc.name,
            "cpk": capability["cpk"],
            "status": pc_doc.capability_status
        }
        
    except Exception as e:
        frappe.log_error(f"Error calculating Cpk: {str(e)}")
        return {"error": str(e)}

# =============================================================================
# ELECTRONIC SIGNATURE WORKFLOWS
# =============================================================================

@frappe.whitelist()
def trigger_electronic_signature(doctype, docname, signature_meaning, required_role=None):
    """Trigger electronic signature workflow for documents"""
    
    # Check if signature already exists
    existing_sig = frappe.get_all("SPC Electronic Signature",
        filters={
            "document_type": doctype,
            "document_name": docname,
            "signature_meaning": signature_meaning
        }
    )
    
    if existing_sig:
        return {"status": "already_signed", "signature": existing_sig[0].name}
    
    # Validate user has required role
    if required_role and required_role not in frappe.get_roles():
        frappe.throw(_("You do not have the required role '{0}' to sign this document").format(required_role))
    
    # Create electronic signature
    signature = frappe.get_doc({
        "doctype": "SPC Electronic Signature",
        "document_type": doctype,
        "document_name": docname,
        "signature_meaning": signature_meaning,
        "signed_by": frappe.session.user,
        "signature_date": now_datetime(),
        "user_role": ", ".join(frappe.get_roles()),
        "ip_address": frappe.local.request_ip if frappe.local.request_ip else "Unknown",
        "browser_info": get_browser_info()
    })
    
    signature.insert(ignore_permissions=True)
    
    # Update document status if needed
    update_document_signature_status(doctype, docname, signature_meaning)
    
    return {"status": "signed", "signature": signature.name}

def get_browser_info():
    """Get browser information for audit trail"""
    
    try:
        user_agent = frappe.get_request_header("User-Agent", "Unknown")
        return user_agent[:200]  # Limit length
    except:
        return "Unknown"

def update_document_signature_status(doctype, docname, signature_meaning):
    """Update document status after electronic signature"""
    
    try:
        doc = frappe.get_doc(doctype, docname)
        
        # Update specific fields based on signature meaning
        if signature_meaning == "Approved":
            if hasattr(doc, "approval_status"):
                doc.approval_status = "Approved"
            if hasattr(doc, "approved_by"):
                doc.approved_by = frappe.session.user
            if hasattr(doc, "approval_date"):
                doc.approval_date = now_datetime()
        
        elif signature_meaning == "Reviewed":
            if hasattr(doc, "review_status"):
                doc.review_status = "Reviewed"
            if hasattr(doc, "reviewed_by"):
                doc.reviewed_by = frappe.session.user
            if hasattr(doc, "review_date"):
                doc.review_date = now_datetime()
        
        elif signature_meaning == "Acknowledged":
            if hasattr(doc, "acknowledged"):
                doc.acknowledged = 1
            if hasattr(doc, "acknowledged_by"):
                doc.acknowledged_by = frappe.session.user
            if hasattr(doc, "acknowledgment_date"):
                doc.acknowledgment_date = now_datetime()
        
        doc.save(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Error updating document signature status: {str(e)}")

# =============================================================================
# BOT USER AUTOMATION
# =============================================================================

@frappe.whitelist(allow_guest=True)
def bot_authenticate(api_key, bot_type):
    """Authenticate bot users and return session token"""
    
    try:
        # Find bot configuration
        bot_config = frappe.get_all("Bot User Configuration",
            filters={
                "api_key": api_key,
                "bot_type": bot_type,
                "is_active": 1
            },
            fields=["user", "plant", "allowed_operations", "rate_limit"]
        )
        
        if not bot_config:
            return {"error": "Invalid API key or inactive bot"}
        
        bot = bot_config[0]
        
        # Check rate limits
        if not check_bot_rate_limit(bot.user):
            return {"error": "Rate limit exceeded"}
        
        # Generate session token
        session_token = generate_bot_session_token(bot.user)
        
        # Log authentication
        create_audit_trail("Bot Authentication", "System", bot.user, 
                          f"Bot {bot_type} authenticated successfully")
        
        return {
            "status": "authenticated",
            "session_token": session_token,
            "user": bot.user,
            "plant": bot.plant,
            "allowed_operations": bot.allowed_operations.split(",") if bot.allowed_operations else []
        }
        
    except Exception as e:
        frappe.log_error(f"Bot authentication error: {str(e)}")
        return {"error": "Authentication failed"}

@frappe.whitelist()
def bot_submit_data(data_points, session_token):
    """Handle bulk data submission from bot users"""
    
    try:
        # Validate session token
        bot_user = validate_bot_session_token(session_token)
        if not bot_user:
            return {"error": "Invalid session token"}
        
        results = []
        
        for data in data_points:
            try:
                # Validate required fields
                if not all(key in data for key in ["parameter", "workstation", "measurement_value"]):
                    results.append({"status": "error", "message": "Missing required fields"})
                    continue
                
                # Create data point
                data_point = frappe.get_doc({
                    "doctype": "SPC Data Point",
                    "parameter": data["parameter"],
                    "workstation": data["workstation"],
                    "measurement_value": flt(data["measurement_value"]),
                    "measurement_datetime": data.get("measurement_datetime", now_datetime()),
                    "operator": bot_user,
                    "measurement_source": "Automated",
                    "data_entry_method": "API",
                    "measurement_precision": data.get("measurement_precision", 0.001)
                })
                
                data_point.insert(ignore_permissions=True)
                
                # Check for alerts
                alert_created = auto_create_spc_alert(data_point.name)
                
                results.append({
                    "status": "success",
                    "data_point": data_point.name,
                    "alert_created": alert_created is not None
                })
                
            except Exception as e:
                results.append({"status": "error", "message": str(e)})
        
        return {"results": results}
        
    except Exception as e:
        frappe.log_error(f"Bot data submission error: {str(e)}")
        return {"error": "Data submission failed"}

def check_bot_rate_limit(bot_user):
    """Check if bot user is within rate limits"""
    
    one_minute_ago = add_to_date(now_datetime(), minutes=-1)
    
    recent_requests = frappe.get_all("SPC Audit Trail",
        filters={
            "user": bot_user,
            "creation": [">=", one_minute_ago],
            "action": "API Request"
        }
    )
    
    # Get bot configuration for rate limit
    bot_config = frappe.get_value("Bot User Configuration", 
                                 {"user": bot_user}, "rate_limit")
    
    rate_limit = int(bot_config.split("/")[0]) if bot_config else 60
    
    return len(recent_requests) < rate_limit

def generate_bot_session_token(bot_user):
    """Generate secure session token for bot user"""
    
    import secrets
    import hashlib
    
    # Generate random token
    token = secrets.token_urlsafe(32)
    
    # Store token in cache with expiry
    frappe.cache().set_value(f"bot_session:{token}", bot_user, expires_in_sec=24*60*60)
    
    return token

def validate_bot_session_token(session_token):
    """Validate bot session token and return user"""
    
    bot_user = frappe.cache().get_value(f"bot_session:{session_token}")
    
    if bot_user:
        # Log API request for rate limiting
        create_audit_trail("API Request", "System", bot_user, "Data submission")
    
    return bot_user

# =============================================================================
# REPORT GENERATION AUTOMATION
# =============================================================================

@frappe.whitelist()
def auto_generate_spc_reports():
    """Automatically generate scheduled SPC reports"""
    
    # Get report schedules
    scheduled_reports = frappe.get_all("SPC Report",
        filters={
            "auto_generate": 1,
            "status": "Active",
            "next_generation_date": ["<=", now_datetime()]
        },
        fields=["name", "report_type", "frequency", "plant", "workstation"]
    )
    
    results = []
    
    for report_config in scheduled_reports:
        try:
            # Generate report
            report = generate_spc_report(report_config.name)
            
            # Update next generation date
            next_date = calculate_next_generation_date(report_config.frequency)
            frappe.db.set_value("SPC Report", report_config.name, 
                              "next_generation_date", next_date)
            
            # Send to recipients
            send_report_to_recipients(report["name"])
            
            results.append({
                "report": report_config.name,
                "status": "generated",
                "generated_report": report["name"]
            })
            
        except Exception as e:
            frappe.log_error(f"Error generating report {report_config.name}: {str(e)}")
            results.append({
                "report": report_config.name,
                "status": "error",
                "message": str(e)
            })
    
    return {"processed": len(scheduled_reports), "results": results}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_audit_trail(action, document_type, user, details):
    """Create audit trail entry"""
    
    try:
        audit = frappe.get_doc({
            "doctype": "SPC Audit Trail",
            "action": action,
            "document_type": document_type,
            "user": user,
            "timestamp": now_datetime(),
            "details": details,
            "ip_address": frappe.local.request_ip if frappe.local.request_ip else "System"
        })
        
        audit.insert(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Error creating audit trail: {str(e)}")

def add_to_date(date, years=0, months=0, days=0, hours=0, minutes=0, seconds=0):
    """Utility function to add time to date"""
    from dateutil.relativedelta import relativedelta
    
    if isinstance(date, str):
        date = get_datetime(date)
    
    return date + relativedelta(years=years, months=months, days=days, 
                               hours=hours, minutes=minutes, seconds=seconds)

# =============================================================================
# SCHEDULED TASKS
# =============================================================================

def daily_spc_maintenance():
    """Daily maintenance tasks for SPC system"""
    
    # Generate scheduled reports
    auto_generate_spc_reports()
    
    # Check for escalated alerts
    escalate_overdue_alerts()
    
    # Clean up old audit trail entries
    cleanup_old_audit_trail()
    
    # Update process capability studies
    update_capability_studies()

def hourly_spc_checks():
    """Hourly checks for SPC system"""
    
    # Check for critical alerts without acknowledgment
    check_unacknowledged_critical_alerts()
    
    # Validate bot user tokens
    cleanup_expired_bot_tokens()
    
    # Check system health
    perform_system_health_check()