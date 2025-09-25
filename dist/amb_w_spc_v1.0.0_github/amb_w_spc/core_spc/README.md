# Core SPC DocTypes for ERPNext

This directory contains the core Statistical Process Control (SPC) DocTypes designed for ERPNext V15, implementing a comprehensive SPC system for manufacturing quality control.

## Overview

The SPC system consists of 4 main DocTypes and 3 child table DocTypes that work together to provide complete statistical process control functionality:

### Main DocTypes

1. **SPC Parameter Master** - Central configuration for quality parameters
2. **SPC Data Point** - Individual measurement data with statistical calculations
3. **SPC Control Chart** - Control chart configurations and limits
4. **SPC Specification** - Quality specifications and capability targets

### Child Table DocTypes

1. **SPC Parameter Target Value** - Product-specific target values
2. **SPC Parameter Control Limit** - Chart-specific control limits
3. **SPC Parameter Specification** - Product-specific quality specifications

## DocType Specifications

### 1. SPC Parameter Master (`spc_parameter_master.json`)

**Purpose**: Central master data for all quality parameters measured in the plant.

**Key Features**:
- Unique parameter codes with descriptive names
- Parameter type classification (Temperature, Brix, Total Solids, pH, etc.)
- Plant and department association
- Unit of measure integration
- Child tables for target values, control limits, and specifications
- Active/inactive status tracking

**Important Fields**:
- `parameter_code`: Unique identifier (required)
- `parameter_name`: Descriptive name (required)
- `parameter_type`: Classified parameter types (required)
- `unit_of_measure`: Links to UOM master
- `plant`: Links to Warehouse (required)
- `department`: Links to Department master

**Child Tables**:
- `target_values`: Product-specific target values
- `control_limits`: Chart-specific control limits
- `specifications`: Quality specifications per product

### 2. SPC Data Point (`spc_data_point.json`)

**Purpose**: Individual measurement records with statistical calculations and audit trail.

**Key Features**:
- High-performance data structure optimized for large volumes
- Multiple data sources (Manual, PLC, Bot, SCADA, LIMS)
- Real-time statistical calculations (X-value, R-value, moving averages)
- Complete audit trail with approval workflow
- Out-of-control detection and violation tracking
- Batch and shift tracking for traceability

**Important Fields**:
- `timestamp`: Measurement time (required)
- `measured_value`: Actual measurement (required, precision 6)
- `parameter`: Links to SPC Parameter Master (required)
- `plant`: Plant location (required)
- `data_source`: Source of measurement (required)
- `validation_status`: Quality validation status
- `is_out_of_control`: Automated SPC rule violation flag

**Statistical Fields**:
- `x_value`: X-bar chart value
- `r_value`: Range chart value
- `moving_average`: Calculated moving average
- `standard_deviation`: Process standard deviation

### 3. SPC Control Chart (`spc_control_chart.json`)

**Purpose**: Configuration and management of statistical control charts.

**Key Features**:
- Multiple chart types (X-bar R, Individual-Moving Range, p-chart, c-chart, etc.)
- Configurable control limits and statistical parameters
- Western Electric and Nelson rules implementation
- Auto-update capabilities with data point limits
- Alert configuration and display options
- Real-time to monthly chart periods

**Important Fields**:
- `chart_name`: Unique chart identifier (required)
- `chart_type`: Statistical chart type (required)
- `parameter`: Associated parameter (required)
- `ucl/lcl`: Upper/Lower control limits
- `subgroup_size`: Statistical subgroup size
- `control_period`: Period for control limit calculation

**Chart Types Supported**:
- X-bar R (Variable data with subgroups)
- Individual-Moving Range (Individual measurements)
- p-chart (Proportion defective)
- c-chart (Count of defects)
- u-chart (Defects per unit)
- np-chart (Number of defective units)
- CUSUM (Cumulative sum)
- EWMA (Exponentially weighted moving average)

### 4. SPC Specification (`spc_specification.json`)

**Purpose**: Quality specifications and capability requirements for products and parameters.

**Key Features**:
- Product-specific quality limits (USL/LSL)
- Process capability targets (Cp, Cpk, Pp, Ppk)
- Six Sigma level targets and defect rates
- Approval workflow with version control
- Regulatory and customer requirements tracking
- Document attachment support

**Important Fields**:
- `specification_name`: Unique specification name (required)
- `upper_spec_limit/lower_spec_limit`: Quality boundaries
- `cpk_target`: Process capability target (default 1.33)
- `sigma_level`: Six Sigma level target (default 4.0)
- `approval_status`: Workflow status
- `revision`: Version control

## Child Table DocTypes

### SPC Parameter Target Value
Product-specific target values with tolerance ranges and effective date management.

### SPC Parameter Control Limit  
Chart-specific control limits supporting different chart types with sigma level configuration.

### SPC Parameter Specification
Simplified specification entries for quick parameter-product associations.

## Implementation Guidelines

### 1. Database Performance Optimization

