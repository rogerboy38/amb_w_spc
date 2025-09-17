# FDA Compliance Module

## Table of Contents
- [Overview](#overview)
- [FDA 21 CFR Part 11 Compliance](#fda-21-cfr-part-11-compliance)
- [DocTypes and Features](#doctypes-and-features)
- [Validation Scripts](#validation-scripts)
- [Audit Trail Capabilities](#audit-trail-capabilities)
- [Electronic Signature Features](#electronic-signature-features)
- [Installation and Configuration](#installation-and-configuration)
- [Compliance Verification](#compliance-verification)
- [Regulatory Guidelines](#regulatory-guidelines)
- [Usage Examples](#usage-examples)
- [Maintenance and Support](#maintenance-and-support)
- [Contributing](#contributing)

## Overview

The FDA Compliance module is a comprehensive implementation of FDA 21 CFR Part 11 requirements for electronic records, electronic signatures, audit trails, and data integrity in pharmaceutical and regulated manufacturing environments. Built for the ERPNext/Frappe framework, this module ensures full regulatory compliance while maintaining operational efficiency.

### Key Features
- ✅ **Complete FDA 21 CFR Part 11 compliance**
- ✅ **ALCOA+ data integrity principles**
- ✅ **Immutable audit trails with tamper detection**
- ✅ **Multi-factor electronic signatures**
- ✅ **Comprehensive batch record management**
- ✅ **Integrated deviation and CAPA management**
- ✅ **Real-time compliance monitoring**
- ✅ **Regulatory reporting capabilities**

### Regulatory Scope
This module addresses critical FDA requirements including:
- Electronic records management (§ 11.10)
- Electronic signatures (§ 11.50, § 11.70, § 11.100, § 11.200, § 11.300)
- Audit trail requirements (§ 11.10(e))
- Data integrity and ALCOA+ principles
- Good Manufacturing Practice (GMP) compliance
- Change control and deviation management

## FDA 21 CFR Part 11 Compliance

### Electronic Records Compliance (§ 11.10)
The module ensures comprehensive electronic records compliance through:

- **System Validation**: Comprehensive validation scripts and data integrity checks
- **Audit Trail**: Complete audit trail capturing all CRUD operations with tamper evidence
- **Record Retention**: Permanent record storage with backup status tracking
- **Record Copying**: Export capabilities for regulatory submissions
- **Record Security**: Role-based permissions and access control
- **Record Protection**: Protection from unauthorized access, modification, or destruction

### Electronic Signatures Compliance (§ 11.50, § 11.70, § 11.100, § 11.200, § 11.300)
Electronic signature implementation includes:

- **Signature Components**: Printed name, date/time, and meaning captured
- **Authentication**: Multi-factor authentication support
- **Non-repudiation**: Cryptographic hash validation
- **Signature Linking**: Direct linking to signed documents
- **Signature Meaning**: Clear indication of signature purpose
- **Human Readable**: Signatures displayed in human readable format

### Data Integrity (ALCOA+)
Full implementation of ALCOA+ principles:

- **Attributable**: Clear user attribution with electronic signatures
- **Legible**: Human readable format with proper validation
- **Contemporaneous**: Real-time data capture with accurate timestamps
- **Original**: Source data preservation with complete audit trail
- **Accurate**: Validation rules and comprehensive data integrity checks
- **Complete**: Comprehensive data capture including metadata
- **Consistent**: Standardized data formats and validation
- **Enduring**: Permanent record retention with backup capabilities
- **Available**: Accessible throughout record lifecycle

## DocTypes and Features

The module implements 13 DocTypes organized into main DocTypes and child table DocTypes:

### Main DocTypes (4)

#### 1. SPC Audit Trail
**Purpose**: Immutable audit records meeting FDA 21 CFR Part 11 requirements

**Key Fields**:
- Record ID (unique identifier)
- Timestamp (exact date/time of action)
- User ID (user performing action)
- Action Type (Create, Read, Update, Delete, Print, Export, Sign, Approve, Reject)
- Session Information (IP address, computer name, browser info)
- Data Integrity (checksums, hash values, tamper evidence)

**Compliance Features**:
- Immutable records with no write permissions after creation
- Comprehensive tracking of all CRUD operations
- Tamper detection using checksums and cryptographic hashes
- Complete session traceability
- Electronic signature integration

#### 2. SPC Electronic Signature
**Purpose**: Comprehensive electronic signature management compliant with FDA requirements

**Key Fields**:
- Signature ID and document information
- Authentication methods (Password, Biometric, Token, Digital Certificate, Multi-Factor)
- Signature meaning (Authored, Reviewed, Approved, Witnessed, etc.)
- Verification methods and witness signatures
- Cryptographic components (signature hash, certificate serial number)

**Compliance Features**:
- Multiple authentication methods support
- Clear signature meaning indication
- Multi-factor authentication for enhanced security
- Witness signature support
- Certificate management and tracking
- JSON-formatted signature components

#### 3. SPC Batch Record
**Purpose**: Comprehensive batch manufacturing record management with complete traceability

**Key Fields**:
- Batch identification (number, product code, plant, production date)
- Quality data (parameters, test results, specifications compliance)
- Personnel (production supervisor, quality inspector, approvers)
- Traceability (raw materials, equipment, environmental conditions)
- Release management (status, dates, shelf life)

**Compliance Features**:
- Complete traceability from raw materials to finished product
- Role-based personnel accountability
- Equipment calibration status tracking
- Environmental conditions documentation
- Deviation integration
- Change control integration
- GMP and CFR Part 211 compliance flags

#### 4. SPC Deviation
**Purpose**: Comprehensive deviation lifecycle management with CAPA tracking

**Key Fields**:
- Identification (deviation number, type, severity)
- Investigation details (root cause analysis, team, timeline)
- CAPA management (corrective/preventive actions)
- Regulatory reporting (reportable status, FDA reports)
- Closure management (status, approvals, lessons learned)

**Compliance Features**:
- Automated deviation numbering
- Investigation timeline enforcement (30 days for critical)
- CAPA integration for major/critical deviations
- Regulatory reporting automation
- Customer notification tracking
- QA review and approval requirements

### Child Table DocTypes (9)

#### 5. SPC Batch Parameter
**Purpose**: Quality parameter tracking during batch production
- Parameter name, test method, specifications
- Results with pass/fail determination
- Units and measurement data

#### 6. SPC Batch Deviation
**Purpose**: Links deviations to specific batches
- Deviation number reference
- Impact assessment on batch
- Resolution status tracking

#### 7. SPC Raw Material
**Purpose**: Raw material traceability
- Material code and lot numbers
- Quantity used with precision
- Expiry dates and supplier information

#### 8. SPC Equipment
**Purpose**: Equipment usage and calibration tracking
- Equipment identification and names
- Calibration status and dates
- Usage hours tracking

#### 9. SPC Environment
**Purpose**: Environmental conditions monitoring
- Environmental parameters (temperature, humidity, pressure, etc.)
- Specifications and actual values
- Compliance status and monitoring frequency

#### 10. SPC Change Control
**Purpose**: Change control documentation
- Change control numbers and descriptions
- Change types (temporary, permanent, emergency)
- Approval status tracking

#### 11. Deviation Team Member
**Purpose**: Investigation team composition
- Team member roles and expertise
- Department and responsibility assignment

#### 12. Deviation Timeline
**Purpose**: Investigation milestone tracking
- Milestone definitions and dates
- Responsible persons and status
- Progress tracking and comments

#### 13. Deviation CAPA Action
**Purpose**: CAPA tracking and management
- Action descriptions and types
- Responsibility assignment and timelines
- Effectiveness verification and closure

## Validation Scripts

The `validation_scripts.py` file implements comprehensive FDA 21 CFR Part 11 validation framework:

### Audit Trail Capture System
```python
def capture_audit_trail(doc, method):
    """
    Universal audit trail capture for all document operations
    - Captures all CRUD operations across all DocTypes
    - Records comprehensive metadata including session information
    - Generates MD5 checksums and SHA-256 hashes for tamper detection
    - Tracks old and new values for field modifications
    """
```

### Electronic Signature Validation
```python
def validate_electronic_signature(self):
    """
    Comprehensive electronic signature validation
    - Validates signature components (ID, credentials, meaning)
    - Generates SHA-256 hashes for signature integrity
    - Sets CFR Part 11 compliance flags automatically
    - Creates JSON-formatted signature components
    """
```

### ALCOA+ Data Integrity Validation
```python
def validate_alcoa_plus_compliance(doc):
    """
    Implements ALCOA+ data integrity principles
    - Attributable: User attribution with electronic signatures
    - Legible: Meaningful content validation (minimum 10 characters)
    - Contemporaneous: Timestamp validity within 5-minute tolerance
    - Original: Source data preservation with audit trails
    - Accurate: Validation rules and integrity checks
    - Complete: Comprehensive data capture including metadata
    - Consistent: Standardized formats and validation
    - Enduring: Permanent retention with backup status
    - Available: Accessibility throughout lifecycle
    """
```

### DocType-Specific Validations

#### Batch Record Validation
- Personnel requirements based on batch status
- Specification compliance validation
- Data integrity verification upon release
- Status progression enforcement

#### Deviation Validation
- Automatic unique numbering generation
- Timeline enforcement (30 days for critical deviations)
- CAPA requirements for major/critical deviations
- Regulatory reporting automation

## Audit Trail Capabilities

### Comprehensive Activity Tracking
The audit trail system provides complete traceability through:

- **Universal Coverage**: All document operations across all DocTypes
- **Detailed Metadata**: Timestamp, user, action type, IP address, browser, session ID
- **Change Tracking**: Old and new values for all field modifications
- **System Information**: Complete session and system context
- **Integrity Protection**: MD5 checksums and SHA-256 hashes

### Tamper Detection
Advanced security features include:
- Cryptographic hash validation
- Checksum verification
- Tamper evidence flags
- Immutable record structure
- Backup status tracking

### Audit Trail Reports
Automated reporting capabilities:
- Daily compliance checks with email notifications
- Weekly audit trail summaries
- Investigation timeline monitoring
- Critical document verification
- Overdue CAPA tracking

## Electronic Signature Features

### Authentication Methods
Support for multiple authentication methods:
- **Password-based**: Traditional username/password
- **Biometric**: Fingerprint, retinal, or other biometric methods
- **Token-based**: Hardware or software tokens
- **Digital Certificate**: PKI-based digital certificates
- **Multi-Factor**: Combination of multiple methods

### Signature Components
Complete signature implementation includes:
- Printed name of signer
- Date and time of signing
- Meaning of signature (purpose)
- User credentials verification
- Witness signature support when required

### Signature Meanings
Predefined signature meanings for regulatory clarity:
- Authored
- Reviewed
- Approved
- Witnessed
- Verified
- Released
- Rejected

### Cryptographic Security
Advanced security features:
- SHA-256 signature hash generation
- Certificate serial number tracking
- Expiration date management
- Non-repudiation capabilities
- CFR Part 11 compliance validation

## Installation and Configuration

### Prerequisites
- ERPNext version 14.0 or later
- Administrator access to ERPNext instance
- Understanding of ERPNext DocType customization
- FDA 21 CFR Part 11 compliance knowledge

### Installation Steps

#### 1. DocType Import
```bash
# Import main DocTypes first
bench import-doc --path="path/to/doctypes/spc_audit_trail.json"
bench import-doc --path="path/to/doctypes/spc_electronic_signature.json"
bench import-doc --path="path/to/doctypes/spc_batch_record.json"
bench import-doc --path="path/to/doctypes/spc_deviation.json"

# Import child table DocTypes
bench import-doc --path="path/to/doctypes/deviation_capa_action.json"
bench import-doc --path="path/to/doctypes/deviation_team_member.json"
# ... continue for all child tables
```

#### 2. Permission Configuration
Set up role-based permissions with proper segregation of duties:

```python
# Example permission setup
roles = [
    'Quality Manager',
    'Production Supervisor', 
    'Quality Inspector',
    'FDA Compliance Officer',
    'System Administrator'
]

# Configure permissions for each DocType
for doctype in doctypes:
    setup_doctype_permissions(doctype, roles)
```

#### 3. Validation Scripts Implementation
Option A: Custom App (Recommended)
```bash
bench new-app fda_compliance
# Add validation scripts to hooks.py
```

Option B: Custom Scripts
```python
# Add validation scripts via ERPNext interface
# Custom Scripts > New Custom Script
```

#### 4. Electronic Signature Setup
Configure authentication methods and certificate management:
```python
# Electronic signature configuration
signature_config = {
    'authentication_methods': ['Password', 'Digital Certificate', 'Multi-Factor'],
    'certificate_validation': True,
    'witness_signature_required': False,
    'signature_timeout': 300  # 5 minutes
}
```

#### 5. Audit Trail Automation
Register hooks for automatic audit trail capture:
```python
# hooks.py
doc_events = {
    "*": {
        "after_insert": "fda_compliance.validation_scripts.capture_audit_trail",
        "on_update": "fda_compliance.validation_scripts.capture_audit_trail",
        "on_cancel": "fda_compliance.validation_scripts.capture_audit_trail",
        "on_trash": "fda_compliance.validation_scripts.capture_audit_trail"
    }
}
```

#### 6. Scheduled Jobs Configuration
Set up automated compliance monitoring:
```python
# Configure scheduled jobs
scheduler_events = {
    "daily": [
        "fda_compliance.validation_scripts.daily_compliance_check"
    ],
    "weekly": [
        "fda_compliance.validation_scripts.weekly_audit_summary"
    ]
}
```

### Configuration Parameters

#### System Settings
```python
# FDA Compliance Settings
FDA_COMPLIANCE_SETTINGS = {
    'audit_trail_retention_years': 10,
    'signature_timeout_minutes': 5,
    'investigation_timeline_days': 30,
    'backup_frequency_hours': 24,
    'tamper_check_frequency_hours': 1
}
```

#### User Role Configuration
```python
# Role-based access control
USER_ROLES = {
    'Quality Manager': ['read', 'write', 'submit', 'cancel', 'amend'],
    'Production Supervisor': ['read', 'write', 'submit'],
    'Quality Inspector': ['read', 'write'],
    'FDA Compliance Officer': ['read', 'export', 'print'],
    'System Administrator': ['read', 'write', 'delete', 'import', 'export']
}
```

## Compliance Verification

### Installation Qualification (IQ)
Verify system installation meets specifications:

#### IQ Checklist
- [ ] All 13 DocTypes imported successfully
- [ ] Validation scripts installed and active
- [ ] Permissions configured correctly
- [ ] Electronic signature setup completed
- [ ] Audit trail automation functional
- [ ] Scheduled jobs configured
- [ ] Backup procedures implemented

#### IQ Testing Script
```python
def installation_qualification():
    """
    Automated IQ testing script
    Verifies all system components are properly installed
    """
    results = {}
    
    # Test DocType installation
    results['doctypes'] = test_doctype_installation()
    
    # Test validation scripts
    results['validation'] = test_validation_scripts()
    
    # Test permissions
    results['permissions'] = test_permission_setup()
    
    # Test electronic signatures
    results['signatures'] = test_electronic_signatures()
    
    # Test audit trail
    results['audit_trail'] = test_audit_trail()
    
    return results
```

### Operational Qualification (OQ)
Verify functional requirements are met:

#### OQ Test Cases
1. **Audit Trail Functionality**
   - Create, update, delete operations logged
   - Tamper detection working
   - Hash generation functional

2. **Electronic Signature Validation**
   - Signature components captured
   - Authentication methods working
   - CFR Part 11 compliance flags set

3. **Batch Record Management**
   - Complete traceability functional
   - Quality parameter tracking
   - Personnel signature requirements

4. **Deviation Management**
   - Automatic numbering generation
   - Investigation timeline enforcement
   - CAPA integration working

#### OQ Testing Script
```python
def operational_qualification():
    """
    Comprehensive OQ testing
    Tests all functional requirements
    """
    test_results = []
    
    # Test each functional area
    test_results.append(test_audit_trail_functionality())
    test_results.append(test_electronic_signatures())
    test_results.append(test_batch_records())
    test_results.append(test_deviation_management())
    test_results.append(test_data_integrity())
    
    return generate_oq_report(test_results)
```

### Performance Qualification (PQ)
Verify system performance under actual conditions:

#### PQ Performance Metrics
- Response time for audit trail queries
- Electronic signature processing speed
- Report generation performance
- Data integrity check efficiency
- Concurrent user support

#### PQ Testing Script
```python
def performance_qualification():
    """
    Performance testing under actual conditions
    Tests system performance with realistic data volumes
    """
    performance_metrics = {}
    
    # Load testing
    performance_metrics['load_test'] = perform_load_testing()
    
    # Stress testing
    performance_metrics['stress_test'] = perform_stress_testing()
    
    # Volume testing
    performance_metrics['volume_test'] = perform_volume_testing()
    
    return performance_metrics
```

### Validation Documentation

#### Required Documentation
1. **Validation Master Plan**: Overall validation strategy
2. **System Requirements Specification**: Detailed functional requirements
3. **Installation Qualification Protocol**: IQ procedures and results
4. **Operational Qualification Protocol**: OQ procedures and results
5. **Performance Qualification Protocol**: PQ procedures and results
6. **Validation Summary Report**: Overall validation conclusion

#### Documentation Templates
```markdown
# Validation Summary Report Template

## Executive Summary
- System description
- Validation approach
- Key findings
- Compliance conclusion

## Validation Activities
- IQ Results: [Pass/Fail]
- OQ Results: [Pass/Fail] 
- PQ Results: [Pass/Fail]

## Compliance Assessment
- FDA 21 CFR Part 11 compliance: [Compliant/Non-Compliant]
- Data integrity (ALCOA+): [Compliant/Non-Compliant]
- Audit trail requirements: [Compliant/Non-Compliant]

## Recommendations
- Approved for production use
- Required corrective actions
- Ongoing monitoring requirements
```

## Regulatory Guidelines

### FDA 21 CFR Part 11 Requirements

#### Electronic Records (§ 11.10)
**Requirement**: Controls for closed systems to ensure authenticity, integrity, and confidentiality

**Implementation**:
- ✅ Validation of systems to ensure accuracy, reliability, consistent intended performance
- ✅ Generation of accurate and complete copies for inspection, review, and copying
- ✅ Protection of records throughout retention period
- ✅ Limiting system access to authorized individuals
- ✅ Use of secure, computer-generated, time-stamped audit trails
- ✅ Use of appropriate controls over systems documentation

#### Electronic Signatures (§ 11.50)
**Requirement**: Signature manifestations and controls

**Implementation**:
- ✅ Unique signature representation for each individual
- ✅ Verification of signature genuineness before use
- ✅ Control over signature use by individual
- ✅ Direct linkage between signature and electronic record

#### Audit Trail Requirements (§ 11.10(e))
**Requirement**: Computer-generated, time-stamped audit trails

**Implementation**:
- ✅ Independently record date and time of operator entries and actions
- ✅ Record user identification for all entries and actions
- ✅ Capture record changes without obscuring previously recorded information
- ✅ Ensure audit trail availability for review and copying

### Data Integrity Guidelines

#### ALCOA+ Principles Implementation

**Attributable**
- User identification required for all actions
- Electronic signatures with user credentials
- Session tracking with IP and browser information

**Legible**
- Human readable data formats
- Clear field labels and descriptions
- Standardized data presentation

**Contemporaneous**
- Real-time data capture
- Accurate timestamps with timezone information
- Validation of entry timing

**Original**
- Source data preservation
- Complete audit trail of changes
- Raw data accessibility

**Accurate**
- Validation rules for data entry
- Specification compliance checking
- Error detection and correction

**Complete**
- Comprehensive data capture
- Metadata inclusion
- Relationship documentation

**Consistent**
- Standardized data formats
- Uniform validation rules
- Consistent user interfaces

**Enduring**
- Permanent record retention
- Backup and archive procedures
- Long-term accessibility

**Available**
- Controlled access throughout lifecycle
- Export capabilities for regulatory review
- Search and retrieval functionality

### Best Practices

#### System Administration
- Regular backup procedures (daily recommended)
- User access reviews (quarterly)
- Audit trail monitoring (daily)
- Performance monitoring (continuous)
- Security assessments (annually)

#### User Training
- Initial FDA compliance training
- System-specific training on module functionality
- Regular refresher training (annually)
- Change control training when updates occur
- Documentation of training completion

#### Change Control
- Formal change control procedures
- Impact assessment for all changes
- Testing requirements for modifications
- Approval workflows for changes
- Documentation of change rationale

#### Periodic Review
- Monthly compliance dashboard review
- Quarterly audit trail analysis
- Annual system revalidation
- Regulatory update assessments
- Continuous improvement initiatives

## Usage Examples

### Creating a Batch Record

```python
# Example: Creating a new batch record
batch_record = frappe.new_doc('SPC Batch Record')
batch_record.update({
    'batch_number': 'BTH-2025-001',
    'product_code': 'PROD-001',
    'plant': 'Plant A',
    'production_date': '2025-09-17',
    'batch_size': 1000,
    'production_supervisor': 'user@company.com',
    'quality_inspector': 'qa@company.com'
})

# Add raw materials
batch_record.append('raw_materials', {
    'material_code': 'RM-001',
    'lot_number': 'LOT-2025-001',
    'quantity_used': 100.5,
    'uom': 'kg'
})

# Add quality parameters
batch_record.append('batch_parameters', {
    'parameter_name': 'Moisture Content',
    'test_method': 'TM-001',
    'specification': '≤ 5%',
    'result': '3.2%',
    'pass_fail': 'Pass'
})

batch_record.save()
```

### Electronic Signature Application

```python
# Example: Applying electronic signature
signature = frappe.new_doc('SPC Electronic Signature')
signature.update({
    'signature_id': 'SIG-2025-001',
    'document_type': 'SPC Batch Record',
    'document_name': 'BTH-2025-001',
    'signer': 'qa@company.com',
    'signature_method': 'Digital Certificate',
    'signature_meaning': 'Approved',
    'user_credential_verified': 1
})

signature.save()
```

### Deviation Management

```python
# Example: Creating a deviation
deviation = frappe.new_doc('SPC Deviation')
deviation.update({
    'deviation_type': 'Quality',
    'severity': 'Major',
    'plant': 'Plant A',
    'department': 'Production',
    'description': 'Temperature excursion during batch processing',
    'immediate_action': 'Batch placed on hold for investigation',
    'impact_assessment': 'Potential impact on product quality'
})

# Add investigation team
deviation.append('investigation_team', {
    'team_member': 'investigator@company.com',
    'role_in_investigation': 'Lead Investigator',
    'department': 'Quality Assurance'
})

# Add CAPA actions
deviation.append('capa_actions', {
    'action_description': 'Review and update temperature monitoring procedures',
    'action_type': 'Corrective',
    'responsible_person': 'qa.manager@company.com',
    'target_completion_date': '2025-10-17'
})

deviation.save()
```

### Audit Trail Query

```python
# Example: Querying audit trail
audit_records = frappe.get_all('SPC Audit Trail',
    filters={
        'table_name': 'SPC Batch Record',
        'record_name': 'BTH-2025-001',
        'timestamp': ['between', ['2025-09-17 00:00:00', '2025-09-17 23:59:59']]
    },
    fields=['*'],
    order_by='timestamp asc'
)

for record in audit_records:
    print(f"Action: {record.action_type} by {record.user_id} at {record.timestamp}")
```

## Maintenance and Support

### Daily Maintenance Tasks

```python
# Daily compliance check script
def daily_compliance_check():
    """
    Automated daily compliance monitoring
    """
    # Check audit trail integrity
    audit_integrity = check_audit_trail_integrity()
    
    # Verify electronic signatures
    signature_status = verify_daily_signatures()
    
    # Monitor overdue investigations
    overdue_investigations = check_overdue_investigations()
    
    # Check critical document signatures
    unsigned_critical_docs = check_unsigned_critical_documents()
    
    # Generate daily report
    generate_daily_compliance_report({
        'audit_integrity': audit_integrity,
        'signatures': signature_status,
        'investigations': overdue_investigations,
        'critical_docs': unsigned_critical_docs
    })
```

### Weekly Maintenance Tasks

```python
# Weekly audit trail summary
def weekly_audit_summary():
    """
    Comprehensive weekly audit reporting
    """
    # Audit trail statistics
    audit_stats = generate_audit_statistics()
    
    # User activity summary
    user_activity = summarize_user_activity()
    
    # Deviation trends
    deviation_trends = analyze_deviation_trends()
    
    # Compliance metrics
    compliance_metrics = calculate_compliance_metrics()
    
    # Generate weekly report
    generate_weekly_report({
        'audit_stats': audit_stats,
        'user_activity': user_activity,
        'deviations': deviation_trends,
        'compliance': compliance_metrics
    })
```

### Monthly Maintenance Tasks

- User access review and certification
- Compliance dashboard analysis
- System performance evaluation
- Backup verification and testing
- Documentation updates

### Annual Maintenance Tasks

- Full system revalidation
- Regulatory requirement updates
- SOP review and updates
- Training program evaluation
- Risk assessment updates

### Support Contacts

For technical support and compliance questions:

- **Technical Support**: Contact your system administrator
- **Regulatory Compliance**: Contact your FDA compliance officer
- **Training**: Contact your quality training coordinator
- **Documentation**: Refer to the complete documentation package

### Troubleshooting

#### Common Issues and Solutions

**Audit Trail Not Capturing**
```python
# Check if hooks are properly registered
frappe.get_hooks('doc_events')

# Verify validation scripts are loaded
frappe.get_attr('fda_compliance.validation_scripts.capture_audit_trail')
```

**Electronic Signature Validation Failing**
```python
# Check signature configuration
signature_settings = frappe.get_single('FDA Compliance Settings')

# Verify user credentials
user_credentials = frappe.get_doc('User', signature.signer)
```

**Performance Issues**
```python
# Check audit trail table size
audit_count = frappe.db.count('SPC Audit Trail')

# Review index usage
frappe.db.sql("SHOW INDEX FROM `tabSPC Audit Trail`")
```

## Contributing

### Development Guidelines

When contributing to the FDA Compliance module:

1. **Follow FDA Requirements**: All changes must maintain FDA 21 CFR Part 11 compliance
2. **Test Thoroughly**: Include comprehensive validation testing
3. **Document Changes**: Update documentation for all modifications
4. **Review Process**: All changes require quality assurance review
5. **Validation Impact**: Assess impact on existing validation

### Code Standards

- Follow ERPNext/Frappe coding standards
- Include comprehensive error handling
- Add detailed comments for compliance logic
- Implement proper logging for audit purposes
- Use type hints for better code documentation

### Testing Requirements

- Unit tests for all validation functions
- Integration tests for DocType relationships
- Performance tests for large data volumes
- Compliance tests for regulatory requirements
- User acceptance tests for workflows

### Documentation Requirements

- Update README for functional changes
- Modify installation guide for new requirements
- Update validation documentation
- Revise user training materials
- Maintain change control documentation

---

## License

This module is developed for FDA-regulated environments and must be used in compliance with applicable regulations. Ensure proper validation and qualification before production use.

## Disclaimer

This module is provided as-is for regulatory compliance purposes. Users are responsible for ensuring proper validation, qualification, and ongoing compliance with FDA requirements. Consult with regulatory experts and conduct thorough validation before production deployment.

---

**Document Information**
- Version: 1.0
- Last Updated: September 17, 2025
- Author: MiniMax Agent
- Classification: Technical Documentation