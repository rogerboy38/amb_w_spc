"""
Warehouse Management Scheduler Tasks
Handles all scheduled operations for warehouse optimization and monitoring
"""

import frappe
from frappe.utils import now_datetime, add_days, getdate
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@frappe.whitelist()
def optimize_warehouse_operations():
    """
    Hourly task to optimize warehouse operations
    - Update pick task priorities based on urgency
    - Optimize warehouse zone assignments
    - Update inventory levels and alerts
    """
    try:
        logger.info("Starting warehouse operations optimization")
        
        # Update pick task priorities
        update_pick_task_priorities()
        
        # Optimize zone assignments
        optimize_zone_assignments()
        
        # Update inventory alerts
        update_inventory_alerts()
        
        logger.info("Warehouse operations optimization completed successfully")
        
    except Exception as e:
        logger.error(f"Error in warehouse operations optimization: {str(e)}")
        frappe.log_error(f"Warehouse Optimization Error: {str(e)}", "Warehouse Scheduler")

@frappe.whitelist()
def update_pick_task_priorities():
    """
    Update pick task priorities based on sales order urgency and delivery dates
    """
    try:
        # Get all pending pick tasks
        pick_tasks = frappe.get_all("Warehouse Pick Task", 
            filters={"status": ["in", ["Pending", "In Progress"]]},
            fields=["name", "sales_order", "delivery_date", "priority"])
        
        for task in pick_tasks:
            if task.delivery_date:
                days_to_delivery = (getdate(task.delivery_date) - getdate()).days
                
                # Update priority based on urgency
                if days_to_delivery <= 1:
                    priority = "High"
                elif days_to_delivery <= 3:
                    priority = "Medium"
                else:
                    priority = "Low"
                
                if task.priority != priority:
                    frappe.db.set_value("Warehouse Pick Task", task.name, "priority", priority)
        
        frappe.db.commit()
        logger.info("Pick task priorities updated successfully")
        
    except Exception as e:
        logger.error(f"Error updating pick task priorities: {str(e)}")

@frappe.whitelist()
def check_temperature_compliance():
    """
    Check temperature compliance for temperature-controlled warehouse zones
    """
    try:
        # Get all temperature-controlled warehouses
        warehouses = frappe.get_all("Warehouse",
            filters={"temperature_controlled": 1},
            fields=["name", "min_temperature", "max_temperature", "current_temperature"])
        
        for warehouse in warehouses:
            if warehouse.current_temperature:
                if (warehouse.current_temperature < warehouse.min_temperature or 
                    warehouse.current_temperature > warehouse.max_temperature):
                    
                    # Create temperature alert
                    create_temperature_alert(warehouse)
        
        logger.info("Temperature compliance check completed")
        
    except Exception as e:
        logger.error(f"Error in temperature compliance check: {str(e)}")

def create_temperature_alert(warehouse):
    """Create temperature alert for non-compliant warehouse"""
    try:
        alert_doc = frappe.new_doc("Warehouse Alert")
        alert_doc.warehouse = warehouse.name
        alert_doc.alert_type = "Temperature Violation"
        alert_doc.severity = "High"
        alert_doc.message = f"Temperature {warehouse.current_temperature}°C is outside acceptable range ({warehouse.min_temperature}°C - {warehouse.max_temperature}°C)"
        alert_doc.alert_datetime = now_datetime()
        alert_doc.status = "Open"
        alert_doc.insert()
        
        # Send notification to warehouse manager
        send_temperature_alert_notification(warehouse, alert_doc)
        
    except Exception as e:
        logger.error(f"Error creating temperature alert: {str(e)}")

def send_temperature_alert_notification(warehouse, alert_doc):
    """Send notification for temperature alert"""
    try:
        # Get warehouse managers
        warehouse_managers = frappe.get_all("User",
            filters={"role_profile_name": "Warehouse Manager", "enabled": 1},
            fields=["email", "full_name"])
        
        for manager in warehouse_managers:
            frappe.sendmail(
                recipients=[manager.email],
                subject=f"Temperature Alert - {warehouse.name}",
                message=f"""
                Dear {manager.full_name},
                
                A temperature violation has been detected in warehouse {warehouse.name}.
                
                Current Temperature: {warehouse.current_temperature}°C
                Acceptable Range: {warehouse.min_temperature}°C - {warehouse.max_temperature}°C
                
                Alert ID: {alert_doc.name}
                Time: {alert_doc.alert_datetime}
                
                Please take immediate action to correct the temperature.
                
                Best regards,
                AMB Warehouse Management System
                """
            )
            
    except Exception as e:
        logger.error(f"Error sending temperature alert notification: {str(e)}")

