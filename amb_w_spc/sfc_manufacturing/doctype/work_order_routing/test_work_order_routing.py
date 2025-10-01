# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import now_datetime

class TestWorkOrderRouting(unittest.TestCase):
    
    def setUp(self):
        """Set up test data"""
        self.work_order = self.create_test_work_order()
        self.routing = self.create_test_routing()
    
    def tearDown(self):
        """Clean up test data"""
        test_docs = [
            'Work Order Routing',
            'Work Order',
            'Item',
            'BOM'
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
        # Create test item first
        item_doc = frappe.get_doc({
            'doctype': 'Item',
            'item_code': 'TEST-ITEM-001',
            'item_name': 'Test Item 001',
            'item_group': 'All Item Groups',
            'stock_uom': 'Nos'
        })
        try:
            item_doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass
        
        # Create test work order
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
    
    def create_test_routing(self):
        """Create a test work order routing"""
        doc = frappe.get_doc({
            'doctype': 'Work Order Routing',
            'work_order': self.work_order,
            'item_code': 'TEST-ITEM-001',
            'qty': 100,
            'operations': [
                {
                    'operation': 'Cut',
                    'sequence': 1,
                    'setup_time': 0.5,
                    'operation_time': 2.0,
                    'workstation': 'Cutting Station'
                },
                {
                    'operation': 'Weld',
                    'sequence': 2,
                    'setup_time': 1.0,
                    'operation_time': 3.0,
                    'workstation': 'Welding Station'
                },
                {
                    'operation': 'Assembly',
                    'sequence': 3,
                    'setup_time': 0.5,
                    'operation_time': 2.5,
                    'workstation': 'Assembly Station'
                }
            ]
        })
        try:
            doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            doc = frappe.get_doc('Work Order Routing', 
                               {'work_order': self.work_order})
        return doc
    
    def test_create_routing(self):
        """Test creating a work order routing"""
        self.assertTrue(self.routing.name)
        self.assertEqual(len(self.routing.operations), 3)
        self.assertEqual(self.routing.total_estimated_time, 9.5)  # Sum of all times
    
    def test_sequence_validation(self):
        """Test operation sequence validation"""
        # Test duplicate sequence
        doc = frappe.get_doc({
            'doctype': 'Work Order Routing',
            'work_order': 'TEST-WO-002',
            'item_code': 'TEST-ITEM-001',
            'qty': 50,
            'operations': [
                {
                    'operation': 'Cut',
                    'sequence': 1,
                    'setup_time': 0.5,
                    'operation_time': 2.0
                },
                {
                    'operation': 'Weld',
                    'sequence': 1,  # Duplicate sequence
                    'setup_time': 1.0,
                    'operation_time': 3.0
                }
            ]
        })
        
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)
    
    def test_time_validation(self):
        """Test operation time validation"""
        # Test negative setup time
        doc = frappe.get_doc({
            'doctype': 'Work Order Routing',
            'work_order': 'TEST-WO-003',
            'item_code': 'TEST-ITEM-001',
            'qty': 50,
            'operations': [
                {
                    'operation': 'Cut',
                    'sequence': 1,
                    'setup_time': -0.5,  # Negative time
                    'operation_time': 2.0
                }
            ]
        })
        
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)
    
    def test_get_next_operation(self):
        """Test getting next operation in sequence"""
        # Get operation after sequence 1
        next_op = self.routing.get_next_operation(1)
        self.assertIsNotNone(next_op)
        self.assertEqual(next_op.sequence, 2)
        self.assertEqual(next_op.operation, 'Weld')
        
        # No operation after sequence 3 (last operation)
        no_next = self.routing.get_next_operation(3)
        self.assertIsNone(no_next)
    
    def test_get_operation_by_sequence(self):
        """Test getting operation by sequence number"""
        # Get first operation
        first_op = self.routing.get_operation_by_sequence(1)
        self.assertIsNotNone(first_op)
        self.assertEqual(first_op.operation, 'Cut')
        
        # Get non-existent operation
        no_op = self.routing.get_operation_by_sequence(99)
        self.assertIsNone(no_op)
    
    def test_start_operation(self):
        """Test starting an operation"""
        # Create test operator and workstation
        operator = self.create_test_operator()
        workstation = self.create_test_workstation()
        
        # Start first operation
        transaction_id = self.routing.start_operation(1, workstation, operator)
        self.assertTrue(transaction_id)
        
        # Verify transaction was created
        transaction = frappe.get_doc('SFC Transaction', transaction_id)
        self.assertEqual(transaction.transaction_type, 'Start')
        self.assertEqual(transaction.status, 'In Progress')
    
    def test_complete_operation(self):
        """Test completing an operation"""
        # Create test operator and workstation
        operator = self.create_test_operator()
        workstation = self.create_test_workstation()
        
        # Start operation first
        start_id = self.routing.start_operation(1, workstation, operator)
        
        # Complete operation
        quality_data = {'measurement': 10.5, 'pass_fail': 'Pass'}
        complete_id = self.routing.complete_operation(1, 2.2, quality_data)
        self.assertTrue(complete_id)
        
        # Verify completion transaction
        complete_doc = frappe.get_doc('SFC Transaction', complete_id)
        self.assertEqual(complete_doc.transaction_type, 'Complete')
        self.assertEqual(complete_doc.actual_time, 2.2)
    
    def test_total_time_calculation(self):
        """Test automatic total time calculation"""
        # Check calculated totals
        self.assertEqual(self.routing.total_setup_time, 2.0)    # 0.5 + 1.0 + 0.5
        self.assertEqual(self.routing.total_operation_time, 7.5) # 2.0 + 3.0 + 2.5
        self.assertEqual(self.routing.total_estimated_time, 9.5) # 2.0 + 7.5
    
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