# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
import socket
import json
from frappe.model.document import Document
from frappe.utils import now, add_to_date, get_datetime
from frappe import _

class ManufacturingStation(Document):
    def validate(self):
        """Validation logic for Manufacturing Station"""
        self.validate_network_settings()
        self.validate_performance_targets()
        self.validate_alert_settings()
        
    def validate_network_settings(self):
        """Validate network configuration"""
        if self.ip_address:
            # Basic IP address format validation
            parts = self.ip_address.split('.')
            if len(parts) != 4:
                frappe.throw(_("Invalid IP address format"))
            
            for part in parts:
                try:
                    num = int(part)
                    if num < 0 or num > 255:
                        frappe.throw(_("Invalid IP address range"))
                except ValueError:
                    frappe.throw(_("IP address must contain only numbers and dots"))
        
        if self.port_number:
            if self.port_number < 1 or self.port_number > 65535:
                frappe.throw(_("Port number must be between 1 and 65535"))
    
    def validate_performance_targets(self):
        """Validate performance metrics"""
        if self.oee_target and (self.oee_target < 0 or self.oee_target > 100):
            frappe.throw(_("OEE Target must be between 0 and 100 percent"))
            
        if self.read_interval and self.read_interval < 50:
            frappe.throw(_("Read interval cannot be less than 50 milliseconds"))
            
        if self.reply_interval and self.reply_interval < 1:
            frappe.throw(_("Reply interval cannot be less than 1 second"))
    
    def validate_alert_settings(self):
        """Validate alert configuration"""
        if self.speaker_on_duration and self.speaker_on_duration < 0:
            frappe.throw(_("Speaker on duration cannot be negative"))
            
        if self.speaker_off_duration and self.speaker_off_duration < 0:
            frappe.throw(_("Speaker off duration cannot be negative"))
            
        if self.speaker_repeat_times and self.speaker_repeat_times < 1:
            frappe.throw(_("Speaker repeat times must be at least 1"))
    
    def after_insert(self):
        """Actions after creating new station"""
        self.create_default_sensor_configurations()
        self.initialize_performance_metrics()
        
    def create_default_sensor_configurations(self):
        """Create default sensor configurations for the station"""
        default_sensors = [
            {
                "sensor_id": f"{self.station_id}_TEMP",
                "sensor_name": f"{self.station_name} Temperature",
                "sensor_type": "Temperature",
                "polling_interval": 1000,
                "upper_warning": 80.0,
                "upper_alarm": 90.0,
                "lower_warning": 10.0,
                "lower_alarm": 5.0
            },
            {
                "sensor_id": f"{self.station_id}_PRESS",
                "sensor_name": f"{self.station_name} Pressure",
                "sensor_type": "Pressure",
                "polling_interval": 1000,
                "upper_warning": 100.0,
                "upper_alarm": 120.0,
                "lower_warning": 5.0,
                "lower_alarm": 0.0
            }
        ]
        
        for sensor_config in default_sensors:
            if not frappe.db.exists("Sensor Configuration", {"sensor_id": sensor_config["sensor_id"]}):
                sensor_doc = frappe.get_doc({
                    "doctype": "Sensor Configuration",
                    "station": self.name,
                    **sensor_config
                })
                sensor_doc.insert()
    
    def initialize_performance_metrics(self):
        """Initialize performance tracking"""
        self.db_set({
            "current_oee": 0.0,
            "uptime_percentage": 100.0,
            "total_production_count": 0,
            "communication_status": "Offline"
        })
    
    def test_connection(self):
        """Test network connection to the station"""
        if not self.ip_address or not self.port_number:
            frappe.throw(_("IP Address and Port Number are required for connection test"))
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.connection_timeout or 30)
            result = sock.connect_ex((self.ip_address, self.port_number))
            sock.close()
            
            if result == 0:
                self.db_set({
                    "communication_status": "Online",
                    "last_communication": now()
                })
                return {"status": "success", "message": "Connection successful"}
            else:
                self.db_set("communication_status", "Offline")
                return {"status": "error", "message": "Connection failed"}
                
        except Exception as e:
            self.db_set("communication_status", "Error")
            frappe.log_error(f"Connection test failed for {self.station_id}: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_current_status(self):
        """Get current operational status of the station"""
        return {
            "station_id": self.station_id,
            "station_name": self.station_name,
            "status": self.status,
            "communication_status": self.communication_status,
            "current_oee": self.current_oee,
            "uptime_percentage": self.uptime_percentage,
            "last_communication": self.last_communication,
            "active_operators": self.get_active_operators_count(),
            "active_alerts": self.get_active_alerts_count(),
            "current_work_order": self.get_current_work_order()
        }
    
    def get_active_operators_count(self):
        """Get count of currently checked-in operators"""
        return frappe.db.count("Operator Check-in", {
            "station": self.name,
            "status": "Active"
        })
    
    def get_active_alerts_count(self):
        """Get count of active alerts for this station"""
        return frappe.db.count("Process Alert", {
            "station": self.name,
            "status": "Active"
        })
    
    def get_current_work_order(self):
        """Get currently active work order for this station"""
        work_order = frappe.db.get_value("Work Order Operation", 
                                        filters={
                                            "workstation": self.name,
                                            "status": "Work in Progress"
                                        },
                                        fieldname=["parent", "operation"])
        
        if work_order:
            return {
                "work_order": work_order[0],
                "operation": work_order[1]
            }
        return None
    
    def calculate_oee(self, from_date=None, to_date=None):
        """Calculate Overall Equipment Effectiveness"""
        if not from_date:
            # from_date = add_to_date(now(), -60)  
            # Last hour
            from_date = add_to_date(current_time, minutes=-60)
        if not to_date:
            to_date = now()
        
        # Get production data for the period
        production_data = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_produced,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as good_produced,
                AVG(TIMESTAMPDIFF(MINUTE, start_time, end_time)) as avg_cycle_time
            FROM `tabWork Order Operation`
            WHERE workstation = %s 
            AND start_time BETWEEN %s AND %s
        """, (self.name, from_date, to_date), as_dict=True)
        
        if not production_data or not production_data[0].total_produced:
            return 0.0
        
        data = production_data[0]
        
        # Calculate OEE components
        # Availability = (Operating Time / Planned Production Time) * 100
        planned_time = 60  # minutes
        operating_time = planned_time - self.get_downtime_minutes(from_date, to_date)
        availability = (operating_time / planned_time) * 100 if planned_time > 0 else 0
        
        # Performance = (Ideal Cycle Time / Actual Cycle Time) * 100
        ideal_cycle_time = 5  # minutes (default)
        actual_cycle_time = data.avg_cycle_time or ideal_cycle_time
        performance = (ideal_cycle_time / actual_cycle_time) * 100 if actual_cycle_time > 0 else 0
        
        # Quality = (Good Units / Total Units) * 100
        quality = (data.good_produced / data.total_produced) * 100 if data.total_produced > 0 else 0
        
        # OEE = Availability * Performance * Quality / 10000
        oee = (availability * performance * quality) / 10000
        
        # Update current OEE
        self.db_set("current_oee", min(oee, 100.0))
        
        return oee
    
    def get_downtime_minutes(self, from_date, to_date):
        """Calculate downtime in minutes for the given period"""
        downtime = frappe.db.sql("""
            SELECT 
                COALESCE(SUM(TIMESTAMPDIFF(MINUTE, triggered_at, 
                    COALESCE(resolved_at, %s))), 0) as total_downtime
            FROM `tabProcess Alert`
            WHERE station = %s 
            AND alert_type = 'Alarm'
            AND triggered_at BETWEEN %s AND %s
        """, (to_date, self.name, from_date, to_date))
        
        return downtime[0][0] if downtime and downtime[0][0] else 0
    
    def send_command(self, command, parameters=None):
        """Send command to the manufacturing station"""
        if self.communication_status != "Online":
            frappe.throw(_("Station is not online. Cannot send command."))
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.reply_interval or 5)
            sock.connect((self.ip_address, self.port_number))
            
            # Format command based on station protocol
            command_str = self.format_command(command, parameters)
            sock.send(command_str.encode())
            
            # Receive response
            response = sock.recv(1024).decode().strip()
            sock.close()
            
            # Log the command
            self.log_command(command, parameters, response)
            
            return {
                "status": "success",
                "command": command,
                "response": response
            }
            
        except Exception as e:
            frappe.log_error(f"Command failed for {self.station_id}: {str(e)}")
            return {
                "status": "error",
                "command": command,
                "error": str(e)
            }
    
    def format_command(self, command, parameters=None):
        """Format command according to station protocol"""
        if parameters:
            param_str = json.dumps(parameters)
            return f"{command} {param_str}\n"
        else:
            return f"{command}\n"
    
    def log_command(self, command, parameters, response):
        """Log command execution for audit trail"""
        log_entry = frappe.get_doc({
            "doctype": "Station Command Log",
            "station": self.name,
            "command": command,
            "parameters": json.dumps(parameters) if parameters else None,
            "response": response,
            "timestamp": now(),
            "user": frappe.session.user
        })
        log_entry.insert()

# Whitelisted methods for API access
@frappe.whitelist()
def test_station_connection(station_name):
    """Test connection to a manufacturing station"""
    station = frappe.get_doc("Manufacturing Station", station_name)
    return station.test_connection()

@frappe.whitelist()
def get_station_status(station_name):
    """Get current status of a manufacturing station"""
    station = frappe.get_doc("Manufacturing Station", station_name)
    return station.get_current_status()

@frappe.whitelist()
def calculate_station_oee(station_name, from_date=None, to_date=None):
    """Calculate OEE for a station"""
    station = frappe.get_doc("Manufacturing Station", station_name)
    return station.calculate_oee(from_date, to_date)

@frappe.whitelist()
def send_station_command(station_name, command, parameters=None):
    """Send command to a manufacturing station"""
    station = frappe.get_doc("Manufacturing Station", station_name)
    return station.send_command(command, parameters)

@frappe.whitelist()
def get_dashboard_data():
    """Get data for shop floor dashboard"""
    stations = frappe.get_all("Manufacturing Station",
                            filters={"status": ["in", ["Active", "Maintenance"]]},
                            fields=["name", "station_id", "station_name", "station_type", 
                                   "status", "current_oee", "oee_target", "uptime_percentage",
                                   "communication_status", "last_communication"])
    
    for station in stations:
        station_doc = frappe.get_doc("Manufacturing Station", station.name)
        station.update({
            "active_operators": station_doc.get_active_operators_count(),
            "active_alerts": station_doc.get_active_alerts_count(),
            "current_work_order": station_doc.get_current_work_order()
        })
    
    return {
        "stations": stations,
        "total_stations": len(stations),
        "online_stations": len([s for s in stations if s.communication_status == "Online"]),
        "average_oee": sum([s.current_oee or 0 for s in stations]) / len(stations) if stations else 0
    }
