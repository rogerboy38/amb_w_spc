# -*- coding: utf-8 -*-
# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
import json
from collections import defaultdict
from frappe.utils import now_datetime, flt

class MRPPlanning(Document):
    def validate(self):
        """Validate the MRP Planning document before saving"""
        if not self.sales_order:
            frappe.throw(_("Sales Order is mandatory"))
        
        # Validate that the sales order exists
        if not frappe.db.exists("Sales Order", self.sales_order):
            frappe.throw(_("Sales Order {0} does not exist").format(self.sales_order))

    def on_submit(self):
        """Execute MRP logic when document is submitted"""
        try:
            self.execute_mrp_planning()
            self.initialize_warehouse_integration()
            frappe.msgprint(_("MRP Planning executed successfully with warehouse integration"))
        except Exception as e:
            frappe.log_error(message=str(e), title="MRP Planning Error")
            frappe.throw(_("Error executing MRP Planning: {0}").format(str(e)))

    def execute_mrp_planning(self):
        """Main MRP execution logic"""
        frappe.msgprint(_("Starting MRP Planning execution for Sales Order: {0}").format(self.sales_order))
        
        # Step 1: Get Sales Order items
        sales_order_items = self.get_sales_order_items()
        
        # Step 2: Process each item and generate work orders
        all_requirements = {}
        
        for item in sales_order_items:
            frappe.msgprint(_("Processing item: {0}").format(item.item_code))
            
            # Check if this is a finished good that needs production
            if self.is_finished_good(item.item_code):
                # Generate work orders cascade for this item
                work_orders = self.generate_work_orders_cascade(item)
                
                # Explode BOM to get all material requirements
                material_requirements = self.explode_bom_requirements(item.item_code, item.qty)
                
                # Merge requirements
                self.merge_requirements(all_requirements, material_requirements)
        
        # Step 3: Create purchase requisitions for raw materials
        if all_requirements:
            self.create_purchase_requisitions(all_requirements)
        
        # Step 4: Create Material Assessment Logs for tracking
        self.create_material_assessment_logs(all_requirements)
        
        # Step 5: Update planning status
        self.planning_status = "Completed"
        self.save()

    def get_sales_order_items(self):
        """Get items from the linked Sales Order"""
        return frappe.get_all("Sales Order Item", 
            filters={"parent": self.sales_order},
            fields=["item_code", "qty", "item_name", "warehouse"]
        )

    def is_finished_good(self, item_code):
        """Check if an item is a finished good that can be sold"""
        item = frappe.get_doc("Item", item_code)
        return getattr(item, 'is_sales_item', 0) == 1

    def get_item_plant_code(self, item_code):
        """Get the plant code for an item to determine production routing"""
        item = frappe.get_doc("Item", item_code)
        
        # Check if there's a plant_code field in the item
        plant_code = getattr(item, 'plant_code', None)
        
        if not plant_code:
            # Fallback logic based on item code patterns
            # This is based on the user's example:
            # M033 -> juice plant
            # 0227 -> dry plant  
            # 0303/0302/0301 -> dry plant
            # 0334 -> mix plant
            
            if item_code.startswith('M'):
                return 'juice'
            elif item_code.startswith('02'):
                return 'dry'
            elif item_code.startswith('03'):
                # Check if it's powder (dry) or mix
                if len(item_code) == 4 and item_code[2:4] in ['01', '02', '03']:
                    return 'dry'  # Powder
                elif item_code.startswith('033'):
                    return 'mix'  # Mix
                else:
                    return 'dry'  # Default for 03xx items
            else:
                return 'mix'  # Default to mix plant
        
        return plant_code

    def generate_work_orders_cascade(self, sales_item):
        """Generate cascading work orders based on production levels"""
        work_orders = []
        
        item_code = sales_item.item_code
        quantity = sales_item.qty
        
        # Get the BOM for this item
        bom = self.get_active_bom(item_code)
        if not bom:
            frappe.msgprint(_("No active BOM found for item {0}").format(item_code))
            return work_orders
        
        # Determine plant routing based on item and BOM structure
        plant_routing = self.determine_plant_routing(item_code, bom)
        
        # Create work orders for each production level
        for level, plant_info in plant_routing.items():
            work_order = self.create_work_order(
                item_code=plant_info['item_code'],
                qty=plant_info['qty'] * quantity,
                plant_code=plant_info['plant_code'],
                production_level=level,
                bom=plant_info['bom']
            )
            if work_order:
                work_orders.append(work_order)
                # Create warehouse pick request for this work order
                self.create_warehouse_pick_request(work_order, plant_info['plant_code'])
        
        return work_orders

    def determine_plant_routing(self, finished_item, bom):
        """Determine the routing through different plants based on BOM structure"""
        routing = {}
        
        # Start with the finished good
        plant_code = self.get_item_plant_code(finished_item)
        routing['finished'] = {
            'item_code': finished_item,
            'qty': 1,  # Will be multiplied by actual qty needed
            'plant_code': plant_code,
            'bom': bom
        }
        
        # Analyze BOM to find intermediate levels
        bom_doc = frappe.get_doc("BOM", bom)
        
        for item in bom_doc.items:
            sub_item_code = item.item_code
            sub_plant_code = self.get_item_plant_code(sub_item_code)
            
            # Check if this item has its own BOM (indicating it's manufactured)
            sub_bom = self.get_active_bom(sub_item_code)
            
            if sub_bom and sub_plant_code != plant_code:
                # This is a manufactured intermediate with different plant
                level_name = f"{sub_plant_code}_level"
                
                if level_name not in routing:
                    routing[level_name] = {
                        'item_code': sub_item_code,
                        'qty': item.qty,
                        'plant_code': sub_plant_code,
                        'bom': sub_bom
                    }
        
        return routing

    def create_work_order(self, item_code, qty, plant_code, production_level, bom):
        """Create a work order for production"""
        try:
            work_order = frappe.get_doc({
                'doctype': 'Work Order',
                'production_item': item_code,
                'qty': qty,
                'bom_no': bom,
                'company': self.company,
                'planned_start_date': self.planned_start_date,
                'plant_code': plant_code,
                'production_level': production_level,
                'mrp_planning': self.name,
                'sales_order': self.sales_order,
                # Initialize warehouse fields
                'custom_current_zone_status': 'Red Zone',
                'custom_zone_status_color': '#dc3545',
                'custom_material_completion_percentage': 0,
                'custom_last_zone_update': now_datetime(),
                'custom_sap_movement_type': self.get_sap_movement_type(production_level, plant_code)
            })
            
            work_order.insert()
            frappe.msgprint(_("Created Work Order {0} for {1} at {2} plant").format(
                work_order.name, item_code, plant_code))
            
            return work_order.name
            
        except Exception as e:
            frappe.log_error(message=str(e), title="Work Order Creation Error")
            frappe.msgprint(_("Error creating work order for {0}: {1}").format(item_code, str(e)))
            return None

    def get_active_bom(self, item_code):
        """Get the active BOM for an item"""
        bom = frappe.db.get_value("BOM", 
            filters={"item": item_code, "is_active": 1, "is_default": 1},
            fieldname="name"
        )
        return bom

    def explode_bom_requirements(self, item_code, qty):
        """Recursively explode BOM to get all material requirements"""
        requirements = defaultdict(float)
        
        # Get the BOM for this item
        bom = self.get_active_bom(item_code)
        if not bom:
            return requirements
        
        # Get BOM items
        bom_items = frappe.get_all("BOM Item",
            filters={"parent": bom},
            fields=["item_code", "qty", "stock_uom"]
        )
        
        for bom_item in bom_items:
            required_qty = bom_item.qty * qty
            
            # Check if this item has its own BOM (manufactured item)
            sub_bom = self.get_active_bom(bom_item.item_code)
            
            if sub_bom:
                # Recursively explode this BOM
                sub_requirements = self.explode_bom_requirements(bom_item.item_code, required_qty)
                self.merge_requirements(requirements, sub_requirements)
            else:
                # This is a raw material/purchased item
                requirements[bom_item.item_code] += required_qty
        
        return dict(requirements)

    def merge_requirements(self, target_dict, source_dict):
        """Merge material requirements dictionaries"""
        for item_code, qty in source_dict.items():
            target_dict[item_code] = target_dict.get(item_code, 0) + qty

    def create_purchase_requisitions(self, requirements):
        """Create purchase requisitions for raw materials"""
        # Group by supplier or category if needed
        frappe.msgprint(_("Creating purchase requisitions for {0} raw materials").format(len(requirements)))
        
        for item_code, qty in requirements.items():
            # Check current stock
            available_qty = self.get_available_stock(item_code)
            
            if available_qty < qty:
                shortage = qty - available_qty
                self.create_purchase_request(item_code, shortage)

    def get_available_stock(self, item_code):
        """Get available stock for an item"""
        # This could be enhanced to check specific warehouses
        stock = frappe.db.sql("""
            SELECT SUM(actual_qty) 
            FROM `tabStock Ledger Entry` 
            WHERE item_code = %s AND is_cancelled = 0
        """, item_code)
        
        return stock[0][0] if stock and stock[0][0] else 0

    def create_purchase_request(self, item_code, qty):
        """Create a purchase request for shortage items"""
        try:
            purchase_request = frappe.get_doc({
                'doctype': 'Material Request',
                'material_request_type': 'Purchase',
                'company': self.company,
                'transaction_date': frappe.utils.today(),
                'schedule_date': self.required_date,
                'mrp_planning': self.name,
                'items': [{
                    'item_code': item_code,
                    'qty': qty,
                    'schedule_date': self.required_date,
                    'warehouse': self.warehouse or frappe.db.get_single_value('Stock Settings', 'default_warehouse')
                }]
            })
            
            purchase_request.insert()
            frappe.msgprint(_("Created Material Request {0} for {1}").format(
                purchase_request.name, item_code))
            
        except Exception as e:
            frappe.log_error(message=str(e), title="Material Request Creation Error")
            frappe.msgprint(_("Error creating material request for {0}: {1}").format(item_code, str(e)))
    
    def initialize_warehouse_integration(self):
        """Initialize warehouse integration for all created work orders"""
        try:
            from amb_w_spc.sfc_manufacturing.warehouse_management.integration import WarehouseIntegration
            
            # Get all work orders created by this MRP Planning
            work_orders = frappe.get_all(
                "Work Order",
                filters={"mrp_planning": self.name},
                fields=["name", "plant_code", "production_level"]
            )
            
            for wo in work_orders:
                # Initialize zone status and material assessment
                self.update_work_order_zone_status(wo.name)
                
                # Create warehouse pick request
                pick_request = WarehouseIntegration.create_warehouse_pick_request(wo.name)
                
                if pick_request:
                    frappe.msgprint(_("Created warehouse pick request {0} for work order {1}")
                                  .format(pick_request, wo.name))
                
                # Initialize stock entries for Work Order
                self.create_initial_stock_entries(wo.name, wo.plant_code, wo.production_level)
                
        except Exception as e:
            frappe.log_error(f"Warehouse integration initialization failed: {str(e)}")
            # Don't fail MRP Planning due to warehouse integration issues
    
    def create_warehouse_pick_request(self, work_order_name, plant_code):
        """Create warehouse pick request for a work order"""
        try:
            work_order = frappe.get_doc("Work Order", work_order_name)
            
            if not work_order.bom_no:
                return None
            
            # Get warehouse zone based on plant code
            warehouse_zones = self.get_warehouse_zones_for_plant(plant_code)
            
            # Get BOM items
            bom_items = frappe.get_all(
                "BOM Item",
                filters={"parent": work_order.bom_no},
                fields=["item_code", "qty", "warehouse", "item_name"]
            )
            
            # Create Material Assessment Log
            assessment = frappe.get_doc({
                "doctype": "Material Assessment Log",
                "work_order": work_order_name,
                "mrp_planning": self.name,
                "assessment_date": now_datetime(),
                "zone_status": "Red Zone",  # Initial status
                "completion_percentage": 0,
                "plant_code": plant_code,
                "warehouse_zones": json.dumps(warehouse_zones),
                "assessed_by": frappe.session.user,
                "items": []
            })
            
            # Add assessment items
            for bom_item in bom_items:
                required_qty = flt(bom_item.qty * work_order.qty)
                available_qty = self.get_available_stock(bom_item.item_code)
                
                assessment.append("items", {
                    "item_code": bom_item.item_code,
                    "item_name": bom_item.item_name,
                    "required_qty": required_qty,
                    "available_qty": available_qty,
                    "shortage_qty": max(0, required_qty - available_qty),
                    "warehouse": bom_item.warehouse or warehouse_zones.get('raw_material', ''),
                    "status": "Available" if available_qty >= required_qty else "Shortage"
                })
            
            try:
                assessment.insert(ignore_permissions=True)
                return assessment.name
            except Exception as insert_error:
                frappe.log_error(f"Material Assessment Log creation failed: {str(insert_error)}")
                return None
                
        except Exception as e:
            frappe.log_error(f"Warehouse pick request creation failed: {str(e)}")
            return None
    
    def get_warehouse_zones_for_plant(self, plant_code):
        """Get warehouse zones mapping for a plant code"""
        warehouse_mapping = {
            'juice': {
                'raw_material': 'Juice RM Warehouse',
                'work_in_progress': 'Juice WIP Warehouse', 
                'finished_goods': 'Juice FG Warehouse',
                'transit': 'Juice Transit Warehouse'
            },
            'dry': {
                'raw_material': 'Dry RM Warehouse',
                'work_in_progress': 'Dry WIP Warehouse',
                'finished_goods': 'Dry FG Warehouse', 
                'transit': 'Dry Transit Warehouse'
            },
            'mix': {
                'raw_material': 'Mix RM Warehouse',
                'work_in_progress': 'Mix WIP Warehouse',
                'finished_goods': 'Mix FG Warehouse',
                'transit': 'Mix Transit Warehouse'
            }
        }
        
        return warehouse_mapping.get(plant_code, {
            'raw_material': 'Main Raw Material Warehouse',
            'work_in_progress': 'Main WIP Warehouse',
            'finished_goods': 'Main FG Warehouse',
            'transit': 'Main Transit Warehouse'
        })
    
    def get_sap_movement_type(self, production_level, plant_code):
        """Determine SAP movement type based on production level and plant"""
        # Define movement type mapping
        movement_mapping = {
            'finished': '261',  # FrontFlush - Final production
            'intermediate': '311',  # BackFlush - Intermediate transfers
            'raw': '261'  # FrontFlush - Raw material consumption
        }
        
        return movement_mapping.get(production_level, '261')
    
    def create_initial_stock_entries(self, work_order_name, plant_code, production_level):
        """Create initial stock entries for material movements"""
        try:
            work_order = frappe.get_doc("Work Order", work_order_name)
            
            if not work_order.bom_no:
                return
            
            # Create Material Issue stock entry for raw materials
            stock_entry = frappe.get_doc({
                "doctype": "Stock Entry",
                "purpose": "Material Issue",
                "work_order": work_order_name,
                "company": self.company,
                "posting_date": self.planned_start_date,
                "custom_work_order_reference": work_order_name,
                "custom_sap_movement_type": self.get_sap_movement_type(production_level, plant_code),
                "custom_current_zone_status": "Red Zone",
                "custom_zone_status_color": "#dc3545",
                "custom_material_completion_percentage": 0,
                "items": []
            })
            
            # Get warehouse zones
            warehouse_zones = self.get_warehouse_zones_for_plant(plant_code)
            
            # Add BOM items to stock entry
            bom_items = frappe.get_all(
                "BOM Item",
                filters={"parent": work_order.bom_no},
                fields=["item_code", "qty", "item_name", "uom"]
            )
            
            for bom_item in bom_items:
                required_qty = flt(bom_item.qty * work_order.qty)
                
                stock_entry.append("items", {
                    "item_code": bom_item.item_code,
                    "qty": required_qty,
                    "uom": bom_item.uom,
                    "s_warehouse": warehouse_zones.get('raw_material'),
                    "t_warehouse": warehouse_zones.get('work_in_progress'),
                    "allow_zero_valuation_rate": 1
                })
            
            # Save as draft - will be submitted later by warehouse operations
            stock_entry.insert(ignore_permissions=True)
            
            frappe.msgprint(_("Created draft stock entry {0} for work order {1}")
                          .format(stock_entry.name, work_order_name))
            
            return stock_entry.name
            
        except Exception as e:
            frappe.log_error(f"Initial stock entry creation failed: {str(e)}")
            return None
    
    def update_work_order_zone_status(self, work_order_name):
        """Update work order zone status based on material availability"""
        try:
            from amb_w_spc.sfc_manufacturing.warehouse_management.work_order import update_material_requirements
            
            work_order = frappe.get_doc("Work Order", work_order_name)
            update_material_requirements(work_order)
            work_order.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Work order zone status update failed: {str(e)}")
    
    def create_material_assessment_logs(self, all_requirements):
        """Create material assessment logs for tracking"""
        try:
            # Create master assessment log for this MRP Planning
            master_assessment = frappe.get_doc({
                "doctype": "Material Assessment Log",
                "mrp_planning": self.name,
                "assessment_date": now_datetime(),
                "zone_status": "Planning Phase",
                "completion_percentage": 0,
                "assessed_by": frappe.session.user,
                "assessment_type": "MRP Master Assessment",
                "total_requirements": len(all_requirements),
                "items": []
            })
            
            # Add requirement items
            for item_code, qty in all_requirements.items():
                available_qty = self.get_available_stock(item_code)
                shortage = max(0, qty - available_qty)
                
                master_assessment.append("items", {
                    "item_code": item_code,
                    "required_qty": qty,
                    "available_qty": available_qty,
                    "shortage_qty": shortage,
                    "status": "Available" if shortage == 0 else "Shortage"
                })
            
            try:
                master_assessment.insert(ignore_permissions=True)
                self.master_assessment_log = master_assessment.name
            except Exception as insert_error:
                frappe.log_error(f"Master assessment log creation failed: {str(insert_error)}")
                
        except Exception as e:
            frappe.log_error(f"Material assessment logs creation failed: {str(e)}")

