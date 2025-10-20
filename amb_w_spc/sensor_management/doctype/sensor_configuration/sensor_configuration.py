# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import now, add_days, get_datetime, today
from frappe import _
import math

class SensorConfiguration(Document):
    def validate(self):
        """Validation logic for Sensor Configuration"""
        self.validate_threshold_values()
        self.validate_polling_interval()
        self.validate_scaling_parameters()
        self.validate_calibration_dates()
        
    def validate_threshold_values(self):
        """Ensure alarm thresholds are outside warning thresholds"""
        if self.upper_alarm and self.upper_warning:
            if self.upper_alarm <= self.upper_warning:
                frappe.throw(_("Upper alarm threshold must be greater than upper warning threshold"))
                
        if self.lower_alarm and self.lower_warning:
            if self.lower_alarm >= self.lower_warning:
                frappe.throw(_("Lower alarm threshold must be less than lower warning threshold"))
        
        # Ensure upper thresholds are greater than lower thresholds
        if self.upper_warning and self.lower_warning:
            if self.upper_warning <= self.lower_warning:
                frappe.throw(_("Upper warning threshold must be greater than lower warning threshold"))
                
        if self.upper_alarm and self.lower_alarm:
            if self.upper_alarm <= self.lower_alarm:
                frappe.throw(_("Upper alarm threshold must be greater than lower alarm threshold"))
    
    def validate_polling_interval(self):
        """Ensure polling interval is reasonable"""
        if self.polling_interval and self.polling_interval < 100:
            frappe.throw(_("Polling interval cannot be less than 100 milliseconds"))
        
        if self.polling_interval and self.polling_interval > 3600000:  # 1 hour
            frappe.throw(_("Polling interval cannot be more than 1 hour"))
    
    def validate_scaling_parameters(self):
        """Validate scaling factor and offset"""
        if self.scaling_factor is not None and self.scaling_factor == 0:
            frappe.throw(_("Scaling factor cannot be zero"))
    
    def validate_calibration_dates(self):
        """Validate calibration date logic"""
        if self.last_calibration and self.calibration_due:
            if get_datetime(self.calibration_due) <= get_datetime(self.last_calibration):
                frappe.throw(_("Calibration due date must be after last calibration date"))
    
    def after_insert(self):
        """Actions after creating new sensor"""
        self.initialize_readings()
        self.setup_data_collection()
    
    def initialize_readings(self):
        """Initialize reading counters"""
        self.db_set({
            "reading_count_today": 0,
            "average_reading_today": 0.0
        })
    
    def setup_data_collection(self):
        """Setup automated data collection for this sensor"""
        # This would integrate with the scheduler to enable data collection
        frappe.logger().info(f"Data collection setup for sensor {self.sensor_id}")
    
    def get_current_value(self):
        """Get the most recent sensor reading"""
        latest_reading = frappe.db.get_value("Real-time Process Data", 
                                            filters={
                                                "sensor": self.name,
                                                "timestamp": [">=", frappe.utils.add_minutes(now(), -10)]
                                            },
                                            fieldname=["value", "timestamp"],
                                            order_by="timestamp desc")
        
        if latest_reading:
            return {
                "value": latest_reading[0],
                "timestamp": latest_reading[1],
                "status": self.evaluate_reading_status(latest_reading[0])
            }
        return None
    
    def evaluate_reading_status(self, value):
        """Evaluate the status of a reading based on thresholds"""
        if self.upper_alarm and value >= self.upper_alarm:
            return "Alarm"
        elif self.lower_alarm and value <= self.lower_alarm:
            return "Alarm"
        elif self.upper_warning and value >= self.upper_warning:
            return "Warning"
        elif self.lower_warning and value <= self.lower_warning:
            return "Warning"
        else:
            return "Normal"
    
    def process_raw_reading(self, raw_value):
        """Apply scaling and offset to raw sensor reading"""
        try:
            # Convert to appropriate data type
            if self.data_type == "Integer":
                processed_value = int(raw_value)
            elif self.data_type == "Float":
                processed_value = float(raw_value)
            elif self.data_type == "Boolean":
                processed_value = bool(raw_value)
            else:  # String
                processed_value = str(raw_value)
                return processed_value  # No scaling for strings
            
            # Apply scaling and offset for numeric types
            if self.data_type in ["Integer", "Float"]:
                scaling_factor = self.scaling_factor or 1.0
                offset = self.offset or 0.0
                processed_value = (processed_value * scaling_factor) + offset
            
            return processed_value
            
        except (ValueError, TypeError) as e:
            frappe.log_error(f"Error processing raw reading for sensor {self.sensor_id}: {str(e)}")
            return None
    
    def create_process_data_record(self, raw_value, work_order=None, item=None, batch_no=None):
        """Create a real-time process data record"""
        processed_value = self.process_raw_reading(raw_value)
        
        if processed_value is None:
            return None
        
        status = self.evaluate_reading_status(processed_value) if self.data_type in ["Integer", "Float"] else "Normal"
        
        process_data = frappe.get_doc({
            "doctype": "Real-time Process Data",
            "timestamp": now(),
            "station": self.station,
            "sensor": self.name,
            "parameter_name": self.sensor_name,
            "value": processed_value,
            "unit_of_measure": self.unit_of_measure,
            "upper_limit": self.upper_warning,
            "lower_limit": self.lower_warning,
            "status": status,
            "work_order": work_order,
            "item": item,
            "batch_no": batch_no
        })
        
        try:
            process_data.insert()
            self.update_reading_statistics(processed_value)
            return process_data
        except Exception as e:
            frappe.log_error(f"Error creating process data record for sensor {self.sensor_id}: {str(e)}")
            return None
    
    def update_reading_statistics(self, new_value):
        """Update daily reading statistics"""
        current_count = self.reading_count_today or 0
        current_average = self.average_reading_today or 0.0
        
        # Calculate new average
        new_count = current_count + 1
        new_average = ((current_average * current_count) + new_value) / new_count
        
        self.db_set({
            "last_reading": new_value,
            "last_reading_time": now(),
            "reading_count_today": new_count,
            "average_reading_today": new_average
        })
    
    def get_reading_history(self, hours=24):
        """Get reading history for specified number of hours"""
        from_time = frappe.utils.add_hours(now(), -hours)
        
        readings = frappe.db.sql("""
            SELECT 
                timestamp,
                value,
                status
            FROM `tabReal-time Process Data`
            WHERE sensor = %s
            AND timestamp >= %s
            ORDER BY timestamp ASC
        """, (self.name, from_time), as_dict=True)
        
        return readings
    
    def get_statistical_summary(self, hours=24):
        """Get statistical summary of sensor readings"""
        readings = self.get_reading_history(hours)
        
        if not readings:
            return None
        
        values = [r.value for r in readings if r.value is not None]
        
        if not values:
            return None
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "average": sum(values) / len(values),
            "std_dev": self.calculate_std_dev(values),
            "normal_count": len([r for r in readings if r.status == "Normal"]),
            "warning_count": len([r for r in readings if r.status == "Warning"]),
            "alarm_count": len([r for r in readings if r.status == "Alarm"])
        }
    
    def calculate_std_dev(self, values):
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)
    
    def check_calibration_due(self):
        """Check if calibration is due"""
        if not self.calibration_due:
            return False
        
        days_until_due = frappe.utils.date_diff(self.calibration_due, today())
        
        if days_until_due <= 0:
            return "overdue"
        elif days_until_due <= 30:
            return "due_soon"
        else:
            return "current"
    
    def schedule_calibration(self, due_date, notes=None):
        """Schedule calibration for this sensor"""
        calibration_task = frappe.get_doc({
            "doctype": "Task",
            "subject": f"Calibrate Sensor {self.sensor_name}",
            "description": f"Calibration required for sensor {self.sensor_id}\nNotes: {notes or ''}",
            "exp_end_date": due_date,
            "status": "Open",
            "priority": "Medium",
            "project": "Sensor Maintenance"  # Assuming a maintenance project exists
        })
        calibration_task.insert()
        
        self.db_set("calibration_due", due_date)
        return calibration_task
    
    def simulate_reading(self, base_value=None):
        """Generate simulated reading for testing purposes"""
        if base_value is None:
            # Generate a reading based on sensor type
            base_values = {
                "Temperature": 25.0,
                "Pressure": 50.0,
                "Flow": 100.0,
                "Level": 75.0,
                "Vibration": 1.0,
                "Speed": 1500.0,
                "pH": 7.0,
                "Humidity": 60.0
            }
            base_value = base_values.get(self.sensor_type, 50.0)
        
        # Add some random variation (±10%)
        import random
        variation = random.uniform(-0.1, 0.1)
        simulated_value = base_value * (1 + variation)
        
        return self.create_process_data_record(simulated_value)

