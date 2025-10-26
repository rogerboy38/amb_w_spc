# FDA 21 CFR Part 11 DocTypes - Installation Guide

This guide provides step-by-step instructions for installing and configuring the FDA compliant DocTypes in ERPNext.

## Prerequisites

- ERPNext version 14.0 or later
- Administrator access to ERPNext instance
- Basic understanding of ERPNext DocType customization
- FDA 21 CFR Part 11 compliance requirements knowledge

## Installation Steps

### Step 1: Import DocTypes

1. **Access DocType List**
   - Go to: `Setup > Customize > DocType`
   - Click on "Import" button

2. **Import Main DocTypes** (in this order):
   ```
   1. spc_audit_trail.json
   2. electronic_signature.json
   3. spc_batch_record.json
   4. deviation.json
   ```

3. **Import Child Table DocTypes**:
   ```
   1. spc_batch_parameter.json
   2. spc_batch_deviation.json
   3. spc_change_control.json
   4. spc_raw_material.json
   5. spc_equipment.json
   6. spc_environment.json
   7. deviation_team_member.json
   8. deviation_timeline.json
   9. deviation_capa_action.json
   ```

### Step 2: Configure Permissions

1. **Create Custom Roles** (if not already existing):
   ```
   - Quality Manager
   - Production Manager  
   - Manufacturing User
   - Auditor
   ```

2. **Assign Role Permissions**:
   - Go to each DocType
   - Click on "Permissions" 
   - Configure as per the permissions defined in JSON files
   - Ensure proper segregation of duties

### Step 3: Set Up Workflows (Recommended)

#### Electronic Signature Workflow
1. Create workflow: `Setup > Workflows > New Workflow`
2. Configure states:
   ```
   - Draft (allow_edit: 1)
   - Pending Verification (allow_edit: 0) 
   - Verified (allow_edit: 0)
   - Invalid (allow_edit: 0)
   ```
3. Configure transitions with appropriate role permissions

#### Deviation Workflow  
1. Create workflow for Deviation DocType
2. Configure states:
   ```
   - Open (allow_edit: 1)
   - Under Investigation (allow_edit: 1)
   - Pending CAPA (allow_edit: 1)
   - CAPA In Progress (allow_edit: 1)
   - Pending QA Review (allow_edit: 0)
   - Closed (allow_edit: 0)
   ```

#### SPC Batch Record Workflow
1. Create workflow for batch lifecycle
2. Configure states:
   ```
   - In Process (allow_edit: 1)
   - Complete (allow_edit: 0)
   - Approved (allow_edit: 0)  
   - Released (allow_edit: 0)
   - Rejected (allow_edit: 0)
   ```

### Step 4: Configure Validation Scripts

1. **Create Custom App** (recommended):
   ```bash
   bench new-app fda_compliance
   bench --site [site-name] install-app fda_compliance
   ```

2. **Add Validation Hooks**:
   - Copy `validation_scripts.py` to your custom app
   - Update `hooks.py` with the doc_events configuration
   - Include the path to your validation functions

3. **Alternative: Custom Scripts**:
   - Go to `Setup > Customize > Custom Script`
   - Create scripts for each DocType using relevant validation functions

### Step 5: Configure Electronic Signatures

1. **Enable Electronic Signatures**:
   - Go to `Setup > System Settings`
   - Enable "Allow Electronic Signature" if available
   - Configure signature timeout settings

2. **Create Signature Templates**:
   - Define standard signature meanings
   - Set up multi-factor authentication requirements
   - Configure certificate validation if using digital certificates

### Step 6: Set Up Audit Trail Automation

1. **Configure Automatic Capture**:
   - Implement audit trail hooks in custom app
   - Test audit trail generation for all operations
   - Verify tamper detection mechanisms

2. **Set Up Scheduled Jobs**:
   ```python
   # Add to hooks.py
   scheduler_events = {
       "daily": [
           "fda_compliance.validation_scripts.daily_compliance_check"
       ],
       "weekly": [
           "fda_compliance.validation_scripts.weekly_audit_trail_summary"
       ]
   }
   ```

