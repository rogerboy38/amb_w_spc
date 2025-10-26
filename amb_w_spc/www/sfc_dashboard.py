# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def get_context(context):
    """Get context for SFC Dashboard page"""
    context.title = _("SFC Production Dashboard")
    
    # Get dashboard data
    context.dashboard_data = get_dashboard_data()
    
    return context

def get_dashboard_data():
    """Get dashboard data for SFC operations"""
    
    # Active work orders
    active_work_orders = frappe.db.sql("""
        SELECT 
            wo.name,
            wo.production_item,
            wo.qty,
            wo.produced_qty,
            wo.status,
            IFNULL((wo.produced_qty / wo.qty) * 100, 0) as completion_percentage
        FROM `tabWork Order` wo
        WHERE wo.status IN ('In Process', 'Not Started')
        ORDER BY wo.planned_start_date
        LIMIT 10
    """, as_dict=True)
    
    # Active operators
    active_operators = frappe.db.sql("""
        SELECT 
            o.name,
            o.operator_name,
            oa.workstation,
            oa.clock_in_time
        FROM `tabSFC Operator` o
        JOIN `tabSFC Operator Attendance` oa ON o.name = oa.operator
        WHERE oa.status = 'Present' AND oa.clock_out_time IS NULL
        ORDER BY oa.clock_in_time
    """, as_dict=True)
    
    # Recent transactions
    recent_transactions = frappe.db.sql("""
        SELECT 
            t.name,
            t.work_order,
            t.operation,
            t.operator,
            t.workstation,
            t.transaction_type,
            t.timestamp,
            t.status
        FROM `tabSFC Transaction` t
        ORDER BY t.timestamp DESC
        LIMIT 20
    """, as_dict=True)
    
    # Workstation utilization
    workstation_utilization = frappe.db.sql("""
        SELECT 
            w.name,
            w.workstation_name,
            COUNT(CASE WHEN t.status = 'In Progress' THEN 1 END) as active_operations,
            COUNT(t.name) as total_operations_today
        FROM `tabWorkstation` w
        LEFT JOIN `tabSFC Transaction` t ON w.name = t.workstation 
            AND DATE(t.timestamp) = CURDATE()
        GROUP BY w.name, w.workstation_name
        ORDER BY active_operations DESC
    """, as_dict=True)
    
    # Production metrics for today
    production_metrics = frappe.db.sql("""
        SELECT 
            COUNT(DISTINCT t.work_order) as work_orders_active,
            COUNT(CASE WHEN t.transaction_type = 'Start' THEN 1 END) as operations_started,
            COUNT(CASE WHEN t.transaction_type = 'Complete' THEN 1 END) as operations_completed,
            AVG(CASE WHEN t.actual_time IS NOT NULL THEN t.actual_time END) as avg_operation_time
        FROM `tabSFC Transaction` t
        WHERE DATE(t.timestamp) = CURDATE()
    """, as_dict=True)
    
    return {
        'active_work_orders': active_work_orders,
        'active_operators': active_operators,
        'recent_transactions': recent_transactions,
        'workstation_utilization': workstation_utilization,
        'production_metrics': production_metrics[0] if production_metrics else {}
    }

@frappe.whitelist()
def get_real_time_data():
    """Get real-time data for dashboard updates"""
    return get_dashboard_data()

@frappe.whitelist()
def get_operator_performance(operator_id, date_range='today'):
    """Get operator performance data"""
    
    date_condition = ""
    if date_range == 'today':
        date_condition = "AND DATE(t.timestamp) = CURDATE()"
    elif date_range == 'week':
        date_condition = "AND t.timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
    elif date_range == 'month':
        date_condition = "AND t.timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
    
    performance_data = frappe.db.sql(f"""
        SELECT 
            COUNT(CASE WHEN t.transaction_type = 'Complete' THEN 1 END) as operations_completed,
            AVG(CASE WHEN t.actual_time IS NOT NULL THEN t.actual_time END) as avg_time_per_operation,
            SUM(CASE WHEN t.actual_time IS NOT NULL THEN t.actual_time END) as total_hours,
            COUNT(DISTINCT DATE(t.timestamp)) as days_worked
        FROM `tabSFC Transaction` t
        WHERE t.operator = %s {date_condition}
    """, (operator_id,), as_dict=True)
    
    return performance_data[0] if performance_data else {}

@frappe.whitelist()
def get_workstation_status(workstation_id):
    """Get current status of a workstation"""
    
    # Get current active operations
    active_operations = frappe.db.sql("""
        SELECT 
            t.work_order,
            t.operation,
            t.operator,
            t.timestamp as start_time
        FROM `tabSFC Transaction` t
        WHERE t.workstation = %s 
            AND t.transaction_type = 'Start'
            AND t.status = 'In Progress'
        ORDER BY t.timestamp
    """, (workstation_id,), as_dict=True)
    
    # Get today's completed operations
    completed_today = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabSFC Transaction` t
        WHERE t.workstation = %s 
            AND t.transaction_type = 'Complete'
            AND DATE(t.timestamp) = CURDATE()
    """, (workstation_id,), as_dict=True)
    
    return {
        'active_operations': active_operations,
        'completed_today': completed_today[0]['count'] if completed_today else 0,
        'status': 'Busy' if active_operations else 'Available'
    }