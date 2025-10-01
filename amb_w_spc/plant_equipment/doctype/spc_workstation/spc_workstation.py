import frappe
from frappe.model.document import Document

class SPCWorkstation(Document):
    def validate(self):
        if not self.workstation_code:
            frappe.throw("Field 'Workstation Code' is required.")
        if not self.workstation_name:
            frappe.throw("Field 'Workstation Name' is required.")
        if not self.plant:
            frappe.throw("Field 'Plant' is required.")
        if not self.department:
            frappe.throw("Field 'Department' is required.")
        if self.department and self.department not in ['Production', 'Quality Control', 'Maintenance', 'Packaging', 'Storage', 'Laboratory', 'Utilities']:
            frappe.throw("Field 'Department' must be one of ['Production', 'Quality Control', 'Maintenance', 'Packaging', 'Storage', 'Laboratory', 'Utilities'].")
        if not self.equipment_type:
            frappe.throw("Field 'Equipment Type' is required.")
        if self.equipment_type and self.equipment_type not in ['Mixer', 'Dryer', 'Extruder', 'Centrifuge', 'Analyzer', 'Scale', 'Sensor', 'Pump', 'Compressor', 'Heat Exchanger', 'Reactor', 'Separator']:
            frappe.throw("Field 'Equipment Type' must be one of ['Mixer', 'Dryer', 'Extruder', 'Centrifuge', 'Analyzer', 'Scale', 'Sensor', 'Pump', 'Compressor', 'Heat Exchanger', 'Reactor', 'Separator'].")
        if not self.workstation_status:
            frappe.throw("Field 'Workstation Status' is required.")
        if self.workstation_status and self.workstation_status not in ['Operational', 'Maintenance', 'Calibration', 'Out of Service', 'Standby']:
            frappe.throw("Field 'Workstation Status' must be one of ['Operational', 'Maintenance', 'Calibration', 'Out of Service', 'Standby'].")
        if self.communication_protocol and self.communication_protocol not in ['OPC-UA', 'Ethernet/IP', 'Modbus TCP', 'Modbus RTU', 'Profinet', 'DeviceNet', 'Serial']:
            frappe.throw("Field 'Communication Protocol' must be one of ['OPC-UA', 'Ethernet/IP', 'Modbus TCP', 'Modbus RTU', 'Profinet', 'DeviceNet', 'Serial'].")
        if self.data_collection_frequency and self.data_collection_frequency not in ['Continuous', 'Every Second', 'Every 5 Seconds', 'Every 10 Seconds', 'Every 30 Seconds', 'Every Minute', 'Every 5 Minutes', 'Every 15 Minutes', 'Every Hour']:
            frappe.throw("Field 'Data Collection Frequency' must be one of ['Continuous', 'Every Second', 'Every 5 Seconds', 'Every 10 Seconds', 'Every 30 Seconds', 'Every Minute', 'Every 5 Minutes', 'Every 15 Minutes', 'Every Hour'].")
        if self.sensor_type and self.sensor_type not in ['Temperature', 'Pressure', 'Flow', 'Level', 'Vibration', 'PH', 'Conductivity', 'Turbidity', 'Weight', 'Speed', 'Torque', 'Voltage', 'Current']:
            frappe.throw("Field 'Sensor Type' must be one of ['Temperature', 'Pressure', 'Flow', 'Level', 'Vibration', 'PH', 'Conductivity', 'Turbidity', 'Weight', 'Speed', 'Torque', 'Voltage', 'Current'].")
        if self.calibration_interval and self.calibration_interval not in ['Weekly', 'Monthly', 'Quarterly', 'Semi-Annual', 'Annual', 'Bi-Annual']:
            frappe.throw("Field 'Calibration Interval' must be one of ['Weekly', 'Monthly', 'Quarterly', 'Semi-Annual', 'Annual', 'Bi-Annual'].")
        if self.operational_status and self.operational_status not in ['Online', 'Offline', 'Error', 'Warning', 'Maintenance', 'Calibrating']:
            frappe.throw("Field 'Operational Status' must be one of ['Online', 'Offline', 'Error', 'Warning', 'Maintenance', 'Calibrating'].")
        if self.maintenance_schedule and self.maintenance_schedule not in ['Daily', 'Weekly', 'Monthly', 'Quarterly', 'Semi-Annual', 'Annual', 'Condition-Based']:
            frappe.throw("Field 'Maintenance Schedule' must be one of ['Daily', 'Weekly', 'Monthly', 'Quarterly', 'Semi-Annual', 'Annual', 'Condition-Based'].")
