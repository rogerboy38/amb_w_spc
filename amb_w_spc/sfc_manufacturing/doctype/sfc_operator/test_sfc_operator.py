# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import now_datetime, today

class TestSFCOperator(unittest.TestCase):
    
    def setUp(self):
        """Set up test data"""
        self.create_test_employee()
        self.operator = self.create_test_operator()
        self.workstation = self.create_test_workstation()
    
    def tearDown(self):
        """Clean up test data"""
        test_docs = [
            'SFC Operator Attendance',
            'SFC Operator',
            'Employee',
            'Workstation'
        ]
        
        for doctype in test_docs:
            records = frappe.get_all(doctype, {'name': ['like', 'TEST-%']})
            for record in records:
                try:
                    frappe.delete_doc(doctype, record.name, force=True)
                except:
                    pass
    
    def create_test_employee(self):
        """Create a test employee"""
        doc = frappe.get_doc({
            'doctype': 'Employee',
            'name': 'TEST-EMP-001',
            'employee_name': 'Test Employee 001',
            'status': 'Active',
            'company': 'Test Company'
        })
        try:
            doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass
        return doc.name
    
    def create_test_operator(self):
        """Create a test operator"""
        doc = frappe.get_doc({
            'doctype': 'SFC Operator',
            'name': 'TEST-OP-001',
            'operator_name': 'Test Operator 001',
            'employee': 'TEST-EMP-001',
            'is_active': 1,
            'skills': [
                {
                    'skill': 'Welding',
                    'skill_level': 4
                },
                {
                    'skill': 'Assembly',
                    'skill_level': 3
                }
            ]
        })
        try:
            doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            doc = frappe.get_doc('SFC Operator', 'TEST-OP-001')
        return doc
    
    def create_test_workstation(self):
        """Create a test workstation"""
        doc = frappe.get_doc({
            'doctype': 'Workstation',
            'name': 'TEST-WS-001',
            'workstation_name': 'Test Workstation 001',
            'hour_rate': 100
        })
        try:
            doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass
        return doc.name
    
    def test_create_operator(self):
        """Test creating an SFC operator"""
        self.assertTrue(self.operator.name)
        self.assertEqual(self.operator.operator_name, 'Test Operator 001')
        self.assertEqual(self.operator.is_active, 1)
    
    def test_skill_validation(self):
        """Test skill level validation"""
        # Test invalid skill level
        doc = frappe.get_doc({
            'doctype': 'SFC Operator',
            'operator_name': 'Test Invalid Operator',
            'is_active': 1,
            'skills': [
                {
                    'skill': 'Welding',
                    'skill_level': 6  # Invalid - should be 1-5
                }
            ]
        })
        
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)
    
    def test_clock_in_out(self):
        """Test clock in/out functionality"""
        # Test clock in
        attendance_id = self.operator.clock_in(self.workstation)
        self.assertTrue(attendance_id)
        self.assertTrue(self.operator.is_clocked_in())
        
        # Test clock out
        self.operator.clock_out()
        self.assertFalse(self.operator.is_clocked_in())
    
    def test_double_clock_in(self):
        """Test that double clock in raises error"""
        # First clock in should work
        self.operator.clock_in(self.workstation)
        
        # Second clock in should fail
        with self.assertRaises(frappe.ValidationError):
            self.operator.clock_in(self.workstation)
    
    def test_get_skill_level(self):
        """Test getting operator skill level"""
        welding_level = self.operator.get_skill_level('Welding')
        self.assertEqual(welding_level, 4)
        
        assembly_level = self.operator.get_skill_level('Assembly')
        self.assertEqual(assembly_level, 3)
        
        # Non-existent skill should return 0
        unknown_level = self.operator.get_skill_level('Unknown Skill')
        self.assertEqual(unknown_level, 0)
    
    def test_can_perform_operation(self):
        """Test operation capability check"""
        # Operator should be able to perform operation requiring Welding level 3
        self.assertTrue(self.operator.can_perform_operation('Test Operation', 3))
        
        # Operator should not be able to perform operation requiring Welding level 5
        # (operator only has level 4 in our test data)
        # This test would need a proper Operation doctype setup
    
    def test_get_current_workstation(self):
        """Test getting current workstation"""
        # Initially no workstation
        self.assertIsNone(self.operator.get_current_workstation())
        
        # After clock in, should return workstation
        self.operator.clock_in(self.workstation)
        current_ws = self.operator.get_current_workstation()
        self.assertEqual(current_ws, self.workstation)
        
        # After clock out, should return None again
        self.operator.clock_out()
        self.assertIsNone(self.operator.get_current_workstation())
    
    def test_daily_hours_calculation(self):
        """Test daily hours calculation"""
        # Clock in and out multiple times in a day
        self.operator.clock_in(self.workstation)
        
        # Simulate 4 hours of work
        attendance = frappe.get_doc('SFC Operator Attendance', 
                                  self.operator.get_active_attendance())
        attendance.clock_out_time = frappe.utils.add_to_date(
            attendance.clock_in_time, hours=4)
        attendance.status = 'Completed'
        attendance.save()
        
        # Check daily hours
        daily_hours = self.operator.get_daily_hours(today())
        self.assertEqual(daily_hours, 4.0)
    
    def test_employee_auto_population(self):
        """Test auto-population of fields from employee"""
        # Create new operator with employee link
        new_operator = frappe.get_doc({
            'doctype': 'SFC Operator',
            'employee': 'TEST-EMP-001',
            'is_active': 1
        })
        new_operator.validate()
        
        # Check if operator name is auto-populated
        self.assertEqual(new_operator.operator_name, 'Test Employee 001')