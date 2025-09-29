# Copyright (c) 2025, MiniMax Agent and contributors
# Shop Floor Dashboard backend

import frappe
from frappe import _
from frappe.utils import now, add_hours, add_minutes

@frappe.whitelist()
def get_dashboard_data():
    """Get all data needed for real-time dashboard"""
    try:
        return {
            "stations": get_station_status(),
            "alerts": get_active_alerts(),
            "production_metrics": get_production_metrics(),
            "sensor_readings": get_recent_sensor_readings(),
            "system_status": get_system_status(),
            "timestamp": now()
        }
    except Exception as e:
        frappe.log_error(f"Error getting dashboard data: {str(e)}")
        return {"error": str(e)}

def get_station_status():
    """Get current status of all manufacturing stations"""
    try:
        stations = frappe.db.sql("""
            SELECT 
                ms.name,
                ms.station_id,
                ms.station_name,
                ms.station_type,
                ms.status,
                ms.current_oee,
                ms.oee_target,
                ms.uptime_percentage,
                ms.communication_status,
                ms.last_communication,
                ms.total_production_count,
                COUNT(DISTINCT oc.name) as active_operators,
                wo.name as current_work_order,
                wo.production_item as current_item,
                wo.qty as work_order_qty,
                wo.produced_qty as produced_qty
            FROM `tabManufacturing Station` ms
            LEFT JOIN `tabOperator Check-in` oc ON oc.station = ms.name AND oc.status = 'Active'
            LEFT JOIN `tabWork Order Operation` woo ON woo.workstation = ms.name AND woo.status = 'Work in Progress'
            LEFT JOIN `tabWork Order` wo ON wo.name = woo.parent
            WHERE ms.status IN ('Active', 'Maintenance')
            GROUP BY ms.name
            ORDER BY ms.station_name
        """, as_dict=True)
        
        # Enhance station data with real-time metrics
        for station in stations:
            # Get latest sensor readings count
            station['sensor_count'] = frappe.db.count("Sensor Configuration", {
                "station": station.name,
                "status": "Active"
            })
            
            # Get active alerts count
            station['active_alerts'] = frappe.db.count("Process Alert", {
                "station": station.name,
                "status": "Active"
            })
            
            # Calculate production progress
            if station.current_work_order and station.work_order_qty:
                station['production_progress'] = (station.produced_qty or 0) / station.work_order_qty * 100
            else:
                station['production_progress'] = 0
            
            # Get latest communication status
            station['connection_quality'] = get_connection_quality(station.name)
        
        return stations
        
    except Exception as e:
        frappe.log_error(f"Error getting station status: {str(e)}")
        return []

