# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import now, get_datetime
from frappe import _

class RealTimeProcessData(Document):
    def validate(self):
        """Validation logic for Real-time Process Data"""
        self.validate_timestamp()
        self.validate_sensor_station_link()
        self.validate_limits()
        
    def validate_timestamp(self):
        """Ensure timestamp is not in future"""
        if get_datetime(self.timestamp) > get_datetime(now()):
            frappe.throw(_("Timestamp cannot be in the future"))
    
    def validate_sensor_station_link(self):
        """Ensure sensor belongs to the specified station"""
        if self.sensor and self.station:
            sensor_station = frappe.db.get_value("Sensor Configuration", self.sensor, "station")
            if sensor_station != self.station:
                frappe.throw(_("Sensor {0} does not belong to station {1}").format(self.sensor, self.station))
    
    def validate_limits(self):
        """Validate limit relationships"""
        if self.upper_limit and self.lower_limit:
            if self.upper_limit <= self.lower_limit:
                frappe.throw(_("Upper limit must be greater than lower limit"))
        
        if self.upper_alarm_limit and self.lower_alarm_limit:
            if self.upper_alarm_limit <= self.lower_alarm_limit:
                frappe.throw(_("Upper alarm limit must be greater than lower alarm limit"))
    
    def before_insert(self):
        """Actions before inserting record"""
        self.set_quality_indicators()
        self.determine_status()
        
    def after_insert(self):
        """Process data after insertion"""
        self.check_thresholds()
        self.update_spc_data()
        self.publish_realtime_update()
        self.update_sensor_statistics()
    
    def set_quality_indicators(self):
        """Set quality-related indicators"""
        if self.upper_limit and self.lower_limit and self.value is not None:
            # Check if within specification
            self.within_spec = self.lower_limit <= self.value <= self.upper_limit
            
            # Calculate deviation percentage
            if self.within_spec:
                # Calculate deviation from center point
                center = (self.upper_limit + self.lower_limit) / 2
                range_size = self.upper_limit - self.lower_limit
                deviation = abs(self.value - center)
                self.deviation_percentage = (deviation / (range_size / 2)) * 100
            else:
                # Calculate how far outside limits
                if self.value > self.upper_limit:
                    self.deviation_percentage = ((self.value - self.upper_limit) / self.upper_limit) * 100
                else:
                    self.deviation_percentage = ((self.lower_limit - self.value) / self.lower_limit) * 100
    
    def determine_status(self):
        """Determine status based on thresholds"""
        if self.value is None:
            self.status = "Normal"
            return
        
        # Check alarm thresholds first
        if self.upper_alarm_limit and self.value >= self.upper_alarm_limit:
            self.status = "Alarm"
        elif self.lower_alarm_limit and self.value <= self.lower_alarm_limit:
            self.status = "Alarm"
        # Check warning thresholds
        elif self.upper_limit and self.value >= self.upper_limit:
            self.status = "Warning"
        elif self.lower_limit and self.value <= self.lower_limit:
            self.status = "Warning"
        else:
            self.status = "Normal"
    
    def check_thresholds(self):
        """Check if value exceeds thresholds and create alerts"""
        if self.status in ["Warning", "Alarm"]:
            self.create_process_alert()
    
    def create_process_alert(self):
        """Create process alert for threshold violation"""
        # Check if similar alert already exists and is active
        existing_alert = frappe.db.exists("Process Alert", {
            "station": self.station,
            "sensor": self.sensor,
            "status": "Active",
            "alert_type": self.status
        })
        
        if existing_alert:
            # Update existing alert with latest reading
            alert_doc = frappe.get_doc("Process Alert", existing_alert)
            alert_doc.message = f"{self.parameter_name} {self.status.lower()}: {self.value} {self.unit_of_measure or ''} at {self.timestamp}"
            alert_doc.save()
            return
        
        # Create new alert
        alert = frappe.get_doc({
            "doctype": "Process Alert",
            "alert_type": self.status,
            "station": self.station,
            "sensor": self.sensor,
            "message": f"{self.parameter_name} {self.status.lower()}: {self.value} {self.unit_of_measure or ''} at {self.timestamp}",
            "triggered_at": self.timestamp,
            "status": "Active",
            "priority": "High" if self.status == "Alarm" else "Medium",
            "process_data": self.name
        })
        alert.insert()
        
        # Publish real-time alert
        frappe.realtime.publish_realtime(
            event="new_alert",
            message={
                "alert_id": alert.name,
                "alert_type": self.status,
                "station": self.station,
                "sensor": self.sensor,
                "message": alert.message,
                "priority": alert.priority
            },
            room="alerts"
        )
    
    def update_spc_data(self):
        """Link sensor data to SPC quality measurements"""
        if self.work_order and self.item and self.within_spec is not None:
            try:
                # Create quality measurement for SPC analysis
                quality_measurement = frappe.get_doc({
                    "doctype": "Quality Measurement",
                    "work_order": self.work_order,
                    "item": self.item,
                    "parameter": self.parameter_name,
                    "value": self.value,
                    "uom": self.unit_of_measure,
                    "measurement_time": self.timestamp,
                    "real_time_source": 1,
                    "sensor": self.sensor,
                    "process_data": self.name,
                    "within_specification": self.within_spec
                })
                quality_measurement.insert()
                
                # Mark this data point for control chart inclusion
                self.db_set("control_chart_point", 1)
                
            except Exception as e:
                frappe.log_error(f"Error creating quality measurement: {str(e)}")
    
    def publish_realtime_update(self):
        """Publish real-time update to dashboard"""
        frappe.realtime.publish_realtime(
            event="sensor_data_update",
            message={
                "station": self.station,
                "sensor": self.sensor,
                "parameter": self.parameter_name,
                "value": self.value,
                "unit": self.unit_of_measure,
                "status": self.status,
                "timestamp": self.timestamp,
                "within_spec": self.within_spec
            },
            room=f"station_{self.station}"
        )
        
        # Also publish to general monitoring room
        frappe.realtime.publish_realtime(
            event="sensor_data_update",
            message={
                "station": self.station,
                "sensor": self.sensor,
                "parameter": self.parameter_name,
                "value": self.value,
                "status": self.status,
                "timestamp": self.timestamp
            },
            room="shop_floor_monitoring"
        )
    
    def update_sensor_statistics(self):
        """Update sensor statistics"""
        try:
            sensor_doc = frappe.get_doc("Sensor Configuration", self.sensor)
            sensor_doc.update_reading_statistics(self.value)
        except Exception as e:
            frappe.log_error(f"Error updating sensor statistics: {str(e)}")
    
    def get_control_chart_data(self):
        """Get data formatted for control charts"""
        return {
            "timestamp": self.timestamp,
            "value": self.value,
            "ucl": self.upper_limit,
            "lcl": self.lower_limit,
            "usl": self.upper_alarm_limit,
            "lsl": self.lower_alarm_limit,
            "status": self.status,
            "parameter": self.parameter_name,
            "within_spec": self.within_spec
        }
    
    def calculate_process_capability(self, specification_limits=None):
        """Calculate process capability indices"""
        if not specification_limits:
            if not (self.upper_alarm_limit and self.lower_alarm_limit):
                return None
            usl = self.upper_alarm_limit
            lsl = self.lower_alarm_limit
        else:
            usl = specification_limits.get("upper")
            lsl = specification_limits.get("lower")
        
        if not (usl and lsl):
            return None
        
        # Get recent data for this sensor/parameter
        recent_data = frappe.db.sql("""
            SELECT value 
            FROM `tabReal-time Process Data`
            WHERE sensor = %s 
            AND parameter_name = %s
            AND timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            AND value IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 100
        """, (self.sensor, self.parameter_name))
        
        if len(recent_data) < 10:  # Need minimum data points
            return None
        
        values = [r[0] for r in recent_data]
        
        # Calculate mean and standard deviation
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return None
        
        # Calculate capability indices
        cp = (usl - lsl) / (6 * std_dev)
        cpu = (usl - mean) / (3 * std_dev)
        cpl = (mean - lsl) / (3 * std_dev)
        cpk = min(cpu, cpl)
        
        self.db_set("process_capability", cpk)
        
        return {
            "cp": cp,
            "cpu": cpu,
            "cpl": cpl,
            "cpk": cpk,
            "mean": mean,
            "std_dev": std_dev,
            "data_points": len(values)
        }