**Indexing Strategy**:
- Primary indexes on timestamp, parameter, plant combinations
- Composite indexes for common query patterns
- Separate indexes for statistical calculations

**Recommended Indexes**:
```sql
-- SPC Data Point performance indexes
CREATE INDEX idx_spc_data_point_timestamp ON `tabSPC Data Point` (timestamp);
CREATE INDEX idx_spc_data_point_param_plant ON `tabSPC Data Point` (parameter, plant);
CREATE INDEX idx_spc_data_point_batch ON `tabSPC Data Point` (batch_number);

-- SPC Parameter Master indexes
CREATE INDEX idx_spc_param_plant_dept ON `tabSPC Parameter Master` (plant, department);
CREATE INDEX idx_spc_param_type ON `tabSPC Parameter Master` (parameter_type);
```

### 2. Data Validation Rules

**SPC Data Point Validations**:
- Timestamp cannot be in the future
- Measured value must be numeric and within reasonable bounds
- Data source must be from approved list
- Parameter must be active in the specified plant

**SPC Specification Validations**:
- USL must be greater than LSL
- Target value should be between USL and LSL
- Cpk target should be >= 1.0 for manufacturing processes
- Effective date cannot be in the past for new specifications

### 3. Statistical Calculations

**Real-time Calculations**:
- X-bar and R values calculated upon data entry
- Moving averages updated with configurable window size
- Standard deviation calculated using appropriate method (sample/population)
- Control limit violations checked against Western Electric rules

**Performance Considerations**:
- Use database triggers for high-frequency calculations
- Implement caching for frequently accessed statistical values
- Consider batch processing for historical data analysis

### 4. Integration Points

**ERPNext Standard Modules**:
- **Manufacturing**: Work Order integration for batch tracking
- **Stock**: Item and Warehouse integration for plant/product mapping
- **HR**: Employee integration for operator tracking
- **Quality Management**: Quality Inspection integration

**External Systems**:
- **PLC Integration**: Real-time data acquisition from production equipment
- **LIMS Integration**: Laboratory data synchronization
- **SCADA Systems**: Process data collection and monitoring

### 5. Permissions and Security

**Role-Based Access Control**:
- **Manufacturing Manager**: Full access to all SPC functions
- **Quality Manager**: Create/edit parameters, specifications, and charts
- **Manufacturing User**: Create data points, view charts (limited edit)
- **Operator**: Create manual data points only

**Data Security**:
- Audit trail for all critical data changes
- Approval workflow for specifications and control limits
- Version control for specification changes
- Data validation and integrity checks

## Usage Examples

### Creating a New Parameter
```python
# Example: Temperature parameter for pasteurization
parameter = frappe.new_doc("SPC Parameter Master")
parameter.parameter_code = "TEMP_PAST_001"
parameter.parameter_name = "Pasteurization Temperature"
parameter.parameter_type = "Temperature"
parameter.unit_of_measure = "°C"
parameter.plant = "Main Plant"
parameter.department = "Production"
parameter.save()
```

### Recording Data Points
```python
# Example: Manual temperature reading
data_point = frappe.new_doc("SPC Data Point")
data_point.timestamp = frappe.utils.now()
data_point.parameter = "TEMP_PAST_001"
data_point.measured_value = 72.5
data_point.plant = "Main Plant"
data_point.operator = "EMP001"
data_point.data_source = "Manual"
data_point.batch_number = "BATCH2025001"
data_point.shift = "Day"
data_point.save()
```

### Setting Up Control Charts
```python
# Example: X-bar R chart for temperature
chart = frappe.new_doc("SPC Control Chart")
chart.chart_name = "Temperature Control Chart"
chart.chart_type = "X-bar R"
chart.parameter = "TEMP_PAST_001"
chart.plant = "Main Plant"
chart.subgroup_size = 5
chart.ucl = 75.0
chart.lcl = 70.0
chart.center_line = 72.5
chart.save()
```

## Migration and Deployment

### Installation Steps
1. Copy all JSON files to ERPNext apps/[app_name]/[app_name]/[module]/doctype/
2. Run `bench migrate` to create database tables
3. Set up initial master data (parameters, plants, departments)
4. Configure control charts and specifications
5. Begin data collection and monitoring

### Data Migration
- Import existing historical data using Data Import Tool
- Validate data integrity after migration
- Recalculate statistical values for imported data
- Set up automated data collection from existing systems

## Maintenance and Monitoring

### Regular Tasks
- Review and update control limits monthly
- Validate data source integrations daily
- Monitor system performance and optimize queries
- Update specifications per product changes
- Archive old data per retention policy

### Performance Monitoring
- Track data point creation rates
- Monitor chart calculation performance
- Review storage utilization growth
- Validate statistical accuracy periodically

## Conclusion

This SPC DocType implementation provides a robust foundation for statistical process control in ERPNext, supporting both manual and automated data collection with comprehensive statistical analysis capabilities. The modular design allows for easy customization and extension based on specific manufacturing requirements.