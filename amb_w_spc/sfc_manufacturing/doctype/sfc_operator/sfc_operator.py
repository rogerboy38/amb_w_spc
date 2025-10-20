# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, get_time

class SFCOperator(Document):
    def validate(self):
        """Validate the SFC operator"""
        self.validate_employee_link()
        self.validate_skill_levels()
        self.set_active_status()
    
    def validate_employee_link(self):
        """Validate employee exists and is active"""
        if self.employee:
            employee = frappe.get_doc('Employee', self.employee)
            if employee.status != 'Active':
                frappe.throw(f"Employee {self.employee} is not active")
            
            # Auto-populate fields from employee if not set
            if not self.operator_name:
                self.operator_name = employee.employee_name
            if not self.department:
                self.department = employee.department
    
    def validate_skill_levels(self):
        """Validate skill levels are within acceptable range"""
        for skill in self.skills:
            if skill.skill_level < 1 or skill.skill_level > 5:
                frappe.throw(f"Skill level for {skill.skill} must be between 1 and 5")
    
    def set_active_status(self):
        """Set default active status if not specified"""
        if self.is_active is None:
            self.is_active = 1
    
    def clock_in(self, workstation=None):
        """Clock in operator for shift"""
        if self.is_clocked_in():
            frappe.throw(f"Operator {self.operator_name} is already clocked in")
        
        # Create attendance record
        attendance_doc = frappe.get_doc({
            'doctype': 'SFC Operator Attendance',
            'operator': self.name,
            'clock_in_time': now_datetime(),
            'workstation': workstation,
            'status': 'Present'
        })
        attendance_doc.insert()
        
        return attendance_doc.name
    
    def clock_out(self):
        """Clock out operator from shift"""
        active_attendance = self.get_active_attendance()
        if not active_attendance:
            frappe.throw(f"No active attendance found for operator {self.operator_name}")
        
        # Update attendance record
        frappe.db.set_value('SFC Operator Attendance', active_attendance, {
            'clock_out_time': now_datetime(),
            'status': 'Completed'
        })
        
        return active_attendance
    
    def is_clocked_in(self):
        """Check if operator is currently clocked in"""
        return bool(self.get_active_attendance())
    
    def get_active_attendance(self):
        """Get active attendance record"""
        return frappe.get_value('SFC Operator Attendance', {
            'operator': self.name,
            'status': 'Present',
            'clock_out_time': ['is', 'not set']
        }, 'name')
    
    def get_skill_level(self, skill_name):
        """Get operator's skill level for a specific skill"""
        for skill in self.skills:
            if skill.skill == skill_name:
                return skill.skill_level
        return 0
    
    def can_perform_operation(self, operation_name, required_skill_level=1):
        """Check if operator can perform a specific operation"""
        if not self.is_active:
            return False
        
        # Get operation requirements
        operation_doc = frappe.get_doc('Operation', operation_name)
        required_skills = getattr(operation_doc, 'required_skills', [])
        
        if not required_skills:
            return True  # No specific skills required
        
        # Check if operator has required skills
        for req_skill in required_skills:
            operator_skill_level = self.get_skill_level(req_skill.skill)
            if operator_skill_level < req_skill.required_level:
                return False
        
        return True
    
    def get_current_workstation(self):
        """Get operator's current workstation"""
        active_attendance = self.get_active_attendance()
        if active_attendance:
            return frappe.get_value('SFC Operator Attendance', active_attendance, 'workstation')
        return None
    
    def get_daily_hours(self, date=None):
        """Get total hours worked for a specific date"""
        if not date:
            date = frappe.utils.today()
        
        attendances = frappe.get_all('SFC Operator Attendance', {
            'operator': self.name,
            'creation': ['like', f"{date}%"],
            'status': 'Completed'
        }, ['clock_in_time', 'clock_out_time'])
        
        total_hours = 0
        for att in attendances:
            if att.clock_in_time and att.clock_out_time:
                duration = att.clock_out_time - att.clock_in_time
                total_hours += duration.total_seconds() / 3600
        
        return total_hours