# Whitelisted methods for API access
@frappe.whitelist()
def create_bulk_process_data(data_list):
    """Create multiple process data records efficiently"""
    if isinstance(data_list, str):
        data_list = json.loads(data_list)
    
    created_records = []
    errors = []
    
    for data in data_list:
        try:
            process_data = frappe.get_doc({
                "doctype": "Real-time Process Data",
                **data
            })
            process_data.insert()
            created_records.append(process_data.name)
        except Exception as e:
            errors.append({
                "data": data,
                "error": str(e)
            })
    
    return {
        "created": len(created_records),
        "errors": len(errors),
        "record_names": created_records,
        "error_details": errors
    }

@frappe.whitelist()
def get_station_realtime_data(station_name, limit=50):
    """Get recent real-time data for a station"""
    data = frappe.db.sql("""
        SELECT 
            name,
            timestamp,
            sensor,
            parameter_name,
            value,
            unit_of_measure,
            status,
            within_spec
        FROM `tabReal-time Process Data`
        WHERE station = %s
        ORDER BY timestamp DESC
        LIMIT %s
    """, (station_name, limit), as_dict=True)
    
    return data

@frappe.whitelist()
def get_sensor_trend_data(sensor_name, hours=24):
    """Get trend data for a specific sensor"""
    from_time = frappe.utils.add_hours(now(), -int(hours))
    
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
    
    return data

