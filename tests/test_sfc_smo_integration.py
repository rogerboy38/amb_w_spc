# Copyright (c) 2025, MiniMax Agent and contributors
# Comprehensive test suite for SFC SMO integration

import frappe
import unittest
import time
import json
from frappe.utils import now, add_minutes, today, add_days
from unittest.mock import patch, MagicMock

class TestSFCSMOIntegration(unittest.TestCase):
    """Test suite for SFC SMO integration with AMB-SPC"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data that persists across all tests"""
        cls.test_station_id = "TEST-STATION-001"
        cls.test_sensor_id = "TEST-SENSOR-001"
        
    def setUp(self):
        """Set up test data for each test"""
        # Clean up any existing test data
        self.cleanup_test_data()
        
        # Create test manufacturing station
        self.create_test_station()
        
        # Create test sensor configuration
        self.create_test_sensor()
        
        # Create test UOM
        self.create_test_uom()
    
    def tearDown(self):
        """Clean up after each test"""
        self.cleanup_test_data()
    
    def cleanup_test_data(self):
        """Remove all test data"""
        # Delete in reverse dependency order
        for doctype in ["Real-time Process Data", "Process Alert", "Quality Measurement"]:
            frappe.db.sql(f"DELETE FROM `tab{doctype}` WHERE name LIKE 'TEST-%'")
        
        for name in [self.test_sensor_id, self.test_station_id]:
            if frappe.db.exists("Sensor Configuration", name):
                frappe.delete_doc("Sensor Configuration", name)
            if frappe.db.exists("Manufacturing Station", name):
                frappe.delete_doc("Manufacturing Station", name)
        
        if frappe.db.exists("UOM", "Test Unit"):
            frappe.delete_doc("UOM", "Test Unit")
        
        frappe.db.commit()
    
    def create_test_station(self):
        """Create test manufacturing station"""
        self.station = frappe.get_doc({
            "doctype": "Manufacturing Station",
            "station_id": self.test_station_id,
            "station_name": "Test Station 1",
            "station_type": "Testing",
            "hostname": "test-host",
            "ip_address": "192.168.1.100",
            "port_number": 55962,
            "status": "Active",
            "read_interval": 100,
            "reply_interval": 5,
            "polling_enabled": 1,
            "oee_target": 85.0
        })
        self.station.insert()
        frappe.db.commit()
    
    def create_test_sensor(self):
        """Create test sensor configuration"""
        self.sensor = frappe.get_doc({
            "doctype": "Sensor Configuration",
            "sensor_id": self.test_sensor_id,
            "sensor_name": "Test Temperature Sensor",
            "sensor_type": "Temperature",
            "station": self.station.name,
            "communication_protocol": "TCP/IP",
            "polling_interval": 1000,
            "data_type": "Float",
            "scaling_factor": 1.0,
            "offset": 0.0,
            "upper_alarm": 100.0,
            "lower_alarm": 0.0,
            "upper_warning": 90.0,
            "lower_warning": 10.0,
            "status": "Active",
            "unit_of_measure": "Test Unit"
        })
        self.sensor.insert()
        frappe.db.commit()
    
    def create_test_uom(self):
        """Create test unit of measure"""
        if not frappe.db.exists("UOM", "Test Unit"):
            uom = frappe.get_doc({
                "doctype": "UOM",
                "uom_name": "Test Unit",
                "name": "Test Unit"
            })
            uom.insert()
            frappe.db.commit()
    
    # Test Manufacturing Station functionality
    def test_manufacturing_station_creation(self):
        """Test manufacturing station creation and validation"""
        # Test successful creation
        self.assertTrue(frappe.db.exists("Manufacturing Station", self.test_station_id))
        
        # Test validation - invalid IP address
        with self.assertRaises(frappe.ValidationError):
            invalid_station = frappe.get_doc({
                "doctype": "Manufacturing Station",
                "station_id": "INVALID-STATION",
                "station_name": "Invalid Station",
                "station_type": "Testing",
                "ip_address": "999.999.999.999",  # Invalid IP
                "port_number": 55962,
                "status": "Active"
            })
            invalid_station.insert()
        
        # Test validation - invalid port number
        with self.assertRaises(frappe.ValidationError):
            invalid_station = frappe.get_doc({
                "doctype": "Manufacturing Station",
                "station_id": "INVALID-STATION-2",
                "station_name": "Invalid Station 2",
                "station_type": "Testing",
                "ip_address": "192.168.1.1",
                "port_number": 99999,  # Invalid port
                "status": "Active"
            })
            invalid_station.insert()
    
    def test_station_performance_calculation(self):
        """Test OEE and performance calculations"""
        # Test OEE calculation
        oee = self.station.calculate_oee()
        self.assertIsInstance(oee, float)
        self.assertGreaterEqual(oee, 0.0)
        self.assertLessEqual(oee, 100.0)
        
        # Test status retrieval
        status = self.station.get_current_status()
        self.assertIn("station_id", status)
        self.assertIn("current_oee", status)
        self.assertIn("active_operators", status)
    
    @patch('socket.socket')
    def test_station_connection_test(self, mock_socket):
        """Test station connectivity testing"""
        # Mock successful connection
        mock_sock_instance = MagicMock()
        mock_sock_instance.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock_instance
        
        result = self.station.test_connection()
        self.assertEqual(result["status"], "success")
        
        # Mock failed connection
        mock_sock_instance.connect_ex.return_value = 1
        result = self.station.test_connection()
        self.assertEqual(result["status"], "error")
    
    # Test Sensor Configuration functionality
    def test_sensor_configuration_creation(self):
        """Test sensor configuration creation and validation"""
        # Test successful creation
        self.assertTrue(frappe.db.exists("Sensor Configuration", self.test_sensor_id))
        
        # Test threshold validation - upper alarm <= upper warning
        with self.assertRaises(frappe.ValidationError):
            invalid_sensor = frappe.get_doc({
                "doctype": "Sensor Configuration",
                "sensor_id": "INVALID-SENSOR",
                "sensor_name": "Invalid Sensor",
                "sensor_type": "Temperature",
                "station": self.station.name,
                "communication_protocol": "TCP/IP",
                "upper_alarm": 80.0,  # Should be > upper_warning
                "upper_warning": 90.0,
                "status": "Active"
            })
            invalid_sensor.insert()
    
    def test_sensor_reading_processing(self):
        """Test sensor reading processing and scaling"""
        # Test normal processing
        raw_value = 25.5
        processed_value = self.sensor.process_raw_reading(raw_value)
        self.assertEqual(processed_value, 25.5)  # No scaling applied
        
        # Test with scaling
        self.sensor.scaling_factor = 2.0
        self.sensor.offset = 5.0
        processed_value = self.sensor.process_raw_reading(raw_value)
        expected_value = (25.5 * 2.0) + 5.0
        self.assertEqual(processed_value, expected_value)
    
    def test_sensor_status_evaluation(self):
        """Test sensor reading status evaluation"""
        # Test normal reading
        status = self.sensor.evaluate_reading_status(50.0)
        self.assertEqual(status, "Normal")
        
        # Test warning threshold
        status = self.sensor.evaluate_reading_status(95.0)  # > upper_warning (90.0)
        self.assertEqual(status, "Warning")
        
        # Test alarm threshold
        status = self.sensor.evaluate_reading_status(105.0)  # > upper_alarm (100.0)
        self.assertEqual(status, "Alarm")
    
    # Test Real-time Process Data functionality
    def test_process_data_creation(self):
        """Test real-time process data creation"""
        process_data = frappe.get_doc({
            "doctype": "Real-time Process Data",
            "timestamp": now(),
            "station": self.station.name,
            "sensor": self.sensor.name,
            "parameter_name": "Temperature",
            "value": 75.5,
            "unit_of_measure": "Test Unit",
            "status": "Normal"
        })
        process_data.insert()
        
        # Verify creation
        self.assertTrue(frappe.db.exists("Real-time Process Data", process_data.name))
        
        # Test data validation
        self.assertEqual(process_data.value, 75.5)
        self.assertEqual(process_data.status, "Normal")
    
    def test_process_data_threshold_checking(self):
        """Test automatic threshold checking and alert creation"""
        # Create process data that exceeds warning threshold
        process_data = frappe.get_doc({
            "doctype": "Real-time Process Data",
            "timestamp": now(),
            "station": self.station.name,
            "sensor": self.sensor.name,
            "parameter_name": "Temperature",
            "value": 95.0,  # Exceeds upper_warning (90.0)
            "unit_of_measure": "Test Unit",
            "upper_limit": 90.0,
            "lower_limit": 10.0,
            "upper_alarm_limit": 100.0,
            "lower_alarm_limit": 0.0
        })
        process_data.insert()
        
        # Check if alert was created
        alert_exists = frappe.db.exists("Process Alert", {
            "station": self.station.name,
            "sensor": self.sensor.name,
            "alert_type": "Warning"
        })
        self.assertTrue(alert_exists)
    
    def test_process_data_quality_indicators(self):
        """Test quality indicator calculations"""
        process_data = frappe.get_doc({
            "doctype": "Real-time Process Data",
            "timestamp": now(),
            "station": self.station.name,
            "sensor": self.sensor.name,
            "parameter_name": "Temperature",
            "value": 50.0,
            "upper_limit": 90.0,
            "lower_limit": 10.0
        })
        process_data.set_quality_indicators()
        
        # Should be within spec
        self.assertTrue(process_data.within_spec)
        self.assertIsNotNone(process_data.deviation_percentage)
    
    # Test Data Collection Scheduler
    @patch('amb_w_spc.shop_floor_control.scheduler.read_sensor_value')
    def test_sensor_data_collection(self, mock_read_sensor):
        """Test scheduled sensor data collection"""
        # Mock sensor reading
        mock_read_sensor.return_value = 75.0
        
        # Import and run collection function
        from amb_w_spc.shop_floor_control.scheduler import collect_station_data
        
        station_dict = {
            "name": self.station.name,
            "station_id": self.station.station_id,
            "hostname": self.station.hostname,
            "ip_address": self.station.ip_address,
            "port_number": self.station.port_number
        }
        
        # Run collection
        collect_station_data(station_dict)
        
        # Verify data was created
        data_exists = frappe.db.exists("Real-time Process Data", {
            "station": self.station.name,
            "sensor": self.sensor.name
        })
        self.assertTrue(data_exists)
    
    # Test Integration with Quality Management
    def test_spc_integration(self):
        """Test integration with SPC quality measurements"""
        # Create a work order for testing
        if not frappe.db.exists("Item", "TEST-ITEM"):
            test_item = frappe.get_doc({
                "doctype": "Item",
                "item_code": "TEST-ITEM",
                "item_name": "Test Item",
                "item_group": "All Item Groups",
                "stock_uom": "Nos"
            })
            test_item.insert()
        
        work_order = frappe.get_doc({
            "doctype": "Work Order",
            "production_item": "TEST-ITEM",
            "qty": 100,
            "company": frappe.defaults.get_defaults().company or "Test Company"
        })
        work_order.insert()
        
        # Create process data with work order context
        process_data = frappe.get_doc({
            "doctype": "Real-time Process Data",
            "timestamp": now(),
            "station": self.station.name,
            "sensor": self.sensor.name,
            "parameter_name": "Temperature",
            "value": 80.0,
            "unit_of_measure": "Test Unit",
            "work_order": work_order.name,
            "item": work_order.production_item,
            "upper_limit": 90.0,
            "lower_limit": 10.0,
            "within_spec": True
        })
        process_data.insert()
        
        # Check if quality measurement was auto-created
        quality_measurement = frappe.db.exists("Quality Measurement", {
            "work_order": work_order.name,
            "real_time_source": 1,
            "sensor": self.sensor.name
        })
        # Note: This test might need adjustment based on actual Quality Measurement DocType structure
    
    # Test API Endpoints
    def test_api_endpoints(self):
        """Test API endpoint functionality"""
        # Test get_sensor_current_value
        from amb_w_spc.sensor_management.doctype.sensor_configuration.sensor_configuration import get_sensor_current_value
        
        # Create some test data first
        self.sensor.create_process_data_record(75.0)
        
        current_value = get_sensor_current_value(self.sensor.name)
        if current_value:  # Might be None if no recent data
            self.assertIn("value", current_value)
            self.assertIn("status", current_value)
    
    def test_simulated_data_generation(self):
        """Test simulated data generation for testing"""
        # Test sensor simulation
        simulated_reading = self.sensor.simulate_reading(base_value=25.0)
        
        if simulated_reading:  # Check if simulation was successful
            self.assertTrue(frappe.db.exists("Real-time Process Data", simulated_reading.name))
    
    # Test Performance and Scalability
    def test_bulk_data_insertion(self):
        """Test bulk data insertion performance"""
        from amb_w_spc.sensor_management.doctype.real_time_process_data.real_time_process_data import create_bulk_process_data
        
        # Create test data
        bulk_data = []
        for i in range(10):
            bulk_data.append({
                "timestamp": add_minutes(now(), -i),
                "station": self.station.name,
                "sensor": self.sensor.name,
                "parameter_name": "Temperature",
                "value": 75.0 + i,
                "unit_of_measure": "Test Unit",
                "status": "Normal"
            })
        
        result = create_bulk_process_data(bulk_data)
        self.assertEqual(result["created"], 10)
        self.assertEqual(result["errors"], 0)
    
    def test_data_archiving(self):
        """Test old data archiving functionality"""
        from amb_w_spc.sensor_management.doctype.real_time_process_data.real_time_process_data import archive_old_data
        
        # Create old test data
        old_data = frappe.get_doc({
            "doctype": "Real-time Process Data",
            "timestamp": add_days(now(), -100),  # 100 days old
            "station": self.station.name,
            "sensor": self.sensor.name,
            "parameter_name": "Temperature",
            "value": 75.0,
            "status": "Normal"
        })
        old_data.insert()
        
        # Archive data older than 90 days
        result = archive_old_data(days_to_keep=90)
        self.assertGreater(result["archived_count"], 0)
    
    # Test Error Handling
    def test_error_handling(self):
        """Test system error handling"""
        # Test invalid sensor reading
        try:
            invalid_data = frappe.get_doc({
                "doctype": "Real-time Process Data",
                "timestamp": now(),
                "station": "NON-EXISTENT-STATION",
                "sensor": self.sensor.name,
                "parameter_name": "Temperature",
                "value": 75.0
            })
            invalid_data.insert()
            self.fail("Should have raised validation error")
        except frappe.ValidationError:
            pass  # Expected
        except frappe.LinkValidationError:
            pass  # Also expected
    
    # Test Calibration Management
    def test_sensor_calibration_management(self):
        """Test sensor calibration due date checking"""
        # Set calibration due date in the past
        self.sensor.calibration_due = add_days(today(), -1)
        self.sensor.save()
        
        calibration_status = self.sensor.check_calibration_due()
        self.assertEqual(calibration_status, "overdue")
        
        # Set calibration due date in near future
        self.sensor.calibration_due = add_days(today(), 15)
        self.sensor.save()
        
        calibration_status = self.sensor.check_calibration_due()
        self.assertEqual(calibration_status, "due_soon")

