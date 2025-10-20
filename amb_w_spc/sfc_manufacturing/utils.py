# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

"""
AMB-SPC Application Utilities
Integrated Shop Floor Control and Statistical Process Control
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, flt
import json

def get_app_version():
    """Get application version"""
    return "2.0.0"

def get_app_info():
    """Get application information"""
    return {
        'name': 'AMB-SPC',
        'full_name': 'Advanced Manufacturing & Statistical Process Control',
        'version': get_app_version(),
        'description': 'Integrated Shop Floor Control and Quality Management System',
        'modules': [
            'Statistical Process Control (SPC)',
            'Shop Floor Control (SFC)',
            'Quality Management',
            'Production Monitoring'
        ]
    }

def validate_sfc_configuration():
    """Validate SFC module configuration"""
    errors = []
    
    # Check if required doctypes exist
    required_doctypes = [
        'SFC Transaction',
        'SFC Operator',
        'Work Order Routing',
        'SPC Data Point'
    ]
    
    for doctype in required_doctypes:
        if not frappe.db.exists('DocType', doctype):
            errors.append(f"Required DocType '{doctype}' not found")
    
    # Check if workstations are configured
    workstation_count = frappe.db.count('Workstation')
    if workstation_count == 0:
        errors.append("No workstations configured. Please create at least one workstation.")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors
    }

def get_active_work_orders():
    """Get list of active work orders"""
    return frappe.get_all('Work Order', {
        'status': ['in', ['In Process', 'Not Started']]
    }, ['name', 'production_item', 'qty', 'produced_qty', 'status'])

def get_operator_status_summary():
    """Get summary of operator statuses"""
    # Get all operators
    operators = frappe.get_all('SFC Operator', {
        'is_active': 1
    }, ['name', 'operator_name'])
    
    status_summary = {
        'total_operators': len(operators),
        'clocked_in': 0,
        'clocked_out': 0
    }
    
    for operator in operators:
        operator_doc = frappe.get_doc('SFC Operator', operator.name)
        if operator_doc.is_clocked_in():
            status_summary['clocked_in'] += 1
        else:
            status_summary['clocked_out'] += 1
    
    return status_summary

def get_production_efficiency(work_order=None, date_from=None, date_to=None):
    """Calculate production efficiency metrics"""
    conditions = []
    values = []
    
    if work_order:
        conditions.append("t.work_order = %s")
        values.append(work_order)
    
    if date_from:
        conditions.append("DATE(t.timestamp) >= %s")
        values.append(date_from)
    
    if date_to:
        conditions.append("DATE(t.timestamp) <= %s")
        values.append(date_to)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    # Get efficiency data
    efficiency_data = frappe.db.sql(f"""
        SELECT 
            COUNT(CASE WHEN t.transaction_type = 'Complete' THEN 1 END) as completed_operations,
            AVG(CASE WHEN t.actual_time IS NOT NULL AND wr.operation_time IS NOT NULL 
                THEN (wr.operation_time / t.actual_time) * 100 END) as avg_efficiency,
            SUM(CASE WHEN t.actual_time IS NOT NULL THEN t.actual_time ELSE 0 END) as total_actual_time,
            SUM(CASE WHEN wr.operation_time IS NOT NULL THEN wr.operation_time ELSE 0 END) as total_planned_time
        FROM `tabSFC Transaction` t
        LEFT JOIN `tabWork Order Routing` wor ON t.work_order = wor.work_order
        LEFT JOIN `tabWork Order Routing Operation` wr ON wor.name = wr.parent 
            AND t.operation_sequence = wr.sequence
        WHERE {where_clause}
    """, values, as_dict=True)
    
    result = efficiency_data[0] if efficiency_data else {}
    
    # Calculate overall efficiency
    if result.get('total_actual_time') and result.get('total_planned_time'):
        result['overall_efficiency'] = (result['total_planned_time'] / result['total_actual_time']) * 100
    else:
        result['overall_efficiency'] = 0
    
    return result

def create_sample_data():
    """Create sample data for testing and demonstration"""
    try:
        # Create sample items
        sample_items = [
            {'code': 'SAMPLE-PART-001', 'name': 'Sample Part 001'},
            {'code': 'SAMPLE-PART-002', 'name': 'Sample Part 002'}
        ]
        
        for item in sample_items:
            if not frappe.db.exists('Item', item['code']):
                item_doc = frappe.get_doc({
                    'doctype': 'Item',
                    'item_code': item['code'],
                    'item_name': item['name'],
                    'item_group': 'All Item Groups',
                    'stock_uom': 'Nos'
                })
                item_doc.insert(ignore_permissions=True)
        
        # Create sample workstations
        sample_workstations = [
            {'name': 'WS-MACHINE-001', 'desc': 'CNC Machine 001'},
            {'name': 'WS-ASSEMBLY-001', 'desc': 'Assembly Station 001'},
            {'name': 'WS-QUALITY-001', 'desc': 'Quality Control Station'}
        ]
        
        for ws in sample_workstations:
            if not frappe.db.exists('Workstation', ws['name']):
                ws_doc = frappe.get_doc({
                    'doctype': 'Workstation',
                    'name': ws['name'],
                    'workstation_name': ws['desc'],
                    'hour_rate': 100
                })
                ws_doc.insert(ignore_permissions=True)
        
        # Create sample operators
        sample_operators = [
            {'name': 'OP-001', 'full_name': 'John Smith'},
            {'name': 'OP-002', 'full_name': 'Jane Doe'}
        ]
        
        for op in sample_operators:
            if not frappe.db.exists('SFC Operator', op['name']):
                op_doc = frappe.get_doc({
                    'doctype': 'SFC Operator',
                    'name': op['name'],
                    'operator_name': op['full_name'],
                    'is_active': 1
                })
                op_doc.insert(ignore_permissions=True)
        
        return {
            'status': 'success',
            'message': 'Sample data created successfully'
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating sample data: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

def cleanup_test_data():
    """Clean up test data (for development only)"""
    if frappe.conf.get('developer_mode'):
        test_doctypes = [
            'SFC Transaction',
            'SFC Operator Attendance',
            'SPC Data Point',
            'Quality Inspection'
        ]
        
        for doctype in test_doctypes:
            test_records = frappe.get_all(doctype, {'name': ['like', 'TEST-%']})
            for record in test_records:
                try:
                    frappe.delete_doc(doctype, record.name, force=True)
                except:
                    pass
        
        return f"Cleaned up test data from {len(test_doctypes)} doctypes"
    else:
        return "Cleanup only available in developer mode"

def get_system_health():
    """Get system health metrics"""
    try:
        # Check database connectivity
        frappe.db.sql("SELECT 1")
        db_status = 'healthy'
    except:
        db_status = 'error'
    
    # Get recent transaction count
    recent_transactions = frappe.db.count('SFC Transaction', {
        'creation': ['>', frappe.utils.add_days(frappe.utils.now(), -1)]
    })
    
    # Get active operator count
    active_operators = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabSFC Operator Attendance`
        WHERE status = 'Present' AND clock_out_time IS NULL
    """)[0][0]
    
    return {
        'database_status': db_status,
        'recent_transactions_24h': recent_transactions,
        'active_operators': active_operators,
        'app_version': get_app_version(),
        'timestamp': now_datetime()
    }

# Convenience functions for common operations
def quick_start_operation(work_order, sequence, operator, workstation):
    """Quick start operation with validation"""
    try:
        from amb_w_spc.amb_w_spc.api.sfc_operations import start_operation
        return start_operation(work_order, sequence, workstation, operator)
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def quick_complete_operation(work_order, sequence, actual_time=None, measurements=None):
    """Quick complete operation with optional quality data"""
    try:
        from amb_w_spc.amb_w_spc.api.sfc_operations import complete_operation
        from amb_w_spc.amb_w_spc.api.quality_integration import record_quality_measurement
        
        # Complete the operation
        result = complete_operation(work_order, sequence, actual_time)
        
        # Record quality measurements if provided
        if measurements and result.get('status') == 'success':
            quality_result = record_quality_measurement(work_order, sequence, measurements)
            result['quality_recorded'] = quality_result.get('status') == 'success'
        
        return result
    except Exception as e:
        return {'status': 'error', 'message': str(e)}