@frappe.whitelist()
def generate_warehouse_performance_report():
    """
    Daily task to generate warehouse performance reports
    """
    try:
        # Calculate daily metrics
        daily_metrics = calculate_daily_warehouse_metrics()
        
        # Store metrics in Warehouse Performance Log
        performance_log = frappe.new_doc("Warehouse Performance Log")
        performance_log.date = getdate()
        performance_log.total_pick_tasks = daily_metrics.get("total_pick_tasks", 0)
        performance_log.completed_pick_tasks = daily_metrics.get("completed_pick_tasks", 0)
        performance_log.completion_rate = daily_metrics.get("completion_rate", 0)
        performance_log.average_pick_time = daily_metrics.get("average_pick_time", 0)
        performance_log.insert()
        
        logger.info("Daily warehouse performance report generated")
        
    except Exception as e:
        logger.error(f"Error generating warehouse performance report: {str(e)}")

def calculate_daily_warehouse_metrics():
    """Calculate daily warehouse performance metrics"""
    try:
        today = getdate()
        
        # Get today's pick tasks
        total_tasks = frappe.db.count("Warehouse Pick Task", {
            "creation": [">=", today]
        })
        
        completed_tasks = frappe.db.count("Warehouse Pick Task", {
            "creation": [">=", today],
            "status": "Completed"
        })
        
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Calculate average pick time
        completed_task_times = frappe.db.sql("""
            SELECT AVG(TIMESTAMPDIFF(MINUTE, creation, completion_datetime))
            FROM `tabWarehouse Pick Task`
            WHERE DATE(creation) = %s AND status = 'Completed'
        """, (today,))
        
        average_pick_time = completed_task_times[0][0] if completed_task_times[0][0] else 0
        
        return {
            "total_pick_tasks": total_tasks,
            "completed_pick_tasks": completed_tasks,
            "completion_rate": completion_rate,
            "average_pick_time": average_pick_time
        }
        
    except Exception as e:
        logger.error(f"Error calculating daily warehouse metrics: {str(e)}")
        return {}

@frappe.whitelist()
def cleanup_expired_pick_tasks():
    """
    Clean up expired or old pick tasks
    """
    try:
        # Get expired pick tasks (older than 30 days and completed/cancelled)
        cutoff_date = add_days(getdate(), -30)
        
        expired_tasks = frappe.get_all("Warehouse Pick Task",
            filters={
                "creation": ["<", cutoff_date],
                "status": ["in", ["Completed", "Cancelled"]]
            },
            fields=["name"])
        
        for task in expired_tasks:
            # Archive or delete based on company policy
            frappe.delete_doc("Warehouse Pick Task", task.name)
        
        logger.info(f"Cleaned up {len(expired_tasks)} expired pick tasks")
        
    except Exception as e:
        logger.error(f"Error cleaning up expired pick tasks: {str(e)}")

@frappe.whitelist()
def validate_warehouse_zones():
    """
    Validate warehouse zone configurations and capacity
    """
    try:
        warehouses = frappe.get_all("Warehouse", 
            filters={"is_group": 0},
            fields=["name", "warehouse_capacity", "current_utilization"])
        
        for warehouse in warehouses:
            if warehouse.current_utilization and warehouse.warehouse_capacity:
                utilization_rate = (warehouse.current_utilization / warehouse.warehouse_capacity) * 100
                
                if utilization_rate > 95:
                    # Create capacity alert
                    create_capacity_alert(warehouse, utilization_rate)
        
        logger.info("Warehouse zone validation completed")
        
    except Exception as e:
        logger.error(f"Error in warehouse zone validation: {str(e)}")

