# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import now_datetime, add_days

class TestSFCTransaction(unittest.TestCase):
    
    def setUp(self):
        """Set up test data"""
        self.work_order = self.create_test_work_order()
        self.workstation = self.create_test_workstation()
        self.operator = self.create_test_operator()
    
    def tearDown(self):
        """Clean up test data"""
        # Delete test records
        test_docs = [
            'SFC Transaction',
            'SFC Operator',
            'Workstation',
            'Work Order'
        ]
        
        for doctype in test_docs:
            records = frappe.get_all(doctype, {'name': ['like', 'TEST-%']})
            for record in records:
                try:
                    frappe.delete_doc(doctype, record.name, force=True)
                except:
                    pass
    
    def create_test_work_order(self):
        """Create a test work order"""
        doc = frappe.get_doc({
            'doctype': 'Work Order',
            'name': 'TEST-WO-001',
            'production_item': 'TEST-ITEM-001',
            'qty': 100,
            'company': 'Test Company'
        })
        try:
            doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass
        return doc.name
    
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
    
    def create_test_operator(self):
        """Create a test operator"""
        doc = frappe.get_doc({
            'doctype': 'SFC Operator',
            'name': 'TEST-OP-001',
            'operator_name': 'Test Operator 001',
            'is_active': 1
        })
        try:
            doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass
        return doc.name
    
    def test_create_sfc_transaction(self):
        """Test creating an SFC transaction"""
        doc = frappe.get_doc({
            'doctype': 'SFC Transaction',
            'work_order': self.work_order,
            'operation': 'TEST-OP-001',
            'operation_sequence': 1,
            'workstation': self.workstation,
            'operator': self.operator,
            'transaction_type': 'Start',
            'timestamp': now_datetime(),
            'status': 'In Progress'
        })
        
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)
        self.assertEqual(doc.transaction_type, 'Start')
        self.assertEqual(doc.status, 'In Progress')
    
    def test_complete_operation_workflow(self):
        """Test complete start-to-finish operation workflow"""
        # Create start transaction
        start_doc = frappe.get_doc({
            'doctype': 'SFC Transaction',
            'work_order': self.work_order,
            'operation': 'TEST-OP-001',
            'operation_sequence': 1,
            'workstation': self.workstation,
            'operator': self.operator,
            'transaction_type': 'Start',
            'timestamp': now_datetime(),
            'status': 'In Progress'
        })
        start_doc.insert(ignore_permissions=True)
        
        # Create complete transaction
        complete_doc = frappe.get_doc({
            'doctype': 'SFC Transaction',
            'work_order': self.work_order,
            'operation': 'TEST-OP-001',
            'operation_sequence': 1,
            'workstation': self.workstation,
            'operator': self.operator,
            'transaction_type': 'Complete',
            'timestamp': now_datetime(),
            'status': 'Completed',
            'actual_time': 2.5
        })
        complete_doc.insert(ignore_permissions=True)
        
        # Verify both transactions exist
        self.assertTrue(start_doc.name)
        self.assertTrue(complete_doc.name)
        self.assertEqual(complete_doc.actual_time, 2.5)
    
    def test_calculate_operation_duration(self):
        """Test operation duration calculation"""
        start_time = now_datetime()
        end_time = frappe.utils.add_to_date(start_time, hours=2, minutes=30)
        
        # Create start transaction
        start_doc = frappe.get_doc({
            'doctype': 'SFC Transaction',
            'work_order': self.work_order,
            'operation': 'TEST-OP-001',
            'operation_sequence': 1,
            'workstation': self.workstation,
            'operator': self.operator,
            'transaction_type': 'Start',
            'timestamp': start_time,
            'status': 'In Progress'
        })
        start_doc.insert(ignore_permissions=True)
        
        # Create complete transaction
        complete_doc = frappe.get_doc({
            'doctype': 'SFC Transaction',
            'work_order': self.work_order,
            'operation': 'TEST-OP-001',
            'operation_sequence': 1,
            'workstation': self.workstation,
            'operator': self.operator,
            'transaction_type': 'Complete',
            'timestamp': end_time,
            'status': 'Completed'
        })
        complete_doc.insert(ignore_permissions=True)
        
        # Test duration calculation method
        duration = complete_doc.calculate_operation_duration(start_doc.name)
        self.assertEqual(duration, 2.5)  # 2.5 hours
    
    def test_invalid_transaction_type(self):
        """Test validation of transaction type"""
        doc = frappe.get_doc({
            'doctype': 'SFC Transaction',
            'work_order': self.work_order,
            'operation': 'TEST-OP-001',
            'operation_sequence': 1,
            'workstation': self.workstation,
            'operator': self.operator,
            'transaction_type': 'Invalid',
            'timestamp': now_datetime(),
            'status': 'In Progress'
        })
        
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)
    
    def test_quality_data_integration(self):
        """Test integration with quality data"""
        quality_data = {
            'measurement_1': 10.5,
            'measurement_2': 15.2,
            'pass_fail': 'Pass',
            'inspector': 'Test Inspector'
        }
        
        doc = frappe.get_doc({
            'doctype': 'SFC Transaction',
            'work_order': self.work_order,
            'operation': 'TEST-OP-001',
            'operation_sequence': 1,
            'workstation': self.workstation,
            'operator': self.operator,
            'transaction_type': 'Complete',
            'timestamp': now_datetime(),
            'status': 'Completed',
            'quality_data': frappe.as_json(quality_data)
        })
        
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.quality_data)
        
        # Verify quality data is properly stored
        retrieved_data = frappe.parse_json(doc.quality_data)
        self.assertEqual(retrieved_data['pass_fail'], 'Pass')
        self.assertEqual(retrieved_data['measurement_1'], 10.5)