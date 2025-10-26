# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate
import json

@frappe.whitelist()
def record_quality_measurement(work_order, operation_sequence, measurements, inspector=None):
    """Record quality measurements for an operation"""
    try:
        # Validate inputs
        if not all([work_order, operation_sequence, measurements]):
            frappe.throw(_("work_order, operation_sequence, and measurements are required"))
        
        # Parse measurements if string
        if isinstance(measurements, str):
            measurements = json.loads(measurements)
        
        # Find the corresponding SFC transaction
        transaction = frappe.get_value('SFC Transaction', {
            'work_order': work_order,
            'operation_sequence': operation_sequence,
            'transaction_type': 'Complete'
        }, 'name', order_by='timestamp desc')
        
        if not transaction:
            frappe.throw(_(f"No completed operation found for work order {work_order}, sequence {operation_sequence}"))
        
        # Create quality record
        quality_doc = frappe.get_doc({
            'doctype': 'Quality Inspection',
            'reference_type': 'SFC Transaction',
            'reference_name': transaction,
            'work_order': work_order,
            'operation_sequence': operation_sequence,
            'inspector': inspector or frappe.session.user,
            'inspection_date': frappe.utils.today(),
            'measurements': json.dumps(measurements)
        })
        
        # Process measurements for SPC analysis
        for param, value in measurements.items():
            if isinstance(value, (int, float)):
                # Create SPC data point
                spc_doc = frappe.get_doc({
                    'doctype': 'SPC Data Point',
                    'work_order': work_order,
                    'operation': operation_sequence,
                    'parameter': param,
                    'measurement_value': flt(value),
                    'timestamp': frappe.utils.now_datetime(),
                    'source': 'SFC Operation',
                    'reference_doc': transaction
                })
                spc_doc.insert(ignore_permissions=True)
        
        quality_doc.insert(ignore_permissions=True)
        
        # Update SFC transaction with quality data
        frappe.db.set_value('SFC Transaction', transaction, 
                           'quality_data', json.dumps(measurements))
        
        return {
            'status': 'success',
            'quality_inspection': quality_doc.name,
            'message': _("Quality measurements recorded successfully")
        }
        
    except Exception as e:
        frappe.log_error(f"Error recording quality measurement: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

@frappe.whitelist()
def get_spc_analysis(work_order=None, operation=None, parameter=None, days=30):
    """Get SPC analysis for quality parameters"""
    try:
        conditions = []
        values = []
        
        if work_order:
            conditions.append("work_order = %s")
            values.append(work_order)
        
        if operation:
            conditions.append("operation = %s")
            values.append(operation)
        
        if parameter:
            conditions.append("parameter = %s")
            values.append(parameter)
        
        # Add date filter
        conditions.append("timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)")
        values.append(days)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Get measurement data
        data_points = frappe.db.sql(f"""
            SELECT 
                parameter,
                measurement_value,
                timestamp,
                work_order,
                operation
            FROM `tabSPC Data Point`
            WHERE {where_clause}
            ORDER BY parameter, timestamp
        """, values, as_dict=True)
        
        # Group by parameter for analysis
        parameter_data = {}
        for point in data_points:
            param = point['parameter']
            if param not in parameter_data:
                parameter_data[param] = []
            parameter_data[param].append({
                'value': point['measurement_value'],
                'timestamp': point['timestamp'],
                'work_order': point['work_order'],
                'operation': point['operation']
            })
        
        # Calculate SPC statistics for each parameter
        analysis_results = {}
        for param, values_list in parameter_data.items():
            if len(values_list) >= 3:  # Minimum points for analysis
                values_only = [v['value'] for v in values_list]
                
                # Calculate basic statistics
                mean = sum(values_only) / len(values_only)
                variance = sum([(x - mean) ** 2 for x in values_only]) / len(values_only)
                std_dev = variance ** 0.5
                
                # Calculate control limits (3-sigma)
                ucl = mean + (3 * std_dev)
                lcl = mean - (3 * std_dev)
                
                # Identify out-of-control points
                out_of_control = []
                for i, v in enumerate(values_list):
                    if v['value'] > ucl or v['value'] < lcl:
                        out_of_control.append({
                            'index': i,
                            'value': v['value'],
                            'timestamp': v['timestamp'],
                            'work_order': v['work_order']
                        })
                
                analysis_results[param] = {
                    'mean': mean,
                    'std_dev': std_dev,
                    'ucl': ucl,
                    'lcl': lcl,
                    'data_points': values_list,
                    'out_of_control': out_of_control,
                    'process_capability': calculate_process_capability(values_only, ucl, lcl)
                }
        
        return {
            'status': 'success',
            'analysis': analysis_results,
            'total_points': len(data_points)
        }
        
    except Exception as e:
        frappe.log_error(f"Error in SPC analysis: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

def calculate_process_capability(values, ucl, lcl):
    """Calculate process capability indices"""
    if len(values) < 10:  # Need sufficient data
        return None
    
    # Calculate Cp and Cpk
    mean = sum(values) / len(values)
    std_dev = (sum([(x - mean) ** 2 for x in values]) / len(values)) ** 0.5
    
    if std_dev == 0:
        return None
    
    # Assume specification limits equal control limits for simplicity
    usl = ucl  # Upper specification limit
    lsl = lcl  # Lower specification limit
    
    cp = (usl - lsl) / (6 * std_dev) if (usl - lsl) > 0 else 0
    cpk = min((usl - mean) / (3 * std_dev), (mean - lsl) / (3 * std_dev))
    
    return {
        'cp': cp,
        'cpk': cpk,
        'interpretation': get_capability_interpretation(cp, cpk)
    }

def get_capability_interpretation(cp, cpk):
    """Get interpretation of capability indices"""
    if cpk >= 1.33:
        return "Excellent capability"
    elif cpk >= 1.0:
        return "Good capability"
    elif cpk >= 0.67:
        return "Marginal capability"
    else:
        return "Poor capability - process improvement needed"

@frappe.whitelist()
def generate_quality_report(work_order, date_from=None, date_to=None):
    """Generate comprehensive quality report for a work order"""
    try:
        date_conditions = ""
        values = [work_order]
        
        if date_from:
            date_conditions += " AND DATE(t.timestamp) >= %s"
            values.append(getdate(date_from))
        
        if date_to:
            date_conditions += " AND DATE(t.timestamp) <= %s"
            values.append(getdate(date_to))
        
        # Get quality data
        quality_data = frappe.db.sql(f"""
            SELECT 
                t.operation_sequence,
                t.operation,
                t.quality_data,
                t.timestamp,
                t.operator,
                o.operator_name
            FROM `tabSFC Transaction` t
            LEFT JOIN `tabSFC Operator` o ON t.operator = o.name
            WHERE t.work_order = %s 
                AND t.transaction_type = 'Complete'
                AND t.quality_data IS NOT NULL
                {date_conditions}
            ORDER BY t.operation_sequence, t.timestamp
        """, values, as_dict=True)
        
        # Process quality data
        report_data = []
        for record in quality_data:
            if record.quality_data:
                try:
                    measurements = json.loads(record.quality_data)
                    for param, value in measurements.items():
                        report_data.append({
                            'operation_sequence': record.operation_sequence,
                            'operation': record.operation,
                            'parameter': param,
                            'value': value,
                            'timestamp': record.timestamp,
                            'operator': record.operator_name
                        })
                except:
                    continue
        
        # Get SPC analysis for this work order
        spc_analysis = get_spc_analysis(work_order=work_order)
        
        return {
            'status': 'success',
            'work_order': work_order,
            'quality_data': report_data,
            'spc_analysis': spc_analysis.get('analysis', {}),
            'date_range': {
                'from': date_from,
                'to': date_to
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error generating quality report: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }