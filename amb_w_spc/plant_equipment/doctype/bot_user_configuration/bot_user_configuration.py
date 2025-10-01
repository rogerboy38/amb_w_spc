import frappe
from frappe.model.document import Document

class BotUserConfiguration(Document):
    def validate(self):
        if not self.bot_name:
            frappe.throw("Field 'Bot Name' is required.")
        if not self.bot_type:
            frappe.throw("Field 'Bot Type' is required.")
        if self.bot_type and self.bot_type not in ['Data Collection Bot', 'Monitoring Bot', 'Analysis Bot', 'Alert Bot', 'Maintenance Bot', 'Quality Control Bot', 'Reporting Bot', 'Integration Bot']:
            frappe.throw("Field 'Bot Type' must be one of ['Data Collection Bot', 'Monitoring Bot', 'Analysis Bot', 'Alert Bot', 'Maintenance Bot', 'Quality Control Bot', 'Reporting Bot', 'Integration Bot'].")
        if not self.plant:
            frappe.throw("Field 'Plant' is required.")
        if not self.user_account:
            frappe.throw("Field 'User Account' is required.")
        if not self.bot_status:
            frappe.throw("Field 'Bot Status' is required.")
        if self.bot_status and self.bot_status not in ['Active', 'Inactive', 'Paused', 'Error', 'Maintenance']:
            frappe.throw("Field 'Bot Status' must be one of ['Active', 'Inactive', 'Paused', 'Error', 'Maintenance'].")
        if self.priority and self.priority not in ['Low', 'Medium', 'High', 'Critical']:
            frappe.throw("Field 'Priority' must be one of ['Low', 'Medium', 'High', 'Critical'].")
        if self.collection_frequency and self.collection_frequency not in ['Real-time', 'Every 5 Seconds', 'Every 10 Seconds', 'Every 30 Seconds', 'Every Minute', 'Every 5 Minutes', 'Every 15 Minutes', 'Every 30 Minutes', 'Hourly', 'Daily']:
            frappe.throw("Field 'Collection Frequency' must be one of ['Real-time', 'Every 5 Seconds', 'Every 10 Seconds', 'Every 30 Seconds', 'Every Minute', 'Every 5 Minutes', 'Every 15 Minutes', 'Every 30 Minutes', 'Hourly', 'Daily'].")
        if not self.data_source:
            frappe.throw("Field 'Data Source' is required.")
        if self.data_source and self.data_source not in ['PLC', 'SCADA', 'API', 'Database', 'File System', 'Sensor Network', 'Web Service', 'Manual Entry']:
            frappe.throw("Field 'Data Source' must be one of ['PLC', 'SCADA', 'API', 'Database', 'File System', 'Sensor Network', 'Web Service', 'Manual Entry'].")
        if self.collection_method and self.collection_method not in ['Pull', 'Push', 'Subscription', 'Polling', 'Event-Driven']:
            frappe.throw("Field 'Collection Method' must be one of ['Pull', 'Push', 'Subscription', 'Polling', 'Event-Driven'].")
        if self.batch_size is not None and not isinstance(self.batch_size, int):
            frappe.throw("Field 'Batch Size' must be an integer.")
        if self.buffer_size is not None and not isinstance(self.buffer_size, int):
            frappe.throw("Field 'Buffer Size' must be an integer.")
        if self.access_level and self.access_level not in ['Read Only', 'Read/Write', 'Admin', 'Restricted', 'Full Access']:
            frappe.throw("Field 'Access Level' must be one of ['Read Only', 'Read/Write', 'Admin', 'Restricted', 'Full Access'].")
        if self.collection_count is not None and not isinstance(self.collection_count, int):
            frappe.throw("Field 'Collection Count' must be an integer.")
        if self.error_count is not None and not isinstance(self.error_count, int):
            frappe.throw("Field 'Error Count' must be an integer.")
        if self.average_response_time is not None and not isinstance(self.average_response_time, float):
            frappe.throw("Field 'Average Response Time (ms)' must be a float.")
