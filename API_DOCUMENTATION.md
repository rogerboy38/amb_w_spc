# AMB_W_SPC API Documentation

## Table of Contents

1. [Overview](#overview)
2. [Authentication & Authorization](#authentication--authorization)
3. [Core SPC Module APIs](#core-spc-module-apis)
4. [FDA Compliance Module APIs](#fda-compliance-module-apis)
5. [Plant Equipment Module APIs](#plant-equipment-module-apis)
6. [SPC Quality Management Module APIs](#spc-quality-management-module-apis)
7. [System Integration APIs](#system-integration-apis)
8. [Workflow APIs](#workflow-apis)
9. [Webhook Configurations](#webhook-configurations)
10. [Data Models & Relationships](#data-models--relationships)
11. [Integration Patterns](#integration-patterns)
12. [Code Examples](#code-examples)
13. [Error Handling](#error-handling)
14. [Rate Limiting](#rate-limiting)
15. [Troubleshooting](#troubleshooting)

## Overview

The AMB_W_SPC (AMB Working Statistical Process Control) system provides a comprehensive REST API and Python SDK for industrial quality management, FDA compliance, and manufacturing equipment integration. The API is built on the Frappe framework and integrates seamlessly with ERPNext.

### Base URL
```
https://{your-site}.erpnext.com/api/
```

### API Versions
- **Current Version**: v1
- **Supported Formats**: JSON, XML
- **Protocol**: HTTPS only

### System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    AMB_W_SPC System API                        │
├─────────────────────────────────────────────────────────────────┤
│  Core SPC    │  FDA Compliance  │  Plant Equipment  │  Quality │
│    Module    │     Module       │     Module        │   Mgmt   │
├─────────────────────────────────────────────────────────────────┤
│                 System Integration Layer                        │
├─────────────────────────────────────────────────────────────────┤
│                    ERPNext Foundation                           │
└─────────────────────────────────────────────────────────────────┘
```

## Authentication & Authorization

### Authentication Methods

#### 1. API Key Authentication (Recommended for Bots)
```http
GET /api/resource/SPC Parameter Master
Authorization: token {api_key}:{api_secret}
```

#### 2. Session-Based Authentication
```http
POST /api/method/login
Content-Type: application/json

{
    "usr": "user@example.com",
    "pwd": "password"
}
```

#### 3. JWT Token Authentication
```http
GET /api/resource/SPC Data Point
Authorization: Bearer {jwt_token}
```

### Role-Based Access Control

The system implements 6 user roles with specific API access patterns:

| Role | Access Level | Rate Limit | Special Permissions |
|------|-------------|------------|-------------------|
| Quality User | Full System | 200/min | Electronic Signature Authority |
| Inspector User | Data Entry Focus | 120/min | Limited to Owned Records |
| Manufacturing User | Production Data | 100/min | Plant-Based Restrictions |
| Warehouse Bot User | Automated Warehouse | 60/min | API-Only Access |
| Workstation Bot User | PLC Integration | 120/min | High-Volume Data Entry |
| Weight Bot User | Scale Integration | 30/min | Weight Parameters Only |

### Plant-Based Multi-Tenancy

All APIs support plant-based data isolation:

```python
# Python SDK Example
import frappe

# Data automatically filtered by user's assigned plants
data_points = frappe.get_all('SPC Data Point', 
                           filters={'plant': 'Plant-001'},
                           fields=['*'])
```

## Core SPC Module APIs

### SPC Parameter Master

The foundation DocType for all quality parameters in the system.

#### REST Endpoints

```http
# Create Parameter Master
POST /api/resource/SPC Parameter Master
Content-Type: application/json

{
    "parameter_name": "Product Temperature",
    "parameter_code": "TEMP-001",
    "company": "Your Company",
    "plant": "Plant-001",
    "department": "Production",
    "parameter_type": "Temperature",
    "data_type": "Numeric",
    "default_precision": 2,
    "unit_of_measurement": "Degree Celsius"
}

# Get Parameter Master
GET /api/resource/SPC Parameter Master/{parameter_code}

# Update Parameter Master
PUT /api/resource/SPC Parameter Master/{parameter_code}

# List Parameters with Filters
GET /api/resource/SPC Parameter Master?filters=[["plant","=","Plant-001"]]

# Delete Parameter Master
DELETE /api/resource/SPC Parameter Master/{parameter_code}
```

#### Python API Methods

```python
import frappe

class SPCParameterMasterAPI:
    
    @staticmethod
    def create_parameter(data):
        """Create new SPC Parameter Master"""
        doc = frappe.new_doc('SPC Parameter Master')
        doc.update(data)
        doc.insert()
        return doc
    
    @staticmethod
    def get_parameter(parameter_code):
        """Get parameter by code"""
        return frappe.get_doc('SPC Parameter Master', parameter_code)
    
    @staticmethod
    def update_parameter(parameter_code, data):
        """Update existing parameter"""
        doc = frappe.get_doc('SPC Parameter Master', parameter_code)
        doc.update(data)
        doc.save()
        return doc
    
    @staticmethod
    def get_parameters_by_plant(plant):
        """Get all parameters for a plant"""
        return frappe.get_all('SPC Parameter Master',
                            filters={'plant': plant},
                            fields=['*'])
    
    @staticmethod
    def get_active_parameters():
        """Get all active parameters"""
        return frappe.get_all('SPC Parameter Master',
                            filters={'is_active': 1},
                            fields=['parameter_name', 'parameter_code', 'unit_of_measurement'])
```

### SPC Data Point

Individual measurement records with statistical calculations.

#### REST Endpoints

```http
# Submit Data Point
POST /api/resource/SPC Data Point
Content-Type: application/json

{
    "parameter": "TEMP-001",
    "measured_value": 180.5,
    "plant": "Plant-001",
    "workstation": "WS-001",
    "operator": "EMP-001",
    "batch_number": "BATCH-2025-001",
    "shift": "Day",
    "data_source": "Manual"
}

# Bulk Data Submission
POST /api/method/core_spc.api.submit_bulk_data
Content-Type: application/json

{
    "data_points": [
        {
            "parameter": "TEMP-001",
            "measured_value": 180.5,
            "timestamp": "2025-01-15 10:30:00"
        },
        {
            "parameter": "TEMP-001", 
            "measured_value": 181.2,
            "timestamp": "2025-01-15 10:35:00"
        }
    ]
}

# Get Data Points with Statistical Analysis
GET /api/resource/SPC Data Point?fields=["*"]&filters=[["parameter","=","TEMP-001"]]&order_by="timestamp desc"&limit_page_length=100

# Get Control Chart Data
GET /api/method/core_spc.api.get_control_chart_data?parameter=TEMP-001&chart_type=X-bar R&days=30
```

#### Python API Methods

```python
class SPCDataPointAPI:
    
    @staticmethod
    def submit_measurement(parameter_code, value, **kwargs):
        """Submit single measurement"""
        doc = frappe.new_doc('SPC Data Point')
        doc.parameter = parameter_code
        doc.measured_value = value
        doc.timestamp = kwargs.get('timestamp', frappe.utils.now())
        doc.update(kwargs)
        doc.insert()
        
        # Trigger automatic statistical calculations
        SPCDataPointAPI.calculate_statistics(doc)
        return doc
    
    @staticmethod
    def submit_bulk_data(data_points):
        """Submit multiple measurements efficiently"""
        results = []
        for data in data_points:
            try:
                doc = SPCDataPointAPI.submit_measurement(**data)
                results.append({'status': 'success', 'name': doc.name})
            except Exception as e:
                results.append({'status': 'error', 'error': str(e), 'data': data})
        return results
    
    @staticmethod
    def calculate_statistics(doc):
        """Calculate X-bar, R-values, and control limits"""
        # Get last 30 valid data points for parameter
        recent_data = frappe.get_all('SPC Data Point',
                                   filters={
                                       'parameter': doc.parameter,
                                       'status': 'Valid',
                                       'timestamp': ['>', frappe.utils.add_days(None, -30)]
                                   },
                                   fields=['measured_value'],
                                   order_by='timestamp desc',
                                   limit=30)
        
        if len(recent_data) >= 5:
            values = [d.measured_value for d in recent_data]
            doc.x_bar = sum(values) / len(values)
            
            # Calculate R-value from last 5 values
            if len(values) >= 5:
                last_5 = values[:5]
                doc.r_value = max(last_5) - min(last_5)
            
            doc.save()
    
    @staticmethod
    def get_control_chart_data(parameter_code, chart_type="X-bar R", days=30):
        """Get data formatted for control charts"""
        from_date = frappe.utils.add_days(None, -days)
        
        data = frappe.get_all('SPC Data Point',
                            filters={
                                'parameter': parameter_code,
                                'timestamp': ['>=', from_date]
                            },
                            fields=['timestamp', 'measured_value', 'x_bar', 'r_value', 
                                  'upper_control_limit', 'lower_control_limit'],
                            order_by='timestamp asc')
        
        return {
            'parameter': parameter_code,
            'chart_type': chart_type,
            'data_points': data,
            'statistics': SPCDataPointAPI.get_statistical_summary(parameter_code, days)
        }
    
    @staticmethod
    def get_statistical_summary(parameter_code, days=30):
        """Get statistical summary for parameter"""
        from_date = frappe.utils.add_days(None, -days)
        
        summary = frappe.db.sql("""
            SELECT 
                AVG(measured_value) as mean,
                STDDEV(measured_value) as std_dev,
                MIN(measured_value) as min_value,
                MAX(measured_value) as max_value,
                COUNT(*) as sample_size
            FROM `tabSPC Data Point`
            WHERE parameter = %s 
            AND timestamp >= %s
            AND status = 'Valid'
        """, (parameter_code, from_date), as_dict=True)[0]
        
        return summary
```

### SPC Control Chart

Configuration and management of statistical control charts.

#### REST Endpoints

```http
# Create Control Chart
POST /api/resource/SPC Control Chart
Content-Type: application/json

{
    "chart_name": "Temperature Control Chart",
    "chart_type": "X-bar R",
    "parameter": "TEMP-001",
    "plant": "Plant-001",
    "workstation": "WS-001",
    "sample_size": 5,
    "sigma_level": 3.0,
    "enable_alerts": 1,
    "western_electric_rules": 1,
    "nelson_rules": 1
}

# Get Chart Configuration
GET /api/resource/SPC Control Chart/{chart_name}

# Get Real-time Chart Data
GET /api/method/core_spc.api.get_realtime_chart_data?chart_name={chart_name}
```

#### Python API Methods

```python
class SPCControlChartAPI:
    
    @staticmethod
    def create_chart(chart_data):
        """Create new control chart"""
        doc = frappe.new_doc('SPC Control Chart')
        doc.update(chart_data)
        doc.insert()
        
        # Calculate initial control limits
        SPCControlChartAPI.calculate_control_limits(doc)
        return doc
    
    @staticmethod
    def calculate_control_limits(chart_doc):
        """Calculate control limits based on historical data"""
        historical_data = frappe.get_all('SPC Data Point',
                                       filters={
                                           'parameter': chart_doc.parameter,
                                           'status': 'Valid'
                                       },
                                       fields=['measured_value'],
                                       limit=100)
        
        if len(historical_data) >= 25:
            values = [d.measured_value for d in historical_data]
            mean = sum(values) / len(values)
            std_dev = (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5
            
            chart_doc.center_line = mean
            chart_doc.ucl = mean + (chart_doc.sigma_level * std_dev)
            chart_doc.lcl = mean - (chart_doc.sigma_level * std_dev)
            chart_doc.save()
    
    @staticmethod
    def get_chart_violations(chart_name, days=7):
        """Get control chart violations"""
        chart = frappe.get_doc('SPC Control Chart', chart_name)
        from_date = frappe.utils.add_days(None, -days)
        
        violations = frappe.get_all('SPC Data Point',
                                  filters={
                                      'parameter': chart.parameter,
                                      'timestamp': ['>=', from_date],
                                      'is_out_of_control': 1
                                  },
                                  fields=['*'])
        
        return violations
```

### SPC Specification

Quality specifications and capability requirements.

#### REST Endpoints

```http
# Create Specification
POST /api/resource/SPC Specification
Content-Type: application/json

{
    "specification_name": "Product Temperature Spec",
    "parameter": "TEMP-001",
    "product_code": "PROD-001",
    "upper_spec_limit": 185.0,
    "lower_spec_limit": 175.0,
    "target_value": 180.0,
    "cpk_target": 1.33,
    "approval_status": "Draft"
}

# Get Active Specifications
GET /api/resource/SPC Specification?filters=[["status","=","Active"]]
```

## FDA Compliance Module APIs

### SPC Audit Trail

Immutable audit records for FDA 21 CFR Part 11 compliance.

#### REST Endpoints

```http
# Get Audit Trail (Read Only)
GET /api/resource/SPC Audit Trail?filters=[["table_name","=","SPC Data Point"]]&order_by="timestamp desc"

# Search Audit Trail
GET /api/method/fda_compliance.api.search_audit_trail?user_id=user@example.com&action_type=Update&from_date=2025-01-01
```

#### Python API Methods

```python
class SPCAuditTrailAPI:
    
    @staticmethod
    def create_audit_record(table_name, record_name, action_type, old_values=None, new_values=None):
        """Create audit trail record (internal use only)"""
        doc = frappe.new_doc('SPC Audit Trail')
        doc.record_id = f"{table_name}-{record_name}-{frappe.utils.now()}"
        doc.timestamp = frappe.utils.now()
        doc.user_id = frappe.session.user
        doc.action_type = action_type
        doc.table_name = table_name
        doc.record_name = record_name
        doc.old_values = frappe.as_json(old_values) if old_values else None
        doc.new_values = frappe.as_json(new_values) if new_values else None
        doc.ip_address = frappe.local.request_ip
        doc.browser_info = frappe.get_request_header('User-Agent')
        doc.session_id = frappe.session.sid
        
        # Generate integrity hash
        doc.hash_value = SPCAuditTrailAPI.generate_hash(doc)
        doc.insert(ignore_permissions=True)
        return doc
    
    @staticmethod
    def generate_hash(doc):
        """Generate SHA-256 hash for tamper detection"""
        import hashlib
        data = f"{doc.record_id}{doc.timestamp}{doc.user_id}{doc.action_type}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def verify_audit_integrity(audit_record):
        """Verify audit record integrity"""
        calculated_hash = SPCAuditTrailAPI.generate_hash(audit_record)
        return calculated_hash == audit_record.hash_value
    
    @staticmethod
    def get_document_history(table_name, record_name):
        """Get complete audit history for a document"""
        return frappe.get_all('SPC Audit Trail',
                            filters={
                                'table_name': table_name,
                                'record_name': record_name
                            },
                            fields=['*'],
                            order_by='timestamp asc')
```

### SPC Electronic Signature

Electronic signature management for FDA compliance.

#### REST Endpoints

```http
# Create Electronic Signature
POST /api/resource/SPC Electronic Signature
Content-Type: application/json

{
    "document_type": "SPC Batch Record",
    "document_name": "BATCH-2025-001",
    "signature_meaning": "Approved",
    "signer_user": "quality.manager@company.com",
    "signature_method": "Password",
    "signature_components": {
        "printed_name": "John Smith",
        "date_time": "2025-01-15 14:30:00",
        "meaning": "Approved by Quality Manager"
    }
}

# Verify Signature
GET /api/method/fda_compliance.api.verify_signature?signature_id={signature_id}
```

#### Python API Methods

```python
class SPCElectronicSignatureAPI:
    
    @staticmethod
    def create_signature(document_type, document_name, signature_meaning, password):
        """Create electronic signature with validation"""
        # Verify password
        if not SPCElectronicSignatureAPI.verify_password(frappe.session.user, password):
            frappe.throw("Invalid password for electronic signature")
        
        doc = frappe.new_doc('SPC Electronic Signature')
        doc.signature_id = f"SIG-{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S')}"
        doc.document_type = document_type
        doc.document_name = document_name
        doc.signature_meaning = signature_meaning
        doc.signer_user = frappe.session.user
        doc.signature_method = "Password"
        doc.signature_timestamp = frappe.utils.now()
        
        # Create signature components
        user = frappe.get_doc('User', frappe.session.user)
        doc.signature_components = frappe.as_json({
            'printed_name': user.full_name,
            'date_time': doc.signature_timestamp,
            'meaning': signature_meaning
        })
        
        # Generate signature hash
        doc.signature_hash = SPCElectronicSignatureAPI.generate_signature_hash(doc)
        doc.cfr_part_11_compliant = 1
        doc.insert()
        return doc
    
    @staticmethod
    def verify_password(user, password):
        """Verify user password for signature"""
        from frappe.auth import check_password
        return check_password(user, password)
    
    @staticmethod
    def generate_signature_hash(signature_doc):
        """Generate SHA-256 signature hash"""
        import hashlib
        data = f"{signature_doc.signature_id}{signature_doc.signer_user}{signature_doc.signature_timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()
```

### SPC Batch Record

Comprehensive batch manufacturing record management.

#### REST Endpoints

```http
# Create Batch Record
POST /api/resource/SPC Batch Record
Content-Type: application/json

{
    "batch_number": "BATCH-2025-001",
    "product_code": "PROD-001",
    "plant": "Plant-001",
    "production_date": "2025-01-15",
    "batch_size": 1000,
    "production_supervisor": "EMP-001",
    "quality_inspector": "EMP-002"
}

# Get Batch Record with Relations
GET /api/resource/SPC Batch Record/{batch_number}?fields=["*"]

# Update Batch Status
PUT /api/method/fda_compliance.api.update_batch_status
Content-Type: application/json

{
    "batch_number": "BATCH-2025-001",
    "status": "Released",
    "electronic_signature": {
        "meaning": "Approved for Release",
        "password": "user_password"
    }
}
```

### SPC Deviation

Comprehensive deviation lifecycle management.

#### REST Endpoints

```http
# Create Deviation
POST /api/resource/SPC Deviation
Content-Type: application/json

{
    "deviation_type": "Process",
    "severity": "Major",
    "description": "Temperature exceeded specification limits",
    "plant": "Plant-001",
    "department": "Production",
    "immediate_action": "Stopped production and contained material"
}

# Get Open Deviations
GET /api/resource/SPC Deviation?filters=[["status","=","Open"]]

# Update Investigation
PUT /api/method/fda_compliance.api.update_deviation_investigation
Content-Type: application/json

{
    "deviation_number": "DEV-2025-001",
    "investigation_findings": "Root cause identified as sensor calibration drift",
    "capa_required": true
}
```

## Plant Equipment Module APIs

### Plant Configuration

Master foundation for plant-level integration settings.

#### REST Endpoints

```http
# Create Plant Configuration
POST /api/resource/Plant Configuration
Content-Type: application/json

{
    "plant_code": "PLANT-001",
    "plant_name": "Main Manufacturing Plant",
    "plant_type": "Production",
    "category": "Production",
    "time_zone": "America/New_York",
    "shift_schedule": "3 Shifts",
    "data_retention_days": 365,
    "backup_frequency": "Daily"
}
```

### SPC Workstation

Equipment layer for individual measurement stations.

#### REST Endpoints

```http
# Create Workstation
POST /api/resource/SPC Workstation
Content-Type: application/json

{
    "workstation_id": "WS-001",
    "workstation_name": "Mixing Station 1",
    "plant": "PLANT-001",
    "department": "Production",
    "equipment_type": "Mixer",
    "plc_address": "192.168.1.100",
    "communication_protocol": "Modbus TCP",
    "data_collection_frequency": "Every 5 minutes",
    "sensor_types": ["Temperature", "Pressure", "Flow"]
}

# Get Workstation Status
GET /api/method/plant_equipment.api.get_workstation_status?workstation_id=WS-001
```

### PLC Integration

Central communication hub for automation systems.

#### REST Endpoints

```http
# Create PLC Integration
POST /api/resource/PLC Integration
Content-Type: application/json

{
    "integration_name": "Main Line PLC",
    "plc_type": "Siemens S7-1500",
    "ip_address": "192.168.1.100",
    "port": 102,
    "protocol": "S7 Communication",
    "authentication_method": "Username/Password",
    "username": "plc_user",
    "connection_timeout": 5000,
    "polling_rate": 1000
}

# Test PLC Connection
GET /api/method/plant_equipment.api.test_plc_connection?integration_name={name}

# Get PLC Status
GET /api/method/plant_equipment.api.get_plc_status?integration_name={name}
```

#### Python API Methods

```python
class PLCIntegrationAPI:
    
    @staticmethod
    def test_connection(integration_name):
        """Test PLC connection"""
        plc_config = frappe.get_doc('PLC Integration', integration_name)
        
        try:
            if plc_config.plc_type.startswith('Siemens'):
                result = PLCIntegrationAPI.test_siemens_connection(plc_config)
            elif plc_config.plc_type.startswith('Allen-Bradley'):
                result = PLCIntegrationAPI.test_ab_connection(plc_config)
            else:
                result = PLCIntegrationAPI.test_modbus_connection(plc_config)
            
            # Update connection status
            plc_config.connection_status = 'Connected' if result['success'] else 'Disconnected'
            plc_config.last_connection_test = frappe.utils.now()
            plc_config.save()
            
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def read_plc_data(integration_name, tag_list):
        """Read data from PLC"""
        plc_config = frappe.get_doc('PLC Integration', integration_name)
        
        # Get parameter mappings
        mappings = frappe.get_all('PLC Parameter Mapping',
                                filters={'parent': integration_name},
                                fields=['*'])
        
        results = []
        for mapping in mappings:
            if mapping.plc_address in tag_list:
                try:
                    raw_value = PLCIntegrationAPI.read_plc_tag(plc_config, mapping.plc_address)
                    
                    # Apply scaling and offset
                    scaled_value = (raw_value * mapping.scaling_factor) + mapping.offset_value
                    
                    results.append({
                        'parameter': mapping.parameter_name,
                        'raw_value': raw_value,
                        'scaled_value': scaled_value,
                        'timestamp': frappe.utils.now(),
                        'data_type': mapping.data_type
                    })
                    
                    # Update last read info
                    mapping.last_read_value = scaled_value
                    mapping.last_read_timestamp = frappe.utils.now()
                    
                except Exception as e:
                    results.append({
                        'parameter': mapping.parameter_name,
                        'error': str(e),
                        'timestamp': frappe.utils.now()
                    })
        
        return results
```

### Bot User Configuration

Automation engine for data collection and monitoring.

#### REST Endpoints

```http
# Create Bot User
POST /api/resource/Bot User Configuration
Content-Type: application/json

{
    "bot_name": "Temperature Monitor Bot",
    "bot_type": "Data Collection",
    "plant": "PLANT-001",
    "data_source_type": "PLC",
    "collection_method": "Polling",
    "collection_frequency": "Every 5 minutes",
    "batch_size": 100,
    "api_endpoint": "https://plant-api.company.com/data"
}

# Get Bot Status
GET /api/method/plant_equipment.api.get_bot_status?bot_name={name}

# Start/Stop Bot
POST /api/method/plant_equipment.api.control_bot
Content-Type: application/json

{
    "bot_name": "Temperature Monitor Bot",
    "action": "start"
}
```

#### Python API Methods

```python
class BotUserAPI:
    
    @staticmethod
    def start_bot(bot_name):
        """Start bot data collection"""
        bot_config = frappe.get_doc('Bot User Configuration', bot_name)
        
        if bot_config.bot_type == 'Data Collection':
            return BotUserAPI.start_data_collection_bot(bot_config)
        elif bot_config.bot_type == 'Monitoring':
            return BotUserAPI.start_monitoring_bot(bot_config)
        else:
            frappe.throw(f"Unsupported bot type: {bot_config.bot_type}")
    
    @staticmethod
    def collect_data(bot_config):
        """Collect data based on bot configuration"""
        if bot_config.data_source_type == 'PLC':
            return BotUserAPI.collect_plc_data(bot_config)
        elif bot_config.data_source_type == 'API':
            return BotUserAPI.collect_api_data(bot_config)
        elif bot_config.data_source_type == 'Database':
            return BotUserAPI.collect_database_data(bot_config)
        else:
            frappe.throw(f"Unsupported data source: {bot_config.data_source_type}")
    
    @staticmethod
    def collect_plc_data(bot_config):
        """Collect data from PLC systems"""
        try:
            # Get PLC integration for this plant
            plc_integrations = frappe.get_all('PLC Integration',
                                            filters={'plant': bot_config.plant},
                                            fields=['name'])
            
            collected_data = []
            for plc in plc_integrations:
                data = PLCIntegrationAPI.read_plc_data(plc.name, bot_config.parameter_list)
                collected_data.extend(data)
            
            # Submit collected data
            for data_point in collected_data:
                if 'error' not in data_point:
                    SPCDataPointAPI.submit_measurement(
                        parameter_code=data_point['parameter'],
                        value=data_point['scaled_value'],
                        data_source='PLC',
                        timestamp=data_point['timestamp']
                    )
            
            # Update bot statistics
            bot_config.collection_count += len(collected_data)
            bot_config.last_collection_time = frappe.utils.now()
            bot_config.save()
            
            return {'success': True, 'data_points': len(collected_data)}
            
        except Exception as e:
            bot_config.error_count += 1
            bot_config.last_error = str(e)
            bot_config.save()
            return {'success': False, 'error': str(e)}
```

## SPC Quality Management Module APIs

### SPC Alert

Real-time monitoring and alerting for process control violations.

#### REST Endpoints

```http
# Get Active Alerts
GET /api/resource/SPC Alert?filters=[["alert_status","=","Open"]]&order_by="timestamp desc"

# Acknowledge Alert
PUT /api/method/spc_quality_management.api.acknowledge_alert
Content-Type: application/json

{
    "alert_id": "ALERT-2025-01-001",
    "acknowledgment_notes": "Investigating temperature sensor calibration"
}

# Escalate Alert
POST /api/method/spc_quality_management.api.escalate_alert
Content-Type: application/json

{
    "alert_id": "ALERT-2025-01-001",
    "escalation_reason": "No response within 24 hours"
}
```

#### Python API Methods

```python
class SPCAlertAPI:
    
    @staticmethod
    def create_alert(parameter, violation_type, severity, data_point_value):
        """Create new SPC alert"""
        doc = frappe.new_doc('SPC Alert')
        doc.alert_id = f"ALERT-{frappe.utils.now_datetime().strftime('%Y-%m-%d')}-{frappe.utils.random_string(3).upper()}"
        doc.timestamp = frappe.utils.now()
        doc.parameter = parameter
        doc.alert_type = violation_type
        doc.severity_level = severity
        doc.measured_value = data_point_value
        doc.alert_status = 'Open'
        
        # Determine recipients based on severity and plant
        recipients = SPCAlertAPI.get_alert_recipients(parameter, severity)
        for recipient in recipients:
            doc.append('notification_recipients', {
                'user': recipient['user'],
                'notification_method': recipient['method'],
                'priority_level': severity
            })
        
        doc.insert()
        
        # Send notifications
        SPCAlertAPI.send_alert_notifications(doc)
        
        return doc
    
    @staticmethod
    def send_alert_notifications(alert_doc):
        """Send alert notifications to recipients"""
        for recipient in alert_doc.notification_recipients:
            if recipient.notification_method in ['Email', 'All Methods']:
                SPCAlertAPI.send_email_alert(alert_doc, recipient.user)
            
            if recipient.notification_method in ['SMS', 'All Methods']:
                SPCAlertAPI.send_sms_alert(alert_doc, recipient.user)
            
            # Always send system notification
            SPCAlertAPI.send_system_notification(alert_doc, recipient.user)
    
    @staticmethod
    def check_western_electric_rules(parameter_code, latest_data_point):
        """Check Western Electric Rules for violations"""
        # Get last 15 data points for analysis
        recent_data = frappe.get_all('SPC Data Point',
                                   filters={'parameter': parameter_code},
                                   fields=['measured_value', 'x_bar', 'upper_control_limit', 'lower_control_limit'],
                                   order_by='timestamp desc',
                                   limit=15)
        
        violations = []
        
        if len(recent_data) >= 1:
            # Rule 1: One point beyond 3σ
            latest = recent_data[0]
            if latest.measured_value > latest.upper_control_limit or latest.measured_value < latest.lower_control_limit:
                violations.append({
                    'rule': 'Rule 1',
                    'description': 'One point beyond 3σ control limits',
                    'severity': 'High'
                })
        
        if len(recent_data) >= 9:
            # Rule 2: Nine consecutive points on one side of centerline
            values = [d.measured_value for d in recent_data[:9]]
            center_line = recent_data[0].x_bar
            
            above_center = all(v > center_line for v in values)
            below_center = all(v < center_line for v in values)
            
            if above_center or below_center:
                violations.append({
                    'rule': 'Rule 2',
                    'description': 'Nine consecutive points on one side of centerline',
                    'severity': 'Medium'
                })
        
        # Additional rules can be implemented here...
        
        return violations
```

### SPC Corrective Action

Comprehensive CAPA management system.

#### REST Endpoints

```http
# Create Corrective Action
POST /api/resource/SPC Corrective Action
Content-Type: application/json

{
    "title": "Temperature Control System Investigation",
    "problem_description": "Temperature exceeded specification limits causing product quality issues",
    "priority": "High",
    "plant": "PLANT-001",
    "department": "Production",
    "overall_responsible_person": "quality.engineer@company.com"
}

# Update Investigation
PUT /api/method/spc_quality_management.api.update_capa_investigation
Content-Type: application/json

{
    "ca_number": "CA-2025-01-001",
    "root_cause_analysis": "Sensor calibration drift identified as root cause",
    "analysis_method": "5 Why Analysis",
    "corrective_actions": "Recalibrate temperature sensor and implement weekly checks"
}
```

### SPC Process Capability

Statistical capability studies and process performance assessment.

#### REST Endpoints

```http
# Create Process Capability Study
POST /api/resource/SPC Process Capability
Content-Type: application/json

{
    "study_name": "Temperature Process Capability Q1 2025",
    "parameter": "TEMP-001",
    "plant": "PLANT-001",
    "product_code": "PROD-001",
    "study_type": "Initial",
    "sample_size": 50,
    "target_value": 180.0,
    "lower_specification_limit": 175.0,
    "upper_specification_limit": 185.0
}

# Calculate Capability Indices
POST /api/method/spc_quality_management.api.calculate_capability
Content-Type: application/json

{
    "study_name": "Temperature Process Capability Q1 2025"
}
```

#### Python API Methods

```python
class SPCProcessCapabilityAPI:
    
    @staticmethod
    def calculate_capability_indices(study_doc):
        """Calculate Cp, Cpk, Pp, Ppk values"""
        # Get measurement data
        measurements = frappe.get_all('SPC Process Capability Measurement',
                                    filters={'parent': study_doc.name},
                                    fields=['measurement_value'])
        
        if len(measurements) < 30:
            frappe.throw("Minimum 30 measurements required for capability study")
        
        values = [m.measurement_value for m in measurements]
        
        # Calculate statistics
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        std_dev = variance ** 0.5
        
        # Calculate capability indices
        usl = study_doc.upper_specification_limit
        lsl = study_doc.lower_specification_limit
        target = study_doc.target_value
        
        # Cp (Process Capability)
        cp = (usl - lsl) / (6 * std_dev) if std_dev > 0 else 0
        
        # Cpk (Process Capability Index)
        cpu = (usl - mean) / (3 * std_dev) if std_dev > 0 else 0
        cpl = (mean - lsl) / (3 * std_dev) if std_dev > 0 else 0
        cpk = min(cpu, cpl)
        
        # Update study document
        study_doc.process_mean = mean
        study_doc.process_std_dev = std_dev
        study_doc.cp = cp
        study_doc.cpk = cpk
        
        # Determine capability rating
        if cpk >= 2.0:
            study_doc.capability_rating = 'Excellent'
        elif cpk >= 1.33:
            study_doc.capability_rating = 'Adequate'
        elif cpk >= 1.0:
            study_doc.capability_rating = 'Marginal'
        else:
            study_doc.capability_rating = 'Inadequate'
        
        # Calculate defect rate (PPM)
        if std_dev > 0:
            z_usl = (usl - mean) / std_dev
            z_lsl = (mean - lsl) / std_dev
            
            # Using normal distribution approximation
            from scipy import stats
            defect_rate = (1 - stats.norm.cdf(z_usl) + stats.norm.cdf(-z_lsl)) * 1000000
            study_doc.defect_rate_ppm = defect_rate
        
        study_doc.save()
        return study_doc
```

### SPC Report

Comprehensive reporting system for process performance.

#### REST Endpoints

```http
# Generate Report
POST /api/method/spc_quality_management.api.generate_report
Content-Type: application/json

{
    "report_type": "Daily Quality Report",
    "plant": "PLANT-001",
    "from_date": "2025-01-15",
    "to_date": "2025-01-15",
    "parameters": ["TEMP-001", "PRESS-001"],
    "include_charts": true,
    "report_format": "PDF"
}

# Get Report Status
GET /api/method/spc_quality_management.api.get_report_status?report_name={name}

# Download Report
GET /api/method/spc_quality_management.api.download_report?report_name={name}
```

## System Integration APIs

### Workflow APIs

The system provides comprehensive workflow management APIs for all business processes.

#### SPC Alert Workflow

```http
# Acknowledge Alert
POST /api/method/workflow.api.apply_workflow
Content-Type: application/json

{
    "doctype": "SPC Alert",
    "docname": "ALERT-2025-01-001",
    "action": "Acknowledge",
    "electronic_signature": {
        "meaning": "Acknowledged",
        "password": "user_password"
    }
}

# Start Investigation
POST /api/method/workflow.api.apply_workflow
Content-Type: application/json

{
    "doctype": "SPC Alert",
    "docname": "ALERT-2025-01-001",
    "action": "Start Investigation",
    "investigation_notes": "Beginning root cause analysis"
}
```

#### Process Capability Workflow

```http
# Complete Study
POST /api/method/workflow.api.apply_workflow
Content-Type: application/json

{
    "doctype": "SPC Process Capability",
    "docname": "PC-2025-001",
    "action": "Complete",
    "electronic_signature": {
        "meaning": "Study Completed",
        "password": "user_password"
    }
}
```

#### Python Workflow API

```python
class WorkflowAPI:
    
    @staticmethod
    def apply_workflow_action(doctype, docname, action, **kwargs):
        """Apply workflow action with validation"""
        doc = frappe.get_doc(doctype, docname)
        
        # Validate user permissions for this action
        if not WorkflowAPI.validate_workflow_permission(doc, action):
            frappe.throw("Insufficient permissions for this workflow action")
        
        # Apply electronic signature if required
        if kwargs.get('electronic_signature'):
            signature_data = kwargs['electronic_signature']
            SPCElectronicSignatureAPI.create_signature(
                document_type=doctype,
                document_name=docname,
                signature_meaning=signature_data['meaning'],
                password=signature_data['password']
            )
        
        # Apply workflow transition
        from frappe.model.workflow import apply_workflow
        apply_workflow(doc, action)
        
        return doc
    
    @staticmethod
    def get_workflow_state(doctype, docname):
        """Get current workflow state"""
        doc = frappe.get_doc(doctype, docname)
        workflow = frappe.get_doc('Workflow', {'document_type': doctype})
        
        current_state = None
        for state in workflow.states:
            if state.state == doc.workflow_state:
                current_state = state
                break
        
        # Get available transitions
        available_actions = []
        for transition in workflow.transitions:
            if (transition.state == doc.workflow_state and 
                WorkflowAPI.validate_workflow_permission(doc, transition.action)):
                available_actions.append(transition.action)
        
        return {
            'current_state': doc.workflow_state,
            'available_actions': available_actions,
            'state_doc': current_state
        }
```

### Bulk Operations API

High-performance APIs for bulk data operations.

```http
# Bulk Data Submission
POST /api/method/core_spc.api.bulk_data_submission
Content-Type: application/json

{
    "data_points": [
        {
            "parameter": "TEMP-001",
            "measured_value": 180.5,
            "timestamp": "2025-01-15 10:30:00",
            "workstation": "WS-001",
            "operator": "EMP-001"
        },
        // ... up to 1000 data points
    ],
    "validate_individually": true,
    "create_alerts": true
}

# Bulk Alert Acknowledgment
POST /api/method/spc_quality_management.api.bulk_acknowledge_alerts
Content-Type: application/json

{
    "alert_ids": ["ALERT-2025-01-001", "ALERT-2025-01-002"],
    "acknowledgment_notes": "Batch acknowledgment for sensor calibration issues",
    "electronic_signature": {
        "meaning": "Bulk Acknowledged",
        "password": "user_password"
    }
}
```

#### Python Bulk Operations

```python
class BulkOperationsAPI:
    
    @staticmethod
    def bulk_submit_data(data_points, validate_individually=True, create_alerts=True):
        """Submit multiple data points efficiently"""
        results = []
        
        # Use database transaction for consistency
        try:
            for data in data_points:
                try:
                    # Create data point
                    doc = SPCDataPointAPI.submit_measurement(**data)
                    
                    # Generate alerts if enabled
                    if create_alerts:
                        violations = SPCAlertAPI.check_western_electric_rules(
                            data['parameter'], doc
                        )
                        for violation in violations:
                            SPCAlertAPI.create_alert(
                                parameter=data['parameter'],
                                violation_type=violation['rule'],
                                severity=violation['severity'],
                                data_point_value=data['measured_value']
                            )
                    
                    results.append({
                        'status': 'success',
                        'data_point': doc.name,
                        'alerts_created': len(violations) if create_alerts else 0
                    })
                    
                except Exception as e:
                    if validate_individually:
                        results.append({
                            'status': 'error',
                            'error': str(e),
                            'data': data
                        })
                    else:
                        raise e
            
            frappe.db.commit()
            return {
                'success': True,
                'total_submitted': len([r for r in results if r['status'] == 'success']),
                'total_errors': len([r for r in results if r['status'] == 'error']),
                'results': results
            }
            
        except Exception as e:
            frappe.db.rollback()
            return {
                'success': False,
                'error': str(e),
                'results': results
            }
```

## Webhook Configurations

The system provides comprehensive webhook support for real-time integration with external systems.

### Webhook Event Types

| Event Type | Trigger | Payload |
|------------|---------|---------|
| `spc_data_point.created` | New measurement submitted | Data point details + statistical analysis |
| `spc_alert.created` | Alert generated | Alert details + violation information |
| `spc_alert.escalated` | Alert escalated | Alert details + escalation reason |
| `deviation.created` | Deviation opened | Deviation details + initial assessment |
| `batch_record.released` | Batch approved for release | Batch details + quality summary |
| `process_capability.completed` | Capability study finished | Study results + statistical analysis |
| `electronic_signature.applied` | Document signed | Signature details + document reference |

### Webhook Configuration

```http
# Register Webhook
POST /api/resource/Webhook
Content-Type: application/json

{
    "webhook_doctype": "SPC Data Point",
    "webhook_docevent": "after_insert",
    "request_url": "https://your-system.com/webhooks/spc-data",
    "request_structure": "JSON",
    "condition": "doc.status == 'Valid'",
    "webhook_headers": [
        {
            "key": "Authorization",
            "value": "Bearer your-api-token"
        },
        {
            "key": "Content-Type", 
            "value": "application/json"
        }
    ],
    "webhook_data": [
        {
            "fieldname": "parameter",
            "key": "parameter_code"
        },
        {
            "fieldname": "measured_value",
            "key": "value"
        },
        {
            "fieldname": "timestamp",
            "key": "measurement_time"
        }
    ]
}
```

### Sample Webhook Payloads

#### SPC Data Point Created
```json
{
    "event": "spc_data_point.created",
    "timestamp": "2025-01-15T10:30:00Z",
    "data": {
        "name": "SPC-TEMP-001-00001",
        "parameter_code": "TEMP-001",
        "parameter_name": "Product Temperature",
        "measured_value": 180.5,
        "plant": "PLANT-001",
        "workstation": "WS-001",
        "operator": "EMP-001",
        "measurement_time": "2025-01-15T10:30:00Z",
        "status": "Valid",
        "statistical_analysis": {
            "x_bar": 180.2,
            "r_value": 1.2,
            "within_control_limits": true,
            "within_specification_limits": true
        }
    }
}
```

#### SPC Alert Created
```json
{
    "event": "spc_alert.created",
    "timestamp": "2025-01-15T10:35:00Z",
    "data": {
        "alert_id": "ALERT-2025-01-001",
        "parameter": "TEMP-001",
        "plant": "PLANT-001",
        "workstation": "WS-001",
        "alert_type": "Rule 1",
        "severity_level": "High",
        "violation_description": "One point beyond 3σ control limits",
        "measured_value": 188.5,
        "upper_control_limit": 185.0,
        "alert_status": "Open",
        "notification_recipients": [
            "production.manager@company.com",
            "quality.engineer@company.com"
        ]
    }
}
```

## Data Models & Relationships

### Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   SPC Parameter │──────▶│   SPC Data      │──────▶│   SPC Alert     │
│     Master      │ 1:N   │     Point       │ 1:N   │                 │
└─────────────────┘       └─────────────────┘       └─────────────────┘
         │                         │                         │
         │ 1:N                     │ N:1                     │ 1:N
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  SPC Control    │       │  SPC Batch      │       │  SPC Corrective │
│     Chart       │       │    Record       │       │     Action      │
└─────────────────┘       └─────────────────┘       └─────────────────┘
         │                         │                         
         │ 1:1                     │ 1:N                     
         ▼                         ▼                         
┌─────────────────┐       ┌─────────────────┐               
│ SPC Specification│       │ SPC Deviation   │               
│                 │       │                 │               
└─────────────────┘       └─────────────────┘               
```

### Core Data Models

#### SPC Parameter Master Model
```python
{
    "doctype": "SPC Parameter Master",
    "fields": {
        "parameter_name": "string, required, unique",
        "parameter_code": "string, required, unique, uppercase",
        "company": "link:Company, required",
        "plant": "link:Warehouse, required", 
        "department": "link:Department",
        "parameter_type": "select:Temperature|Pressure|Flow|pH|etc",
        "data_type": "select:Numeric|Text",
        "default_precision": "int, default:2",
        "unit_of_measurement": "link:UOM",
        "is_active": "check, default:1",
        
        # Child Tables
        "target_values": "table:SPC Parameter Target Value",
        "control_limits": "table:SPC Parameter Control Limit", 
        "specifications": "table:SPC Parameter Specification"
    },
    "naming": "field:parameter_code",
    "permissions": "plant_based_access",
    "validation_rules": [
        "parameter_code_format_validation",
        "unique_parameter_per_company",
        "precision_required_for_numeric"
    ]
}
```

#### SPC Data Point Model
```python
{
    "doctype": "SPC Data Point",
    "fields": {
        "parameter": "link:SPC Parameter Master, required",
        "measured_value": "float, required, precision:6",
        "timestamp": "datetime, required, default:now",
        "plant": "link:Warehouse, required",
        "workstation": "link:SPC Workstation",
        "operator": "link:Employee",
        "batch_number": "string",
        "shift": "select:Day|Evening|Night|Rotating",
        "data_source": "select:Manual|PLC|Bot|SCADA|LIMS",
        
        # Statistical Fields (auto-calculated)
        "x_bar": "float, read_only",
        "r_value": "float, read_only", 
        "moving_average": "float",
        "moving_range": "float, read_only",
        "standard_deviation": "float",
        
        # Control Limits
        "upper_control_limit": "float",
        "lower_control_limit": "float",
        "upper_spec_limit": "float",
        "lower_spec_limit": "float",
        "target_value": "float",
        
        # Process Capability
        "cp": "float, read_only",
        "cpk": "float, read_only", 
        "pp": "float, read_only",
        "ppk": "float, read_only",
        "sigma_level": "float, read_only",
        
        # Status and Validation
        "status": "select:Valid|Invalid|Pending Review",
        "is_out_of_control": "check, default:0",
        "validation_status": "select:Pending|Validated|Rejected|Under Review",
        "validation_notes": "text",
        "corrective_action": "text"
    },
    "naming": "SPC-{parameter}-{#####}",
    "permissions": "plant_based_access",
    "triggers": [
        "after_insert:calculate_statistics",
        "after_insert:check_control_limits",
        "after_insert:create_alerts_if_needed"
    ]
}
```

#### SPC Alert Model
```python
{
    "doctype": "SPC Alert",
    "fields": {
        "alert_id": "string, required, unique",
        "timestamp": "datetime, required, default:now",
        "parameter": "link:SPC Parameter Master, required",
        "plant": "link:Warehouse, required",
        "workstation": "link:SPC Workstation",
        "alert_type": "select:Rule 1|Rule 2|...|Out of Spec",
        "severity_level": "select:Low|Medium|High|Critical",
        "measured_value": "float",
        "violation_description": "text",
        
        # Western Electric Rules
        "rule_violated": "select:Rule 1|Rule 2|Rule 3|...|Rule 8",
        "consecutive_points": "int",
        "trend_direction": "select:Increasing|Decreasing|None",
        
        # Response Management
        "alert_status": "select:Open|Acknowledged|Investigating|Resolved",
        "acknowledged_by": "link:User",
        "acknowledged_time": "datetime",
        "response_required": "check, default:1",
        "escalation_level": "int, default:0",
        
        # Notifications
        "email_sent": "check, default:0",
        "sms_sent": "check, default:0", 
        "dashboard_notification": "check, default:1",
        
        # Child Tables
        "notification_recipients": "table:SPC Alert Recipient"
    },
    "naming": "ALERT-{YYYY}-{MM}-{#####}",
    "workflow": "SPC Alert Workflow",
    "permissions": "role_based_access"
}
```

### Integration Data Models

#### PLC Integration Model
```python
{
    "doctype": "PLC Integration",
    "fields": {
        "integration_name": "string, required, unique",
        "plc_type": "select:Siemens S7-1500|Allen-Bradley|Schneider|etc",
        "ip_address": "string, required",
        "port": "int, default:502",
        "protocol": "select:OPC-UA|Modbus TCP|S7 Communication|etc",
        
        # Authentication
        "authentication_method": "select:Username/Password|Certificate|Token|etc",
        "username": "string",
        "password": "password", 
        "certificate_path": "string",
        "encryption_level": "select:None|Sign|SignAndEncrypt|etc",
        
        # Connection Settings
        "connection_timeout": "int, default:5000",
        "retry_attempts": "int, default:3",
        "polling_rate": "int, default:1000",
        "max_concurrent_connections": "int, default:5",
        "keepalive_interval": "int, default:30000",
        
        # Status
        "connection_status": "select:Connected|Disconnected|Error",
        "last_connection_test": "datetime",
        "error_count": "int, default:0",
        "last_error": "text",
        
        # Child Tables
        "parameter_mappings": "table:PLC Parameter Mapping"
    },
    "naming": "field:integration_name",
    "permissions": "plant_based_access"
}
```

### Relationship Mapping

#### Parameter-Centric Relationships
```python
PARAMETER_RELATIONSHIPS = {
    "SPC Parameter Master": {
        "children": [
            "SPC Data Point",      # 1:N - measurements
            "SPC Control Chart",   # 1:N - monitoring charts
            "SPC Specification",   # 1:N - quality specs
            "SPC Alert"           # 1:N - violations
        ],
        "child_tables": [
            "SPC Parameter Target Value",
            "SPC Parameter Control Limit", 
            "SPC Parameter Specification"
        ]
    }
}
```

#### Plant-Centric Relationships
```python
PLANT_RELATIONSHIPS = {
    "Plant Configuration": {
        "children": [
            "SPC Workstation",     # 1:N - equipment
            "PLC Integration",     # 1:N - automation
            "Bot User Configuration", # 1:N - automation bots
            "SPC Parameter Master", # 1:N - quality parameters
            "SPC Batch Record"     # 1:N - production batches
        ]
    }
}
```

## Integration Patterns

### Real-Time Data Collection Pattern

```python
# Pattern 1: PLC → Bot → Data Point → Alert
class RealTimeDataPattern:
    
    @staticmethod
    def collect_and_process():
        """Real-time data collection with immediate processing"""
        
        # 1. Bot collects data from PLC
        bot_config = frappe.get_doc('Bot User Configuration', 'Temperature-Bot')
        plc_data = BotUserAPI.collect_plc_data(bot_config)
        
        # 2. Submit data points
        for data in plc_data:
            data_point = SPCDataPointAPI.submit_measurement(
                parameter_code=data['parameter'],
                value=data['scaled_value'],
                data_source='PLC'
            )
            
            # 3. Immediate statistical analysis
            SPCDataPointAPI.calculate_statistics(data_point)
            
            # 4. Check for violations and create alerts
            violations = SPCAlertAPI.check_western_electric_rules(
                data['parameter'], data_point
            )
            
            for violation in violations:
                alert = SPCAlertAPI.create_alert(
                    parameter=data['parameter'],
                    violation_type=violation['rule'],
                    severity=violation['severity'],
                    data_point_value=data['scaled_value']
                )
                
                # 5. Immediate notification
                SPCAlertAPI.send_alert_notifications(alert)
```

### Batch Processing Pattern

```python
# Pattern 2: Batch → Parameters → Deviations → CAPA
class BatchQualityPattern:
    
    @staticmethod
    def complete_batch_quality_cycle(batch_number):
        """Complete quality cycle for batch production"""
        
        # 1. Get batch record
        batch = frappe.get_doc('SPC Batch Record', batch_number)
        
        # 2. Collect all quality parameters
        parameters = batch.parameters_tested
        for param in parameters:
            # Verify specification compliance
            if param.result != 'Pass':
                # 3. Create deviation
                deviation = frappe.new_doc('SPC Deviation')
                deviation.update({
                    'deviation_type': 'Quality',
                    'severity': 'Major',
                    'description': f"Parameter {param.parameter_name} failed specification",
                    'batch_number': batch_number
                })
                deviation.insert()
                
                # 4. Auto-create CAPA if required
                if deviation.severity in ['Major', 'Critical']:
                    capa = frappe.new_doc('SPC Corrective Action')
                    capa.update({
                        'title': f"CAPA for {deviation.deviation_type} Deviation",
                        'problem_description': deviation.description,
                        'priority': 'High'
                    })
                    capa.insert()
        
        # 5. Final batch approval with electronic signature
        return BatchQualityPattern.approve_batch(batch)
```

### Statistical Analysis Pattern

```python
# Pattern 3: Data Collection → Statistical Analysis → Process Capability
class StatisticalAnalysisPattern:
    
    @staticmethod
    def automated_capability_study(parameter_code, days=30):
        """Automated process capability analysis"""
        
        # 1. Collect sufficient data
        from_date = frappe.utils.add_days(None, -days)
        data_points = frappe.get_all('SPC Data Point',
                                   filters={
                                       'parameter': parameter_code,
                                       'timestamp': ['>=', from_date],
                                       'status': 'Valid'
                                   },
                                   fields=['measured_value'])
        
        if len(data_points) < 30:
            return {'error': 'Insufficient data for capability study'}
        
        # 2. Create capability study
        study = frappe.new_doc('SPC Process Capability')
        study.update({
            'study_name': f"{parameter_code} Auto Study {frappe.utils.today()}",
            'parameter': parameter_code,
            'study_type': 'Ongoing',
            'sample_size': len(data_points)
        })
        
        # 3. Add measurement data
        for i, data in enumerate(data_points):
            study.append('measurement_data', {
                'sequence_number': i + 1,
                'measurement_value': data.measured_value
            })
        
        study.insert()
        
        # 4. Calculate capability indices
        capability_result = SPCProcessCapabilityAPI.calculate_capability_indices(study)
        
        # 5. Auto-trigger CAPA if capability is inadequate
        if capability_result.cpk < 1.0:
            StatisticalAnalysisPattern.trigger_capability_improvement(study)
        
        return capability_result
```

## Code Examples

### Complete Integration Example

```python
"""
Complete example: Temperature monitoring system with PLC integration,
real-time alerts, and automated CAPA generation
"""

class TemperatureMonitoringSystem:
    
    def __init__(self, plant_code):
        self.plant_code = plant_code
        self.setup_system()
    
    def setup_system(self):
        """Initialize complete temperature monitoring system"""
        
        # 1. Create parameter master
        self.temp_parameter = SPCParameterMasterAPI.create_parameter({
            'parameter_name': 'Product Temperature',
            'parameter_code': 'TEMP-001',
            'plant': self.plant_code,
            'parameter_type': 'Temperature',
            'data_type': 'Numeric',
            'default_precision': 1,
            'unit_of_measurement': 'Degree Celsius'
        })
        
        # 2. Setup PLC integration
        self.plc_integration = self.setup_plc_connection()
        
        # 3. Create control chart
        self.control_chart = self.setup_control_chart()
        
        # 4. Setup automated data collection
        self.data_bot = self.setup_data_collection_bot()
        
        # 5. Configure specifications
        self.specification = self.setup_specifications()
    
    def setup_plc_connection(self):
        """Setup PLC integration for temperature sensor"""
        
        plc_config = frappe.new_doc('PLC Integration')
        plc_config.update({
            'integration_name': f'Temperature PLC {self.plant_code}',
            'plc_type': 'Siemens S7-1500',
            'ip_address': '192.168.1.100',
            'port': 102,
            'protocol': 'S7 Communication',
            'authentication_method': 'Username/Password',
            'username': 'plc_operator',
            'polling_rate': 5000  # 5 second polling
        })
        plc_config.insert()
        
        # Add parameter mapping
        plc_config.append('parameter_mappings', {
            'parameter_name': 'TEMP-001',
            'plc_address': 'DB1.DBD0',  # Siemens DB1, Double Word 0
            'data_type': 'Float',
            'access_type': 'Read Only',
            'scaling_factor': 1.0,
            'offset_value': 0.0,
            'enabled': 1
        })
        plc_config.save()
        
        return plc_config
    
    def setup_control_chart(self):
        """Setup X-bar R control chart"""
        
        chart = SPCControlChartAPI.create_chart({
            'chart_name': f'Temperature Chart {self.plant_code}',
            'chart_type': 'X-bar R',
            'parameter': 'TEMP-001',
            'plant': self.plant_code,
            'sample_size': 5,
            'sigma_level': 3.0,
            'enable_alerts': 1,
            'western_electric_rules': 1,
            'nelson_rules': 1,
            'auto_update': 1,
            'refresh_interval': 5
        })
        
        # Setup alert recipients
        chart.append('alert_recipients', {
            'user': 'production.manager@company.com',
            'alert_method': 'Email',
            'priority_level': 'High'
        })
        chart.append('alert_recipients', {
            'user': 'quality.engineer@company.com', 
            'alert_method': 'All Methods',
            'priority_level': 'Critical'
        })
        chart.save()
        
        return chart
    
    def setup_data_collection_bot(self):
        """Setup automated data collection bot"""
        
        bot = frappe.new_doc('Bot User Configuration')
        bot.update({
            'bot_name': f'Temperature Bot {self.plant_code}',
            'bot_type': 'Data Collection',
            'plant': self.plant_code,
            'data_source_type': 'PLC',
            'collection_method': 'Polling',
            'collection_frequency': 'Every 5 minutes',
            'batch_size': 10,
            'buffer_size': 100,
            'enabled': 1
        })
        bot.insert()
        
        return bot
    
    def setup_specifications(self):
        """Setup quality specifications"""
        
        spec = frappe.new_doc('SPC Specification')
        spec.update({
            'specification_name': f'Temperature Spec {self.plant_code}',
            'parameter': 'TEMP-001',
            'plant': self.plant_code,
            'upper_spec_limit': 185.0,
            'lower_spec_limit': 175.0,
            'target_value': 180.0,
            'tolerance': 5.0,
            'cpk_target': 1.33,
            'approval_status': 'Approved',
            'status': 'Active'
        })
        spec.insert()
        
        return spec
    
    def start_monitoring(self):
        """Start real-time temperature monitoring"""
        
        # Start data collection bot
        BotUserAPI.start_bot(self.data_bot.bot_name)
        
        # Setup scheduled capability studies
        self.schedule_capability_studies()
        
        print(f"Temperature monitoring system started for {self.plant_code}")
    
    def schedule_capability_studies(self):
        """Schedule automated capability studies"""
        
        # Weekly capability study
        frappe.get_doc({
            'doctype': 'Scheduled Job Type',
            'method': 'temperature_monitoring.run_weekly_capability_study',
            'frequency': 'Weekly',
            'enabled': 1
        }).insert()
    
    def process_temperature_alert(self, alert_doc):
        """Process temperature alert with automated CAPA"""
        
        if alert_doc.severity_level == 'Critical':
            # Auto-create deviation
            deviation = frappe.new_doc('SPC Deviation')
            deviation.update({
                'deviation_type': 'Process',
                'severity': 'Critical',
                'description': f"Critical temperature violation: {alert_doc.measured_value}°C",
                'plant': self.plant_code,
                'immediate_action': 'Production stopped, investigating temperature control system'
            })
            deviation.insert()
            
            # Auto-create CAPA
            capa = frappe.new_doc('SPC Corrective Action')
            capa.update({
                'title': 'Temperature Control System Investigation',
                'problem_description': deviation.description,
                'priority': 'Critical',
                'plant': self.plant_code,
                'overall_responsible_person': 'maintenance.manager@company.com'
            })
            capa.insert()
            
            # Send immediate escalation
            self.send_critical_alert_escalation(alert_doc, deviation, capa)
    
    def send_critical_alert_escalation(self, alert, deviation, capa):
        """Send critical alert escalation to management"""
        
        recipients = [
            'plant.manager@company.com',
            'quality.director@company.com',
            'production.director@company.com'
        ]
        
        message = f"""
        CRITICAL TEMPERATURE ALERT - IMMEDIATE ACTION REQUIRED
        
        Plant: {self.plant_code}
        Alert: {alert.alert_id}
        Measured Value: {alert.measured_value}°C
        Specification Limit: {alert.specification_limit}°C
        
        Deviation Created: {deviation.name}
        CAPA Created: {capa.name}
        
        Production has been stopped pending investigation.
        """
        
        for recipient in recipients:
            frappe.sendmail(
                recipients=[recipient],
                subject=f"CRITICAL: Temperature Alert {alert.alert_id}",
                message=message,
                delayed=False
            )

# Usage Example
if __name__ == "__main__":
    # Initialize temperature monitoring system
    temp_system = TemperatureMonitoringSystem('PLANT-001')
    temp_system.start_monitoring()
    
    # Simulate temperature data collection
    for i in range(10):
        temp_value = 180.0 + (i * 0.5)  # Gradually increasing temperature
        
        data_point = SPCDataPointAPI.submit_measurement(
            parameter_code='TEMP-001',
            value=temp_value,
            data_source='PLC',
            workstation='MIXER-001'
        )
        
        # Check for alerts
        violations = SPCAlertAPI.check_western_electric_rules('TEMP-001', data_point)
        for violation in violations:
            alert = SPCAlertAPI.create_alert(
                parameter='TEMP-001',
                violation_type=violation['rule'],
                severity=violation['severity'],
                data_point_value=temp_value
            )
            
            # Process alert with automated response
            temp_system.process_temperature_alert(alert)
```

### API Client Example

```python
"""
Example API client for external system integration
"""

import requests
import json
from datetime import datetime, timedelta

class SPCAPIClient:
    
    def __init__(self, base_url, api_key, api_secret):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {api_key}:{api_secret}',
            'Content-Type': 'application/json'
        })
    
    def submit_measurement(self, parameter_code, value, **kwargs):
        """Submit single measurement"""
        
        data = {
            'parameter': parameter_code,
            'measured_value': value,
            'timestamp': kwargs.get('timestamp', datetime.now().isoformat()),
            **kwargs
        }
        
        response = self.session.post(
            f'{self.base_url}/api/resource/SPC Data Point',
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def submit_bulk_measurements(self, measurements):
        """Submit multiple measurements efficiently"""
        
        response = self.session.post(
            f'{self.base_url}/api/method/core_spc.api.bulk_data_submission',
            json={'data_points': measurements}
        )
        response.raise_for_status()
        return response.json()
    
    def get_active_alerts(self, plant=None, severity=None):
        """Get active alerts with optional filtering"""
        
        filters = [['alert_status', '=', 'Open']]
        if plant:
            filters.append(['plant', '=', plant])
        if severity:
            filters.append(['severity_level', '=', severity])
        
        params = {
            'filters': json.dumps(filters),
            'fields': json.dumps(['*']),
            'order_by': 'timestamp desc'
        }
        
        response = self.session.get(
            f'{self.base_url}/api/resource/SPC Alert',
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def acknowledge_alert(self, alert_id, notes=None):
        """Acknowledge an alert"""
        
        data = {
            'alert_id': alert_id,
            'acknowledgment_notes': notes or 'Acknowledged via API'
        }
        
        response = self.session.put(
            f'{self.base_url}/api/method/spc_quality_management.api.acknowledge_alert',
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def get_control_chart_data(self, parameter_code, days=7):
        """Get control chart data for visualization"""
        
        params = {
            'parameter': parameter_code,
            'chart_type': 'X-bar R',
            'days': days
        }
        
        response = self.session.get(
            f'{self.base_url}/api/method/core_spc.api.get_control_chart_data',
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def create_batch_record(self, batch_data):
        """Create new batch record"""
        
        response = self.session.post(
            f'{self.base_url}/api/resource/SPC Batch Record',
            json=batch_data
        )
        response.raise_for_status()
        return response.json()
    
    def get_process_capability(self, parameter_code, days=30):
        """Get process capability analysis"""
        
        params = {
            'parameter': parameter_code,
            'days': days
        }
        
        response = self.session.get(
            f'{self.base_url}/api/method/spc_quality_management.api.get_process_capability',
            params=params
        )
        response.raise_for_status()
        return response.json()

# Usage example
if __name__ == "__main__":
    # Initialize client
    client = SPCAPIClient(
        base_url='https://your-erp.company.com',
        api_key='your-api-key',
        api_secret='your-api-secret'
    )
    
    # Submit temperature measurements
    measurements = []
    for i in range(5):
        measurements.append({
            'parameter': 'TEMP-001',
            'measured_value': 180.0 + (i * 0.2),
            'workstation': 'WS-001',
            'operator': 'EMP-001',
            'shift': 'Day'
        })
    
    # Bulk submit
    result = client.submit_bulk_measurements(measurements)
    print(f"Submitted {result['total_submitted']} measurements")
    
    # Check for alerts
    alerts = client.get_active_alerts(plant='PLANT-001', severity='High')
    print(f"Found {len(alerts['data'])} active high-severity alerts")
    
    # Acknowledge alerts if any
    for alert in alerts['data']:
        client.acknowledge_alert(alert['alert_id'], 'Acknowledged and investigating')
    
    # Get control chart data for visualization
    chart_data = client.get_control_chart_data('TEMP-001', days=7)
    print(f"Retrieved {len(chart_data['data_points'])} data points for charting")
```

## Error Handling

### Standard Error Response Format

```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Measured value is required",
        "details": {
            "field": "measured_value",
            "doctype": "SPC Data Point",
            "validation_rule": "required_field"
        },
        "timestamp": "2025-01-15T10:30:00Z",
        "request_id": "req_abc123"
    }
}
```

### Error Codes Reference

| Error Code | HTTP Status | Description | Action |
|------------|-------------|-------------|---------|
| `VALIDATION_ERROR` | 422 | Field validation failed | Check field values and requirements |
| `PERMISSION_DENIED` | 403 | Insufficient permissions | Verify user role and plant access |
| `RESOURCE_NOT_FOUND` | 404 | Document not found | Check document name/ID |
| `DUPLICATE_ENTRY` | 409 | Unique constraint violation | Use different identifier |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests | Implement request throttling |
| `PLC_CONNECTION_ERROR` | 503 | PLC communication failed | Check network and PLC status |
| `SIGNATURE_REQUIRED` | 422 | Electronic signature needed | Provide valid signature |
| `WORKFLOW_VIOLATION` | 422 | Invalid workflow transition | Check current state and permissions |

### Error Handling Best Practices

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class SPCAPIClientWithRetry:
    
    def __init__(self, base_url, api_key, api_secret):
        self.base_url = base_url
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS", "POST", "PUT"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.headers.update({
            'Authorization': f'token {api_key}:{api_secret}',
            'Content-Type': 'application/json'
        })
    
    def submit_measurement_with_retry(self, parameter_code, value, **kwargs):
        """Submit measurement with comprehensive error handling"""
        
        try:
            data = {
                'parameter': parameter_code,
                'measured_value': value,
                **kwargs
            }
            
            response = self.session.post(
                f'{self.base_url}/api/resource/SPC Data Point',
                json=data,
                timeout=(5, 30)  # Connect timeout, read timeout
            )
            
            if response.status_code == 422:
                error_data = response.json()
                if error_data.get('error', {}).get('code') == 'VALIDATION_ERROR':
                    return self.handle_validation_error(error_data, data)
            
            response.raise_for_status()
            return {'success': True, 'data': response.json()}
            
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'Connection failed', 'retry': True}
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Request timeout', 'retry': True}
        except requests.exceptions.HTTPError as e:
            return self.handle_http_error(e)
        except Exception as e:
            return {'success': False, 'error': str(e), 'retry': False}
    
    def handle_validation_error(self, error_data, original_data):
        """Handle validation errors with automatic correction"""
        
        error_details = error_data.get('error', {}).get('details', {})
        field = error_details.get('field')
        
        if field == 'measured_value' and 'required' in error_details.get('validation_rule', ''):
            return {'success': False, 'error': 'Measured value is required', 'field': field}
        elif field == 'parameter' and 'not_found' in error_details.get('validation_rule', ''):
            return {'success': False, 'error': 'Parameter not found', 'field': field}
        
        return {'success': False, 'error': error_data.get('error', {}).get('message')}
    
    def handle_http_error(self, error):
        """Handle HTTP errors with specific guidance"""
        
        status_code = error.response.status_code
        
        if status_code == 429:
            retry_after = error.response.headers.get('Retry-After', 60)
            return {
                'success': False,
                'error': 'Rate limit exceeded',
                'retry_after': int(retry_after),
                'retry': True
            }
        elif status_code == 403:
            return {
                'success': False,
                'error': 'Permission denied - check user role and plant access',
                'retry': False
            }
        elif status_code == 404:
            return {
                'success': False,
                'error': 'Resource not found',
                'retry': False
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {status_code}: {error.response.text}',
                'retry': status_code >= 500
            }
```

## Rate Limiting

### Rate Limits by User Role

| User Role | Requests/Minute | Burst Limit | Notes |
|-----------|----------------|-------------|-------|
| Quality User | 200 | 300 | Full system access |
| Inspector User | 120 | 180 | Data entry focused |
| Manufacturing User | 100 | 150 | Production data |
| Warehouse Bot User | 60 | 90 | Automated warehouse |
| Workstation Bot User | 120 | 180 | High-volume PLC data |
| Weight Bot User | 30 | 45 | Specialized scale data |

### Rate Limiting Headers

```http
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 85
X-RateLimit-Reset: 1642234800
X-RateLimit-Retry-After: 45
```

### Rate Limiting Implementation

```python
import time
from functools import wraps

def rate_limit_aware(func):
    """Decorator for rate limit aware API calls"""
    
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = func(self, *args, **kwargs)
                return response
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get('Retry-After', 60))
                    print(f"Rate limit hit, waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    retry_count += 1
                else:
                    raise e
        
        raise Exception("Max retries exceeded due to rate limiting")
    
    return wrapper

# Usage
class RateLimitAwareClient(SPCAPIClient):
    
    @rate_limit_aware
    def submit_measurement(self, parameter_code, value, **kwargs):
        return super().submit_measurement(parameter_code, value, **kwargs)
```

## Troubleshooting

### Common Issues and Solutions

#### 1. PLC Connection Issues

**Problem**: `PLC_CONNECTION_ERROR` when trying to read data

**Solutions**:
```python
# Test PLC connectivity
result = PLCIntegrationAPI.test_connection('Main-PLC')
if not result['success']:
    print(f"PLC Error: {result['error']}")
    
    # Common fixes:
    # 1. Check IP address and port
    # 2. Verify network connectivity
    # 3. Check PLC authentication
    # 4. Validate protocol settings
```

#### 2. Permission Denied Errors

**Problem**: `PERMISSION_DENIED` when accessing resources

**Solutions**:
```python
# Check user permissions
user_permissions = frappe.get_all('User Permission',
                                filters={'user': frappe.session.user},
                                fields=['*'])

# Verify plant access
if not any(p.allow == 'PLANT-001' for p in user_permissions):
    print("User doesn't have access to PLANT-001")
```

#### 3. Validation Errors

**Problem**: `VALIDATION_ERROR` when submitting data

**Common Issues**:
- Missing required fields
- Invalid data types
- Parameter code not found
- Specification limits violated

**Solutions**:
```python
def validate_data_point(data):
    """Validate data point before submission"""
    
    required_fields = ['parameter', 'measured_value']
    for field in required_fields:
        if field not in data or data[field] is None:
            return f"Required field missing: {field}"
    
    # Check parameter exists
    if not frappe.db.exists('SPC Parameter Master', data['parameter']):
        return f"Parameter not found: {data['parameter']}"
    
    # Validate numeric value
    try:
        float(data['measured_value'])
    except (ValueError, TypeError):
        return "Measured value must be numeric"
    
    return None  # Valid
```

#### 4. Electronic Signature Issues

**Problem**: `SIGNATURE_REQUIRED` or signature validation fails

**Solutions**:
```python
def troubleshoot_signature(document_type, document_name):
    """Troubleshoot electronic signature issues"""
    
    # Check if signature is required
    workflow = frappe.get_doc('Workflow', {'document_type': document_type})
    
    # Check user signature authority
    user_roles = frappe.get_roles(frappe.session.user)
    
    # Verify password
    # (Password validation happens during signature creation)
    
    print(f"Document: {document_type} - {document_name}")
    print(f"User roles: {user_roles}")
    print(f"Signature requirements: Check workflow configuration")
```

### Performance Optimization

#### 1. Bulk Operations

```python
# Use bulk operations for high-volume data
def optimize_bulk_submission(data_points):
    """Optimized bulk data submission"""
    
    # Group by parameter for efficient processing
    grouped_data = {}
    for data in data_points:
        param = data['parameter']
        if param not in grouped_data:
            grouped_data[param] = []
        grouped_data[param].append(data)
    
    # Submit in batches of 100
    batch_size = 100
    results = []
    
    for parameter, param_data in grouped_data.items():
        for i in range(0, len(param_data), batch_size):
            batch = param_data[i:i + batch_size]
            result = BulkOperationsAPI.bulk_submit_data(batch)
            results.append(result)
    
    return results
```

#### 2. Database Query Optimization

```python
# Optimize database queries
def get_optimized_data_points(parameter, days=30):
    """Get data points with optimized query"""
    
    from_date = frappe.utils.add_days(None, -days)
    
    # Use specific fields instead of *
    data = frappe.db.sql("""
        SELECT 
            timestamp, measured_value, x_bar, r_value,
            upper_control_limit, lower_control_limit
        FROM `tabSPC Data Point`
        WHERE parameter = %s 
        AND timestamp >= %s
        AND status = 'Valid'
        ORDER BY timestamp ASC
    """, (parameter, from_date), as_dict=True)
    
    return data
```

#### 3. Caching Strategies

```python
import frappe.cache_manager as cache

def get_cached_control_limits(parameter):
    """Get control limits with caching"""
    
    cache_key = f"control_limits_{parameter}"
    limits = cache.get_value(cache_key)
    
    if not limits:
        # Calculate control limits
        limits = SPCControlChartAPI.calculate_control_limits_for_parameter(parameter)
        
        # Cache for 1 hour
        cache.set_value(cache_key, limits, expires_in_sec=3600)
    
    return limits
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-15  
**Author**: MiniMax Agent  
**Status**: Production Ready  

For technical support, contact: [support@amb-w-spc.com](mailto:support@amb-w-spc.com)