def get_connection_quality(station_name):
    """Calculate connection quality based on recent communication"""
    try:
        # Get communication attempts in last hour
        recent_communications = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_attempts,
                SUM(CASE WHEN communication_status = 'Online' THEN 1 ELSE 0 END) as successful_attempts
            FROM `tabManufacturing Station`
            WHERE name = %s
            AND last_communication >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
        """, (station_name,), as_dict=True)
        
        if recent_communications and recent_communications[0].total_attempts > 0:
            success_rate = recent_communications[0].successful_attempts / recent_communications[0].total_attempts
            return round(success_rate * 100, 1)
        
        return 0
        
    except Exception:
        return 0

def get_active_alerts():
    """Get all active process alerts"""
    try:
        alerts = frappe.db.sql("""
            SELECT 
                pa.name,
                pa.alert_type,
                pa.station,
                pa.sensor,
                pa.message,
                pa.triggered_at,
                pa.priority,
                pa.status,
                ms.station_name,
                sc.sensor_name
            FROM `tabProcess Alert` pa
            LEFT JOIN `tabManufacturing Station` ms ON ms.name = pa.station
            LEFT JOIN `tabSensor Configuration` sc ON sc.name = pa.sensor
            WHERE pa.status = 'Active'
            ORDER BY 
                CASE pa.priority 
                    WHEN 'High' THEN 1 
                    WHEN 'Medium' THEN 2 
                    WHEN 'Low' THEN 3 
                END,
                pa.triggered_at DESC
            LIMIT 50
        """, as_dict=True)
        
        return alerts
        
    except Exception as e:
        frappe.log_error(f"Error getting active alerts: {str(e)}")
        return []

def get_production_metrics():
    """Get production metrics for the dashboard"""
    try:
        # Get today's production metrics
        today_metrics = frappe.db.sql("""
            SELECT 
                COUNT(DISTINCT ms.name) as active_stations,
                SUM(ms.total_production_count) as total_production_today,
                AVG(ms.current_oee) as average_oee,
                AVG(ms.uptime_percentage) as average_uptime,
                COUNT(DISTINCT CASE WHEN ms.communication_status = 'Online' THEN ms.name END) as stations_online
            FROM `tabManufacturing Station` ms
            WHERE ms.status = 'Active'
        """, as_dict=True)
        
        # Get work order statistics
        work_order_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as active_work_orders,
                SUM(wo.qty) as total_planned_qty,
                SUM(wo.produced_qty) as total_produced_qty,
                AVG(CASE WHEN wo.qty > 0 THEN (wo.produced_qty / wo.qty) * 100 ELSE 0 END) as average_completion
            FROM `tabWork Order` wo
            WHERE wo.status IN ('In Process', 'Work in Progress')
        """, as_dict=True)
        
        # Get quality metrics
        quality_metrics = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_readings_today,
                AVG(CASE WHEN status = 'Normal' THEN 1 ELSE 0 END) * 100 as normal_percentage,
                AVG(CASE WHEN within_spec = 1 THEN 1 ELSE 0 END) * 100 as within_spec_percentage
            FROM `tabReal-time Process Data`
            WHERE DATE(timestamp) = CURDATE()
        """, as_dict=True)
        
        metrics = {}
        if today_metrics:
            metrics.update(today_metrics[0])
        if work_order_stats:
            metrics.update(work_order_stats[0])
        if quality_metrics:
            metrics.update(quality_metrics[0])
        
        return metrics
        
    except Exception as e:
        frappe.log_error(f"Error getting production metrics: {str(e)}")
        return {}

def get_recent_sensor_readings():
    """Get most recent readings from all sensors"""
    try:
        readings = frappe.db.sql("""
            SELECT 
                rtpd.station,
                rtpd.sensor,
                rtpd.parameter_name,
                rtpd.value,
                rtpd.unit_of_measure,
                rtpd.status,
                rtpd.timestamp,
                rtpd.within_spec,
                sc.sensor_name,
                sc.sensor_type,
                sc.upper_warning,
                sc.lower_warning,
                sc.upper_alarm,
                sc.lower_alarm,
                ms.station_name
            FROM `tabReal-time Process Data` rtpd
            INNER JOIN `tabSensor Configuration` sc ON sc.name = rtpd.sensor
            INNER JOIN `tabManufacturing Station` ms ON ms.name = rtpd.station
            INNER JOIN (
                SELECT sensor, MAX(timestamp) as latest_timestamp
                FROM `tabReal-time Process Data`
                WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
                GROUP BY sensor
            ) latest ON latest.sensor = rtpd.sensor AND latest.latest_timestamp = rtpd.timestamp
            WHERE ms.status = 'Active'
            ORDER BY rtpd.timestamp DESC
        """, as_dict=True)
        
        return readings
        
    except Exception as e:
        frappe.log_error(f"Error getting recent sensor readings: {str(e)}")
        return []

def get_system_status():
    """Get overall system status"""
    try:
        status = {
            "data_collection_running": check_data_collection_status(),
            "database_health": check_database_health(),
            "alert_system_status": check_alert_system_status(),
            "total_data_points_today": get_total_data_points_today()
        }
        
        return status
        
    except Exception as e:
        frappe.log_error(f"Error getting system status: {str(e)}")
        return {}

def check_data_collection_status():
    """Check if data collection is running properly"""
    try:
        # Check if we've received data in the last 5 minutes
        recent_data = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabReal-time Process Data`
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
        """)[0][0]
        
        return recent_data > 0
        
    except Exception:
        return False

def check_database_health():
    """Check database health metrics"""
    try:
        # Simple check - can we query the database?
        frappe.db.sql("SELECT 1")
        return "healthy"
    except Exception:
        return "error"

def check_alert_system_status():
    """Check alert system status"""
    try:
        active_alerts = frappe.db.count("Process Alert", {"status": "Active"})
        return {
            "active_alerts": active_alerts,
            "status": "running"
        }
    except Exception:
        return {"status": "error"}

