# Warehouse Management Module

This module provides advanced warehouse management functionality integrated with SAP Movement Types and zone tracking for the AMB W SPC system.

## Features

### SAP Movement Type Support
- **261 (FrontFlush)**: Goods Issue for Production
- **311 (BackFlush)**: Transfer for Kitting
- Automatic purpose mapping based on movement type
- Warehouse type validation for movements

### Zone Status Tracking
- **Red Zone**: Incomplete materials (< 100% availability)
- **Green Zone**: Complete materials (100% availability)
- Real-time material completion percentage calculation
- Work Order integration for zone status updates

### Digital Signatures
- Warehouse Supervisor signature (required for all movements)
- Kitting Supervisor signature (required for SAP 311 movements)
- Timestamp tracking for signatures
- Workflow integration

### GI/GT Slip Generation
- Automatic slip number generation
- Print and email functionality
- Integration with signature workflow

## File Structure

```
warehouse_management/
├── __init__.py
├── README.md
├── stock_entry.py          # Stock Entry enhancements
├── warehouse.py            # Warehouse configuration
├── work_order.py           # Work Order zone tracking
└── integration.py          # System integrations
```

## Custom Fields Added

### Stock Entry
- `custom_sap_movement_type`: SAP Movement Type selection
- `custom_work_order_reference`: Link to Work Order
- `custom_zone_status`: Red/Green zone status
- `custom_zone_status_color`: Color indicator
- `custom_material_completion_percentage`: Completion percentage
- `custom_gi_gt_slip_number`: GI/GT slip reference
- `custom_gi_gt_slip_generated_on`: Slip generation timestamp
- `custom_warehouse_supervisor_signature`: Supervisor signature
- `custom_warehouse_supervisor_sign_date`: Signature timestamp
- `custom_kitting_supervisor_signature`: Kitting signature
- `custom_kitting_supervisor_sign_date`: Kitting signature timestamp

### Warehouse
- `custom_temperature_control`: Enable temperature monitoring
- `custom_target_temperature`: Target temperature setting
- `custom_warehouse_code`: Unique warehouse code
- `custom_is_zone_warehouse`: Zone warehouse flag
- `custom_zone_type`: Red/Green zone type
- `custom_max_capacity`: Maximum storage capacity
- `custom_current_utilization`: Current utilization percentage
- `custom_last_capacity_update`: Last capacity update timestamp

### Work Order
- `custom_current_zone_status`: Current zone status
- `custom_zone_status_color`: Zone status color
- `custom_material_completion_percentage`: Material completion %
- `custom_last_stock_entry`: Last related stock entry
- `custom_last_zone_update`: Last zone status update
- `custom_missing_materials_json`: Missing materials data

## Integration Points

### Batch AMB System
- Automatic warehouse operation logging
- SAP movement type tracking in batch history
- GI/GT slip reference in batch records

### MRP Planning System
- Zone status integration with MRP planning
- Material availability tracking
- Work Order status updates

### Quality Management
- Quality inspection integration with warehouse context
- SAP movement type context for quality checks
- Signature validation for quality processes

### FDA Compliance
- Audit trail creation for warehouse operations
- Electronic signature tracking
- Movement type compliance logging

## API Endpoints

### Work Order Material Status
```python
@frappe.whitelist()
def get_work_order_material_status(work_order_name):
    """Get detailed material status for a Work Order"""
```

### Zone Status Update
```python
@frappe.whitelist()
def update_work_order_zone_status(work_order_name):
    """Update Work Order zone status"""
```

### Custom Stock Entry Creation
```python
@frappe.whitelist()
def make_custom_stock_entry(work_order, purpose, qty=None):
    """Create Stock Entry with SAP movement type"""
```

### Warehouse Hierarchy Creation
```python
@frappe.whitelist()
def create_warehouse_hierarchy(company, locations=None):
    """Create complete warehouse hierarchy"""
```

### Integration Status
```python
@frappe.whitelist()
def get_integration_status(work_order_name):
    """Get integration status for a Work Order"""
```

## JavaScript Enhancements

### Stock Entry Form
- SAP movement type validation
- Signature field styling
- Zone status display
- Material status dialog
- GI/GT slip printing

### Work Order Form
- Zone status dashboard
- Material status checking
- Stock entry creation
- Related stock entries view

## CSS Styling

Custom CSS classes for visual enhancement:
- `.zone-red`: Red zone styling
- `.zone-green`: Green zone styling
- `.signature-completed`: Completed signature styling
- `.completion-low/medium/high`: Completion percentage styling

## Installation

The warehouse management module is automatically installed when AMB W SPC is installed. The installation includes:

1. Custom field creation
2. DocType installation (Material Assessment Log)
3. Default warehouse hierarchy creation
4. Permission setup
5. Hook registration

## Usage

### Creating SAP Movement Stock Entries

1. Navigate to Stock Entry
2. Select appropriate Purpose
3. Choose SAP Movement Type (261 or 311)
4. Link to Work Order (if applicable)
5. Complete required signatures
6. Submit the entry

### Zone Status Monitoring

1. Open Work Order
2. Click "Check Material Status" to view detailed material availability
3. Click "Update Zone Status" to refresh zone status
4. Monitor zone status changes in real-time

### Warehouse Configuration

1. Navigate to Warehouse
2. Enable temperature control if needed
3. Set warehouse code for identification
4. Configure zone type (Red/Green) if applicable
5. Set capacity limits

## Validation Rules

### SAP Movement Type Validation
- 261: Material Issue from Raw Material to Production
- 311: Material Transfer from Production to Kitting
- Warehouse type validation based on movement

### Signature Requirements
- SAP 261: Warehouse Supervisor signature required
- SAP 311: Both Warehouse and Kitting Supervisor signatures required

### Zone Status Rules
- Red Zone: Material completion < 100%
- Green Zone: Material completion = 100%
- Automatic calculation based on BOM requirements

## Error Handling

The module includes comprehensive error handling:
- Invalid SAP movement type validation
- Missing signature validation
- Warehouse permission checking
- Material availability validation
- Integration error logging

## Backward Compatibility

This module is designed to work alongside existing AMB W SPC functionality:
- Does not modify existing Batch AMB DocTypes
- Preserves existing MRP Planning functionality
- Maintains SPC and FDA compliance systems
- Adds enhancements without breaking changes

## Support

For support and troubleshooting:
1. Check Frappe error logs for detailed error messages
2. Verify custom field installation
3. Ensure proper permissions are set
4. Check integration status using provided API endpoints
