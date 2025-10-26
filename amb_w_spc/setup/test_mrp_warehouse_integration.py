#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for MRP Planning Warehouse Integration

This script tests the integration between MRP Planning and Warehouse Management
including Work Order creation, zone status tracking, SAP movement types,
and Material Assessment Logs.
"""

import frappe
import json
from datetime import datetime, timedelta
from frappe.utils import now_datetime, today, add_days

def test_mrp_warehouse_integration():
    """
    Comprehensive test for MRP Planning Warehouse Integration
    """
    print("\n=== MRP Planning Warehouse Integration Test ===")
    
    try:
        # Test 1: Create test data
        print("\n1. Creating test data...")
        test_data = create_test_data()
        
        # Test 2: Create and submit MRP Planning
        print("\n2. Testing MRP Planning creation...")
        mrp_planning = create_test_mrp_planning(test_data)
        
        # Test 3: Verify Work Order creation with warehouse fields
        print("\n3. Testing Work Order warehouse integration...")
        work_orders = test_work_order_creation(mrp_planning)
        
        # Test 4: Test Material Assessment Log creation
        print("\n4. Testing Material Assessment Log...")
        assessments = test_material_assessment_logs(work_orders)
        
        # Test 5: Test warehouse zone status updates
        print("\n5. Testing zone status updates...")
        test_zone_status_updates(work_orders)
        
        # Test 6: Test warehouse zones mapping
        print("\n6. Testing warehouse zones mapping...")
        test_warehouse_zones_mapping()
        
        # Test 7: Test API endpoints
        print("\n7. Testing API endpoints...")
        test_api_endpoints(mrp_planning, work_orders)
        
        # Test 8: Test integration with existing systems
        print("\n8. Testing system integrations...")
        test_system_integrations(work_orders)
        
        print("\n=== All tests completed successfully! ===")
        return True
        
    except Exception as e:
        print(f"\nTest failed with error: {str(e)}")
        frappe.log_error(f"MRP Warehouse Integration Test Failed: {str(e)}")
        return False
    
    finally:
        # Cleanup test data
        print("\n9. Cleaning up test data...")
        cleanup_test_data()

def create_test_data():
    """
    Create test data including items, BOMs, warehouses, etc.
    """
    test_data = {
        'company': 'Test Company',
        'items': [],
        'warehouses': [],
        'boms': [],
        'sales_order': None
    }
    
    # Create test company if it doesn't exist
    if not frappe.db.exists('Company', test_data['company']):
        company = frappe.get_doc({
            'doctype': 'Company',
            'company_name': test_data['company'],
            'country': 'United States',
            'default_currency': 'USD'
        })
        company.insert(ignore_permissions=True)
        print(f"Created test company: {test_data['company']}")
    
    # Create test items
    item_codes = [
        'M033-TEST-FG',  # Finished good - juice plant
        '0227-TEST-INT', # Intermediate - dry plant
        '0303-TEST-POW', # Powder - dry plant
        '0334-TEST-MIX', # Mix - mix plant
        'RM-TEST-001',   # Raw material
        'RM-TEST-002'    # Raw material
    ]
    
    for item_code in item_codes:
        if not frappe.db.exists('Item', item_code):
            item = frappe.get_doc({
                'doctype': 'Item',
                'item_code': item_code,
                'item_name': f'Test Item {item_code}',
                'stock_uom': 'Kg',
                'is_stock_item': 1,
                'is_sales_item': 1 if 'FG' in item_code else 0,
                'is_purchase_item': 1 if 'RM' in item_code else 0
            })
            item.insert(ignore_permissions=True)
            test_data['items'].append(item_code)
            print(f"Created test item: {item_code}")
    
    # Create test warehouses
    warehouse_names = [
        'Juice RM Warehouse - TC',
        'Juice WIP Warehouse - TC',
        'Juice FG Warehouse - TC',
        'Dry RM Warehouse - TC',
        'Dry WIP Warehouse - TC',
        'Dry FG Warehouse - TC',
        'Mix RM Warehouse - TC',
        'Mix WIP Warehouse - TC',
        'Mix FG Warehouse - TC'
    ]
    
    for warehouse_name in warehouse_names:
        if not frappe.db.exists('Warehouse', warehouse_name):
            warehouse = frappe.get_doc({
                'doctype': 'Warehouse',
                'warehouse_name': warehouse_name,
                'company': test_data['company'],
                'warehouse_type': determine_warehouse_type(warehouse_name)
            })
            warehouse.insert(ignore_permissions=True)
            test_data['warehouses'].append(warehouse_name)
            print(f"Created test warehouse: {warehouse_name}")
    
    # Create test BOMs
    create_test_boms(test_data)
    
    # Create test sales order
    create_test_sales_order(test_data)
    
    return test_data

def determine_warehouse_type(warehouse_name):
    """Determine warehouse type from name"""
    if 'RM' in warehouse_name:
        return 'Raw Material'
    elif 'WIP' in warehouse_name:
        return 'Work In Progress'
    elif 'FG' in warehouse_name:
        return 'Finished Goods'
    else:
        return 'Transit'

def create_test_boms(test_data):
    """Create test BOMs for the integration test"""
    # BOM for finished good
    if not frappe.db.exists('BOM', {'item': 'M033-TEST-FG'}):
        bom_fg = frappe.get_doc({
            'doctype': 'BOM',
            'item': 'M033-TEST-FG',
            'company': test_data['company'],
            'is_default': 1,
            'is_active': 1,
            'items': [
                {
                    'item_code': '0227-TEST-INT',
                    'qty': 2,
                    'uom': 'Kg'
                },
                {
                    'item_code': 'RM-TEST-001',
                    'qty': 1,
                    'uom': 'Kg'
                }
            ]
        })
        bom_fg.insert(ignore_permissions=True)
        bom_fg.submit()
        test_data['boms'].append(bom_fg.name)
        print(f"Created BOM for M033-TEST-FG: {bom_fg.name}")
    
    # BOM for intermediate
    if not frappe.db.exists('BOM', {'item': '0227-TEST-INT'}):
        bom_int = frappe.get_doc({
            'doctype': 'BOM',
            'item': '0227-TEST-INT',
            'company': test_data['company'],
            'is_default': 1,
            'is_active': 1,
            'items': [
                {
                    'item_code': 'RM-TEST-002',
                    'qty': 3,
                    'uom': 'Kg'
                }
            ]
        })
        bom_int.insert(ignore_permissions=True)
        bom_int.submit()
        test_data['boms'].append(bom_int.name)
        print(f"Created BOM for 0227-TEST-INT: {bom_int.name}")

def create_test_sales_order(test_data):
    """Create test sales order"""
    if not frappe.db.exists('Customer', 'Test Customer'):
        customer = frappe.get_doc({
            'doctype': 'Customer',
            'customer_name': 'Test Customer',
            'customer_type': 'Company'
        })
        customer.insert(ignore_permissions=True)
        print("Created test customer")
    
    sales_order = frappe.get_doc({
        'doctype': 'Sales Order',
        'customer': 'Test Customer',
        'company': test_data['company'],
        'delivery_date': add_days(today(), 7),
        'items': [
            {
                'item_code': 'M033-TEST-FG',
                'qty': 10,
                'rate': 100
            }
        ]
    })
    sales_order.insert(ignore_permissions=True)
    sales_order.submit()
    test_data['sales_order'] = sales_order.name
    print(f"Created test sales order: {sales_order.name}")

def create_test_mrp_planning(test_data):
    """Create and test MRP Planning with warehouse integration"""
    mrp_planning = frappe.get_doc({
        'doctype': 'MRP Planning',
        'sales_order': test_data['sales_order'],
        'company': test_data['company'],
        'planned_start_date': today(),
        'required_date': add_days(today(), 7),
        'planning_status': 'Draft'
    })
    
    mrp_planning.insert()
    print(f"Created MRP Planning: {mrp_planning.name}")
    
    # Submit to trigger warehouse integration
    mrp_planning.submit()
    print(f"Submitted MRP Planning: {mrp_planning.name}")
    
    return mrp_planning.name

def test_work_order_creation(mrp_planning_name):
    """Test Work Order creation with warehouse integration"""
    work_orders = frappe.get_all(
        'Work Order',
        filters={'mrp_planning': mrp_planning_name},
        fields=['name', 'plant_code', 'production_level', 'custom_current_zone_status', 
               'custom_sap_movement_type']
    )
    
    print(f"Found {len(work_orders)} work orders created by MRP Planning")
    
    for wo in work_orders:
        print(f"Work Order: {wo.name}")
        print(f"  Plant Code: {wo.plant_code}")
        print(f"  Production Level: {wo.production_level}")
        print(f"  Zone Status: {wo.custom_current_zone_status}")
        print(f"  SAP Movement Type: {wo.custom_sap_movement_type}")
        
        # Verify warehouse fields are set
        assert wo.custom_current_zone_status is not None, "Zone status should be set"
        assert wo.custom_sap_movement_type is not None, "SAP movement type should be set"
    
    return work_orders

def test_material_assessment_logs(work_orders):
    """Test Material Assessment Log creation"""
    assessments = []
    
    for wo in work_orders:
        # Check if assessment log was created
        assessment_logs = frappe.get_all(
            'Material Assessment Log',
            filters={'work_order': wo.name},
            fields=['name', 'zone_status', 'completion_percentage', 'assessment_type']
        )
        
        print(f"Found {len(assessment_logs)} assessment logs for Work Order {wo.name}")
        
        for log in assessment_logs:
            print(f"  Assessment: {log.name}")
            print(f"    Zone Status: {log.zone_status}")
            print(f"    Completion: {log.completion_percentage}%")
            print(f"    Type: {log.assessment_type}")
            
            assessments.append(log)
    
    return assessments

def test_zone_status_updates(work_orders):
    """Test zone status update functionality"""
    for wo in work_orders:
        # Test zone status update API
        from amb_w_spc.sfc_manufacturing.warehouse_management.work_order import update_work_order_zone_status
        
        result = update_work_order_zone_status(wo.name)
        print(f"Zone status update for {wo.name}: {result['status']}")
        
        if result['status'] == 'success':
            print(f"  Updated zone: {result['zone_status']}")
            print(f"  Completion: {result['completion_percentage']}%")

def test_warehouse_zones_mapping():
    """Test warehouse zones mapping functionality"""
    from amb_w_spc.sfc_manufacturing.doctype.mrp_planning.mrp_planning import get_warehouse_zones_mapping
    
    result = get_warehouse_zones_mapping()
    print(f"Warehouse zones mapping: {result['status']}")
    
    if result['status'] == 'success':
        mapping = result['warehouse_mapping']
        for plant, zones in mapping.items():
            print(f"  {plant.upper()} Plant:")
            for zone_type, warehouse in zones.items():
                print(f"    {zone_type}: {warehouse}")

def test_api_endpoints(mrp_planning_name, work_orders):
    """Test API endpoints for warehouse integration"""
    from amb_w_spc.sfc_manufacturing.doctype.mrp_planning.mrp_planning import (
        get_mrp_warehouse_status,
        trigger_warehouse_operations,
        update_all_zone_statuses
    )
    
    # Test MRP warehouse status
    print("Testing MRP warehouse status API...")
    status_result = get_mrp_warehouse_status(mrp_planning_name)
    print(f"MRP warehouse status: {status_result['status']}")
    
    if status_result['status'] == 'success':
        print(f"  Work Orders: {len(status_result['work_orders'])}")
        print(f"  Assessments: {len(status_result['assessments'])}")
        print(f"  Stock Entries: {len(status_result['stock_entries'])}")
    
    # Test zone status update for all work orders
    print("\nTesting zone status update API...")
    update_result = update_all_zone_statuses(mrp_planning_name)
    print(f"Zone status update: {update_result['status']}")
    
    # Test warehouse operations
    if work_orders:
        wo_name = work_orders[0].name
        print(f"\nTesting warehouse operations for {wo_name}...")
        
        # Test pick request operation
        pick_result = trigger_warehouse_operations(wo_name, 'pick_request')
        print(f"Pick request: {pick_result['status']}")
        
        # Test zone update operation
        zone_result = trigger_warehouse_operations(wo_name, 'zone_update')
        print(f"Zone update: {zone_result['status']}")

def test_system_integrations(work_orders):
    """Test integration with existing systems"""
    try:
        from amb_w_spc.sfc_manufacturing.warehouse_management.integration import WarehouseIntegration
        
        for wo in work_orders:
            print(f"Testing integrations for Work Order {wo.name}...")
            
            # Test MRP integration
            mrp_result = WarehouseIntegration.integrate_with_mrp_planning(wo.name)
            print(f"  MRP integration: {mrp_result}")
            
            # Test quality system integration
            quality_result = WarehouseIntegration.sync_with_quality_systems(wo.name)
            print(f"  Quality integration: {quality_result}")
            
            # Test FDA compliance integration
            fda_result = WarehouseIntegration.update_fda_compliance_records(wo.name)
            print(f"  FDA compliance: {fda_result}")
            
    except ImportError as e:
        print(f"Integration module not found: {str(e)}")

def cleanup_test_data():
    """Clean up test data after testing"""
    try:
        # Delete test documents in reverse order of creation
        test_doctypes = [
            ('Material Assessment Log', {'work_order': ('like', '%TEST%')}),
            ('Stock Entry', {'custom_work_order_reference': ('like', '%TEST%')}),
            ('Work Order', {'mrp_planning': ('like', '%MRP%')}),
            ('MRP Planning', {'sales_order': ('like', '%SO%')}),
            ('Sales Order', {'customer': 'Test Customer'}),
            ('BOM', {'item': ('like', '%TEST%')}),
            ('Item', {'item_code': ('like', '%TEST%')}),
            ('Warehouse', {'warehouse_name': ('like', '%TC')}),
            ('Customer', {'customer_name': 'Test Customer'}),
            ('Company', {'company_name': 'Test Company'})
        ]
        
        for doctype, filters in test_doctypes:
            try:
                docs = frappe.get_all(doctype, filters=filters, fields=['name'])
                for doc in docs:
                    try:
                        frappe.delete_doc(doctype, doc.name, force=True)
                    except:
                        pass
                if docs:
                    print(f"Cleaned up {len(docs)} {doctype} records")
            except:
                pass
                
        frappe.db.commit()
        print("Test data cleanup completed")
        
    except Exception as e:
        print(f"Cleanup warning: {str(e)}")

if __name__ == '__main__':
    # Run the test
    test_mrp_warehouse_integration()