def get_total_data_points_today():
    """Get total data points collected today"""
    try:
        count = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabReal-time Process Data`
            WHERE DATE(timestamp) = CURDATE()
        """)[0][0]
        
        return count
        
    except Exception:
        return 0

@frappe.whitelist()
def acknowledge_alert(alert_name):
    """Acknowledge a process alert"""
    try:
        alert = frappe.get_doc("Process Alert", alert_name)
        alert.status = "Acknowledged"
        alert.acknowledged_by = frappe.session.user
        alert.acknowledged_at = now()
        alert.save()
        
        # Publish real-time update
        frappe.realtime.publish_realtime(
            event="alert_acknowledged",
            message={"alert": alert_name},
            room="alerts"
        )
        
        return {"status": "success", "message": "Alert acknowledged successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error acknowledging alert: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def resolve_alert(alert_name, resolution_notes=None):
    """Resolve a process alert"""
    try:
        alert = frappe.get_doc("Process Alert", alert_name)
        alert.status = "Resolved"
        alert.resolved_by = frappe.session.user
        alert.resolved_at = now()
        if resolution_notes:
            alert.resolution_notes = resolution_notes
        alert.save()
        
        # Publish real-time update
        frappe.realtime.publish_realtime(
            event="alert_resolved",
            message={"alert": alert_name},
            room="alerts"
        )
        
        return {"status": "success", "message": "Alert resolved successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error resolving alert: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_station_details(station_name):
    """Get detailed information for a specific station"""
    try:
        station = frappe.get_doc("Manufacturing Station", station_name)
        
        # Get recent sensor data
        sensor_data = frappe.db.sql("""
            SELECT 
                sc.sensor_name,
                sc.sensor_type,
                rtpd.value,
                rtpd.status,
                rtpd.timestamp,
                sc.upper_warning,
                sc.lower_warning
            FROM `tabSensor Configuration` sc
            LEFT JOIN `tabReal-time Process Data` rtpd ON rtpd.sensor = sc.name
            WHERE sc.station = %s
            AND sc.status = 'Active'
            AND (rtpd.timestamp IS NULL OR rtpd.timestamp >= DATE_SUB(NOW(), INTERVAL 1 HOUR))
            ORDER BY sc.sensor_name, rtpd.timestamp DESC
        """, (station_name,), as_dict=True)
        
        # Get recent alerts
        recent_alerts = frappe.db.sql("""
            SELECT 
                alert_type,
                message,
                triggered_at,
                status,
                priority
            FROM `tabProcess Alert`
            WHERE station = %s
            AND triggered_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            ORDER BY triggered_at DESC
            LIMIT 10
        """, (station_name,), as_dict=True)
        
        return {
            "station": station.as_dict(),
            "sensor_data": sensor_data,
            "recent_alerts": recent_alerts,
            "current_oee": station.current_oee,
            "active_operators": station.get_active_operators_count()
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting station details: {str(e)}")
        return {"error": str(e)}

@frappe.whitelist()
def get_sensor_trend_chart_data(sensor_name, hours=24):
    """Get trend data for sensor charts"""
    try:
        from_time = add_hours(now(), -int(hours))
        
        data = frappe.db.sql("""
            SELECT 
                timestamp,
                value,
                status,
                upper_limit,
                lower_limit,
                upper_alarm_limit,
                lower_alarm_limit
            FROM `tabReal-time Process Data`
            WHERE sensor = %s
            AND timestamp >= %s
            ORDER BY timestamp ASC
        """, (sensor_name, from_time), as_dict=True)
        
        return {
            "sensor_name": sensor_name,
            "data": data,
            "hours": hours
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting sensor trend data: {str(e)}")
        return {"error": str(e)}

@frappe.whitelist()
def toggle_station_status(station_name, new_status):
    """Toggle station status (Active/Inactive/Maintenance)"""
    try:
        if new_status not in ["Active", "Inactive", "Maintenance"]:
            return {"status": "error", "message": "Invalid status"}
        
        station = frappe.get_doc("Manufacturing Station", station_name)
        old_status = station.status
        station.status = new_status
        station.save()
        
        # Publish real-time update
        frappe.realtime.publish_realtime(
            event="station_status_change",
            message={
                "station": station_name,
                "old_status": old_status,
                "new_status": new_status
            },
            room="shop_floor_monitoring"
        )
        
        return {"status": "success", "message": f"Station status changed to {new_status}"}
        
    except Exception as e:
        frappe.log_error(f"Error toggling station status: {str(e)}")
        return {"status": "error", "message": str(e)}
