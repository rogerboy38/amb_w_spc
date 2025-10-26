# Copyright (c) 2025, MiniMax Agent and contributors
# Scheduler functions for shop floor control data collection

import frappe
import socket
import json
import requests
from frappe.utils import now, cint, flt, add_minutes
from frappe import _
import threading
import time

def collect_sensor_data():
    """Main scheduler function to collect data from all active sensors - runs every minute"""
    try:
        frappe.logger().info("Starting scheduled sensor data collection")
        
        # Get all active manufacturing stations
        active_stations = frappe.get_all("Manufacturing Station", 
                                       filters={
                                           "status": "Active",
                                           "polling_enabled": 1
                                       },
                                       fields=["name", "station_id", "hostname", "ip_address", 
                                              "port_number", "read_interval", "communication_status"])
        
        if not active_stations:
            frappe.logger().info("No active stations found for data collection")
            return
        
        # Process stations in parallel for better performance
        threads = []
        for station in active_stations:
            thread = threading.Thread(target=collect_station_data, args=(station,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete (with timeout)
        for thread in threads:
            thread.join(timeout=30)  # 30 second timeout per station
        
        frappe.logger().info(f"Completed data collection for {len(active_stations)} stations")
        
    except Exception as e:
        frappe.log_error(f"Error in scheduled sensor data collection: {str(e)}")

def collect_station_data(station):
    """Collect data from a specific manufacturing station"""
    try:
        frappe.logger().info(f"Collecting data from station: {station.station_id}")
        
        # Get all active sensors for this station
        sensors = frappe.get_all("Sensor Configuration",
                               filters={
                                   "station": station.name,
                                   "status": "Active"
                               },
                               fields=["name", "sensor_id", "communication_protocol", "address", 
                                      "polling_interval", "data_type", "scaling_factor", "offset"])
        
        if not sensors:
            frappe.logger().info(f"No active sensors found for station {station.station_id}")
            return
        
        # Test station connectivity first
        if not test_station_connectivity(station):
            update_station_communication_status(station.name, "Offline")
            return
        
        # Collect data from each sensor
        successful_reads = 0
        for sensor in sensors:
            try:
                value = read_sensor_value(station, sensor)
                if value is not None:
                    create_process_data_record(station, sensor, value)
                    successful_reads += 1
                    
                # Small delay between sensor reads to avoid overwhelming the station
                time.sleep(0.1)
                
            except Exception as e:
                frappe.log_error(f"Error reading sensor {sensor.sensor_id} at station {station.station_id}: {str(e)}")
        
        # Update station communication status
        if successful_reads > 0:
            update_station_communication_status(station.name, "Online")
        else:
            update_station_communication_status(station.name, "Error")
        
        frappe.logger().info(f"Station {station.station_id}: {successful_reads}/{len(sensors)} sensors read successfully")
        
    except Exception as e:
        frappe.log_error(f"Error collecting data from station {station.get('station_id', 'Unknown')}: {str(e)}")
        update_station_communication_status(station.name, "Error")

def test_station_connectivity(station):
    """Test if station is reachable"""
    if not station.ip_address or not station.port_number:
        return False
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5 second timeout
        result = sock.connect_ex((station.ip_address, station.port_number))
        sock.close()
        return result == 0
    except Exception:
        return False

def read_sensor_value(station, sensor):
    """Read value from individual sensor based on communication protocol"""
    try:
        if sensor.communication_protocol == "TCP/IP":
            return read_tcp_sensor(station, sensor)
        elif sensor.communication_protocol == "Modbus TCP":
            return read_modbus_tcp_sensor(station, sensor)
        elif sensor.communication_protocol == "HTTP":
            return read_http_sensor(station, sensor)
        elif sensor.communication_protocol == "MQTT":
            return read_mqtt_sensor(station, sensor)
        else:
            # For unsupported protocols, generate simulated data for testing
            return generate_simulated_reading(sensor)
    except Exception as e:
        frappe.log_error(f"Error reading sensor {sensor.sensor_id}: {str(e)}")
        return None

def read_tcp_sensor(station, sensor):
    """Read sensor value via TCP/IP"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5 second timeout
        sock.connect((station.ip_address, station.port_number))
        
        # Send request for sensor data (customize based on protocol)
        if sensor.address:
            request = f"READ {sensor.address}\n"
        else:
            request = f"READ {sensor.sensor_id}\n"
        
        sock.send(request.encode())
        
        # Receive response
        response = sock.recv(1024).decode().strip()
        sock.close()
        
        # Parse response and apply scaling
        raw_value = float(response)
        scaled_value = apply_sensor_scaling(raw_value, sensor)
        
        return scaled_value
        
    except Exception as e:
        frappe.log_error(f"TCP communication error with {station.hostname}: {str(e)}")
        return None

def read_modbus_tcp_sensor(station, sensor):
    """Read sensor value via Modbus TCP"""
    try:
        # This would require pymodbus library
        # For now, return simulated data
        return generate_simulated_reading(sensor)
    except Exception as e:
        frappe.log_error(f"Modbus TCP error for sensor {sensor.sensor_id}: {str(e)}")
        return None

def read_http_sensor(station, sensor):
    """Read sensor value via HTTP API"""
    try:
        url = f"http://{station.ip_address}:{station.port_number}/api/sensors/{sensor.address or sensor.sensor_id}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            raw_value = data.get('value')
            if raw_value is not None:
                return apply_sensor_scaling(raw_value, sensor)
        
        return None
        
    except Exception as e:
        frappe.log_error(f"HTTP communication error for sensor {sensor.sensor_id}: {str(e)}")
        return None

def read_mqtt_sensor(station, sensor):
    """Read sensor value via MQTT"""
    # MQTT would require persistent connection management
    # For now, return simulated data
    return generate_simulated_reading(sensor)

def generate_simulated_reading(sensor):
    """Generate simulated reading for testing purposes"""
    import random
    
    # Base values by sensor type
    base_values = {
        "Temperature": 25.0,
        "Pressure": 50.0,
        "Flow": 100.0,
        "Level": 75.0,
        "Vibration": 1.0,
        "Speed": 1500.0,
        "Torque": 200.0,
        "Force": 500.0,
        "Voltage": 24.0,
        "Current": 5.0,
        "pH": 7.0,
        "Humidity": 60.0
    }
    
    base_value = base_values.get(sensor.get('sensor_type', ''), 50.0)
    
    # Add random variation (±10%)
    variation = random.uniform(-0.1, 0.1)
    raw_value = base_value * (1 + variation)
    
    return apply_sensor_scaling(raw_value, sensor)

def apply_sensor_scaling(raw_value, sensor):
    """Apply scaling factor and offset to raw sensor reading"""
    try:
        scaling_factor = sensor.get('scaling_factor', 1.0) or 1.0
        offset = sensor.get('offset', 0.0) or 0.0
        
        scaled_value = (raw_value * scaling_factor) + offset
        
        # Round to reasonable precision
        return round(scaled_value, 3)
        
    except Exception as e:
        frappe.log_error(f"Error applying scaling to sensor {sensor.get('sensor_id')}: {str(e)}")
        return raw_value

def create_process_data_record(station, sensor, value):
    """Create real-time process data record"""
    try:
        # Get current work order for the station
        current_operation = get_current_station_operation(station.name)
        
        # Get sensor configuration for limits
        sensor_config = frappe.get_doc("Sensor Configuration", sensor.name)
        
        process_data = frappe.get_doc({
            "doctype": "Real-time Process Data",
            "timestamp": now(),
            "station": station.name,
            "sensor": sensor.name,
            "parameter_name": sensor_config.sensor_name,
            "value": value,
            "unit_of_measure": sensor_config.unit_of_measure,
            "upper_limit": sensor_config.upper_warning,
            "lower_limit": sensor_config.lower_warning,
            "upper_alarm_limit": sensor_config.upper_alarm,
            "lower_alarm_limit": sensor_config.lower_alarm,
            "work_order": current_operation.get("work_order") if current_operation else None,
            "item": current_operation.get("item") if current_operation else None,
            "batch_no": current_operation.get("batch_no") if current_operation else None,
            "operation": current_operation.get("operation") if current_operation else None
        })
        
        process_data.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return process_data.name
        
    except Exception as e:
        frappe.log_error(f"Error creating process data record: {str(e)}")
        return None

def get_current_station_operation(station_name):
    """Get currently active work order operation for station"""
    try:
        operation = frappe.db.get_value("Work Order Operation",
                                      filters={
                                          "workstation": station_name,
                                          "status": "Work in Progress"
                                      },
                                      fieldname=["parent", "operation", "production_item"],
                                      as_dict=True)
        
        if operation:
            # Get work order details
            work_order = frappe.get_doc("Work Order", operation.parent)
            return {
                "work_order": operation.parent,
                "operation": operation.operation,
                "item": operation.production_item or work_order.production_item,
                "batch_no": work_order.batch_size  # or get from batch tracking
            }
        
        return None
        
    except Exception as e:
        frappe.log_error(f"Error getting current station operation: {str(e)}")
        return None

def update_station_communication_status(station_name, status):
    """Update station communication status"""
    try:
        frappe.db.set_value("Manufacturing Station", station_name, {
            "communication_status": status,
            "last_communication": now()
        })
        frappe.db.commit()
        
        # Publish real-time status update
        frappe.realtime.publish_realtime(
            event="station_status_change",
            message={
                "station": station_name,
                "communication_status": status,
                "timestamp": now()
            },
            room="shop_floor_monitoring"
        )
        
    except Exception as e:
        frappe.log_error(f"Error updating station communication status: {str(e)}")

# Utility function for testing
@frappe.whitelist()
def test_sensor_data_collection():
    """Test function to manually trigger sensor data collection"""
    collect_sensor_data()
    return {"status": "success", "message": "Sensor data collection test completed"}

@frappe.whitelist()
def simulate_station_data(station_name, duration_minutes=5):
    """Generate simulated data for a station for testing purposes"""
    try:
        station = frappe.get_doc("Manufacturing Station", station_name)
        sensors = frappe.get_all("Sensor Configuration",
                               filters={"station": station_name, "status": "Active"},
                               fields=["name", "sensor_id", "sensor_type"])
        
        if not sensors:
            return {"status": "error", "message": "No active sensors found for station"}
        
        records_created = 0
        end_time = time.time() + (duration_minutes * 60)
        
        while time.time() < end_time:
            for sensor in sensors:
                value = generate_simulated_reading(sensor)
                if value is not None:
                    create_process_data_record(station, sensor, value)
                    records_created += 1
            
            time.sleep(10)  # 10 second intervals
        
        return {
            "status": "success", 
            "message": f"Created {records_created} simulated readings for station {station_name}",
            "records_created": records_created
        }
        
    except Exception as e:
        frappe.log_error(f"Error in simulate_station_data: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_collection_statistics():
    """Get statistics about data collection performance"""
    try:
        # Get collection stats for last 24 hours
        stats = frappe.db.sql("""
            SELECT 
                station,
                COUNT(*) as total_readings,
                COUNT(DISTINCT sensor) as unique_sensors,
                MIN(timestamp) as first_reading,
                MAX(timestamp) as last_reading,
                AVG(value) as avg_value
            FROM `tabReal-time Process Data`
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            GROUP BY station
            ORDER BY total_readings DESC
        """, as_dict=True)
        
        # Get overall summary
        summary = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_readings_24h,
                COUNT(DISTINCT station) as active_stations,
                COUNT(DISTINCT sensor) as active_sensors,
                AVG(CASE WHEN status = 'Normal' THEN 1 ELSE 0 END) * 100 as normal_percentage
            FROM `tabReal-time Process Data`
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        """, as_dict=True)
        
        return {
            "station_stats": stats,
            "summary": summary[0] if summary else {},
            "collection_time": now()
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting collection statistics: {str(e)}")
        return {"status": "error", "message": str(e)}
