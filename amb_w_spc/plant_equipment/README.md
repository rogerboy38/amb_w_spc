# Plant and Equipment Management DocTypes

Complete JSON DocType definitions for multi-plant SPC (Statistical Process Control) operations, designed for ERPNext implementation.

## Overview

This documentation provides comprehensive DocType definitions for managing plant and equipment configurations in a multi-plant manufacturing environment. The system supports data segregation, integration with PLCs, automated data collection, and quality control processes.

## DocType Hierarchy and Relationships

```
Plant Configuration (Master)
    ├── Workstation (Child)
    │   └── PLC Integration (Child)
    └── Bot User Configuration (Child)
```

## 1. Plant Configuration DocType

**File**: `plant_configuration.json`  
**Purpose**: Master configuration for manufacturing plants

### Key Features:
- **Multi-company support** with proper data segregation
- **Plant types**: Mix, Dry, Juice, Laboratory, Formulated
- **Time zone management** for global operations
- **Shift scheduling** (Single, Double, Triple, 24/7)
- **Integration settings** for database connections and API endpoints
- **Data retention policies** (30 days to permanent)
- **Audit trail** capabilities

### Core Fields:
- `plant_code`: Unique identifier (auto-naming field)
- `plant_name`: Select from predefined plant types
- `plant_type`: Production, Quality Control, Research, etc.
- `location`: Physical location
- `company`: Link to Company DocType
- `quality_manager`: Link to User DocType
- `plant_status`: Active, Inactive, Maintenance, Shutdown

### Integration Settings:
- `database_connection`: Connection string for plant database
- `api_endpoints`: JSON configuration for API endpoints
- `data_retention_policy`: Configurable retention periods
- `backup_frequency`: Hourly to Monthly options
- `sync_frequency`: Real-time to Daily options

## 2. Workstation DocType

**File**: `workstation.json`  
**Purpose**: Individual workstation/equipment configuration

### Key Features:
- **Equipment categorization** by type and department
- **Location tracking** with area, line, and position codes
- **Technical specifications** including PLC addressing
- **Maintenance scheduling** and calibration tracking
- **Quality specifications** and operating parameters
- **Safety protocols** and emergency procedures

### Core Fields:
- `workstation_code`: Unique identifier (auto-naming field)
- `workstation_name`: Descriptive name
- `plant`: Link to Plant Configuration
- `department`: Production, QC, Maintenance, etc.
- `equipment_type`: Mixer, Dryer, Extruder, Analyzer, etc.
- `plc_address`: PLC node address
- `communication_protocol`: OPC-UA, Ethernet/IP, Modbus, etc.

### Operational Settings:
- `operational_status`: Online, Offline, Error, Warning, etc.
- `maintenance_schedule`: Daily to Condition-Based
- `calibration_date`: Last calibration date
- `next_maintenance_date`: Scheduled maintenance
- `next_calibration_date`: Scheduled calibration

## 3. PLC Integration DocType

**File**: `plc_integration.json`  
**Purpose**: PLC communication and data mapping configuration

### Key Features:
- **Multi-PLC support** (Siemens S7-1500, Allen-Bradley MicroLogix 1500, etc.)
- **Protocol flexibility** (OPC-UA, Ethernet/IP, Modbus)
- **Security settings** with authentication and encryption
- **Data mapping** and validation rules
- **Connection monitoring** and auto-reconnect
- **Tag management** and parameter scaling

### Core Fields:
- `plc_name`: Unique identifier (auto-naming field)
- `plc_type`: Comprehensive list of supported PLC types
- `ip_address`: Network address
- `port`: Communication port (default 502)
- `protocol`: Communication protocol
- `plant`: Link to Plant Configuration
- `workstation`: Link to Workstation

### Communication Settings:
- `connection_timeout`: Timeout in milliseconds
- `retry_attempts`: Number of retry attempts
- `polling_rate`: Data polling interval
- `keepalive_interval`: Connection keepalive

