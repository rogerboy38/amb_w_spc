import frappe
from frappe.model.document import Document

class PlcIntegration(Document):
    def validate(self):
        if not self.plc_name:
            frappe.throw("Field 'PLC Name' is required.")
        if not self.plc_type:
            frappe.throw("Field 'PLC Type' is required.")
        if self.plc_type and self.plc_type not in ['Siemens S7-1500', 'Siemens S7-1200', 'Siemens S7-300', 'Allen-Bradley MicroLogix 1500', 'Allen-Bradley CompactLogix', 'Allen-Bradley ControlLogix', 'Schneider Electric Modicon', 'Mitsubishi FX Series', 'Omron CP Series', 'GE Fanuc', 'Beckoff CX Series', 'Phoenix Contact AXC', 'Wago PFC200', 'B&R X20']:
            frappe.throw("Field 'PLC Type' must be one of ['Siemens S7-1500', 'Siemens S7-1200', 'Siemens S7-300', 'Allen-Bradley MicroLogix 1500', 'Allen-Bradley CompactLogix', 'Allen-Bradley ControlLogix', 'Schneider Electric Modicon', 'Mitsubishi FX Series', 'Omron CP Series', 'GE Fanuc', 'Beckoff CX Series', 'Phoenix Contact AXC', 'Wago PFC200', 'B&R X20'].")
        if not self.plant:
            frappe.throw("Field 'Plant' is required.")
        if not self.ip_address:
            frappe.throw("Field 'IP Address' is required.")
        if self.port is not None and not isinstance(self.port, int):
            frappe.throw("Field 'Port' must be an integer.")
        if self.rack_number is not None and not isinstance(self.rack_number, int):
            frappe.throw("Field 'Rack Number' must be an integer.")
        if self.slot_number is not None and not isinstance(self.slot_number, int):
            frappe.throw("Field 'Slot Number' must be an integer.")
        if not self.protocol:
            frappe.throw("Field 'Protocol' is required.")
        if self.protocol and self.protocol not in ['OPC-UA', 'Ethernet/IP', 'Modbus TCP', 'Modbus RTU', 'S7 Communication', 'Profinet', 'DeviceNet', 'Serial']:
            frappe.throw("Field 'Protocol' must be one of ['OPC-UA', 'Ethernet/IP', 'Modbus TCP', 'Modbus RTU', 'S7 Communication', 'Profinet', 'DeviceNet', 'Serial'].")
        if self.connection_timeout is not None and not isinstance(self.connection_timeout, int):
            frappe.throw("Field 'Connection Timeout (ms)' must be an integer.")
        if self.retry_attempts is not None and not isinstance(self.retry_attempts, int):
            frappe.throw("Field 'Retry Attempts' must be an integer.")
        if self.polling_rate is not None and not isinstance(self.polling_rate, int):
            frappe.throw("Field 'Polling Rate (ms)' must be an integer.")
        if self.max_concurrent_connections is not None and not isinstance(self.max_concurrent_connections, int):
            frappe.throw("Field 'Max Concurrent Connections' must be an integer.")
        if self.keepalive_interval is not None and not isinstance(self.keepalive_interval, int):
            frappe.throw("Field 'Keepalive Interval (ms)' must be an integer.")
        if self.authentication_method and self.authentication_method not in ['None', 'Username/Password', 'Certificate', 'Token Based', 'Kerberos', 'LDAP']:
            frappe.throw("Field 'Authentication Method' must be one of ['None', 'Username/Password', 'Certificate', 'Token Based', 'Kerberos', 'LDAP'].")
        if self.encryption_level and self.encryption_level not in ['None', 'Basic', 'SignAndEncrypt', 'Sign', 'SignAndEncrypt_256']:
            frappe.throw("Field 'Encryption Level' must be one of ['None', 'Basic', 'SignAndEncrypt', 'Sign', 'SignAndEncrypt_256'].")
        if self.connection_status and self.connection_status not in ['Connected', 'Disconnected', 'Connecting', 'Error', 'Timeout']:
            frappe.throw("Field 'Connection Status' must be one of ['Connected', 'Disconnected', 'Connecting', 'Error', 'Timeout'].")
        if self.error_count is not None and not isinstance(self.error_count, int):
            frappe.throw("Field 'Error Count' must be an integer.")