### Step 7: Configure Data Integrity

1. **Enable Change Tracking**:
   - Ensure `track_changes: 1` is enabled for all DocTypes
   - Configure version control settings
   - Set up automatic backup procedures

2. **Implement Checksums**:
   - Configure automatic checksum generation
   - Set up hash validation procedures
   - Test tamper detection capabilities

### Step 8: Create Standard Operating Procedures (SOPs)

1. **Document Procedures**:
   - Electronic signature procedures
   - Audit trail review procedures  
   - Deviation investigation procedures
   - Data integrity procedures

2. **User Training Materials**:
   - Create training documentation
   - Develop user guides
   - Set up regular training schedules

## Configuration Checklist

### Technical Configuration
- [ ] All DocTypes imported successfully
- [ ] Permissions configured correctly
- [ ] Workflows implemented and tested
- [ ] Validation scripts active
- [ ] Audit trail capture working
- [ ] Electronic signatures functional
- [ ] Data integrity checks enabled
- [ ] Scheduled jobs configured
- [ ] Backup procedures in place

### Compliance Configuration  
- [ ] CFR Part 11 requirements mapped
- [ ] ALCOA+ principles implemented
- [ ] Signature meaning definitions clear
- [ ] User authentication configured
- [ ] Record retention policies defined
- [ ] Regulatory reporting procedures established

### Testing and Validation
- [ ] User acceptance testing completed
- [ ] Security testing performed
- [ ] Compliance validation documented
- [ ] Performance testing completed
- [ ] Disaster recovery tested

## Post-Installation Tasks

### 1. System Validation
- Conduct Installation Qualification (IQ)
- Perform Operational Qualification (OQ)
- Execute Performance Qualification (PQ)
- Document all validation activities

### 2. User Training
- Train all users on new procedures
- Conduct compliance awareness sessions
- Provide ongoing support documentation
- Schedule regular refresher training

### 3. Monitoring and Maintenance
- Set up compliance monitoring dashboards
- Schedule regular system reviews
- Implement change control procedures
- Plan for periodic revalidation

## Troubleshooting

### Common Issues

**DocType Import Failures**:
- Check for naming conflicts
- Verify JSON syntax
- Ensure proper field dependencies

**Permission Errors**:
- Verify role assignments
- Check permission inheritance
- Review custom permission settings

**Validation Script Errors**:
- Check Python syntax
- Verify import statements
- Test with sample data

**Electronic Signature Issues**:
- Verify user authentication
- Check signature validation logic
- Review certificate configurations

### Getting Support

1. **Documentation**: Review ERPNext documentation
2. **Community**: ERPNext community forums
3. **Professional Services**: Consider professional consulting
4. **Regulatory Experts**: Consult with FDA compliance specialists

## Maintenance Schedule

### Daily
- Monitor audit trail generation
- Review compliance dashboard
- Check for system errors

### Weekly  
- Review audit trail summary
- Analyze deviation trends
- Monitor CAPA progress

### Monthly
- Compliance assessment review
- User access review
- System performance evaluation

### Quarterly
- Regulatory compliance audit
- Validation documentation review
- User training assessment

### Annually
- Full system revalidation
- SOP review and update
- Compliance program evaluation

## Regulatory Considerations

### FDA Inspection Readiness
- Maintain current validation documentation
- Keep audit trails readily accessible
- Ensure electronic records are human readable
- Have procedures for record recreation

### Change Control
- Implement formal change control procedures
- Validate all system changes
- Maintain change documentation
- Assess impact on compliance

### Records Management
- Establish record retention policies
- Implement secure archive procedures
- Ensure record accessibility
- Plan for technology obsolescence

## Conclusion

Following this installation guide will establish a solid foundation for FDA 21 CFR Part 11 compliance in ERPNext. However, remember that compliance is an ongoing process requiring continuous monitoring, validation, and improvement.

For specific regulatory questions or complex implementation scenarios, consult with qualified regulatory affairs professionals and validation experts.