# Utility functions that can be called from other parts of the system

@frappe.whitelist()
def run_mrp_planning(sales_order, company=None):
    """API function to run MRP planning for a sales order"""
    try:
        # Create MRP Planning document
        mrp_doc = frappe.get_doc({
            'doctype': 'MRP Planning',
            'sales_order': sales_order,
            'company': company or frappe.defaults.get_user_default('Company'),
            'planned_start_date': frappe.utils.today(),
            'required_date': frappe.utils.add_days(frappe.utils.today(), 7),
            'planning_status': 'Draft'
        })
        
        mrp_doc.insert()
        mrp_doc.submit()
        
        return {
            'status': 'success',
            'mrp_planning': mrp_doc.name,
            'message': 'MRP Planning executed successfully'
        }
        
    except Exception as e:
        frappe.log_error(message=str(e), title="MRP Planning API Error")
        return {
            'status': 'error',
            'message': str(e)
        }

@frappe.whitelist()
def get_production_routing(item_code):
    """Get the production routing for an item based on its BOM structure"""
    try:
        # Create a temporary MRPPlanning instance to use its methods
        mrp = frappe.get_doc({"doctype": "MRP Planning"})
        
        # Get active BOM
        bom = mrp.get_active_bom(item_code)
        if not bom:
            return {'status': 'error', 'message': 'No active BOM found'}
        
        # Determine routing
        routing = mrp.determine_plant_routing(item_code, bom)
        
        return {
            'status': 'success',
            'routing': routing,
            'bom': bom
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

@frappe.whitelist()
def get_mrp_warehouse_status(mrp_planning_name):
    """Get warehouse integration status for an MRP Planning"""
    try:
        mrp_doc = frappe.get_doc("MRP Planning", mrp_planning_name)
        
        # Get all work orders
        work_orders = frappe.get_all(
            "Work Order",
            filters={"mrp_planning": mrp_planning_name},
            fields=["name", "plant_code", "production_level", "custom_current_zone_status", 
                   "custom_material_completion_percentage"]
        )
        
        # Get material assessment logs
        assessments = frappe.get_all(
            "Material Assessment Log",
            filters={"mrp_planning": mrp_planning_name},
            fields=["name", "work_order", "zone_status", "completion_percentage", "assessment_date"]
        )
        
        # Get stock entries
        stock_entries = frappe.get_all(
            "Stock Entry",
            filters={"custom_work_order_reference": ["in", [wo.name for wo in work_orders]]},
            fields=["name", "custom_work_order_reference", "custom_sap_movement_type", 
                   "custom_zone_status", "docstatus"]
        )
        
        return {
            "status": "success",
            "mrp_planning": mrp_planning_name,
            "work_orders": work_orders,
            "assessments": assessments,
            "stock_entries": stock_entries
        }
        
    except Exception as e:
        frappe.log_error(f"MRP warehouse status check failed: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def trigger_warehouse_operations(work_order_name, operation_type):
    """Trigger specific warehouse operations for a work order"""
    try:
        from amb_w_spc.sfc_manufacturing.warehouse_management.integration import WarehouseIntegration
        
        if operation_type == "pick_request":
            pick_request = WarehouseIntegration.create_warehouse_pick_request(work_order_name)
            return {"status": "success", "pick_request": pick_request}
            
        elif operation_type == "zone_update":
            # Update work order zone status
            from amb_w_spc.sfc_manufacturing.warehouse_management.work_order import update_work_order_zone_status
            result = update_work_order_zone_status(work_order_name)
            return result
            
        elif operation_type == "stock_entry":
            # Create stock entry for material issue
            from amb_w_spc.sfc_manufacturing.warehouse_management.stock_entry import make_custom_stock_entry
            stock_entry = make_custom_stock_entry(work_order_name, "Material Issue")
            return {"status": "success", "stock_entry": stock_entry.name}
            
        else:
            return {"status": "error", "message": "Invalid operation type"}
            
    except Exception as e:
        frappe.log_error(f"Warehouse operation trigger failed: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def update_all_zone_statuses(mrp_planning_name):
    """Update zone statuses for all work orders in an MRP Planning"""
    try:
        # Get all work orders
        work_orders = frappe.get_all(
            "Work Order",
            filters={"mrp_planning": mrp_planning_name},
            fields=["name"]
        )
        
        results = []
        for wo in work_orders:
            try:
                from amb_w_spc.sfc_manufacturing.warehouse_management.work_order import update_work_order_zone_status
                result = update_work_order_zone_status(wo.name)
                results.append({"work_order": wo.name, "result": result})
            except Exception as wo_error:
                results.append({"work_order": wo.name, "error": str(wo_error)})
        
        return {
            "status": "success",
            "mrp_planning": mrp_planning_name,
            "results": results
        }
        
    except Exception as e:
        frappe.log_error(f"Zone status update failed: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_warehouse_zones_mapping():
    """Get the complete warehouse zones mapping for all plants"""
    try:
        mrp = frappe.get_doc({"doctype": "MRP Planning"})
        
        mapping = {
            "juice": mrp.get_warehouse_zones_for_plant("juice"),
            "dry": mrp.get_warehouse_zones_for_plant("dry"), 
            "mix": mrp.get_warehouse_zones_for_plant("mix")
        }
        
        return {
            "status": "success",
            "warehouse_mapping": mapping
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

