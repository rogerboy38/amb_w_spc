import frappe
from frappe.model.document import Document

class PlantConfiguration(Document):
    def validate(self):
        if not self.plant_code:
            frappe.throw("Field 'Plant Code' is required.")
        if not self.plant_name:
            frappe.throw("Field 'Plant Name' is required.")
        if self.plant_name and self.plant_name not in ['Mix', 'Dry', 'Juice', 'Laboratory', 'Formulated']:
            frappe.throw("Field 'Plant Name' must be one of ['Mix', 'Dry', 'Juice', 'Laboratory', 'Formulated'].")
        if not self.plant_type:
            frappe.throw("Field 'Plant Type' is required.")
        if self.plant_type and self.plant_type not in ['Production', 'Quality Control', 'Research', 'Packaging', 'Storage']:
            frappe.throw("Field 'Plant Type' must be one of ['Production', 'Quality Control', 'Research', 'Packaging', 'Storage'].")
        if not self.location:
            frappe.throw("Field 'Location' is required.")
        if not self.company:
            frappe.throw("Field 'Company' is required.")
        if self.time_zone and self.time_zone not in ['UTC', 'EST', 'CST', 'MST', 'PST', 'GMT', 'CET', 'IST', 'JST', 'AEST']:
            frappe.throw("Field 'Time Zone' must be one of ['UTC', 'EST', 'CST', 'MST', 'PST', 'GMT', 'CET', 'IST', 'JST', 'AEST'].")
        if self.shift_schedule and self.shift_schedule not in ['Single Shift', 'Double Shift', 'Triple Shift', '24/7 Operations']:
            frappe.throw("Field 'Shift Schedule' must be one of ['Single Shift', 'Double Shift', 'Triple Shift', '24/7 Operations'].")
        if not self.plant_status:
            frappe.throw("Field 'Plant Status' is required.")
        if self.plant_status and self.plant_status not in ['Active', 'Inactive', 'Maintenance', 'Shutdown']:
            frappe.throw("Field 'Plant Status' must be one of ['Active', 'Inactive', 'Maintenance', 'Shutdown'].")
        if self.data_retention_policy and self.data_retention_policy not in ['30 Days', '90 Days', '6 Months', '1 Year', '2 Years', '5 Years', 'Permanent']:
            frappe.throw("Field 'Data Retention Policy' must be one of ['30 Days', '90 Days', '6 Months', '1 Year', '2 Years', '5 Years', 'Permanent'].")
        if self.backup_frequency and self.backup_frequency not in ['Hourly', 'Daily', 'Weekly', 'Monthly']:
            frappe.throw("Field 'Backup Frequency' must be one of ['Hourly', 'Daily', 'Weekly', 'Monthly'].")
        if self.sync_frequency and self.sync_frequency not in ['Real-time', 'Every 5 Minutes', 'Every 15 Minutes', 'Hourly', 'Daily']:
            frappe.throw("Field 'Sync Frequency' must be one of ['Real-time', 'Every 5 Minutes', 'Every 15 Minutes', 'Hourly', 'Daily'].")