# Whitelisted methods for API access
@frappe.whitelist()
def get_sensor_current_value(sensor_name):
    """Get current value of a sensor"""
    sensor = frappe.get_doc("Sensor Configuration", sensor_name)
    return sensor.get_current_value()

@frappe.whitelist()
def get_sensor_history(sensor_name, hours=24):
    """Get reading history for a sensor"""
    sensor = frappe.get_doc("Sensor Configuration", sensor_name)
    return sensor.get_reading_history(int(hours))

@frappe.whitelist()
def get_sensor_statistics(sensor_name, hours=24):
    """Get statistical summary for a sensor"""
    sensor = frappe.get_doc("Sensor Configuration", sensor_name)
    return sensor.get_statistical_summary(int(hours))

@frappe.whitelist()
def simulate_sensor_reading(sensor_name, base_value=None):
    """Generate simulated reading for testing"""
    sensor = frappe.get_doc("Sensor Configuration", sensor_name)
    if base_value:
        base_value = float(base_value)
    return sensor.simulate_reading(base_value)

@frappe.whitelist()
def check_sensors_calibration_status():
    """Check calibration status for all sensors"""
    sensors = frappe.get_all("Sensor Configuration", 
                           filters={"status": "Active"},
                           fields=["name", "sensor_id", "sensor_name", "calibration_due"])
    
    results = []
    for sensor in sensors:
        sensor_doc = frappe.get_doc("Sensor Configuration", sensor.name)
        calibration_status = sensor_doc.check_calibration_due()
        results.append({
            "sensor_id": sensor.sensor_id,
            "sensor_name": sensor.sensor_name,
            "calibration_due": sensor.calibration_due,
            "status": calibration_status
        })
    
    return results

@frappe.whitelist()
def get_station_sensors(station_name):
    """Get all sensors for a manufacturing station"""
    sensors = frappe.get_all("Sensor Configuration",
                           filters={"station": station_name, "status": "Active"},
                           fields=["name", "sensor_id", "sensor_name", "sensor_type", 
                                  "last_reading", "last_reading_time"])
    
    for sensor in sensors:
        sensor_doc = frappe.get_doc("Sensor Configuration", sensor.name)
        current_value = sensor_doc.get_current_value()
        if current_value:
            sensor.update(current_value)
    
    return sensors