### Security Features:
- `authentication_method`: None, Username/Password, Certificate, etc.
- `encryption_level`: None, Basic, SignAndEncrypt, etc.
- `ssl_enabled`: SSL/TLS support
- `certificates`: Certificate storage

### Data Management:
- `tag_list`: JSON configuration of monitored tags
- `parameter_mapping`: PLC to system parameter mapping
- `data_validation_rules`: Data validation and filtering
- `scaling_factors`: Unit conversion and scaling

## 4. Bot User Configuration DocType

**File**: `bot_user_configuration.json`  
**Purpose**: Automated data collection bot configuration

### Key Features:
- **Multiple bot types** (Data Collection, Monitoring, Analysis, etc.)
- **Flexible collection frequencies** (Real-time to Daily)
- **Authentication management** with API keys and tokens
- **Performance monitoring** with success rates and response times
- **Error handling** and retry configuration
- **Notification settings** and alert management

### Core Fields:
- `bot_name`: Unique identifier (auto-naming field)
- `bot_type`: Data Collection, Monitoring, Analysis, etc.
- `plant`: Link to Plant Configuration
- `workstation`: Optional specific workstation link
- `user_account`: Link to User DocType
- `bot_status`: Active, Inactive, Paused, Error, Maintenance

### Collection Settings:
- `collection_frequency`: Real-time to Daily options
- `parameters_collected`: JSON list of collected parameters
- `data_source`: PLC, SCADA, API, Database, etc.
- `collection_method`: Pull, Push, Subscription, Polling
- `batch_size`: Records per batch
- `buffer_size`: Maximum buffer capacity

### Authentication:
- `api_key`: Encrypted API key storage
- `permissions`: JSON permission list
- `access_level`: Read Only to Full Access
- `token_expiry`: Token expiration management
- `security_group`: Access control grouping

### Monitoring:
- `last_collection_time`: Last successful collection
- `collection_count`: Total successful collections
- `error_count`: Total errors
- `success_rate`: Performance percentage
- `average_response_time`: Performance metrics

## Field Relationships and Validation

### Inter-DocType Relationships:
1. **Plant Configuration** → **Workstation** (One-to-Many)
2. **Plant Configuration** → **Bot User Configuration** (One-to-Many)
3. **Workstation** → **PLC Integration** (One-to-Many)
4. **Workstation** → **Bot User Configuration** (One-to-Many)

### Data Segregation:
- Company-based data segregation in Plant Configuration
- Plant-based filtering in child DocTypes
- Role-based permissions (Quality Manager, Manufacturing Manager, Manufacturing User)

### Validation Rules:
- Unique constraints on primary identifier fields
- Required field validation for critical configuration items
- Select field options for standardized data entry
- Link field validation for maintaining referential integrity

## Permissions Structure

### Role-Based Access:
- **System Manager**: Full access to PLC Integration and Bot Configuration
- **Quality Manager**: Full access to Plant and Workstation configuration
- **Manufacturing Manager**: Full access to Plant and Workstation, read access to technical configs
- **Manufacturing User**: Read access with limited write permissions

### Security Features:
- Password fields for sensitive data (API keys, authentication)
- Read-only fields for system-generated data
- Track changes enabled for audit trails
- Search field optimization for performance

## Implementation Guidelines

### Setup Sequence:
1. Create Plant Configuration records
2. Configure Workstations for each plant
3. Set up PLC Integration for connected equipment
4. Configure Bot Users for automated data collection

### Best Practices:
- Use consistent naming conventions for codes and identifiers
- Configure appropriate data retention policies
- Set up proper backup and sync frequencies
- Implement comprehensive error handling and monitoring
- Regular calibration and maintenance scheduling

## File Structure

```
erpnext_doctypes/plant_equipment/
├── plant_configuration.json
├── workstation.json
├── plc_integration.json
└── bot_user_configuration.json
```

All DocType definitions are complete and ready for import into ERPNext, providing a comprehensive foundation for multi-plant SPC operations with proper data segregation, integration capabilities, and automated data collection.