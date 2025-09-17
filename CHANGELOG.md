# Changelog

All notable changes to the AMB_W_SPC (AMB Working Statistical Process Control) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Dashboard widgets for real-time monitoring and visualization
- Advanced statistical analysis tools and machine learning integration
- Mobile app integration for field-based quality management
- API endpoints for external system integration
- IoT sensor data integration for automated data collection
- Industry-specific templates and configurations
- Advanced chart types and visualization options
- Predictive analytics for proactive quality management

## [2.1.0] - 2025-09-10

### Added
- **SPC Quality Management Module**: Complete quality management system with real-time monitoring
  - SPC Alert DocType with Western Electric Rules support (8 control chart rules)
  - SPC Corrective Action DocType with structured problem-solving methodologies
  - SPC Process Capability DocType with automated Cp, Cpk, Pp, Ppk calculations
  - SPC Report DocType with automated generation and multi-format output
  - 8 child table DocTypes for comprehensive data relationships
  - 3 workflow configurations for process automation
  - 6 notification configurations for multi-channel alerts
- **Comprehensive Notification System**: Email, SMS, and dashboard notifications
- **Role-based Security Model**: Quality Manager, Production Manager, Quality Engineer, Production User roles
- **Real-time Alert System**: Automated detection and escalation for process deviations
- **Statistical Analysis Tools**: Process capability studies with normality testing
- **Automated Reporting**: Scheduled report generation with customizable parameters

### Enhanced
- **Core SPC Module**: Improved statistical calculations and control chart management
- **FDA Compliance Module**: Enhanced audit trail capabilities and electronic signature validation
- **Performance Optimization**: Database design optimized for large-scale data collection
- **Integration Framework**: Complete ERPNext master data integration

### Fixed
- Data integrity validation improvements in audit trail capture
- Electronic signature hash generation reliability
- Control chart violation detection accuracy
- Workflow transition validation in corrective action management

## [2.0.0] - 2025-08-15

### Added
- **FDA Compliance Module**: Complete FDA 21 CFR Part 11 implementation
  - SPC Audit Trail DocType with immutable audit records
  - SPC Electronic Signature DocType with multi-factor authentication
  - SPC Batch Record DocType with comprehensive traceability
  - SPC Deviation DocType with integrated CAPA management
  - 9 child table DocTypes for regulatory compliance support
  - ALCOA+ data integrity validation framework
  - Cryptographic data integrity verification
  - Comprehensive deviation lifecycle management
- **Electronic Signature System**: Multi-method authentication (Password, Biometric, Token, Digital Certificate)
- **Batch Manufacturing Records**: Complete traceability from raw materials to finished products
- **Deviation Management**: Automated numbering, investigation timelines, and CAPA integration
- **Regulatory Reporting**: Automatic flagging and timeline management for critical deviations

### Security
- **Immutable Audit Trails**: No write permissions after creation for regulatory compliance
- **Tamper Detection**: MD5 checksums and SHA-256 hashes for data integrity
- **Session Traceability**: Complete session tracking including IP, browser, and computer details
- **Multi-Factor Authentication**: Enhanced security for critical operations

### Breaking Changes
- **Database Schema**: Major restructuring for FDA compliance requirements
- **API Changes**: New validation endpoints for regulatory compliance
- **Permission Model**: Updated role-based permissions for compliance workflows

## [1.5.0] - 2025-07-20

### Added
- **Bilingual Support**: English and Spanish language support
- **Multi-plant Configuration**: Support for multiple manufacturing facilities
- **Advanced Control Charts**: CUSUM and EWMA chart types
- **Process Capability Indices**: Automated Cp, Cpk, Pp, Ppk calculations
- **Client-side Validation**: Enhanced form validation and user experience
- **Data Source Integration**: Support for PLC, SCADA, and LIMS data sources

### Enhanced
- **Statistical Calculations**: Improved accuracy in X-bar, R-values, and moving averages
- **Control Limit Management**: Dynamic control limits based on historical data
- **Alert System**: Enhanced Western Electric and Nelson rules implementation
- **Performance**: Optimized database queries for large datasets

### Fixed
- Parameter code validation regex issues
- Control chart center line calculation accuracy
- Time zone handling in timestamp fields
- Data point validation for out-of-specification values

## [1.0.0] - 2025-06-01

### Added
- **Core SPC Module**: Complete Statistical Process Control implementation
  - SPC Parameter Master DocType with comprehensive parameter management
  - SPC Data Point DocType with real-time statistical calculations
  - SPC Control Chart DocType supporting 8 chart types
  - SPC Specification DocType with quality limits and capability targets
  - 4 child table DocTypes for parameter relationships
- **Control Chart Types**: X-bar R, Individual-MR, p-chart, c-chart, u-chart, np-chart
- **Statistical Engine**: Real-time X-bar, R-values, moving averages calculations
- **Validation Framework**: Comprehensive server-side and client-side validation
- **Setup Scripts**: Automated system configuration and default data creation
- **Multi-source Data Collection**: Manual, PLC, Bot, SCADA, LIMS integration
- **Automated Alert System**: Western Electric and Nelson rules implementation

### Technical
- **ERPNext Compatibility**: Full integration with ERPNext V15
- **Production Ready**: Complete SPC functionality for manufacturing environments
- **Regulatory Compliance**: Foundation for Six Sigma and regulated industry requirements
- **Audit Trail**: Complete change tracking and validation history
- **Performance**: Optimized for high-volume data collection and real-time processing

### Documentation
- **Installation Guide**: Complete setup and configuration documentation
- **API Documentation**: Comprehensive API reference for all DocTypes
- **User Manual**: Step-by-step user guides for all functionality
- **Developer Guide**: Technical implementation details and customization guides

## [0.9.0-beta] - 2025-05-15

### Added
- **Beta Release**: Initial public beta with core SPC functionality
- **Basic Control Charts**: X-bar R and Individual-MR chart support
- **Parameter Management**: Basic parameter master data management
- **Data Collection**: Manual data entry with basic validation
- **Simple Alerting**: Basic out-of-control detection

### Known Issues
- Limited chart types available
- Basic validation rules only
- No multi-plant support
- Limited integration capabilities

## [0.5.0-alpha] - 2025-04-01

### Added
- **Alpha Release**: Initial development version
- **Core Framework**: Basic ERPNext/Frappe application structure
- **Parameter Definition**: Basic parameter master data model
- **Data Point Collection**: Simple measurement data capture
- **Development Environment**: Setup for continued development

### Technical
- **Frappe Framework**: Built on Frappe v14+ foundation
- **Database Design**: Initial schema for SPC data model
- **Basic Validation**: Essential data validation rules
- **Testing Framework**: Unit tests for core functionality

---

## Release Notes Guidelines

### Version Numbering
- **Major (X.0.0)**: Breaking changes, major new features, architectural changes
- **Minor (0.X.0)**: New features, enhancements, non-breaking changes
- **Patch (0.0.X)**: Bug fixes, documentation updates, minor improvements

### Change Categories
- **Added**: New features and functionality
- **Changed**: Changes in existing functionality
- **Deprecated**: Features that will be removed in future versions
- **Removed**: Features removed in this version
- **Fixed**: Bug fixes and issue resolutions
- **Security**: Security improvements and vulnerability fixes
- **Enhanced**: Improvements to existing features
- **Breaking Changes**: Changes that require user action or may break existing implementations

### Compatibility Matrix

| AMB_W_SPC Version | ERPNext Version | Frappe Version | Python Version |
|------------------|-----------------|----------------|-----------------|
| 2.1.0+           | v15+            | v15+           | 3.8+           |
| 2.0.0            | v14-v15         | v14-v15        | 3.7+           |
| 1.x.x            | v14+            | v14+           | 3.7+           |
| 0.x.x            | v14             | v14            | 3.6+           |

### Migration Notes

#### Upgrading to v2.1.0
- Run database migrations for new quality management tables
- Update user permissions for new DocTypes
- Configure notification settings for alert system
- Review and update workflow configurations

#### Upgrading to v2.0.0
- **BREAKING**: Major database schema changes for FDA compliance
- Backup all data before upgrading
- Run FDA compliance migration scripts
- Update user roles and permissions
- Configure electronic signature settings
- Review audit trail configurations

#### Upgrading to v1.5.0
- Update language preferences for bilingual support
- Configure multi-plant settings if applicable
- Review control chart configurations for new types
- Update data source configurations

### Support and Compatibility

- **Current Stable**: v2.1.0
- **LTS Support**: v2.0.0 (supported until 2026-08-15)
- **Minimum ERPNext Version**: v14
- **Recommended ERPNext Version**: v15+

For upgrade assistance and compatibility questions, please refer to the documentation or contact the development team.