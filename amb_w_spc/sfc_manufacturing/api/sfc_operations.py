# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime, flt, get_time_zone
import json

@frappe.whitelist()
def start_operation(work_order, operation_sequence, workstation, operator):
    """API to start an operation"""
    try:
        # Validate inputs
        if not all([work_order, operation_sequence, workstation, operator]):
            frappe.throw(_("All fields are required: work_order, operation_sequence, workstation, operator"))
        
        # Check if operator is clocked in
        operator_doc = frappe.get_doc('SFC Operator', operator)
        if not operator_doc.is_clocked_in():
            frappe.throw(_(f"Operator {operator} is not clocked in"))
        
        # Check if operation is already started
        existing = frappe.get_value('SFC Transaction', {
            'work_order': work_order,
            'operation_sequence': operation_sequence,
            'transaction_type': 'Start',
            'status': 'In Progress'
        })
        
        if existing:
            frappe.throw(_(f"Operation {operation_sequence} is already started"))
        
        # Get work order routing
        routing = frappe.get_value('Work Order Routing', {'work_order': work_order}, 'name')
        if not routing:
            frappe.throw(_(f"No routing found for work order {work_order}"))
        
        routing_doc = frappe.get_doc('Work Order Routing', routing)
        operation = routing_doc.get_operation_by_sequence(operation_sequence)
        
        if not operation:
            frappe.throw(_(f"Operation sequence {operation_sequence} not found in routing"))
        
        # Start the operation
        transaction_id = routing_doc.start_operation(operation_sequence, workstation, operator)
        
        return {
            'status': 'success',
            'transaction_id': transaction_id,
            'message': _(f"Operation {operation.operation} started successfully")
        }
        
    except Exception as e:
        frappe.log_error(f"Error starting operation: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

@frappe.whitelist()
def complete_operation(work_order, operation_sequence, actual_time=None, quality_data=None):
    """API to complete an operation"""
    try:
        # Validate inputs
        if not all([work_order, operation_sequence]):
            frappe.throw(_("work_order and operation_sequence are required"))
        
        # Get work order routing
        routing = frappe.get_value('Work Order Routing', {'work_order': work_order}, 'name')
        if not routing:
            frappe.throw(_(f"No routing found for work order {work_order}"))
        
        routing_doc = frappe.get_doc('Work Order Routing', routing)
        
        # Parse quality data if provided
        if quality_data and isinstance(quality_data, str):
            try:
                quality_data = json.loads(quality_data)
            except:
                quality_data = None
        
        # Complete the operation
        transaction_id = routing_doc.complete_operation(
            operation_sequence, 
            flt(actual_time) if actual_time else None,
            quality_data
        )
        
        return {
            'status': 'success',
            'transaction_id': transaction_id,
            'message': _(f"Operation {operation_sequence} completed successfully")
        }
        
    except Exception as e:
        frappe.log_error(f"Error completing operation: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

@frappe.whitelist()
def get_work_order_status(work_order):
    """Get current status of a work order"""
    try:
        # Get work order routing
        routing = frappe.get_value('Work Order Routing', {'work_order': work_order}, 'name')
        if not routing:
            return {
                'status': 'error',
                'message': _(f"No routing found for work order {work_order}")
            }
        
        routing_doc = frappe.get_doc('Work Order Routing', routing)
        
        # Get all transactions for this work order
        transactions = frappe.get_all('SFC Transaction', {
            'work_order': work_order
        }, ['operation_sequence', 'transaction_type', 'status', 'timestamp', 'actual_time'])
        
        # Organize by operation sequence
        operations_status = {}
        for op in routing_doc.operations:
            operations_status[op.sequence] = {
                'operation': op.operation,
                'sequence': op.sequence,
                'estimated_time': op.operation_time,
                'status': 'Not Started',
                'start_time': None,
                'end_time': None,
                'actual_time': None
            }
        
        # Update with transaction data
        for txn in transactions:
            seq = txn.operation_sequence
            if seq in operations_status:
                if txn.transaction_type == 'Start':
                    operations_status[seq]['start_time'] = txn.timestamp
                    operations_status[seq]['status'] = 'In Progress'
                elif txn.transaction_type == 'Complete':
                    operations_status[seq]['end_time'] = txn.timestamp
                    operations_status[seq]['actual_time'] = txn.actual_time
                    operations_status[seq]['status'] = 'Completed'
        
        # Calculate overall progress
        total_ops = len(routing_doc.operations)
        completed_ops = sum(1 for op in operations_status.values() if op['status'] == 'Completed')
        progress_percentage = (completed_ops / total_ops) * 100 if total_ops > 0 else 0
        
        return {
            'status': 'success',
            'work_order': work_order,
            'operations': list(operations_status.values()),
            'progress_percentage': progress_percentage,
            'total_operations': total_ops,
            'completed_operations': completed_ops
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting work order status: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

@frappe.whitelist()
def clock_in_operator(operator, workstation):
    """API to clock in an operator"""
    try:
        operator_doc = frappe.get_doc('SFC Operator', operator)
        attendance_id = operator_doc.clock_in(workstation)
        
        return {
            'status': 'success',
            'attendance_id': attendance_id,
            'message': _(f"Operator {operator_doc.operator_name} clocked in successfully")
        }
        
    except Exception as e:
        frappe.log_error(f"Error clocking in operator: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

@frappe.whitelist()
def clock_out_operator(operator):
    """API to clock out an operator"""
    try:
        operator_doc = frappe.get_doc('SFC Operator', operator)
        attendance_id = operator_doc.clock_out()
        
        return {
            'status': 'success',
            'attendance_id': attendance_id,
            'message': _(f"Operator {operator_doc.operator_name} clocked out successfully")
        }
        
    except Exception as e:
        frappe.log_error(f"Error clocking out operator: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

@frappe.whitelist()
def get_operator_workload(operator, date=None):
    """Get operator's current workload and statistics"""
    try:
        if not date:
            date = frappe.utils.today()
        
        operator_doc = frappe.get_doc('SFC Operator', operator)
        
        # Get daily hours
        daily_hours = operator_doc.get_daily_hours(date)
        
        # Get current active operations
        active_operations = frappe.get_all('SFC Transaction', {
            'operator': operator,
            'transaction_type': 'Start',
            'status': 'In Progress'
        }, ['work_order', 'operation', 'operation_sequence', 'timestamp'])
        
        # Get completed operations today
        completed_today = frappe.get_all('SFC Transaction', {
            'operator': operator,
            'transaction_type': 'Complete',
            'creation': ['like', f"{date}%"]
        }, ['work_order', 'operation', 'actual_time'])
        
        return {
            'status': 'success',
            'operator': operator_doc.operator_name,
            'daily_hours': daily_hours,
            'is_clocked_in': operator_doc.is_clocked_in(),
            'current_workstation': operator_doc.get_current_workstation(),
            'active_operations': active_operations,
            'completed_operations_today': len(completed_today),
            'total_time_today': sum([flt(op.get('actual_time', 0)) for op in completed_today])
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting operator workload: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

@frappe.whitelist()
def get_production_summary(date=None):
    """Get production summary for a specific date"""
    try:
        if not date:
            date = frappe.utils.today()
        
        # Get work orders with activity on this date
        work_orders = frappe.db.sql("""
            SELECT DISTINCT 
                t.work_order,
                wo.production_item,
                wo.qty as planned_qty,
                wo.produced_qty,
                COUNT(DISTINCT CASE WHEN t.transaction_type = 'Complete' THEN t.operation_sequence END) as completed_operations,
                COUNT(DISTINCT wor.sequence) as total_operations
            FROM `tabSFC Transaction` t
            LEFT JOIN `tabWork Order` wo ON t.work_order = wo.name
            LEFT JOIN `tabWork Order Routing` worc ON t.work_order = worc.work_order
            LEFT JOIN `tabWork Order Routing Operation` wor ON worc.name = wor.parent
            WHERE DATE(t.timestamp) = %s
            GROUP BY t.work_order
        """, (date,), as_dict=True)
        
        # Get operator performance
        operator_performance = frappe.db.sql("""
            SELECT 
                t.operator,
                o.operator_name,
                COUNT(CASE WHEN t.transaction_type = 'Complete' THEN 1 END) as operations_completed,
                SUM(CASE WHEN t.actual_time IS NOT NULL THEN t.actual_time ELSE 0 END) as total_hours
            FROM `tabSFC Transaction` t
            LEFT JOIN `tabSFC Operator` o ON t.operator = o.name
            WHERE DATE(t.timestamp) = %s
            GROUP BY t.operator
            ORDER BY operations_completed DESC
        """, (date,), as_dict=True)
        
        # Get workstation utilization
        workstation_utilization = frappe.db.sql("""
            SELECT 
                t.workstation,
                COUNT(CASE WHEN t.transaction_type = 'Start' THEN 1 END) as operations_started,
                COUNT(CASE WHEN t.transaction_type = 'Complete' THEN 1 END) as operations_completed,
                AVG(CASE WHEN t.actual_time IS NOT NULL THEN t.actual_time END) as avg_time
            FROM `tabSFC Transaction` t
            WHERE DATE(t.timestamp) = %s AND t.workstation IS NOT NULL
            GROUP BY t.workstation
            ORDER BY operations_completed DESC
        """, (date,), as_dict=True)
        
        return {
            'status': 'success',
            'date': date,
            'work_orders': work_orders,
            'operator_performance': operator_performance,
            'workstation_utilization': workstation_utilization
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting production summary: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }