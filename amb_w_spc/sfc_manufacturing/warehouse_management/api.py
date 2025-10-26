"""
Warehouse Management API
Provides API endpoints for warehouse dashboard and operations
"""

import frappe
from frappe.utils import getdate, now_datetime, add_days
from frappe import _
import json

@frappe.whitelist()
def get_warehouse_dashboard_data():
    """
    Get comprehensive warehouse dashboard data for current user
    """
    try:
        user = frappe.session.user
        
        # Get user warehouse permissions
        user_warehouses = get_user_accessible_warehouses(user)
        
        if not user_warehouses:
            return {"error": "No warehouse access permissions"}
        
        warehouse_names = [w.name for w in user_warehouses]
        
        # Get dashboard metrics
        dashboard_data = {
            "summary": get_warehouse_summary(warehouse_names),
            "pick_tasks": get_pick_task_summary(warehouse_names),
            "alerts": get_alert_summary(warehouse_names),
            "performance": get_performance_summary(warehouse_names),
            "temperature_status": get_temperature_status(warehouse_names),
            "utilization": get_utilization_data(warehouse_names),
            "last_updated": now_datetime()
        }
        
        return dashboard_data
        
    except Exception as e:
        frappe.log_error(f"Error getting warehouse dashboard data: {str(e)}", "Warehouse API")
        return {"error": str(e)}

def get_user_accessible_warehouses(user):
    """Get warehouses accessible to user based on permissions"""
    try:
        # System Manager has access to all warehouses
        if "System Manager" in frappe.get_roles(user):
            return frappe.get_all("Warehouse", 
                filters={"is_group": 0},
                fields=["name", "warehouse_name", "warehouse_type", "plant_code"])
        
        # Get user's plant code for filtering
        user_doc = frappe.get_doc("User", user)
        user_plant_code = getattr(user_doc, "plant_code", None)
        
        filters = {"is_group": 0}
        if user_plant_code:
            filters["plant_code"] = user_plant_code
        
        return frappe.get_all("Warehouse", 
            filters=filters,
            fields=["name", "warehouse_name", "warehouse_type", "plant_code"])
        
    except Exception as e:
        frappe.log_error(f"Error getting user accessible warehouses: {str(e)}", "Warehouse API")
        return []