def create_capacity_alert(warehouse, utilization_rate):
    """Create capacity alert for over-utilized warehouse"""
    try:
        alert_doc = frappe.new_doc("Warehouse Alert")
        alert_doc.warehouse = warehouse.name
        alert_doc.alert_type = "Capacity Warning"
        alert_doc.severity = "Medium"
        alert_doc.message = f"Warehouse utilization at {utilization_rate:.1f}% - Consider redistributing inventory"
        alert_doc.alert_datetime = now_datetime()
        alert_doc.status = "Open"
        alert_doc.insert()
        
    except Exception as e:
        logger.error(f"Error creating capacity alert: {str(e)}")

@frappe.whitelist()
def analyze_warehouse_efficiency():
    """
    Weekly analysis of warehouse efficiency and optimization recommendations
    """
    try:
        # Analyze pick path efficiency
        analyze_pick_path_efficiency()
        
        # Analyze inventory turnover
        analyze_inventory_turnover()
        
        # Generate optimization recommendations
        generate_optimization_recommendations()
        
        logger.info("Weekly warehouse efficiency analysis completed")
        
    except Exception as e:
        logger.error(f"Error in warehouse efficiency analysis: {str(e)}")

def analyze_pick_path_efficiency():
    """Analyze pick path efficiency for optimization"""
    try:
        # Implementation for pick path analysis
        pass
    except Exception as e:
        logger.error(f"Error analyzing pick path efficiency: {str(e)}")

def analyze_inventory_turnover():
    """Analyze inventory turnover rates"""
    try:
        # Implementation for inventory turnover analysis
        pass
    except Exception as e:
        logger.error(f"Error analyzing inventory turnover: {str(e)}")

def generate_optimization_recommendations():
    """Generate warehouse optimization recommendations"""
    try:
        # Implementation for generating recommendations
        pass
    except Exception as e:
        logger.error(f"Error generating optimization recommendations: {str(e)}")

@frappe.whitelist()
def monitor_warehouse_alerts():
    """
    Monitor warehouse alerts every 15 minutes
    """
    try:
        # Check for critical alerts that need immediate attention
        critical_alerts = frappe.get_all("Warehouse Alert",
            filters={
                "severity": "High",
                "status": "Open",
                "creation": [">=", add_days(now_datetime(), -1)]
            },
            fields=["name", "warehouse", "alert_type", "message"])
        
        for alert in critical_alerts:
            # Send escalation if alert is more than 1 hour old
            escalate_critical_alert(alert)
        
        logger.info("Warehouse alerts monitoring completed")
        
    except Exception as e:
        logger.error(f"Error monitoring warehouse alerts: {str(e)}")

def escalate_critical_alert(alert):
    """Escalate critical alerts to management"""
    try:
        # Implementation for alert escalation
        pass
    except Exception as e:
        logger.error(f"Error escalating critical alert: {str(e)}")

@frappe.whitelist()
def start_daily_warehouse_operations():
    """
    Start daily warehouse operations at 6 AM
    """
    try:
        # Initialize daily warehouse metrics
        initialize_daily_metrics()
        
        # Update warehouse dashboard cache
        update_warehouse_dashboard_cache()
        
        # Send daily warehouse status report
        send_daily_status_report()
        
        logger.info("Daily warehouse operations started successfully")
        
    except Exception as e:
        logger.error(f"Error starting daily warehouse operations: {str(e)}")

def initialize_daily_metrics():
    """Initialize daily warehouse metrics"""
    try:
        # Implementation for initializing daily metrics
        pass
    except Exception as e:
        logger.error(f"Error initializing daily metrics: {str(e)}")

def update_warehouse_dashboard_cache():
    """Update warehouse dashboard cache"""
    try:
        # Implementation for updating dashboard cache
        pass
    except Exception as e:
        logger.error(f"Error updating warehouse dashboard cache: {str(e)}")

def send_daily_status_report():
    """Send daily warehouse status report"""
    try:
        # Implementation for sending daily status report
        pass
    except Exception as e:
        logger.error(f"Error sending daily status report: {str(e)}")

def optimize_zone_assignments():
    """Optimize warehouse zone assignments"""
    try:
        # Implementation for optimizing zone assignments
        pass
    except Exception as e:
        logger.error(f"Error optimizing zone assignments: {str(e)}")

def update_inventory_alerts():
    """Update inventory level alerts"""
    try:
        # Implementation for updating inventory alerts
        pass
    except Exception as e:
        logger.error(f"Error updating inventory alerts: {str(e)}")
