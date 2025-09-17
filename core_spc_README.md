# Core SPC Module

[![ERPNext](https://img.shields.io/badge/ERPNext-v15%2B-blue.svg)](https://github.com/frappe/erpnext)
[![Python](https://img.shields.io/badge/Python-3.6%2B-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

A comprehensive **Statistical Process Control (SPC)** module for ERPNext, providing enterprise-grade quality control capabilities for manufacturing environments. This module implements industry-standard SPC methodology with real-time statistical calculations, multi-chart support, automated alerting, and regulatory compliance tracking.

## 🎯 Overview

The **core_spc** module is designed to integrate seamlessly with ERPNext's Manufacturing, Quality Management, Stock, and HR modules, providing a complete SPC solution for regulated industries and organizations implementing Six Sigma methodologies.

### Key Highlights
- ✅ **Production-ready SPC implementation** with bilingual support (English/Spanish)
- 📊 **8 different control chart types** including X-bar R, Individual-MR, attribute charts, and advanced CUSUM/EWMA
- 🔄 **Real-time statistical calculations** for X-bar, R-values, moving averages, and process capability indices
- 🚨 **Automated alert system** with Western Electric and Nelson rules implementation
- 📊 **Multi-source data collection** from Manual, PLC, Bot, SCADA, and LIMS systems
- 🔐 **Comprehensive validation system** with client-side and server-side controls
- 🏭 **Multi-plant support** with role-based access control

## 📋 Table of Contents

- [DocTypes](#-doctypes)
- [Key Features](#-key-features)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Usage Examples](#-usage-examples)
- [API Reference](#-api-reference)
- [Integration Guidelines](#-integration-guidelines)
- [Configuration](#%EF%B8%8F-configuration)
- [Performance & Security](#-performance--security)
- [Contributing](#-contributing)
- [License](#-license)

## 📊 DocTypes

The core_spc module consists of **8 DocTypes** organized into main entities and child tables:

### Main DocTypes (4)

#### 1. **SPC Parameter Master**
*Central master data for all quality parameters measured in the plant*

**Purpose**: Defines measurement parameters with their specifications, units, and tolerances.

**Key Features**:
- Unique parameter codes with validation (alphanumeric, hyphens, underscores)
- Multi-company and multi-plant support
- Parameter type classification (Temperature, Brix, Total Solids, pH, Viscosity, etc.)
- Configurable precision for numeric data types
- Child tables for target values, control limits, and specifications

**Fields**:
- `parameter_name` - Descriptive name for the parameter
- `parameter_code` - Alphanumeric identifier (validated, unique)
- `company` - Multi-company support
- `plant` - Plant/warehouse association
- `parameter_type` - Classification of parameter
- `data_type` - Numeric or Text
- `default_precision` - Decimal precision for numeric parameters
- `unit_of_measurement` - UOM link

#### 2. **SPC Data Point**
*Individual measurement records with automated statistical calculations*

**Purpose**: Captures actual measurements and performs real-time statistical analysis.

**Key Features**:
- Real-time X-bar, R-value, and moving average calculations
- Automatic validation against control and specification limits
- Process capability calculations (Cp, Cpk, Pp, Ppk)
- Multi-source data collection support
- Comprehensive audit trail

**Fields**:
- `timestamp` - Measurement time (auto-set to current time)
- `parameter` - Link to SPC Parameter Master
- `measured_value` - Actual measurement (6 decimal precision)
- `plant`, `workstation`, `operator` - Location and personnel tracking
- `batch_number`, `shift` - Production tracking
- `validation_status` - Pending/Validated/Rejected/Under Review
- Statistical fields (auto-calculated): `x_bar`, `r_value`, `moving_average`, etc.

#### 3. **SPC Control Chart**
*Configuration and management of statistical control charts*

**Purpose**: Defines chart parameters, control rules, and alert configurations.

**Supported Chart Types**:
- **X-bar R Chart** - Variable data with subgroups
- **Individual-Moving Range** - Individual measurements
- **p-chart** - Proportion defective
- **c-chart** - Count of defects
- **u-chart** - Defects per unit
- **np-chart** - Number of defective units
- **CUSUM** - Cumulative sum control
- **EWMA** - Exponentially weighted moving average

**Key Features**:
- Western Electric and Nelson rules implementation
- Configurable alert recipients and methods
- Auto-refresh capabilities
- Multiple display and color-coding options

#### 4. **SPC Specification**
*Quality specifications and capability requirements for products*

**Purpose**: Defines quality boundaries, capability targets, and approval workflows.

**Key Features**:
- Complete approval workflow (Draft → Pending → Reviewed → Approved)
- Version control with revision tracking
- Process capability targets (Cpk, Cp, Pp, Ppk)
- Effective date management
- Supporting document attachments
- Regulatory compliance tracking

### Child Table DocTypes (4)

#### 5. **SPC Alert Recipient**
*Child table for managing alert recipients in control charts*

**Features**:
- Multiple alert methods (Email, SMS, Push Notification)
- Configurable alert types (Out of Control, Out of Spec, Trend, Capability)
- Priority levels (Critical, High, Normal, Low)
- User and contact information management

#### 6. **SPC Parameter Control Limit**
*Chart-specific control limits for different chart types*

**Features**:
- Support for all 8 chart types
- Product-specific control limits
- Effective date ranges
- Configurable sigma levels (default 3.0)

#### 7. **SPC Parameter Target Value**
*Product-specific target values with tolerance ranges*

**Features**:
- Product-specific target definitions
- Plus/minus tolerance settings
- Active/inactive status management
- Effective date ranges

#### 8. **SPC Parameter Specification**
*Simplified specification entries for parameter-product associations*

**Features**:
- Quick specification setup
- Product-specific quality limits
- Capability target definitions
- Effective date management

## 🚀 Key Features

### Statistical Process Control Capabilities

#### **Real-time Statistical Calculations**
```python
# Auto-calculated statistical values
- X-bar (mean) from up to 30 recent valid data points
- Range value from last 5 values as subgroup
- Moving range from consecutive value differences
- Standard deviation calculations
- Process capability indices (Cp, Cpk, Pp, Ppk)
```

#### **Control Rules Implementation**
- **Western Electric Rules**: 8 standard violation detection rules
- **Nelson Rules**: Advanced pattern recognition
- **Custom Rule Configuration**: Flexible rule customization

#### **Advanced Chart Types**
- Variable data charts (X-bar R, Individual-MR)
- Attribute data charts (p, np, c, u)
- Advanced monitoring (CUSUM, EWMA)

### Data Collection & Integration

#### **Multi-Source Data Collection**
- 📱 **Manual Entry** - Web interface data input
- 🏭 **PLC Integration** - Real-time equipment data
- 📡 **SCADA Systems** - Process monitoring integration
- 🧪 **LIMS Integration** - Laboratory data import
- 🤖 **Bot/Automated** - Scripted data collection

#### **Comprehensive Validation**
- Client-side immediate feedback
- Server-side integrity validation
- Statistical validation against limits
- Business rule compliance checking

### Alert & Notification System

#### **Alert Methods**
- 📧 Email notifications
- 📱 SMS messaging  
- 🔔 Push notifications
- 📞 Combined multi-method alerts

#### **Alert Types**
- 🚨 Out of Control conditions
- ⚠️ Out of Specification violations
- 📈 Trend alerts for process drift
- 📊 Capability alerts for performance issues
- ⚙️ System alerts for configuration problems

## 💻 Installation

### Prerequisites

- **ERPNext V13+** (recommended V14+)
- **Python 3.6+** for server scripts
- **Administrator access** to ERPNext instance
- **Enabled modules**: Manufacturing, Quality Management, Stock, HR

### Installation Steps

1. **Download and Install Module**
```bash
# Navigate to your Frappe bench
cd /path/to/your/bench

# Install the AMB_W_SPC app
bench get-app https://github.com/rogerboy38/amb_w_spc.git
bench install-app amb_w_spc --site your-site-name
```

2. **Database Migration**
```bash
# Run database migrations
bench migrate --site your-site-name
```

3. **Setup Initial Configuration**
```python
# Execute setup script
import frappe
from amb_w_spc.core_spc.setup_spc import setup_spc_doctypes

# Run in ERPNext console
setup_spc_doctypes()
```

4. **Configure Permissions**
```bash
# Assign roles and permissions through ERPNext UI
# Default roles created: SPC Manager, SPC User
```

## 🚀 Quick Start

### 1. Define Parameters
```python
# Create your first parameter
parameter = frappe.new_doc("SPC Parameter Master")
parameter.parameter_name = "Product Diameter"
parameter.parameter_code = "DIA-001"
parameter.parameter_type = "Dimension"
parameter.data_type = "Numeric"
parameter.default_precision = 3
parameter.unit_of_measurement = "Millimeter"
parameter.company = "Your Company"
parameter.plant = "Main Plant"
parameter.save()
```

### 2. Create Specifications
```python
# Define quality specifications
spec = frappe.new_doc("SPC Specification")
spec.specification_name = "Standard Diameter Spec"
spec.parameter = "DIA-001"
spec.target_value = 25.0
spec.tolerance = 0.05
spec.cpk_target = 1.33
spec.approval_status = "Approved"
spec.save()
```

### 3. Setup Control Charts
```python
# Configure control chart
chart = frappe.new_doc("SPC Control Chart")
chart.chart_name = "Diameter X-bar R Chart"
chart.chart_type = "X-bar R Chart"
chart.parameter = "DIA-001"
chart.sample_size = 5
chart.enable_alerts = 1
chart.western_electric_rules = 1
chart.save()
```

### 4. Record Data Points
```python
# Record measurements
data_point = frappe.new_doc("SPC Data Point")
data_point.parameter = "DIA-001"
data_point.measured_value = 25.02
data_point.operator = frappe.session.user
data_point.save()
# Statistical calculations are performed automatically
```

## 📖 Usage Examples

### Creating a Complete SPC Setup

```python
import frappe
from datetime import datetime

# 1. Create Parameter Master
def create_temperature_parameter():
    if not frappe.db.exists("SPC Parameter Master", {"parameter_code": "TEMP-001"}):
        param = frappe.new_doc("SPC Parameter Master")
        param.parameter_name = "Oven Temperature"
        param.parameter_code = "TEMP-001"
        param.parameter_type = "Temperature"
        param.data_type = "Numeric"
        param.default_precision = 1
        param.unit_of_measurement = "Degree Celsius"
        param.company = frappe.defaults.get_user_default("Company")
        param.plant = frappe.defaults.get_user_default("default_warehouse")
        
        # Add target values
        param.append("target_values", {
            "product_code": "PRODUCT-001",
            "target_value": 180.0,
            "tolerance": 5.0,
            "is_active": 1
        })
        
        param.save()
        return param
    return frappe.get_doc("SPC Parameter Master", {"parameter_code": "TEMP-001"})

# 2. Create Specification
def create_temperature_spec():
    spec = frappe.new_doc("SPC Specification")
    spec.specification_name = "Standard Temperature Spec"
    spec.parameter = "TEMP-001"
    spec.target_value = 180.0
    spec.upper_spec_limit = 185.0
    spec.lower_spec_limit = 175.0
    spec.cpk_target = 1.67
    spec.approval_status = "Approved"
    spec.status = "Active"
    spec.save()
    return spec

# 3. Setup Control Chart with Alerts
def create_temperature_chart():
    chart = frappe.new_doc("SPC Control Chart")
    chart.chart_name = "Temperature Individual-MR Chart"
    chart.chart_type = "Individual-Moving Range"
    chart.parameter = "TEMP-001"
    chart.enable_alerts = 1
    chart.western_electric_rules = 1
    chart.nelson_rules = 1
    
    # Add alert recipient
    chart.append("alert_recipients", {
        "user": frappe.session.user,
        "email": frappe.session.user,
        "alert_method": "Email",
        "alert_types": "Out of Control,Out of Specification",
        "priority_level": "High"
    })
    
    chart.save()
    return chart

# 4. Record Multiple Data Points
def record_temperature_data():
    temperatures = [179.5, 180.2, 181.0, 179.8, 180.5, 182.1, 179.2]
    
    for temp in temperatures:
        data_point = frappe.new_doc("SPC Data Point")
        data_point.parameter = "TEMP-001"
        data_point.measured_value = temp
        data_point.operator = frappe.session.user
        data_point.shift = "Day"
        data_point.save()
        frappe.db.commit()

# Execute complete setup
param = create_temperature_parameter()
spec = create_temperature_spec()
chart = create_temperature_chart()
record_temperature_data()
```

### Bulk Data Import

```python
def bulk_import_data(csv_file_path):
    """Import data from CSV file"""
    import pandas as pd
    
    df = pd.read_csv(csv_file_path)
    
    for index, row in df.iterrows():
        try:
            data_point = frappe.new_doc("SPC Data Point")
            data_point.parameter = row['parameter_code']
            data_point.measured_value = row['measured_value']
            data_point.timestamp = row['timestamp']
            data_point.batch_number = row.get('batch_number', '')
            data_point.operator = row.get('operator', frappe.session.user)
            data_point.save()
            
        except Exception as e:
            frappe.log_error(f"Error importing row {index}: {str(e)}")
    
    frappe.db.commit()
```

## 🔗 API Reference

### REST API Endpoints

The core_spc module provides RESTful API endpoints following ERPNext's standard API structure:

#### **Parameters**
```http
# Get all parameters
GET /api/resource/SPC Parameter Master

# Get specific parameter
GET /api/resource/SPC Parameter Master/{parameter_code}

# Create new parameter
POST /api/resource/SPC Parameter Master
Content-Type: application/json

{
    "parameter_name": "New Parameter",
    "parameter_code": "NEW-001",
    "parameter_type": "Temperature",
    "data_type": "Numeric"
}
```

#### **Data Points**
```http
# Record new measurement
POST /api/resource/SPC Data Point
Content-Type: application/json

{
    "parameter": "TEMP-001",
    "measured_value": 180.5,
    "timestamp": "2024-01-15 10:30:00"
}

# Get data points for parameter
GET /api/resource/SPC Data Point?filters=[["parameter","=","TEMP-001"]]

# Get recent data points
GET /api/resource/SPC Data Point?filters=[["timestamp",">=","2024-01-15"]]&order_by=timestamp desc&limit=100
```

#### **Control Charts**
```http
# Get chart configuration
GET /api/resource/SPC Control Chart/{chart_name}

# Update chart settings
PUT /api/resource/SPC Control Chart/{chart_name}
Content-Type: application/json

{
    "enable_alerts": 1,
    "sigma_level": 3.0,
    "sample_size": 5
}
```

### Python API Methods

#### **Statistical Calculations**
```python
from amb_w_spc.core_spc.spc_server_validations import calculate_statistical_values

# Get statistical values for a data point
doc = frappe.get_doc("SPC Data Point", data_point_name)
stats = calculate_statistical_values(doc)
```

#### **Process Capability**
```python
def calculate_process_capability(parameter_code, days=30):
    """Calculate process capability for parameter"""
    
    # Get recent data points
    data_points = frappe.get_all("SPC Data Point",
        filters={
            "parameter": parameter_code,
            "timestamp": [">=", frappe.utils.add_days(frappe.utils.now(), -days)],
            "status": "Valid"
        },
        fields=["measured_value"]
    )
    
    values = [d.measured_value for d in data_points]
    
    if len(values) >= 30:
        import statistics
        import math
        
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values)
        
        # Get specification limits
        spec = frappe.get_value("SPC Specification", 
            {"parameter": parameter_code, "status": "Active"},
            ["upper_spec_limit", "lower_spec_limit", "target_value"]
        )
        
        if spec:
            usl, lsl, target = spec
            
            # Calculate Cp and Cpk
            cp = (usl - lsl) / (6 * std_dev) if std_dev > 0 else 0
            cpk_upper = (usl - mean) / (3 * std_dev) if std_dev > 0 else 0
            cpk_lower = (mean - lsl) / (3 * std_dev) if std_dev > 0 else 0
            cpk = min(cpk_upper, cpk_lower)
            
            return {
                "cp": cp,
                "cpk": cpk,
                "mean": mean,
                "std_dev": std_dev,
                "sample_size": len(values)
            }
    
    return None
```

### Webhook Integration

```python
# Setup webhook for real-time data collection
def setup_webhook_for_data_collection():
    webhook = frappe.new_doc("Webhook")
    webhook.webhook_doctype = "SPC Data Point"
    webhook.webhook_docevent = "after_insert"
    webhook.request_url = "https://your-system.com/api/spc-data"
    webhook.request_method = "POST"
    webhook.save()
```

## 🔧 Integration Guidelines

### PLC Integration

```python
# Example PLC data integration
def integrate_plc_data():
    """Integrate data from PLC systems"""
    
    # Example using OPC-UA
    try:
        from opcua import Client
        
        client = Client("opc.tcp://plc-server:4840")
        client.connect()
        
        # Read temperature value
        temp_node = client.get_node("ns=2;i=2")  # Temperature node
        temperature = temp_node.get_value()
        
        # Create SPC data point
        data_point = frappe.new_doc("SPC Data Point")
        data_point.parameter = "TEMP-001"
        data_point.measured_value = temperature
        data_point.data_source = "PLC"
        data_point.save()
        
        client.disconnect()
        
    except Exception as e:
        frappe.log_error(f"PLC Integration Error: {str(e)}")
```

### SCADA Integration

```python
# SCADA data integration via MQTT
def setup_mqtt_integration():
    """Setup MQTT listener for SCADA data"""
    
    import paho.mqtt.client as mqtt
    import json
    
    def on_message(client, userdata, message):
        try:
            data = json.loads(message.payload.decode())
            
            # Create data point from SCADA data
            data_point = frappe.new_doc("SPC Data Point")
            data_point.parameter = data['parameter_code']
            data_point.measured_value = data['value']
            data_point.data_source = "SCADA"
            data_point.batch_number = data.get('batch_id', '')
            data_point.save()
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(f"MQTT Integration Error: {str(e)}")
    
    client = mqtt.Client()
    client.on_message = on_message
    client.connect("mqtt-broker", 1883, 60)
    client.subscribe("production/measurements/+")
    client.loop_forever()
```

### LIMS Integration

```python
# Laboratory Information Management System integration
def integrate_lims_data():
    """Integrate laboratory results from LIMS"""
    
    # Example API call to LIMS
    import requests
    
    response = requests.get("https://lims-server/api/results", 
                           headers={"Authorization": "Bearer token"})
    
    if response.status_code == 200:
        results = response.json()
        
        for result in results:
            if result['status'] == 'approved':
                data_point = frappe.new_doc("SPC Data Point")
                data_point.parameter = result['parameter_code']
                data_point.measured_value = result['result_value']
                data_point.data_source = "LIMS"
                data_point.validation_status = "Validated"
                data_point.save()
```

### Custom Dashboard Integration

```javascript
// JavaScript for custom dashboard
function createSPCDashboard() {
    // Real-time chart update
    function updateControlChart(chartName) {
        frappe.call({
            method: 'amb_w_spc.core_spc.api.get_chart_data',
            args: {
                chart_name: chartName,
                limit: 100
            },
            callback: function(r) {
                if (r.message) {
                    renderChart(r.message);
                }
            }
        });
    }
    
    // Auto-refresh every 30 seconds
    setInterval(() => {
        updateControlChart('Temperature Individual-MR Chart');
    }, 30000);
    
    function renderChart(data) {
        // Use Chart.js or similar library
        const ctx = document.getElementById('spcChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.timestamps,
                datasets: [{
                    label: 'Measurements',
                    data: data.values,
                    borderColor: 'blue',
                    backgroundColor: 'rgba(0,0,255,0.1)'
                }, {
                    label: 'UCL',
                    data: data.ucl_line,
                    borderColor: 'red',
                    borderDash: [5, 5]
                }, {
                    label: 'LCL',
                    data: data.lcl_line,
                    borderColor: 'red',
                    borderDash: [5, 5]
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: false
                    }
                }
            }
        });
    }
}
```

## ⚙️ Configuration

### Default Setup Configuration

The module includes an automated setup script that creates:

#### **Default Parameters**
- **Diameter (DIA)**: Millimeter, Precision 3
- **Length (LEN)**: Millimeter, Precision 2  
- **Weight (WT)**: Gram, Precision 2
- **Temperature (TEMP)**: Degree Celsius, Precision 1
- **Pressure (PRESS)**: Bar, Precision 2

#### **System Roles**
- **SPC Manager**: Full system access and configuration
- **SPC User**: Data entry and viewing access

#### **Sample Specifications**
- **Standard Diameter Spec**: Target 25.0mm, ±0.05 tolerance, Cpk 1.33
- **Standard Temperature Spec**: Target 180°C, ±5° tolerance, Cpk 1.67

#### **Number Series**
- `SPC-DATA-.YYYY.-.#####`: For SPC Data Points
- `SPC-SPEC-.YYYY.-.#####`: For SPC Specifications

### Advanced Configuration

#### **Performance Optimization**
```sql
-- Recommended database indexes for large datasets
CREATE INDEX idx_spc_data_point_timestamp ON `tabSPC Data Point` (timestamp);
CREATE INDEX idx_spc_data_point_param_plant ON `tabSPC Data Point` (parameter, plant);
CREATE INDEX idx_spc_data_point_batch ON `tabSPC Data Point` (batch_number);
CREATE INDEX idx_spc_param_plant_dept ON `tabSPC Parameter Master` (plant, department);
```

#### **Custom Validation Rules**
```python
# Add custom validation in hooks.py
doc_events = {
    "SPC Data Point": {
        "validate": "your_app.your_module.custom_validations.validate_data_point"
    }
}

def validate_data_point(doc, method):
    # Add your custom validation logic
    if doc.measured_value < 0:
        frappe.throw("Negative values not allowed for this parameter")
```

#### **Email Alert Templates**
```html
<!-- Custom email template for SPC alerts -->
<div style="padding: 20px; font-family: Arial, sans-serif;">
    <h2 style="color: #d9534f;">SPC Alert: Out of Control Condition</h2>
    <p><strong>Parameter:</strong> {{ parameter_name }}</p>
    <p><strong>Measured Value:</strong> {{ measured_value }} {{ unit }}</p>
    <p><strong>Control Limits:</strong> {{ lcl }} - {{ ucl }}</p>
    <p><strong>Timestamp:</strong> {{ timestamp }}</p>
    <p><strong>Operator:</strong> {{ operator }}</p>
    <p style="color: #d9534f;"><strong>Action Required:</strong> Immediate investigation needed</p>
</div>
```

## 🔒 Performance & Security

### Performance Features

#### **Database Optimization**
- Optimized field ordering for query performance
- Strategic indexing on frequently queried fields
- Configurable data retention policies
- Efficient statistical calculation algorithms

#### **Caching Strategy**
- Parameter master data caching
- Specification limits caching
- Control chart configuration caching
- Statistical calculation result caching

#### **Scalability**
- Support for high-frequency data collection
- Bulk data processing capabilities
- Configurable data archiving
- Multi-plant concurrent operations

### Security Features

#### **Access Control**
- Role-based permissions (Manufacturing Manager, Quality Manager, etc.)
- User-level data access restrictions
- Plant-specific data segregation
- Audit trail for all critical operations

#### **Data Validation**
- Input sanitization for SQL injection prevention
- Client-side and server-side validation
- Business rule enforcement
- Data integrity constraints

#### **Audit & Compliance**
- Complete change tracking
- Digital signature support for specifications
- Regulatory compliance reporting
- Data retention policy enforcement

### Monitoring & Alerting

```python
# System health monitoring
def monitor_spc_system():
    """Monitor SPC system health and performance"""
    
    # Check for missing data points
    missing_data = frappe.db.sql("""
        SELECT parameter, COUNT(*) as expected,
               (SELECT COUNT(*) FROM `tabSPC Data Point` dp 
                WHERE dp.parameter = pm.parameter_code 
                AND dp.timestamp >= NOW() - INTERVAL 1 DAY) as actual
        FROM `tabSPC Parameter Master` pm
        WHERE pm.data_collection_frequency = 'Hourly'
    """, as_dict=True)
    
    # Alert on missing data
    for item in missing_data:
        if item.actual < item.expected * 0.8:  # 80% threshold
            send_system_alert(f"Missing data for parameter {item.parameter}")
    
    # Check system performance
    slow_queries = frappe.db.sql("""
        SELECT * FROM information_schema.processlist 
        WHERE time > 30 AND info LIKE '%SPC%'
    """)
    
    if slow_queries:
        send_system_alert("Slow SPC queries detected")
```

## 🤝 Contributing

We welcome contributions to improve the core_spc module! Here's how you can help:

### Development Setup
```bash
# Clone the repository
git clone https://github.com/rogerboy38/amb_w_spc.git

# Setup development environment
cd amb_w_spc
bench get-app .
bench install-app amb_w_spc --site development.local

# Enable developer mode
bench set-config developer_mode 1 --site development.local
```

### Contribution Guidelines

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Add** tests for your changes
4. **Ensure** all tests pass
5. **Commit** your changes (`git commit -m 'Add amazing feature'`)
6. **Push** to the branch (`git push origin feature/amazing-feature`)
7. **Open** a Pull Request

### Code Standards
- Follow PEP 8 for Python code
- Use ESLint for JavaScript code
- Include docstrings for all functions
- Add unit tests for new features
- Update documentation as needed

### Testing
```bash
# Run tests
bench run-tests --app amb_w_spc

# Run specific test
bench run-tests --app amb_w_spc --module core_spc.tests.test_spc_data_point
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋‍♀️ Support

- **Documentation**: [Full Documentation](docs/)
- **Issues**: [GitHub Issues](https://github.com/rogerboy38/amb_w_spc/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rogerboy38/amb_w_spc/discussions)
- **Email**: support@amb-w-spc.com

## 🗂️ Related Projects

- [ERPNext](https://github.com/frappe/erpnext) - Business management platform
- [Frappe Framework](https://github.com/frappe/frappe) - Web application framework
- [AMB_W_SPC](https://github.com/rogerboy38/amb_w_spc) - Complete SPC application

---

**Made with ❤️ for the manufacturing community**

*Statistical Process Control • Quality Management • Manufacturing Excellence*