def get_warehouse_summary(warehouse_names):
    """Get warehouse summary statistics"""
    try:
        total_warehouses = len(warehouse_names)
        
        # Temperature controlled warehouses
        temp_controlled = frappe.db.count("Warehouse", {
            "name": ["in", warehouse_names],
            "temperature_controlled": 1
        })
        
        # Warehouses with alerts
        warehouses_with_alerts = frappe.db.sql("""
            SELECT COUNT(DISTINCT warehouse)
            FROM `tabWarehouse Alert`
            WHERE warehouse IN %(warehouses)s
                AND status = 'Open'
        """, {"warehouses": warehouse_names})[0][0]
        
        # Total capacity and utilization
        capacity_data = frappe.db.sql("""
            SELECT 
                SUM(warehouse_capacity) as total_capacity,
                SUM(current_utilization) as total_utilization
            FROM `tabWarehouse`
            WHERE name IN %(warehouses)s
                AND warehouse_capacity > 0
        """, {"warehouses": warehouse_names})
        
        total_capacity = capacity_data[0][0] or 0
        total_utilization = capacity_data[0][1] or 0
        utilization_percentage = (total_utilization / total_capacity * 100) if total_capacity > 0 else 0
        
        return {
            "total_warehouses": total_warehouses,
            "temperature_controlled": temp_controlled,
            "warehouses_with_alerts": warehouses_with_alerts,
            "total_capacity": total_capacity,
            "total_utilization": total_utilization,
            "utilization_percentage": utilization_percentage
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting warehouse summary: {str(e)}", "Warehouse API")
        return {}

def get_pick_task_summary(warehouse_names):
    """Get pick task summary"""
    try:
        today = getdate()
        
        # Total pending tasks
        pending_tasks = frappe.db.count("Warehouse Pick Task", {
            "warehouse": ["in", warehouse_names],
            "status": ["in", ["Pending", "In Progress"]]
        })
        
        # Today's completed tasks
        completed_today = frappe.db.count("Warehouse Pick Task", {
            "warehouse": ["in", warehouse_names],
            "status": "Completed",
            "completion_date": today
        })
        
        # High priority tasks
        high_priority = frappe.db.count("Warehouse Pick Task", {
            "warehouse": ["in", warehouse_names],
            "status": ["in", ["Pending", "In Progress"]],
            "priority": "High"
        })
        
        # Overdue tasks
        overdue_tasks = frappe.db.count("Warehouse Pick Task", {
            "warehouse": ["in", warehouse_names],
            "status": ["in", ["Pending", "In Progress"]],
            "expected_completion_date": ["<", today]
        })
        
        # Average completion time (in minutes)
        avg_completion_time = frappe.db.sql("""
            SELECT AVG(TIMESTAMPDIFF(MINUTE, creation, completion_datetime))
            FROM `tabWarehouse Pick Task`
            WHERE warehouse IN %(warehouses)s
                AND status = 'Completed'
                AND DATE(completion_datetime) = %(today)s
        """, {"warehouses": warehouse_names, "today": today})
        
        average_time = avg_completion_time[0][0] if avg_completion_time[0][0] else 0
        
        return {
            "pending_tasks": pending_tasks,
            "completed_today": completed_today,
            "high_priority": high_priority,
            "overdue_tasks": overdue_tasks,
            "average_completion_time": round(average_time, 1)
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting pick task summary: {str(e)}", "Warehouse API")
        return {}

def get_alert_summary(warehouse_names):
    """Get alert summary"""
    try:
        # Critical alerts
        critical_alerts = frappe.db.count("Warehouse Alert", {
            "warehouse": ["in", warehouse_names],
            "severity": "High",
            "status": "Open"
        })
        
        # Warning alerts
        warning_alerts = frappe.db.count("Warehouse Alert", {
            "warehouse": ["in", warehouse_names],
            "severity": "Medium",
            "status": "Open"
        })
        
        # Temperature alerts
        temperature_alerts = frappe.db.count("Warehouse Alert", {
            "warehouse": ["in", warehouse_names],
            "alert_type": "Temperature Violation",
            "status": "Open"
        })
        
        # Recent alerts (last 24 hours)
        recent_alerts = frappe.db.count("Warehouse Alert", {
            "warehouse": ["in", warehouse_names],
            "alert_datetime": [">=", add_days(now_datetime(), -1)]
        })
        
        return {
            "critical_alerts": critical_alerts,
            "warning_alerts": warning_alerts,
            "temperature_alerts": temperature_alerts,
            "recent_alerts": recent_alerts
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting alert summary: {str(e)}", "Warehouse API")
        return {}

def get_performance_summary(warehouse_names):
    """Get performance summary"""
    try:
        today = getdate()
        
        # Today's performance
        performance_data = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_tasks,
                AVG(CASE WHEN status = 'Completed' 
                    THEN TIMESTAMPDIFF(MINUTE, creation, completion_datetime) 
                    ELSE NULL END) as avg_time
            FROM `tabWarehouse Pick Task`
            WHERE warehouse IN %(warehouses)s
                AND DATE(creation) = %(today)s
        """, {"warehouses": warehouse_names, "today": today})
        
        if performance_data:
            total_tasks = performance_data[0][0] or 0
            completed_tasks = performance_data[0][1] or 0
            avg_time = performance_data[0][2] or 0
            
            completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        else:
            completion_rate = 0
            avg_time = 0
        
        # Weekly trends
        week_ago = add_days(today, -7)
        weekly_performance = frappe.db.sql("""
            SELECT 
                DATE(creation) as date,
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_tasks
            FROM `tabWarehouse Pick Task`
            WHERE warehouse IN %(warehouses)s
                AND DATE(creation) BETWEEN %(week_ago)s AND %(today)s
            GROUP BY DATE(creation)
            ORDER BY DATE(creation)
        """, {"warehouses": warehouse_names, "week_ago": week_ago, "today": today})
        
        return {
            "completion_rate": round(completion_rate, 1),
            "average_time": round(avg_time, 1),
            "weekly_trends": [{"date": str(row[0]), "total": row[1], "completed": row[2]} 
                             for row in weekly_performance]
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting performance summary: {str(e)}", "Warehouse API")
        return {}

def get_temperature_status(warehouse_names):
    """Get temperature status for temperature-controlled warehouses"""
    try:
        temp_warehouses = frappe.get_all("Warehouse",
            filters={
                "name": ["in", warehouse_names],
                "temperature_controlled": 1
            },
            fields=["name", "warehouse_name", "min_temperature", "max_temperature", "current_temperature"])
        
        status_data = []
        for warehouse in temp_warehouses:
            if warehouse.current_temperature is not None:
                in_range = (warehouse.min_temperature <= warehouse.current_temperature <= warehouse.max_temperature)
                
                status_data.append({
                    "warehouse": warehouse.name,
                    "warehouse_name": warehouse.warehouse_name,
                    "current_temp": warehouse.current_temperature,
                    "min_temp": warehouse.min_temperature,
                    "max_temp": warehouse.max_temperature,
                    "in_range": in_range,
                    "status": "Normal" if in_range else "Alert"
                })
        
        return status_data
        
    except Exception as e:
        frappe.log_error(f"Error getting temperature status: {str(e)}", "Warehouse API")
        return []

def get_utilization_data(warehouse_names):
    """Get warehouse utilization data"""
    try:
        utilization_data = frappe.db.sql("""
            SELECT 
                name,
                warehouse_name,
                warehouse_capacity,
                current_utilization,
                CASE 
                    WHEN warehouse_capacity > 0 
                    THEN (current_utilization / warehouse_capacity * 100)
                    ELSE 0
                END as utilization_percentage
            FROM `tabWarehouse`
            WHERE name IN %(warehouses)s
                AND warehouse_capacity > 0
            ORDER BY utilization_percentage DESC
        """, {"warehouses": warehouse_names})
        
        return [{"warehouse": row[0], "warehouse_name": row[1], "capacity": row[2], 
                "utilization": row[3], "percentage": round(row[4], 1)} 
                for row in utilization_data]
        
    except Exception as e:
        frappe.log_error(f"Error getting utilization data: {str(e)}", "Warehouse API")
        return []

@frappe.whitelist()
def get_pick_task_data(warehouse=None, status=None, priority=None):
    """
    Get pick task data with filtering options
    """
    try:
        user = frappe.session.user
        user_warehouses = get_user_accessible_warehouses(user)
        
        if not user_warehouses:
            return {"error": "No warehouse access permissions"}
        
        warehouse_names = [w.name for w in user_warehouses]
        
        # Build filters
        filters = {"warehouse": ["in", warehouse_names]}
        
        if warehouse and warehouse in warehouse_names:
            filters["warehouse"] = warehouse
        
        if status:
            filters["status"] = status
            
        if priority:
            filters["priority"] = priority
        
        # Get pick tasks
        pick_tasks = frappe.get_all("Warehouse Pick Task",
            filters=filters,
            fields=[
                "name", "sales_order", "warehouse", "status", "priority",
                "assigned_to", "creation", "expected_completion_date",
                "completion_datetime", "total_items", "completed_items"
            ],
            order_by="creation desc",
            limit=100)
        
        # Get additional details for each task
        for task in pick_tasks:
            if task.assigned_to:
                user_name = frappe.db.get_value("User", task.assigned_to, "full_name")
                task["assigned_to_name"] = user_name
            
            # Calculate progress percentage
            if task.total_items and task.total_items > 0:
                task["progress_percentage"] = (task.completed_items / task.total_items) * 100
            else:
                task["progress_percentage"] = 0
        
        return {"pick_tasks": pick_tasks}
        
    except Exception as e:
        frappe.log_error(f"Error getting pick task data: {str(e)}", "Warehouse API")
        return {"error": str(e)}

@frappe.whitelist()
def update_pick_task_status(pick_task_name, status, completion_notes=None):
    """
    Update pick task status
    """
    try:
        user = frappe.session.user
        
        # Check permissions
        pick_task = frappe.get_doc("Warehouse Pick Task", pick_task_name)
        
        # Verify user has access to this warehouse
        user_warehouses = get_user_accessible_warehouses(user)
        accessible_warehouse_names = [w.name for w in user_warehouses]
        
        if pick_task.warehouse not in accessible_warehouse_names:
            return {"error": "Access denied to this warehouse"}
        
        # Check if user can update (assigned user or warehouse manager)
        user_roles = frappe.get_roles(user)
        if pick_task.assigned_to != user and "Warehouse Manager" not in user_roles:
            return {"error": "You can only update tasks assigned to you"}
        
        # Update status
        pick_task.status = status
        
        if status == "Completed":
            pick_task.completion_datetime = now_datetime()
            pick_task.completed_by = user
        
        if completion_notes:
            pick_task.completion_notes = completion_notes
        
        pick_task.save()
        
        return {"success": True, "message": f"Pick task status updated to {status}"}
        
    except Exception as e:
        frappe.log_error(f"Error updating pick task status: {str(e)}", "Warehouse API")
        return {"error": str(e)}

@frappe.whitelist()
def get_material_assessment_data(warehouse=None, status=None):
    """
    Get material assessment data
    """
    try:
        user = frappe.session.user
        user_warehouses = get_user_accessible_warehouses(user)
        
        if not user_warehouses:
            return {"error": "No warehouse access permissions"}
        
        warehouse_names = [w.name for w in user_warehouses]
        
        # Build filters - join with Stock Entry to get warehouse
        conditions = ["se.warehouse IN %(warehouses)s"]
        values = {"warehouses": warehouse_names}
        
        if warehouse and warehouse in warehouse_names:
            conditions.append("se.warehouse = %(warehouse)s")
            values["warehouse"] = warehouse
        
        if status:
            conditions.append("mal.assessment_status = %(status)s")
            values["status"] = status
        
        where_clause = " AND ".join(conditions)
        
        # Get material assessments with related data
        query = f"""
            SELECT 
                mal.name,
                mal.material_assessment_id,
                mal.batch_id,
                mal.assessment_status,
                mal.assessment_date,
                mal.assessor,
                mal.temperature_recorded,
                mal.quality_grade,
                se.warehouse,
                se.stock_entry_type
            FROM `tabMaterial Assessment Log` mal
            LEFT JOIN `tabStock Entry` se ON mal.stock_entry_reference = se.name
            WHERE {where_clause}
            ORDER BY mal.assessment_date DESC
            LIMIT 100
        """
        
        assessments = frappe.db.sql(query, values, as_dict=True)
        
        # Get additional details
        for assessment in assessments:
            if assessment.assessor:
                assessor_name = frappe.db.get_value("User", assessment.assessor, "full_name")
                assessment["assessor_name"] = assessor_name
        
        return {"material_assessments": assessments}
        
    except Exception as e:
        frappe.log_error(f"Error getting material assessment data: {str(e)}", "Warehouse API")
        return {"error": str(e)}

@frappe.whitelist()
def get_warehouse_alerts(warehouse=None, severity=None, status="Open"):
    """
    Get warehouse alerts
    """
    try:
        user = frappe.session.user
        user_warehouses = get_user_accessible_warehouses(user)
        
        if not user_warehouses:
            return {"error": "No warehouse access permissions"}
        
        warehouse_names = [w.name for w in user_warehouses]
        
        # Build filters
        filters = {
            "warehouse": ["in", warehouse_names],
            "status": status
        }
        
        if warehouse and warehouse in warehouse_names:
            filters["warehouse"] = warehouse
            
        if severity:
            filters["severity"] = severity
        
        # Get alerts
        alerts = frappe.get_all("Warehouse Alert",
            filters=filters,
            fields=[
                "name", "warehouse", "alert_type", "severity", "message",
                "alert_datetime", "status", "acknowledged_by", "acknowledged_datetime"
            ],
            order_by="alert_datetime desc",
            limit=50)
        
        return {"alerts": alerts}
        
    except Exception as e:
        frappe.log_error(f"Error getting warehouse alerts: {str(e)}", "Warehouse API")
        return {"error": str(e)}

@frappe.whitelist()
def acknowledge_alert(alert_name):
    """
    Acknowledge a warehouse alert
    """
    try:
        user = frappe.session.user
        
        alert = frappe.get_doc("Warehouse Alert", alert_name)
        
        # Check access to warehouse
        user_warehouses = get_user_accessible_warehouses(user)
        accessible_warehouse_names = [w.name for w in user_warehouses]
        
        if alert.warehouse not in accessible_warehouse_names:
            return {"error": "Access denied to this warehouse"}
        
        # Acknowledge alert
        alert.acknowledged_by = user
        alert.acknowledged_datetime = now_datetime()
        alert.status = "Acknowledged"
        alert.save()
        
        return {"success": True, "message": "Alert acknowledged successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error acknowledging alert: {str(e)}", "Warehouse API")
        return {"error": str(e)}
