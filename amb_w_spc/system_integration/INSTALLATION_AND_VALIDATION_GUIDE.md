# SPC ERPNext System - Complete Installation and Validation Guide

## Overview

This comprehensive guide provides step-by-step instructions for installing, configuring, and validating the complete Statistical Process Control (SPC) system in ERPNext with FDA compliance, plant automation, and quality management capabilities.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Pre-Installation Checklist](#pre-installation-checklist)
3. [Installation Process](#installation-process)
4. [Post-Installation Configuration](#post-installation-configuration)
5. [Validation Procedures](#validation-procedures)
6. [Testing Checklist](#testing-checklist)
7. [Troubleshooting Guide](#troubleshooting-guide)
8. [Maintenance Procedures](#maintenance-procedures)

## System Requirements

### Software Requirements
- **ERPNext**: Version 14.0.0 or higher
- **Frappe Framework**: Version 14.0.0 or higher
- **Python**: Version 3.8 or higher
- **Database**: MariaDB 10.3+ or PostgreSQL 12+
- **Operating System**: Ubuntu 20.04+ or CentOS 8+

### Hardware Requirements
- **RAM**: Minimum 4GB, Recommended 8GB+
- **Storage**: Minimum 10GB free space
- **CPU**: Multi-core processor recommended
- **Network**: Stable internet connection for updates

### Required Python Packages
```bash
pip install statistics python-dateutil numpy scipy
```

## Pre-Installation Checklist

### 1. ERPNext Environment Verification
- [ ] ERPNext site is running and accessible
- [ ] Administrator access to the site
- [ ] Database backup created
- [ ] System maintenance window scheduled
- [ ] Required Python packages installed

### 2. Planning and Preparation
- [ ] Plant configurations identified
- [ ] Workstations and equipment listed
- [ ] Quality parameters defined
- [ ] User roles and responsibilities mapped
- [ ] Integration points with existing systems identified

### 3. Data Preparation
- [ ] Existing quality data backed up
- [ ] Parameter specifications documented
- [ ] User accounts created in ERPNext
- [ ] Email server configured for notifications

## Installation Process

### Step 1: Download and Prepare Installation Files

```bash
# Navigate to the workspace
cd /workspace/erpnext_doctypes/system_integration

# Make installation script executable
chmod +x installation/install_spc_system.py

# Verify all required files are present
ls -la doctypes_relationships.json
ls -la permissions/role_permissions.json
ls -la workflows/workflow_configurations.json
ls -la validations/spc_validation_rules.py
ls -la scripts/automation_scripts.py
```

### Step 2: Run Installation Script

```bash
# Run the complete installation
python3 installation/install_spc_system.py your-site-name

# Monitor installation log
tail -f spc_installation_*.log
```

### Step 3: Manual Installation (Alternative)

If automated installation fails, follow these manual steps:

#### 3.1 Install DocTypes
```bash
# Install in sequence (critical for dependencies)
bench --site your-site import-doc-type path/to/plant_configuration.json
bench --site your-site import-doc-type path/to/workstation.json
bench --site your-site import-doc-type path/to/spc_parameter_master.json
# ... continue with all DocTypes in order
```

#### 3.2 Create Roles
```bash
bench --site your-site execute "
role = frappe.get_doc({
    'doctype': 'Role',
    'role_name': 'Quality User',
    'desk_access': 1,
    'is_custom': 1
})
role.insert()
frappe.db.commit()
"
```

#### 3.3 Apply Permissions
```bash
bench --site your-site execute "
from frappe.permissions import add_permission
add_permission('SPC Data Point', 'Quality User', 1, write=1, create=1)
frappe.db.commit()
"
```

## Post-Installation Configuration

### 1. Basic System Configuration

#### 1.1 Create Plant Configuration
```bash
bench --site your-site execute "
plant = frappe.get_doc({
    'doctype': 'Plant Configuration',
    'plant_name': 'Main Manufacturing Plant',
    'plant_code': 'PLANT001',
    'company': 'Your Company',
    'is_active': 1,
    'time_zone': 'America/New_York'
})
plant.insert()
frappe.db.commit()
"
```

#### 1.2 Set Up Workstations
```bash
bench --site your-site execute "
workstation = frappe.get_doc({
    'doctype': 'Workstation',
    'workstation_name': 'Production Line 1',
    'plant': 'Main Manufacturing Plant',
    'workstation_type': 'Manufacturing',
    'is_active': 1
})
workstation.insert()
frappe.db.commit()
"
```

#### 1.3 Create Parameter Masters
```bash
bench --site your-site execute "
parameter = frappe.get_doc({
    'doctype': 'SPC Parameter Master',
    'parameter_name': 'Temperature',
    'workstation': 'Production Line 1',
    'parameter_type': 'Process',
    'data_type': 'Numeric',
    'uom': '°C',
    'decimal_precision': 2,
    'is_critical': 1
})
parameter.insert()
frappe.db.commit()
"
```

### 2. User Setup and Permissions

#### 2.1 Assign Users to Roles
```bash
# Quality User role assignment
bench --site your-site execute "
user = frappe.get_doc('User', 'quality@company.com')
user.add_roles('Quality User')
user.save()
frappe.db.commit()
"
```

#### 2.2 Set Plant-Based User Permissions
```bash
bench --site your-site execute "
from frappe.permissions import add_user_permission
add_user_permission('Plant Configuration', 'Main Manufacturing Plant', 'quality@company.com')
frappe.db.commit()
"
```

### 3. Workflow Configuration

#### 3.1 Activate Workflows
```bash
bench --site your-site execute "
workflow = frappe.get_doc('Workflow', 'SPC Alert Workflow')
workflow.is_active = 1
workflow.save()
frappe.db.commit()
"
```

### 4. Email Configuration

#### 4.1 Set Up Email Notifications
```bash
bench --site your-site execute "
notification = frappe.get_doc({
    'doctype': 'Notification',
    'subject': 'SPC Alert - {{ doc.severity }} Alert',
    'document_type': 'SPC Alert',
    'event': 'New',
    'recipients': [{'recipient': 'quality@company.com'}],
    'message': 'A new SPC alert has been generated...',
    'enabled': 1
})
notification.insert()
frappe.db.commit()
"
```

## Validation Procedures

### 1. Installation Validation

#### 1.1 Verify DocTypes Installation
```bash
bench --site your-site execute "
key_doctypes = [
    'Plant Configuration', 'Workstation', 'SPC Parameter Master',
    'SPC Specification', 'SPC Data Point', 'SPC Alert',
    'Process Capability', 'SPC Report', 'Corrective Action',
    'Deviation', 'Electronic Signature', 'SPC Audit Trail'
]

missing = []
for dt in key_doctypes:
    if not frappe.db.exists('DocType', dt):
        missing.append(dt)

if missing:
    print(f'Missing DocTypes: {missing}')
else:
    print('All DocTypes installed successfully')
"
```

#### 1.2 Verify Role and Permission Setup
```bash
bench --site your-site execute "
roles = ['Quality User', 'Inspector User', 'Manufacturing User']
for role in roles:
    if frappe.db.exists('Role', role):
        print(f'Role {role}: OK')
    else:
        print(f'Role {role}: MISSING')
"
```

#### 1.3 Verify Workflow Installation
```bash
bench --site your-site execute "
workflows = ['SPC Alert Workflow', 'Process Capability Workflow']
for wf in workflows:
    if frappe.db.exists('Workflow', wf):
        print(f'Workflow {wf}: OK')
    else:
        print(f'Workflow {wf}: MISSING')
"
```

### 2. Functionality Validation

#### 2.1 Data Entry Validation
```bash
bench --site your-site execute "
# Test data point creation
data_point = frappe.get_doc({
    'doctype': 'SPC Data Point',
    'parameter': 'Temperature',
    'workstation': 'Production Line 1',
    'measurement_value': 75.2,
    'measurement_datetime': frappe.utils.now_datetime(),
    'operator': 'Administrator'
})
try:
    data_point.insert()
    print('Data point creation: PASS')
    frappe.db.rollback()  # Don't save test data
except Exception as e:
    print(f'Data point creation: FAIL - {e}')
"
```

#### 2.2 Alert Generation Validation
```bash
bench --site your-site execute "
# Test alert creation logic
from automation_scripts import auto_create_spc_alert

# This will test the alert creation function
# (assuming test data exists)
result = auto_create_spc_alert('test-data-point')
if result:
    print('Alert generation: PASS')
else:
    print('Alert generation: PASS (no alerts needed)')
"
```

#### 2.3 Electronic Signature Validation
```bash
bench --site your-site execute "
# Test electronic signature
signature = frappe.get_doc({
    'doctype': 'Electronic Signature',
    'document_type': 'SPC Data Point',
    'document_name': 'TEST-001',
    'signature_meaning': 'Approved',
    'signed_by': 'Administrator'
})
try:
    signature.insert()
    print('Electronic signature: PASS')
    frappe.db.rollback()
except Exception as e:
    print(f'Electronic signature: FAIL - {e}')
"
```

## Testing Checklist

### Functional Testing

#### Data Entry and Validation
- [ ] Create SPC Data Point with valid data
- [ ] Verify validation rules for out-of-range values
- [ ] Test decimal precision enforcement
- [ ] Verify timestamp validation
- [ ] Test duplicate measurement detection

#### Alert System
- [ ] Create data point exceeding critical limits
- [ ] Verify automatic alert generation
- [ ] Test alert notification sending
- [ ] Verify alert escalation after 24 hours
- [ ] Test alert acknowledgment workflow

#### Statistical Calculations
- [ ] Verify X-bar R chart calculations
- [ ] Test process capability (Cp, Cpk) calculations
- [ ] Validate control limit calculations
- [ ] Test statistical significance validation

#### Workflow Testing
- [ ] Test SPC Alert workflow transitions
- [ ] Verify Process Capability workflow
- [ ] Test Corrective Action workflow
- [ ] Validate Deviation workflow
- [ ] Test workflow permissions by role

#### Electronic Signatures
- [ ] Create electronic signature
- [ ] Verify signature validation rules
- [ ] Test signature uniqueness enforcement
- [ ] Verify audit trail creation
- [ ] Test signature requirement workflows

#### Reports and Analytics
- [ ] Generate SPC Report
- [ ] Test process capability report
- [ ] Verify trend analysis
- [ ] Test automated report generation
- [ ] Validate report email distribution

### Integration Testing

#### ERPNext Module Integration
- [ ] Link SPC parameters to Work Orders
- [ ] Test Quality Inspection integration
- [ ] Verify Batch/Serial number tracking
- [ ] Test Workstation integration
- [ ] Validate Cost Center allocation

#### API Testing
- [ ] Test bot user authentication
- [ ] Verify bulk data submission API
- [ ] Test PLC integration endpoints
- [ ] Validate API rate limiting
- [ ] Test error handling and responses

#### Email Notifications
- [ ] Test critical alert notifications
- [ ] Verify escalation email sending
- [ ] Test scheduled report emails
- [ ] Validate CAPA reminder emails
- [ ] Test custom notification templates

### Performance Testing

#### Data Volume Testing
- [ ] Insert 1000+ data points
- [ ] Test with multiple concurrent users
- [ ] Verify dashboard performance with large datasets
- [ ] Test report generation with historical data
- [ ] Validate database query performance

#### Scalability Testing
- [ ] Test multiple plant configurations
- [ ] Verify multi-workstation performance
- [ ] Test with high-frequency data collection
- [ ] Validate concurrent alert processing
- [ ] Test backup and restore procedures

### Security Testing

#### Access Control
- [ ] Verify role-based permissions
- [ ] Test plant-based data restrictions
- [ ] Validate user permission inheritance
- [ ] Test bot user API access controls
- [ ] Verify audit trail capture

#### Data Integrity
- [ ] Test data validation rules
- [ ] Verify electronic signature integrity
- [ ] Test audit trail immutability
- [ ] Validate backup and recovery
- [ ] Test data encryption in transit

## Troubleshooting Guide

### Common Installation Issues

#### DocType Import Errors
**Problem**: DocType import fails with dependency errors
**Solution**: 
```bash
# Install DocTypes in correct dependency order
# Check the master_installation.json for proper sequence
```

#### Permission Setup Failures
**Problem**: Users cannot access SPC DocTypes
**Solution**:
```bash
# Verify role assignment
bench --site your-site execute "print(frappe.get_roles('user@company.com'))"

# Check DocType permissions
bench --site your-site execute "print(frappe.permissions.get_doc_permissions('SPC Data Point'))"
```

#### Workflow Not Working
**Problem**: Workflow transitions not available
**Solution**:
```bash
# Check workflow is active
bench --site your-site execute "print(frappe.get_value('Workflow', 'SPC Alert Workflow', 'is_active'))"

# Verify workflow state assignment
bench --site your-site execute "print(frappe.get_value('SPC Alert', 'ALERT-001', 'workflow_state'))"
```

### Runtime Issues

#### Alert Generation Not Working
**Problem**: SPC Alerts not created automatically
**Solution**:
1. Check specification limits are properly set
2. Verify automation scripts are installed
3. Check server error logs
4. Test manual alert creation

#### Email Notifications Not Sent
**Problem**: Email notifications not being sent
**Solution**:
1. Verify email server configuration
2. Check notification settings
3. Test email template rendering
4. Check email queue

#### Performance Issues
**Problem**: System slow with large datasets
**Solution**:
1. Check database indexes
2. Optimize queries
3. Archive old data
4. Increase server resources

### Data Issues

#### Validation Errors
**Problem**: Data validation failing unexpectedly
**Solution**:
1. Check validation rules in spc_validation_rules.py
2. Verify data types and formats
3. Check specification limits
4. Review error logs

#### Statistical Calculation Errors
**Problem**: Cp/Cpk calculations incorrect
**Solution**:
1. Verify sufficient sample size (minimum 30)
2. Check specification limits are set
3. Validate data point values
4. Review calculation formulas

## Maintenance Procedures

### Daily Maintenance

#### System Health Checks
```bash
# Check system status
bench --site your-site execute "from automation_scripts import perform_system_health_check; perform_system_health_check()"

# Review error logs
tail -100 /home/frappe/frappe-bench/logs/your-site.error.log

# Check scheduled job status
bench --site your-site execute "print(frappe.get_all('Scheduled Job Log', limit=10, order_by='creation desc'))"
```

#### Data Validation
```bash
# Check for data anomalies
bench --site your-site execute "
from datetime import datetime, timedelta

# Check for missing data
today = datetime.now().date()
yesterday = today - timedelta(days=1)

data_count = frappe.db.count('SPC Data Point', {
    'creation': ['between', [yesterday, today]]
})

print(f'Data points created yesterday: {data_count}')
"
```

### Weekly Maintenance

#### Performance Optimization
```bash
# Optimize database
bench --site your-site execute "frappe.db.sql('OPTIMIZE TABLE `tabSPC Data Point`')"

# Clear old sessions
bench --site your-site execute "frappe.sessions.clear_expired_sessions()"

# Update statistics
bench --site your-site execute "from automation_scripts import update_capability_studies; update_capability_studies()"
```

#### Backup Verification
```bash
# Create backup
bench --site your-site backup

# Verify backup files
ls -la sites/your-site/private/backups/
```

### Monthly Maintenance

#### Data Archiving
```bash
# Archive old audit trail entries (older than 2 years)
bench --site your-site execute "
from datetime import datetime, timedelta

archive_date = datetime.now() - timedelta(days=730)

# Move old audit trails to archive table
old_records = frappe.get_all('SPC Audit Trail', 
    filters={'creation': ['<', archive_date]},
    limit=1000
)

print(f'Records to archive: {len(old_records)}')
"
```

#### System Updates
```bash
# Update SPC system (if newer version available)
# 1. Backup current system
# 2. Download updates
# 3. Test in staging environment
# 4. Apply to production
```

### Quarterly Maintenance

#### Comprehensive Review
- [ ] Review system performance metrics
- [ ] Analyze user feedback and usage patterns
- [ ] Update documentation
- [ ] Plan system improvements
- [ ] Review security settings
- [ ] Update disaster recovery procedures

## Validation Sign-off

### Installation Validation Sign-off

**Installation Completed By**: _________________ **Date**: _________

**Validated By**: 
- Quality Manager: _________________ **Date**: _________
- IT Manager: _________________ **Date**: _________
- System Administrator: _________________ **Date**: _________

### System Acceptance

**System Accepted By**:
- Operations Manager: _________________ **Date**: _________
- Quality Director: _________________ **Date**: _________
- IT Director: _________________ **Date**: _________

---

## Support and Documentation

For additional support:
- System documentation: `/workspace/erpnext_doctypes/system_integration/`
- Error logs: Check ERPNext error log files
- Community support: ERPNext community forums
- Professional support: Contact your ERPNext implementation partner

## Appendices

### Appendix A: Configuration Files Reference
- [doctypes_relationships.json](doctypes_relationships.json)
- [role_permissions.json](permissions/role_permissions.json)
- [workflow_configurations.json](workflows/workflow_configurations.json)
- [automation_scripts.py](scripts/automation_scripts.py)
- [spc_validation_rules.py](validations/spc_validation_rules.py)

### Appendix B: API Documentation
- [integration_points.json](integration_points.json) - Complete API reference

### Appendix C: Sample Data
- Sample plant configurations
- Example parameter specifications
- Test data sets for validation

---

**Document Version**: 1.0  
**Last Updated**: 2025-09-10  
**Next Review Date**: 2025-12-10