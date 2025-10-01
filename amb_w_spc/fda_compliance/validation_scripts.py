"""
FDA 21 CFR Part 11 Validation Scripts
=====================================

This file contains server-side validation scripts and hooks for ensuring
FDA compliance across all DocTypes. These scripts should be implemented
in ERPNext custom apps or through custom scripts.
"""

import frappe
import hashlib
import json
from datetime import datetime
from frappe import _

# =============================================================================
# AUDIT TRAIL CAPTURE
# =============================================================================

def capture_audit_trail(doc, method):
    """
    Automatic audit trail capture for all document operations
    This should be called from document hooks (after_insert, on_update, on_cancel, etc.)
    """
    if doc.doctype == "SPC Audit Trail":
        return  # Prevent recursive calls
    
    try:
        # Determine action type based on method
        action_mapping = {
            'after_insert': 'Create',
            'on_update': 'Update', 
            'on_cancel': 'Delete',
            'on_submit': 'Approve',
            'before_print': 'Print'
        }
        
        action_type = action_mapping.get(method, 'Read')
        
        # Get session information
        request = frappe.local.request
        ip_address = frappe.utils.get_request_ip()
        browser_info = request.headers.get('User-Agent', '') if request else ''
        
        # Create audit trail record
        audit_trail = frappe.get_doc({
            'doctype': 'SPC Audit Trail',
            'record_id': f"{doc.doctype}_{doc.name}_{frappe.utils.now()}",
            'timestamp': frappe.utils.now(),
            'user_id': frappe.session.user,
            'action_type': action_type,
            'table_name': doc.doctype,
            'record_name': doc.name,
            'ip_address': ip_address,
            'browser_info': browser_info,
            'session_id': frappe.session.sid,
            'checksum': generate_checksum(doc),
            'hash_value': generate_hash(doc),
            'backup_status': 'Pending'
        })
        
        # Add field changes for updates
        if method == 'on_update' and hasattr(doc, '_doc_before_save'):
            changes = get_document_changes(doc._doc_before_save, doc)
            if changes:
                audit_trail.field_changed = changes['field']
                audit_trail.old_value = changes['old_value']
                audit_trail.new_value = changes['new_value']
        
        audit_trail.insert(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Audit trail capture failed: {str(e)}", "FDA Compliance Error")

def generate_checksum(doc):
    """Generate MD5 checksum for document data integrity"""
    doc_data = json.dumps(doc.as_dict(), sort_keys=True, default=str)
    return hashlib.md5(doc_data.encode()).hexdigest()

def generate_hash(doc):
    """Generate SHA-256 hash for tamper detection"""
    doc_data = json.dumps(doc.as_dict(), sort_keys=True, default=str)
    return hashlib.sha256(doc_data.encode()).hexdigest()

def get_document_changes(old_doc, new_doc):
    """Compare documents and return first significant change"""
    for field in new_doc.meta.fields:
        if field.fieldtype in ['Data', 'Text', 'Select', 'Float', 'Int', 'Date', 'Datetime']:
            old_value = old_doc.get(field.fieldname)
            new_value = new_doc.get(field.fieldname)
            if old_value != new_value:
                return {
                    'field': field.fieldname,
                    'old_value': str(old_value or ''),
                    'new_value': str(new_value or '')
                }
    return None

# =============================================================================
# ELECTRONIC SIGNATURE VALIDATION
# =============================================================================

def validate_electronic_signature(doc, method):
    """Validate electronic signature requirements"""
    if doc.doctype != "SPC Electronic Signature":
        return
        
    # Validate signature components
    if not doc.signature_id:
        frappe.throw(_("Signature ID is required for FDA compliance"))
    
    # Validate user credentials
    if not doc.user_credentials_verified:
        frappe.throw(_("User credentials must be verified before signing"))
    
    # Validate signature meaning
    if not doc.signature_meaning:
        frappe.throw(_("Signature meaning is required per 21 CFR Part 11"))
    
    # Generate signature hash
    if not doc.signature_hash:
        signature_data = f"{doc.signer_name}_{doc.signature_date}_{doc.signature_meaning}_{doc.document_type}_{doc.document_name}"
        doc.signature_hash = hashlib.sha256(signature_data.encode()).hexdigest()
    
    # Set CFR Part 11 compliance flag
    doc.cfr_part11_compliant = 1
    
    # Create signature components JSON
    components = {
        'printed_name': frappe.get_value('User', doc.signer_name, 'full_name'),
        'date_time': doc.signature_date,
        'meaning': doc.signature_meaning,
        'method': doc.signature_method
    }
    doc.signature_components = json.dumps(components)

# =============================================================================
# BATCH RECORD VALIDATION
# =============================================================================

def validate_batch_record(doc, method):
    """Validate SPC Batch Record for FDA compliance"""
    if doc.doctype != "SPC Batch Record":
        return
    
    # Validate required personnel signatures
    if doc.batch_status in ['Complete', 'Approved', 'Released']:
        if not doc.production_supervisor:
            frappe.throw(_("Production Supervisor is required before batch completion"))
        
        if not doc.quality_inspector:
            frappe.throw(_("Quality Inspector is required before batch completion"))
    
    if doc.batch_status == 'Released':
        if not doc.batch_approver:
            frappe.throw(_("Batch Approver is required before batch release"))
        
        if not doc.release_date:
            doc.release_date = frappe.utils.today()
    
    # Validate specifications met
    if doc.parameters_tested:
        all_passed = True
        for param in doc.parameters_tested:
            if param.pass_fail != 'Pass':
                all_passed = False
                break
        doc.specifications_met = 1 if all_passed else 0
    
    # Set data integrity verification
    if doc.batch_status == 'Released':
        doc.data_integrity_verified = 1

# =============================================================================
# DEVIATION VALIDATION
# =============================================================================

def validate_deviation(doc, method):
    """Validate Deviation for regulatory compliance"""
    if doc.doctype != "SPC Deviation":
        return
    
    # Auto-generate deviation number if not provided
    if not doc.deviation_number:
        doc.deviation_number = generate_deviation_number(doc.plant, doc.deviation_type)
    
    # Validate investigation timeline for critical deviations
    if doc.severity == 'Critical':
        if not doc.investigation_start_date:
            doc.investigation_start_date = frappe.utils.today()
        
        if not doc.investigation_target_date:
            # Critical deviations must be investigated within 30 days
            doc.investigation_target_date = frappe.utils.add_days(doc.investigation_start_date, 30)
    
    # Validate CAPA requirements for Major and Critical deviations
    if doc.severity in ['Major', 'Critical'] and doc.deviation_status != 'Open':
        if not doc.corrective_actions:
            frappe.throw(_("Corrective actions are required for Major and Critical deviations"))
    
    # Auto-set regulatory reportable flag for critical deviations
    if doc.severity == 'Critical':
        doc.regulatory_reportable = 1
        if not doc.regulatory_timeline:
            # FDA requires reporting within 15 days for critical deviations
            doc.regulatory_timeline = frappe.utils.add_days(doc.detection_date, 15)

def generate_deviation_number(plant, deviation_type):
    """Generate unique deviation number"""
    plant_code = frappe.get_value('Warehouse', plant, 'warehouse_name')[:3].upper()
    type_code = deviation_type[:3].upper()
    year = datetime.now().year
    
    # Get next sequence number
    existing = frappe.get_all('SPC Deviation', 
                            filters={'name': ['like', f'DEV-{plant_code}-{type_code}-{year}-%']},
                            order_by='creation desc',
                            limit=1)
    
    if existing:
        last_num = existing[0].name.split('-')[-1]
        next_num = int(last_num) + 1
    else:
        next_num = 1
    
    return f"DEV-{plant_code}-{type_code}-{year}-{next_num:04d}"

# =============================================================================
# DATA INTEGRITY VALIDATION
# =============================================================================

def validate_data_integrity(doc, method):
    """Validate data integrity across all FDA documents"""
    # Check for required fields based on document status
    required_fields = get_required_fields_by_status(doc)
    
    for field in required_fields:
        if not doc.get(field):
            frappe.throw(_(f"Field {field} is required for current document status"))
    
    # Validate date sequences (e.g., start date before end date)
    validate_date_sequences(doc)
    
    # Check for data completeness (ALCOA+ principles)
    validate_alcoa_compliance(doc)

def get_required_fields_by_status(doc):
    """Return required fields based on document status"""
    required_map = {
        'SPC Batch Record': {
            'Complete': ['production_supervisor', 'quality_inspector', 'test_results'],
            'Approved': ['batch_reviewer'],
            'Released': ['batch_approver', 'release_date']
        },
        'SPC Deviation': {
            'Under Investigation': ['investigation_team', 'investigation_start_date'],
            'Pending CAPA': ['root_cause_analysis', 'corrective_actions'],
            'Closed': ['closure_approval', 'closure_date', 'closure_justification']
        }
    }
    
    status_field_map = {
        'SPC Batch Record': 'batch_status',
        'SPC Deviation': 'deviation_status'
    }
    
    status_field = status_field_map.get(doc.doctype)
    if status_field and doc.get(status_field):
        return required_map.get(doc.doctype, {}).get(doc.get(status_field), [])
    
    return []

def validate_date_sequences(doc):
    """Validate logical date sequences"""
    date_sequences = {
        'SPC Deviation': [
            ('occurrence_date', 'detection_date'),
            ('investigation_start_date', 'investigation_target_date'),
            ('investigation_start_date', 'investigation_completion_date')
        ]
    }
    
    sequences = date_sequences.get(doc.doctype, [])
    for start_field, end_field in sequences:
        start_date = doc.get(start_field)
        end_date = doc.get(end_field)
        
        if start_date and end_date and start_date > end_date:
            frappe.throw(_(f"{start_field} cannot be after {end_field}"))

def validate_alcoa_compliance(doc):
    """Validate ALCOA+ data integrity principles"""
    # Attributable - check user attribution
    if not doc.owner:
        frappe.throw(_("Document must have clear attribution (owner)"))
    
    # Legible - check for required text fields
    text_fields = [field.fieldname for field in doc.meta.fields 
                  if field.fieldtype in ['Text', 'Text Editor', 'Long Text'] and field.reqd]
    
    for field in text_fields:
        value = doc.get(field)
        if value and (len(value.strip()) < 10 or not value.replace(' ', '').replace('\n', '')):
            frappe.throw(_(f"Field {field} must contain meaningful, legible content"))
    
    # Contemporaneous - validate timestamps
    if hasattr(doc, 'timestamp') and doc.timestamp:
        time_diff = abs((datetime.now() - doc.timestamp).total_seconds())
        if time_diff > 300:  # 5 minutes tolerance
            frappe.log_error(f"Non-contemporaneous timestamp detected: {doc.doctype} {doc.name}")

# =============================================================================
# HOOK REGISTRATION
# =============================================================================

# These hooks should be registered in hooks.py of your custom app:

doc_events = {
    "*": {
        "after_insert": "path.to.this.module.capture_audit_trail",
        "on_update": "path.to.this.module.capture_audit_trail", 
        "on_cancel": "path.to.this.module.capture_audit_trail",
        "on_submit": "path.to.this.module.capture_audit_trail",
        "validate": "path.to.this.module.validate_data_integrity"
    },
    "SPC Electronic Signature": {
        "validate": "path.to.this.module.validate_electronic_signature"
    },
    "SPC Batch Record": {
        "validate": "path.to.this.module.validate_batch_record"
    },
    "SPC Deviation": {
        "validate": "path.to.this.module.validate_deviation"
    }
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_fda_compliance_dashboard():
    """Generate FDA compliance dashboard data"""
    return {
        'audit_trail_count': frappe.db.count('SPC Audit Trail'),
        'signatures_today': frappe.db.count('SPC Electronic Signature', {
            'signature_date': ['>=', frappe.utils.today()]
        }),
        'open_deviations': frappe.db.count('SPC Deviation', {
            'deviation_status': ['in', ['Open', 'Under Investigation']]
        }),
        'overdue_capadont': frappe.db.count('Deviation CAPA Action', {
            'status': ['!=', 'Closed'],
            'target_completion_date': ['<', frappe.utils.today()]
        }),
        'batches_pending_release': frappe.db.count('SPC Batch Record', {
            'batch_status': ['in', ['Complete', 'Approved']]
        })
    }

def run_compliance_check():
    """Run comprehensive compliance check"""
    issues = []
    
    # Check for unsigned critical documents
    critical_docs = frappe.get_all('SPC Batch Record', 
                                 filters={'batch_status': 'Released', 'batch_approver': ['is', 'not set']})
    if critical_docs:
        issues.append(f"Found {len(critical_docs)} released batches without approver signature")
    
    # Check for overdue investigations
    overdue_investigations = frappe.get_all('SPC Deviation',
                                          filters={
                                              'investigation_target_date': ['<', frappe.utils.today()],
                                              'deviation_status': ['!=', 'Closed']
                                          })
    if overdue_investigations:
        issues.append(f"Found {len(overdue_investigations)} overdue investigations")
    
    # Check for missing audit trails
    recent_changes = frappe.get_all('Version', filters={'creation': ['>=', frappe.utils.add_days(None, -1)]})
    audit_records = frappe.get_all('SPC Audit Trail', filters={'timestamp': ['>=', frappe.utils.add_days(None, -1)]})
    
    if len(recent_changes) != len(audit_records):
        issues.append("Audit trail records do not match document changes")
    
    return issues

# =============================================================================
# SCHEDULED JOBS
# =============================================================================

def daily_compliance_check():
    """Daily compliance check scheduled job"""
    issues = run_compliance_check()
    
    if issues:
        # Send notification to quality team
        frappe.sendmail(
            recipients=['quality@company.com'],
            subject='FDA Compliance Issues Detected',
            message=f"The following compliance issues were detected:\n\n" + "\n".join(issues)
        )

def weekly_audit_trail_summary():
    """Weekly audit trail summary for compliance review"""
    summary = frappe.db.sql("""
        SELECT action_type, COUNT(*) as count, user_id
        FROM `tabSPC Audit Trail`
        WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        GROUP BY action_type, user_id
        ORDER BY count DESC
    """, as_dict=True)
    
    # Generate and email summary report
    html_content = frappe.render_template('templates/audit_trail_summary.html', {'data': summary})
    
    frappe.sendmail(
        recipients=['quality@company.com', 'audit@company.com'],
        subject='Weekly Audit Trail Summary',
        message=html_content
    )