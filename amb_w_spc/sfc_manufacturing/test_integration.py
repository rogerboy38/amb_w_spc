# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import now_datetime, add_days
import json

class TestSFCIntegration(unittest.TestCase):
    """Integration tests for SFC and SPC modules"""
    
    def setUp(self):
        """Set up test data for integration testing"""
        self.work_order = self.create_test_work_order()
        self.routing = self.create_test_routing()
        self.operator = self.create_test_operator()
        self.workstation = self.create_test_workstation()
    
    def tearDown(self):
        """Clean up test data"""
        test_docs = [
            'SPC Data Point',
            'Quality Inspection',
            'SFC Transaction',
            'SFC Operator Attendance',
            'Work Order Routing',
            'SFC Operator',
            'Work Order',
            'Item',
            'Workstation'
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
        # Create test item
        item_doc = frappe.get_doc({
            'doctype': 'Item',
            'item_code': 'TEST-ITEM-INT-001',
            'item_name': 'Test Integration Item 001',
            'item_group': 'All Item Groups',
            'stock_uom': 'Nos'
        })
        try:
            item_doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass
        
        # Create work order
        doc = frappe.get_doc({
            'doctype': 'Work Order',
            'name': 'TEST-WO-INT-001',
            'production_item': 'TEST-ITEM-INT-001',
            'qty': 50,
            'company': 'Test Company'
        })
        try:
            doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass
        return doc.name
    
    def create_test_routing(self):
        """Create a test routing with multiple operations"""
        doc = frappe.get_doc({
            'doctype': 'Work Order Routing',
            'work_order': self.work_order,
            'item_code': 'TEST-ITEM-INT-001',
            'qty': 50,
            'operations': [
                {
                    'operation': 'Machining',
                    'sequence': 1,
                    'setup_time': 0.5,
                    'operation_time': 1.5,
                    'workstation': 'TEST-WS-INT-001'
                },
                {
                    'operation': 'Quality Check',
                    'sequence': 2,
                    'setup_time': 0.25,
                    'operation_time': 0.5,
                    'workstation': 'TEST-WS-INT-001'
                }
            ]
        })
        try:
            doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            doc = frappe.get_doc('Work Order Routing', 
                               {'work_order': self.work_order})
        return doc
    
    def create_test_operator(self):
        """Create a test operator"""
        doc = frappe.get_doc({
            'doctype': 'SFC Operator',
            'name': 'TEST-OP-INT-001',
            'operator_name': 'Test Integration Operator 001',
            'is_active': 1
        })
        try:
            doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            doc = frappe.get_doc('SFC Operator', 'TEST-OP-INT-001')
        return doc
    
    def create_test_workstation(self):
        """Create a test workstation"""
        doc = frappe.get_doc({
            'doctype': 'Workstation',
            'name': 'TEST-WS-INT-001',
            'workstation_name': 'Test Integration Workstation 001',
            'hour_rate': 150
        })
        try:
            doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass
        return doc.name
    
    def test_complete_sfc_spc_workflow(self):
        """Test complete workflow from SFC operations to SPC analysis"""
        # Step 1: Clock in operator
        self.operator.clock_in(self.workstation)
        self.assertTrue(self.operator.is_clocked_in())
        
        # Step 2: Start first operation
        transaction_1 = self.routing.start_operation(1, self.workstation, self.operator.name)
        self.assertTrue(transaction_1)
        
        # Step 3: Complete first operation with quality data
        quality_data_1 = {
            'dimension_x': 10.2,
            'dimension_y': 15.8,
            'surface_finish': 'Good',
            'pass_fail': 'Pass'
        }
        complete_1 = self.routing.complete_operation(1, 1.8, quality_data_1)
        self.assertTrue(complete_1)
        
        # Step 4: Start second operation
        transaction_2 = self.routing.start_operation(2, self.workstation, self.operator.name)
        self.assertTrue(transaction_2)
        
        # Step 5: Complete second operation with quality data
        quality_data_2 = {
            'dimension_x': 10.1,
            'dimension_y': 15.9,
            'overall_quality': 'Excellent',
            'pass_fail': 'Pass'
        }
        complete_2 = self.routing.complete_operation(2, 0.6, quality_data_2)
        self.assertTrue(complete_2)
        
        # Step 6: Verify SFC transactions were created
        transactions = frappe.get_all('SFC Transaction', {
            'work_order': self.work_order
        })
        self.assertEqual(len(transactions), 4)  # 2 start + 2 complete
        
        # Step 7: Verify quality data integration via API
        from amb_w_spc.amb_w_spc.api.quality_integration import record_quality_measurement
        
        # Record additional quality measurement
        result = record_quality_measurement(
            work_order=self.work_order,
            operation_sequence=1,
            measurements={'hardness': 45.5, 'tolerance': 0.02},
            inspector='Test Inspector'
        )
        self.assertEqual(result['status'], 'success')
        
        # Step 8: Get SPC analysis
        from amb_w_spc.amb_w_spc.api.quality_integration import get_spc_analysis
        
        spc_result = get_spc_analysis(work_order=self.work_order)
        self.assertEqual(spc_result['status'], 'success')
        
        # Step 9: Generate quality report
        from amb_w_spc.amb_w_spc.api.quality_integration import generate_quality_report
        
        report_result = generate_quality_report(work_order=self.work_order)
        self.assertEqual(report_result['status'], 'success')
        self.assertTrue(len(report_result['quality_data']) > 0)
        
        # Step 10: Clock out operator
        self.operator.clock_out()
        self.assertFalse(self.operator.is_clocked_in())
    
    def test_sfc_api_integration(self):
        """Test SFC API functions"""
        from amb_w_spc.amb_w_spc.api.sfc_operations import (
            clock_in_operator, start_operation, complete_operation, 
            get_work_order_status, get_production_summary
        )
        
        # Test clock in via API
        clock_in_result = clock_in_operator(self.operator.name, self.workstation)
        self.assertEqual(clock_in_result['status'], 'success')
        
        # Test start operation via API
        start_result = start_operation(
            work_order=self.work_order,
            operation_sequence=1,
            workstation=self.workstation,
            operator=self.operator.name
        )
        self.assertEqual(start_result['status'], 'success')
        
        # Test complete operation via API
        complete_result = complete_operation(
            work_order=self.work_order,
            operation_sequence=1,
            actual_time=2.0,
            quality_data=json.dumps({'test_param': 25.5})
        )
        self.assertEqual(complete_result['status'], 'success')
        
        # Test work order status via API
        status_result = get_work_order_status(self.work_order)
        self.assertEqual(status_result['status'], 'success')
        self.assertTrue('operations' in status_result)
        
        # Test production summary via API
        summary_result = get_production_summary()
        self.assertEqual(summary_result['status'], 'success')
    
    def test_data_consistency(self):
        """Test data consistency between SFC and SPC modules"""
        # Create SFC transaction with quality data
        transaction_doc = frappe.get_doc({
            'doctype': 'SFC Transaction',
            'work_order': self.work_order,
            'operation': 'Test Operation',
            'operation_sequence': 1,
            'workstation': self.workstation,
            'operator': self.operator.name,
            'transaction_type': 'Complete',
            'timestamp': now_datetime(),
            'status': 'Completed',
            'actual_time': 1.5,
            'quality_data': json.dumps({
                'measurement_1': 10.5,
                'measurement_2': 20.8,
                'pass_fail': 'Pass'
            })
        })
        transaction_doc.insert(ignore_permissions=True)
        
        # Record quality measurement using API
        from amb_w_spc.amb_w_spc.api.quality_integration import record_quality_measurement
        
        result = record_quality_measurement(
            work_order=self.work_order,
            operation_sequence=1,
            measurements={
                'measurement_1': 10.5,
                'measurement_2': 20.8
            }
        )
        
        self.assertEqual(result['status'], 'success')
        
        # Verify SPC data points were created
        spc_points = frappe.get_all('SPC Data Point', {
            'work_order': self.work_order,
            'operation': 1
        })
        
        self.assertTrue(len(spc_points) >= 2)  # At least 2 parameters
        
        # Verify data values match
        for point_name in spc_points:
            point = frappe.get_doc('SPC Data Point', point_name.name)
            if point.parameter == 'measurement_1':
                self.assertEqual(point.measurement_value, 10.5)
            elif point.parameter == 'measurement_2':
                self.assertEqual(point.measurement_value, 20.8)
    
    def test_error_handling(self):
        """Test error handling in integrated workflows"""
        from amb_w_spc.amb_w_spc.api.sfc_operations import start_operation
        
        # Test starting operation without clocking in
        result = start_operation(
            work_order=self.work_order,
            operation_sequence=1,
            workstation=self.workstation,
            operator=self.operator.name
        )
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('not clocked in', result['message'])
        
        # Test starting non-existent operation
        self.operator.clock_in(self.workstation)
        
        result = start_operation(
            work_order=self.work_order,
            operation_sequence=99,  # Non-existent
            workstation=self.workstation,
            operator=self.operator.name
        )
        
        self.assertEqual(result['status'], 'error')
    
    def test_performance_metrics(self):
        """Test performance metrics calculation"""
        # Clock in operator
        self.operator.clock_in(self.workstation)
        
        # Simulate multiple operations
        for i in range(1, 3):  # Operations 1 and 2
            # Start operation
            self.routing.start_operation(i, self.workstation, self.operator.name)
            
            # Complete operation with varying times
            actual_time = 1.0 + (i * 0.5)  # 1.5, 2.0 hours
            quality_data = {'test_measurement': 10.0 + i}
            
            self.routing.complete_operation(i, actual_time, quality_data)
        
        # Get operator workload
        from amb_w_spc.amb_w_spc.api.sfc_operations import get_operator_workload
        
        workload = get_operator_workload(self.operator.name)
        self.assertEqual(workload['status'], 'success')
        self.assertEqual(workload['completed_operations_today'], 2)
        self.assertEqual(workload['total_time_today'], 3.5)  # 1.5 + 2.0
        
        # Clock out
        self.operator.clock_out()