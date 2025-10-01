# SPC ERPNext System Integration Package

This comprehensive package contains all the necessary components to deploy a complete Statistical Process Control (SPC) system in ERPNext with full FDA compliance, plant automation, and quality management capabilities.

## Package Contents

### 1. DocType Relationships Matrix (`doctypes_relationships.json`)
Complete mapping of all 25+ DocTypes with their parent-child relationships, field links, and data flow connections.

### 2. Data Integrity Validation Rules (`validations/`)
Custom validation scripts for each DocType ensuring data integrity, statistical validation, and cross-DocType consistency.

### 3. Role-Based Permission Structure (`permissions/`)
Comprehensive permission matrix for all 6 user roles with plant-based access restrictions and API controls.

### 4. Custom Automation Scripts (`scripts/`)
Automated workflows for alert generation, statistical calculations, electronic signatures, and bot integrations.

### 5. ERPNext Import Package (`installation/`)
Master installation JSON with fixtures, setup scripts, and validation procedures for one-click deployment.

### 6. System Integration Points (`workflows/`)
Connections to existing ERPNext modules, dashboard configurations, and PLC integration APIs.

## Quick Installation

```bash
# 1. Install all DocTypes
frappe --site your-site install-app spc_system

# 2. Run setup fixtures
frappe --site your-site execute spc_system.setup_fixtures

# 3. Apply permissions
frappe --site your-site execute spc_system.apply_permissions

# 4. Install validation rules
frappe --site your-site execute spc_system.install_validations
```

## System Architecture

```
Plant Configuration (Root)
├── Workstation (Equipment Layer)
│   ├── SPC Parameter Master (Parameters)
│   │   ├── SPC Specification (Limits)
│   │   └── SPC Data Point (Measurements)
│   │       ├── SPC Alert (Exceptions)
│   │       └── SPC Control Chart (Visualization)
│   └── Bot User Configuration (Automation)
│       └── PLC Integration (Hardware)
├── Quality Management
│   ├── Process Capability (Analysis)
│   ├── SPC Report (Reporting)
│   └── Corrective Action (CAPA)
└── FDA Compliance
    ├── Deviation (Non-conformance)
    ├── Electronic Signature (Approval)
    └── SPC Audit Trail (Traceability)
```

## User Roles

1. **Quality User** - Quality engineers and managers
2. **Inspector User** - Quality inspectors and technicians
3. **Manufacturing User** - Production operators and supervisors
4. **Warehouse Bot User** - Automated warehouse systems
5. **Workstation Bot User** - Manufacturing equipment integration
6. **Weight Bot User** - Automated weighing systems

## Key Features

- **Real-time SPC Monitoring** - Live data collection and statistical analysis
- **FDA 21 CFR Part 11 Compliance** - Electronic signatures and audit trails
- **Plant-based Multi-tenancy** - Isolated data access per manufacturing facility
- **Automated Alert System** - Real-time notifications for out-of-specification events
- **Statistical Process Control** - X-bar, R-charts, Cpk calculations
- **CAPA Integration** - Corrective and preventive action workflows
- **PLC Integration** - Direct equipment data collection
- **Comprehensive Reporting** - Statistical analysis and compliance reports

## Support

For installation support and customization requests, refer to the individual module documentation in each subdirectory.