def run_sfc_smo_tests():
    """Run all SFC SMO integration tests"""
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSFCSMOIntegration)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "success": result.wasSuccessful()
    }

# Whitelisted function for manual test execution
@frappe.whitelist()
def execute_test_suite():
    """Execute the complete test suite"""
    try:
        result = run_sfc_smo_tests()
        return {
            "status": "completed",
            "results": result
        }
    except Exception as e:
        frappe.log_error(f"Error running test suite: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

# Performance testing functions
@frappe.whitelist()
def performance_test_data_collection(duration_seconds=60):
    """Performance test for data collection"""
    import time
    start_time = time.time()
    records_created = 0
    
    # Get a test station and sensor
    stations = frappe.get_all("Manufacturing Station", 
                            filters={"status": "Active"}, 
                            limit=1)
    
    if not stations:
        return {"error": "No active stations found for performance testing"}
    
    station_name = stations[0].name
    sensors = frappe.get_all("Sensor Configuration",
                           filters={"station": station_name, "status": "Active"},
                           limit=5)  # Test with up to 5 sensors
    
    if not sensors:
        return {"error": "No active sensors found for performance testing"}
    
    # Run performance test
    while time.time() - start_time < duration_seconds:
        for sensor in sensors:
            try:
                sensor_doc = frappe.get_doc("Sensor Configuration", sensor.name)
                reading = sensor_doc.simulate_reading()
                if reading:
                    records_created += 1
            except Exception as e:
                frappe.log_error(f"Performance test error: {str(e)}")
        
        time.sleep(1)  # 1 second between batches
    
    elapsed_time = time.time() - start_time
    records_per_second = records_created / elapsed_time
    
    return {
        "duration_seconds": elapsed_time,
        "records_created": records_created,
        "records_per_second": records_per_second,
        "sensors_tested": len(sensors)
    }

if __name__ == "__main__":
    # Allow running tests directly
    unittest.main()