@frappe.whitelist()
def get_process_capability_report(station_name=None, sensor_name=None, hours=24):
    """Generate process capability report"""
    filters = []
    params = []
    
    if station_name:
        filters.append("station = %s")
        params.append(station_name)
    
    if sensor_name:
        filters.append("sensor = %s")
        params.append(sensor_name)
    
    from_time = frappe.utils.add_hours(now(), -int(hours))
    filters.append("timestamp >= %s")
    params.append(from_time)
    
    where_clause = " AND ".join(filters) if filters else "1=1"
    
    data = frappe.db.sql(f"""
        SELECT 
            sensor,
            parameter_name,
            COUNT(*) as total_readings,
            AVG(value) as mean_value,
            STDDEV(value) as std_deviation,
            MIN(value) as min_value,
            MAX(value) as max_value,
            SUM(CASE WHEN within_spec = 1 THEN 1 ELSE 0 END) as within_spec_count,
            AVG(process_capability) as avg_capability
        FROM `tabReal-time Process Data`
        WHERE {where_clause}
        AND value IS NOT NULL
        GROUP BY sensor, parameter_name
        ORDER BY sensor, parameter_name
    """, params, as_dict=True)
    
    # Calculate yield for each sensor/parameter
    for row in data:
        row['yield_percentage'] = (row['within_spec_count'] / row['total_readings']) * 100 if row['total_readings'] > 0 else 0
    
    return data

@frappe.whitelist()
def archive_old_data(days_to_keep=90):
    """Archive process data older than specified days"""
    cutoff_date = frappe.utils.add_days(now(), -int(days_to_keep))
    
    # Count records to be archived
    count = frappe.db.count("Real-time Process Data", {
        "timestamp": ["<", cutoff_date]
    })
    
    if count == 0:
        return {"message": "No data to archive", "archived_count": 0}
    
    # Move to archive table (if implemented) or delete
    # For now, we'll just delete old data
    frappe.db.sql("""
        DELETE FROM `tabReal-time Process Data`
        WHERE timestamp < %s
    """, (cutoff_date,))
    
    frappe.db.commit()
    
    return {
        "message": f"Archived {count} records older than {cutoff_date}",
        "archived_count": count
    }
