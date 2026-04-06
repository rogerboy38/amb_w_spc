# Copyright (c) 2024, AMB and contributors
# For license information, please see license.txt

# NOTE (Phase 12.1): The Server Script 'validate_var_code39_ok' has been
# retired. Its validation logic (Code-39 format check and gross_weight
# requirement) is now implemented in validate_containers() and
# _is_valid_code39() within this controller.
# The Server Script should be DISABLED in Setup > Server Script.

import json
import random
import string
import re
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    flt,
    nowdate,
    now_datetime,
    get_datetime,
    getdate,
    cstr,
)
from frappe.utils.nestedset import NestedSet


class BatchAMB(NestedSet):
    """
    Batch AMB - Production Batch Management
    """

    def validate(self):
        """Validation before saving"""
        self.set_batch_naming()
        self.validate_production_dates()
        self.validate_quantities()
        self.validate_work_order()
        self.validate_containers()
        self._validate_batch_hierarchy()
        self.validate_barrel_weights()
        self.set_item_details()
        self.validate_processing_dates()
        self.calculate_yield_percentage()
        self.validate_pipeline_transition()

    def _validate_batch_hierarchy(self):
        """Enforce parent-child level rules:
        - L1 (Parent): no parent required
        - L2 (Sub-lot): parent must be L1
        - L3 (Container): parent must be L2
        """
        level = str(self.custom_batch_level or "1")
        parent = self.parent_batch_amb

        if level == "1":
            return  # L1 has no parent requirement

        if not parent:
            frappe.throw(_("Level {0} batch requires a parent batch.").format(level))

        if not frappe.db.exists("Batch AMB", parent):
            frappe.throw(_("Parent batch {0} does not exist.").format(parent))

        parent_level = str(frappe.db.get_value("Batch AMB", parent, "custom_batch_level") or "0")

        expected_parent_levels = {
            "2": "1",  # L2 parent must be L1
            "3": "2",  # L3 parent must be L2
            "4": "3",  # L4 parent must be L3 (future)
        }

        expected = expected_parent_levels.get(level)
        if expected and parent_level != expected:
            frappe.throw(
                _("Level {0} batch requires a Level {1} parent, but {2} is Level {3}.").format(
                    level, expected, parent, parent_level
                )
            )

    def validate_pipeline_transition(self):
        """Enforce pipeline state machine - no skipping stages"""
        # Pipeline states in order
        PIPELINE_ORDER = [
            "Draft", "WO Linked", "In Production", "Weighing", 
            "QI Pending", "QI Passed", "COA Ready", 
            "Ready for Delivery", "Delivered", "Closed"
        ]
        
        # Skip for new documents
        if self.is_new():
            return
        
        # Get old value from database (not _doc_before_save which may not exist)
        old_status = frappe.db.get_value("Batch AMB", self.name, "pipeline_status") or "Draft"
        new_status = self.pipeline_status or "Draft"
        
        # Skip if no change
        if old_status == new_status:
            return
        
        old_idx = PIPELINE_ORDER.index(old_status) if old_status in PIPELINE_ORDER else -1
        new_idx = PIPELINE_ORDER.index(new_status) if new_status in PIPELINE_ORDER else -1
        
        if old_idx < 0 or new_idx < 0:
            return  # Allow if either status is not in our list
        
        diff = new_idx - old_idx
        
        # Allow forward by 1 step
        if diff == 1:
            return
        
        # Allow backward by 1 step ONLY if user has Production Manager role
        if diff == -1:
            if frappe.has_permission("Batch AMB", "validate", "Production Manager"):
                return
        
        # Block invalid transitions
        frappe.throw(
            _("Invalid pipeline transition from '{0}' to '{1}'. Only adjacent state changes are allowed.").format(
                old_status, new_status
            )
        )

    def before_save(self):
        """Before save hook"""
        self.calculate_totals()
        self.set_batch_naming()
        # FIXED: Only auto-set title for NEW documents to prevent title drift
        # This prevents serial base from changing between saves
        if self.is_new():
            self.auto_set_title()
        # FIXED: Keep custom_generated_batch_name in sync with title
        self.custom_generated_batch_name = self.title
        self.update_container_sequence()
        self.calculate_costs()
        self.update_processing_timestamps()
        self.update_planned_qty_from_work_order()

    def on_update(self):
        """After update hook"""
        self.sync_with_lote_amb()
        self.update_work_order_status()
        self.log_batch_history()
        self.update_work_order_processing_status()

    def on_submit(self):
        """On submit"""
        self.create_stock_entry()
        self.create_lote_amb_if_needed()
        self.update_batch_status("Completed")
        self.notify_stakeholders()

    def on_cancel(self):
        """On cancel"""
        self.cancel_stock_entries()
        self.update_batch_status("Cancelled")

    # -----------------------------
    # Core validations
    # -----------------------------

    def validate_production_dates(self):
        """Validate production dates"""
        if self.production_start_date and self.production_end_date:
            start = get_datetime(self.production_start_date)
            end = get_datetime(self.production_end_date)

            if end < start:
                frappe.throw(_("Production end date cannot be before start date"))

    def validate_quantities(self):
        """Validate quantities"""
        if self.produced_qty and flt(self.produced_qty) <= 0:
            frappe.throw(_("Produced quantity must be greater than 0"))

        if self.planned_qty is not None and flt(self.planned_qty) <= 0:
            frappe.throw(_("Planned quantity must be greater than 0"))

    def validate_work_order(self):
        """Validate work order reference"""
        if self.work_order and not frappe.db.exists("Work Order", self.work_order):
            frappe.throw(_("Work Order {0} does not exist").format(self.work_order))

    def validate_containers(self):
        """Validate container barrel rows — with hasattr guards for schema safety."""
        if not self.container_barrels:
            return

        seen_serials = set()
        for i, row in enumerate(self.container_barrels, 1):
            serial = getattr(row, "barrel_serial_number", None) or ""
            
            # Check for duplicate serials
            if serial and serial in seen_serials:
                frappe.throw(_("Row {0}: Duplicate barrel serial number: {1}").format(i, serial))
            if serial:
                seen_serials.add(serial)

            # Validate Code-39 format if serial exists
            if serial and not self._is_valid_code39(serial):
                frappe.throw(_("Row {0}: Invalid CODE-39 barcode format for barrel {1}").format(i, serial))

            # Validate weight if weight_validated is set
            gross = getattr(row, "gross_weight", None) or 0
            tara = getattr(row, "tara_weight", None) or 0
            net = getattr(row, "net_weight", None) or 0

            if getattr(row, "weight_validated", 0) and gross <= 0:
                frappe.throw(_("Row {0}: Gross weight is required for validated barrel {1}").format(i, serial))

            # Auto-calculate net weight
            if gross > 0 and tara >= 0:
                row.net_weight = gross - tara
    
    def validate_barrel_weights(self):
        """Validate barrel weights"""
        if self.custom_batch_level != "3":
            return

        if self.container_barrels:
            for barrel in self.container_barrels:
                if barrel.gross_weight and barrel.tara_weight:
                    net_weight = barrel.gross_weight - barrel.tara_weight
                    if net_weight <= 0:
                        frappe.throw(
                            f"Invalid net weight for barrel {barrel.barrel_serial_number}"
                        )
                    barrel.net_weight = net_weight

    def calculate_yield_percentage(self):
        """Calculate yield percentage based on planned and processed quantities"""
        if (
            hasattr(self, "planned_qty")
            and self.planned_qty
            and flt(self.planned_qty) > 0
        ):
            if (
                hasattr(self, "processed_quantity")
                and self.processed_quantity is not None
            ):
                self.yield_percentage = (
                    flt(self.processed_quantity) / flt(self.planned_qty) * 100
                )
            else:
                self.yield_percentage = 0
        else:
            self.yield_percentage = 0

    def validate_processing_dates(self):
        """Validate processing dates"""
        if hasattr(self, "actual_start") and hasattr(self, "actual_completion"):
            if self.actual_start and self.actual_completion:
                if self.actual_completion < self.actual_start:
                    frappe.throw(
                        _("Actual completion date cannot be before actual start date")
                    )

    @staticmethod
    def _is_valid_code39(serial):
        """Validate that a serial number conforms to CODE-39 barcode character set.
        Valid chars: A-Z, 0-9, -, ., $, /, +, %, space
        """
        import re
        if not serial:
            return True
        return bool(re.match(r'^[A-Z0-9\-\.\$\/\+\%\s]+$', serial.upper()))

    # -----------------------------
    # Presentation / naming
    # -----------------------------

    def auto_set_title(self):
        """Auto-generate title based on batch level and parent using Golden Number."""
        level = str(self.custom_batch_level or "1")

        # Level 1: use Golden Number directly
        if level == "1":
            if self.custom_golden_number:
                self.title = self.custom_golden_number
            else:
                # Fallback to name
                self.title = self.name

        # Level 2: <GoldenNumber>-<sub lot index>
        elif level == "2":
            if self.parent_batch_amb:
                parent = frappe.get_doc("Batch AMB", self.parent_batch_amb)
                parent_gn = parent.custom_golden_number or parent.title or parent.name

                siblings = frappe.db.count(
                    "Batch AMB",
                    {
                        "parent_batch_amb": self.parent_batch_amb,
                        "custom_batch_level": "2",
                        "name": ["!=", self.name],
                    },
                )
                self.title = f"{parent_gn}-{siblings + 1}"
            else:
                self.title = f"{self.name}-L2"

        # Level 3: <Level2Title>-C<container index>
        elif level == "3":
            if self.parent_batch_amb:
                parent = frappe.get_doc("Batch AMB", self.parent_batch_amb)
                parent_title = parent.title or parent.name

                siblings = frappe.db.count(
                    "Batch AMB",
                    {
                        "parent_batch_amb": self.parent_batch_amb,
                        "custom_batch_level": "3",
                        "name": ["!=", self.name],
                    },
                )
                self.title = f"{parent_title}-C{siblings + 1}"
            else:
                self.title = f"{self.name}-L3"

        # Level 4: <Level3Title>-<serial 3-digit>
        elif level == "4":
            if self.parent_batch_amb:
                parent = frappe.get_doc("Batch AMB", self.parent_batch_amb)
                parent_title = parent.title or parent.name

                siblings = frappe.db.count(
                    "Batch AMB",
                    {
                        "parent_batch_amb": self.parent_batch_amb,
                        "custom_batch_level": "4",
                        "name": ["!=", self.name],
                    },
                )
                self.title = f"{parent_title}-{siblings + 1:03d}"
            else:
                self.title = f"{self.name}-L4"

        # Safety: trim very long titles
        if self.title and len(self.title) > 60:
            self.title = self.title[:60]


    def set_item_details(self):
        """Set item details"""
        if self.item_to_manufacture:
            item = frappe.get_doc("Item", self.item_to_manufacture)
            self.item_name = item.item_name
            if not self.uom:
                self.uom = item.stock_uom

    # -----------------------------
    # Weight Calculation & Validation
    # -----------------------------

    def calculate_barrel_weight(self, barrel_row):
        """Calculate net weight for a single barrel row.
        Auto-calculates: net_weight = gross_weight - tara_weight
        """
        gross = flt(barrel_row.get('gross_weight') or 0)
        tara = flt(barrel_row.get('tara_weight') or 0)
        
        if gross and tara:
            barrel_row.net_weight = gross - tara
        elif gross:
            barrel_row.net_weight = gross
        
        return barrel_row.get('net_weight', 0)

    def get_tara_weight_from_item(self, packaging_type: str) -> float:
        """Fetch standard tara weight from Item master.
        Looks for standard_weight on the packaging Item.
        """
        if not packaging_type:
            return 0
        
        # Try to find item by packaging type name
        try:
            item_code = packaging_type
            # Try exact match first
            if frappe.db.exists("Item", item_code):
                item = frappe.get_doc("Item", item_code)
                return flt(item.standard_weight or 0)
            
            # Try with "Barrel" suffix
            barrel_item = f"{item_code} Barrel"
            if frappe.db.exists("Item", barrel_item):
                item = frappe.get_doc("Item", barrel_item)
                return flt(item.standard_weight or 0)
            
            # Try partial match
            items = frappe.get_all("Item", 
                filters={"name": ["like", f"%{item_code}%"], "item_group": "Containers"},
                fields=["name", "standard_weight"],
                limit=1
            )
            if items:
                return flt(items[0].standard_weight or 0)
                
        except Exception:
            pass
        
        return 0

    def validate_barrel_weight(self, barrel_row) -> dict:
        """Validate barrel weight against min/max thresholds.
        Returns: {"valid": bool, "message": str}
        """
        packaging_type = barrel_row.get('packaging_type')
        gross_weight = flt(barrel_row.get('gross_weight') or 0)
        net_weight = flt(barrel_row.get('net_weight') or 0)
        
        # Default thresholds
        min_weight = 0.1  # kg
        max_weight = 1000  # kg
        
        # Try to get custom thresholds from Item
        if packaging_type:
            try:
                if frappe.db.exists("Item", packaging_type):
                    item = frappe.get_doc("Item", packaging_type)
                    # You could add custom fields for min/max weight
                    # For now, use item standard_weight as reference
                    if item.standard_weight:
                        min_weight = item.standard_weight * 0.8
                        max_weight = item.standard_weight * 1.5
            except Exception:
                pass
        
        # Validate
        if net_weight < min_weight:
            return {"valid": False, "message": f"Weight {net_weight} kg below minimum {min_weight} kg"}
        if net_weight > max_weight:
            return {"valid": False, "message": f"Weight {net_weight} kg exceeds maximum {max_weight} kg"}
        
        return {"valid": True, "message": "Weight within valid range"}

    def set_barrel_validated(self, barrel_row):
        """Set weight_validated flag based on validation result."""
        validation = self.validate_barrel_weight(barrel_row)
        barrel_row.weight_validated = validation.get("valid", False)
        return validation

    def update_barrel_weight_from_serial(self, barrel_serial: str, gross_weight: float) -> dict:
        """Update weight for a specific barrel by serial number.
        Used by: Manual entry, Raven command, IoT API
        """
        if not self.container_barrels:
            return {"success": False, "error": "No container barrels defined"}
        
        # Find barrel by serial
        barrel = None
        for row in self.container_barrels:
            if row.get('serial_number') == barrel_serial:
                barrel = row
                break
        
        if not barrel:
            return {"success": False, "error": f"Barrel serial '{barrel_serial}' not found"}
        
        # Get tara weight if not set
        if not barrel.get('tara_weight'):
            packaging = barrel.get('packaging_type')
            barrel.tara_weight = self.get_tara_weight_from_item(packaging)
        
        # Update gross weight
        barrel.gross_weight = flt(gross_weight)
        
        # Auto-calculate net weight
        self.calculate_barrel_weight(barrel)
        
        # Validate and set flag
        validation = self.set_barrel_validated(barrel)
        
        # Recalculate totals
        self.calculate_container_weights()
        
        return {
            "success": True,
            "barrel_serial": barrel_serial,
            "gross_weight": barrel.gross_weight,
            "tara_weight": barrel.tara_weight,
            "net_weight": barrel.net_weight,
            "validated": barrel.weight_validated,
            "validation_message": validation.get("message")
        }

    # -----------------------------
    # Totals and costing
    # -----------------------------

    def calculate_totals(self):
        """Calculate container totals from Container Barrels child table.
        NOTE: Container Barrels has NO 'quantity' field. Use row count only.
        """
        self.total_containers = len(self.container_barrels or [])
        self.total_container_qty = len(self.container_barrels or [])
        if hasattr(self, 'calculate_container_weights'):
            self.calculate_container_weights()

    def calculate_weight(self):
        """Calculate net_weight = gross_weight - tara_weight for all container_barrels rows.
        Called by validation: T4.1
        """
        if not self.container_barrels:
            return
        
        for barrel in self.container_barrels:
            gross = flt(getattr(barrel, 'gross_weight', None) or 0)
            tara = flt(getattr(barrel, 'tara_weight', None) or 0)
            if gross and tara:
                barrel.net_weight = gross - tara
            elif gross:
                barrel.net_weight = gross

    def validate_barrel_weight(self):
        """Validate each barrel weight against min/max thresholds, set weight_validated flag.
        Called by validation: T4.1
        """
        if not self.container_barrels:
            return
        
        for barrel in self.container_barrels:
            if not getattr(barrel, 'gross_weight', None):
                continue
            
            packaging_type = getattr(barrel, 'packaging_type', None)
            net_weight = flt(getattr(barrel, 'net_weight', None) or 0)
            
            # Default thresholds
            min_weight = 0.1
            max_weight = 1000
            
            # Get custom thresholds from Item
            if packaging_type:
                try:
                    if frappe.db.exists("Item", packaging_type):
                        item = frappe.get_doc("Item", packaging_type)
                        if item.standard_weight:
                            min_weight = item.standard_weight * 0.8
                            max_weight = item.standard_weight * 1.5
                except Exception:
                    pass
            
            # Set validated flag
            barrel.weight_validated = 1 if min_weight <= net_weight <= max_weight else 0

    def calculate_costs(self):
        """Calculate costs"""
        if not self.calculate_cost:
            return

        total_cost = 0
        if self.bom_no:
            total_cost += self.get_bom_cost()
        if self.labor_cost:
            total_cost += flt(self.labor_cost)
        if self.overhead_cost:
            total_cost += flt(self.overhead_cost)

        self.total_batch_cost = total_cost
        if self.produced_qty:
            self.cost_per_unit = total_cost / flt(self.produced_qty)

    def get_bom_cost(self):
        """Get BOM cost"""
        if not self.bom_no:
            return 0
        bom = frappe.get_doc("BOM", self.bom_no)
        # original had total_cost * produced_qty – that inflates; keep as-is if you want
        return flt(bom.total_cost) * flt(self.produced_qty)

    def calculate_container_weights(self):
        """Calculate container weights from container_barrels child table."""
        if not getattr(self, "container_barrels", None):
            self.total_gross_weight = 0
            self.total_tara_weight = 0
            self.total_net_weight = 0
            self.barrel_count = 0
            return

        total_gross = 0
        total_tara = 0
        total_net = 0
        barrel_count = 0

        for barrel in self.container_barrels:
            if getattr(barrel, "gross_weight", None):
                total_gross += flt(barrel.gross_weight)
            if getattr(barrel, "tara_weight", None):
                total_tara += flt(barrel.tara_weight)
            if getattr(barrel, "net_weight", None):
                total_net += flt(barrel.net_weight)
            if getattr(barrel, "barrel_serial_number", None):
                barrel_count += 1

        self.total_gross_weight = total_gross
        self.total_tara_weight = total_tara
        self.total_net_weight = total_net
        self.barrel_count = barrel_count

    # -----------------------------
    # Golden number / naming
    # -----------------------------

    def set_batch_naming(self):
        """Generate golden number according to business rules (Level 1 only)."""
        # Only Level 1 should generate a new golden number
        level = str(self.custom_batch_level or "1")
        if level != "1":
            return

        if not self.item_to_manufacture:
            return

        product_code = (self.item_to_manufacture or "")[:4] or "0000"

        consecutive = "001"
        if self.work_order_ref:
            try:
                parts = self.work_order_ref.split("-")
                last_part = parts[-1]
                wo_consecutive = last_part[-3:] if last_part else "001"
                consecutive = wo_consecutive.zfill(3)
            except Exception:
                consecutive = "001"

        year = "24"
        if self.wo_start_date:
            try:
                if isinstance(self.wo_start_date, str):
                    wo_date = datetime.strptime(self.wo_start_date, "%Y-%m-%d")
                    year = str(wo_date.year)[-2:]
                else:
                    year = str(self.wo_start_date.year)[-2:]
            except Exception:
                year = datetime.now().strftime("%y")
        else:
            year = datetime.now().strftime("%y")

        plant_code = "1"
        if self.production_plant:
            try:
                plant_doc = frappe.get_doc("Production Plant AMB", self.production_plant)

                if (
                    hasattr(plant_doc, "production_plant_id")
                    and plant_doc.production_plant_id
                ):
                    plant_code = str(plant_doc.production_plant_id)
                else:
                    plant_mapping = {
                        "Mix": "1",
                        "Dry": "2",
                        "Juice": "3",
                        "Laboratory": "4",
                        "Formulated": "5",
                    }
                    plant_name = getattr(
                        plant_doc, "production_plant_name", ""
                    ) or ""
                    for plant_type, code in plant_mapping.items():
                        if plant_type.lower() in plant_name.lower():
                            plant_code = code
                            break
            except Exception:
                plant_mapping = {
                    "Mix": "1",
                    "Dry": "2",
                    "Juice": "3",
                    "Laboratory": "4",
                    "Formulated": "5",
                }
                for plant_type, code in plant_mapping.items():
                    if plant_type.lower() in (self.production_plant or "").lower():
                        plant_code = code
                        break

        # Fallback: extract plant_code from production_plant_name (e.g. "3 (Juice)")
        if plant_code == "1" and getattr(self, "production_plant_name", None):
            plant_match = re.match(r"(\d+)", str(self.production_plant_name))
            if plant_match:
                plant_code = plant_match.group(1)

        base_golden_number = f"{product_code}{consecutive}{year}{plant_code}"

        # Only set golden number fields here, NOT the title
        self.custom_golden_number = base_golden_number
        self.custom_generated_batch_name = base_golden_number

        # Decompose golden number into component fields
        self.custom_product_family = product_code[:2] or "00"
        self.custom_consecutive = consecutive
        self.custom_subfamily = product_code[2:4] or "00"


    def update_container_sequence(self):
        """Update container sequence"""
        if not self.container_barrels:
            return
        for idx, container in enumerate(self.container_barrels, 1):
            container.idx = idx
    def decompose_golden_number(self):
        """Golden Number format: PPPPAAAYYX
          PPPP = product_code (first 4 chars of item_to_manufacture)
          AAA  = consecutive (3 digits from WO)
          YY   = year (2 digits)
          X    = plant_code (1+ digits)
        """
        gn = self.custom_golden_number
        if not gn or len(gn) < 8:
            return
        try:
            self.custom_product_family = gn[:4]
            self.custom_consecutive = gn[4:7]
            self.custom_subfamily = gn[7:9]  # YY (2-digit year)
        except Exception:
            pass
    
    # -----------------------------
    # External sync / stubs
    # -----------------------------

    def sync_with_lote_amb(self):
        """Sync with Lote AMB"""
        pass

    def update_work_order_status(self):
        """Update work order status"""
        pass

    def log_batch_history(self):
        """Log batch history"""
        pass

    def create_stock_entry(self):
        """Create stock entry"""
        pass

    def create_lote_amb_if_needed(self):
        """Create Lote AMB"""
        pass

    def cancel_stock_entries(self):
        """Cancel stock entries"""
        pass

    def update_batch_status(self, status):
        """Update status"""
        self.db_set("batch_status", status)

    def notify_stakeholders(self):
        """Notify stakeholders"""
        pass

    def update_planned_qty_from_work_order(self):
        """Update planned_qty from Work Order"""
        try:
            work_order_name = None

            if self.work_order_ref:
                work_order_name = self.work_order_ref
            elif self.work_order:
                work_order_name = self.work_order

            if work_order_name:
                wo_doc = frappe.get_doc("Work Order", work_order_name)
                if hasattr(wo_doc, "qty") and wo_doc.qty and flt(wo_doc.qty) > 0:
                    self.planned_qty = flt(wo_doc.qty)
                    return True
        except Exception:
            frappe.log_error(
                f"Error updating planned_qty from work order: {str(frappe.get_traceback())}"
            )
        return False

    def update_processing_timestamps(self):
        """Automatically update timestamps based on status changes"""
        if hasattr(self, "processing_status") and self.has_value_changed(
            "processing_status"
        ):
            current_status = self.processing_status

            if current_status == "In Progress" and not self.actual_start:
                self.actual_start = now_datetime()

            if current_status in ["Quality Check", "Completed"] and not self.actual_completion:
                self.actual_completion = now_datetime()

            if current_status == "In Progress" and self.actual_completion:
                self.actual_completion = None

            if current_status in ["Draft", "Cancelled"]:
                if self.actual_start:
                    self.actual_start = None
                if self.actual_completion:
                    self.actual_completion = None

    def update_work_order_processing_status(self):
        """Sync processing status with linked Work Order"""
        if (
            hasattr(self, "work_order_ref")
            and self.work_order_ref
            and hasattr(self, "processing_status")
        ):
            try:
                wo = frappe.get_doc("Work Order", self.work_order_ref)
                status_map = {
                    "Draft": "Draft",
                    "Scheduled": "Not Started",
                    "In Progress": "In Process",
                    "Quality Check": "In Process",
                    "Completed": "Completed",
                    "On Hold": "On Hold",
                    "Cancelled": "Cancelled",
                }

                wo_status = status_map.get(self.processing_status, wo.status)
                if wo.status != wo_status:
                    wo.db_set("status", wo_status)
                    frappe.db.commit()
            except Exception as e:
                frappe.log_error(f"Error updating Work Order status: {str(e)}")

    # -----------------------------
    # Instance whitelisted methods
    # -----------------------------

    @frappe.whitelist()
    def start_processing(self):
        """Method to start processing"""
        if not frappe.has_permission("Batch AMB", "write"):
            frappe.throw(_("No permission to process Batch AMB"), frappe.PermissionError)
        if self.processing_status in ["Draft", "Scheduled"]:
            self.processing_status = "In Progress"
            self.actual_start = now_datetime()
            self.save()
            frappe.msgprint(_("Processing started successfully"))
            return True
        frappe.msgprint(
            _("Cannot start processing from current status: {0}").format(
                self.processing_status
            )
        )
        return False

    @frappe.whitelist()
    def pause_processing(self):
        """Method to pause processing"""
        if not frappe.has_permission("Batch AMB", "write"):
            frappe.throw(_("No permission to process Batch AMB"), frappe.PermissionError)
        if self.processing_status == "In Progress":
            self.processing_status = "On Hold"
            self.save()
            frappe.msgprint(_("Processing paused"))
            return True
        frappe.msgprint(_("Cannot pause processing from current status"))
        return False

    @frappe.whitelist()
    def resume_processing(self):
        """Method to resume processing"""
        if not frappe.has_permission("Batch AMB", "write"):
            frappe.throw(_("No permission to process Batch AMB"), frappe.PermissionError)
        if self.processing_status == "On Hold":
            self.processing_status = "In Progress"
            self.save()
            frappe.msgprint(_("Processing resumed"))
            return True
        frappe.msgprint(_("Cannot resume processing from current status"))
        return False

    @frappe.whitelist()
    def complete_processing(self):
        """Method to complete processing (move to Quality Check)"""
        if not frappe.has_permission("Batch AMB", "write"):
            frappe.throw(_("No permission to process Batch AMB"), frappe.PermissionError)
        if self.processing_status == "In Progress":
            self.processing_status = "Quality Check"
            self.actual_completion = now_datetime()
            self.save()
            frappe.msgprint(
                _("Processing completed, ready for quality check")
            )
            return True
        frappe.msgprint(_("Cannot complete processing from current status"))
        return False

    @frappe.whitelist()
    def approve_quality(self):
        """Method to approve quality check"""
        if not frappe.has_permission("Batch AMB", "write"):
            frappe.throw(_("No permission to process Batch AMB"), frappe.PermissionError)
        if self.processing_status == "Quality Check":
            self.processing_status = "Completed"
            if hasattr(self, "quality_status"):
                self.quality_status = "Passed"
            self.save()
            frappe.msgprint(_("Quality check approved, batch completed"))
            return True
        frappe.msgprint(_("Cannot approve quality from current status"))
        return False

    @frappe.whitelist()
    def reject_quality(self):
        """Method to reject quality check"""
        if not frappe.has_permission("Batch AMB", "write"):
            frappe.throw(_("No permission to process Batch AMB"), frappe.PermissionError)
        if self.processing_status == "Quality Check":
            self.processing_status = "On Hold"
            if hasattr(self, "quality_status"):
                self.quality_status = "Failed"
            self.save()
            frappe.msgprint(_("Quality check rejected, batch on hold"))
            return True
        frappe.msgprint(_("Cannot reject quality from current status"))
        return False

    @frappe.whitelist()
    def cancel_processing(self):
        """Method to cancel processing"""
        if not frappe.has_permission("Batch AMB", "write"):
            frappe.throw(_("No permission to process Batch AMB"), frappe.PermissionError)
        if self.processing_status not in ["Completed", "Cancelled"]:
            self.processing_status = "Cancelled"
            self.save()
            frappe.msgprint(_("Processing cancelled"))
            return True
        frappe.msgprint(_("Cannot cancel processing from current status"))
        return False

    @frappe.whitelist()
    def schedule_processing(self, start_date, start_time=None):
        """Method to schedule processing"""
        if not frappe.has_permission("Batch AMB", "write"):
            frappe.throw(_("No permission to process Batch AMB"), frappe.PermissionError)
        if self.processing_status == "Draft":
            self.processing_status = "Scheduled"
            self.scheduled_start_date = start_date
            if start_time:
                self.scheduled_start_time = start_time
            self.save()
            frappe.msgprint(_("Processing scheduled for {0}").format(start_date))
            return True
        frappe.msgprint(_("Cannot schedule processing from current status"))
        return False

    @frappe.whitelist()
    def get_processing_timeline(self):
        """Get processing timeline for reporting"""
        timeline = []

        if self.actual_start:
            timeline.append(
                {
                    "event": "Processing Started",
                    "timestamp": self.actual_start,
                    "status": "In Progress",
                }
            )

        if self.actual_completion:
            timeline.append(
                {
                    "event": "Processing Completed",
                    "timestamp": self.actual_completion,
                    "status": "Quality Check",
                }
            )

        try:
            from frappe.desk.form.load import get_versions

            versions = get_versions(self.doctype, self.name)

            for version in versions:
                data = version.get("data")
                if data and "processing_status" in data:
                    timeline.append(
                        {
                            "event": f"Status changed to {data['processing_status']}",
                            "timestamp": version.get("creation"),
                            "status": data["processing_status"],
                        }
                    )
        except Exception:
            pass

        timeline.sort(key=lambda x: x["timestamp"] or "")

        return timeline

    @frappe.whitelist()
    def fixed_generate_serial_numbers(self, quantity=5, prefix=None):
        """
        Generate serial numbers for this batch.
        Called from client-side.
        """
        if not frappe.has_permission("Batch AMB", "write"):
            frappe.throw(_("No permission to modify Batch AMB"), frappe.PermissionError)
        try:
            # Your real logic here...
            return {
                "status": "success",
                "message": f"Generated {quantity} serial numbers",
                "batch_name": self.name,
            }
        except Exception as e:
            frappe.log_error(
                f"Error in fixed_generate_serial_numbers: {str(e)}"
            )
            frappe.throw(_("Error generating serial numbers: {0}").format(str(e)))

    @frappe.whitelist()
    def get_processing_metrics(self):
        """Get processing metrics for analytics"""
        if not frappe.has_permission("Batch AMB", "read"):
            frappe.throw(_("No permission to read Batch AMB"), frappe.PermissionError)
        metrics = {
            "planned_quantity": self.planned_qty
            if hasattr(self, "planned_qty")
            else 0,
            "processed_quantity": self.processed_quantity
            if hasattr(self, "processed_quantity")
            else 0,
            "yield_percentage": self.yield_percentage
            if hasattr(self, "yield_percentage")
            else 0,
            "processing_status": self.processing_status
            if hasattr(self, "processing_status")
            else "Draft",
            "quality_status": self.quality_status
            if hasattr(self, "quality_status")
            else "Pending",
            "schedule_adherence": self.calculate_schedule_adherence(),
            "efficiency": self.calculate_efficiency(),
        }

        return metrics

    def calculate_schedule_adherence(self):
        """Calculate how well processing adhered to schedule"""
        if not self.scheduled_start_date or not self.actual_start:
            return 0

        scheduled = getdate(self.scheduled_start_date)
        actual = getdate(self.actual_start)

        if scheduled == actual:
            return 100
        elif actual > scheduled:
            days_late = (actual - scheduled).days
            return max(0, 100 - (days_late * 10))
        else:
            days_early = (scheduled - actual).days
            return min(100 + (days_early * 5), 120)

    def calculate_efficiency(self):
        """Calculate processing efficiency"""
        if not self.actual_start or not self.actual_completion:
            return 0

        start = get_datetime(self.actual_start)
        end = get_datetime(self.actual_completion)

        processing_time = (end - start).total_seconds() / 3600

        if (
            hasattr(self, "processed_quantity")
            and self.processed_quantity
            and processing_time > 0
        ):
            efficiency = flt(self.processed_quantity) / processing_time * 100
            return min(efficiency, 200)

        return 0


# ==================== MANUFACTURING BUTTON METHODS ====================


@frappe.whitelist()
def create_bom_with_wizard(batch_name, options=None):
    """Create BOM with wizard options - MAIN MANUFACTURING BUTTON - FIXED VERSION"""
    if not frappe.has_permission("Batch AMB", "write"):
        frappe.throw(_("No permission to modify Batch AMB"), frappe.PermissionError)
    try:
        batch = frappe.get_doc("Batch AMB", batch_name)

        if not batch.item_to_manufacture:
            return {"success": False, "message": "No item to manufacture specified"}

        if options and isinstance(options, str):
            options = json.loads(options)
        options = options or {}

        bom_quantity = (
            batch.planned_qty
            or batch.batch_quantity
            or batch.total_net_weight
            or 1000
        )

        item = frappe.get_doc("Item", batch.item_to_manufacture)
        uom = item.stock_uom

        existing_bom = frappe.db.get_value(
            "BOM",
            {"item": batch.item_to_manufacture, "is_active": 1},
            "name",
        )

        if existing_bom:
            return {
                "success": True,
                "bom_name": existing_bom,
                "item_code": batch.item_to_manufacture,
                "qty": bom_quantity,
                "uom": uom,
                "item_count": 1,
                "exists": True,
                "message": f"BOM already exists: {existing_bom}",
            }

        bom_data = {
            "item": batch.item_to_manufacture,
            "quantity": bom_quantity,
            "uom": uom,
            "is_active": 1,
            "is_default": 1,
            "with_operations": 0,
            "currency": "MXN",
            "company": "AMB-Wellness",
            "custom_golden_number": batch.custom_golden_number,
            "custom_batch_reference": batch.name,
        }

        bom = frappe.new_doc("BOM")
        bom.update(bom_data)

        if frappe.db.exists("Item", "M033"):
            bom.append(
                "items",
                {
                    "item_code": "M033",
                    "item_name": "Aloe Vera Gel",
                    "qty": bom_quantity * 0.05,
                    "uom": "Kg",
                    "rate": 0,
                },
            )
        else:
            bom.append(
                "items",
                {
                    "item_code": "0202",
                    "qty": bom_quantity * 0.05,
                    "uom": "Kg",
                    "rate": 0,
                },
            )
        if options.get("include_packaging", 1):
            packaging_item = options.get("primary_packaging", "E001")
            if frappe.db.exists("Item", packaging_item):
                packages_count = options.get("packages_count", 1)
                bom.append(
                    "items",
                    {
                        "item_code": packaging_item,
                        "qty": packages_count,
                        "uom": "Nos",
                        "rate": 0,
                    },
                )
        bom.insert()
        frappe.db.commit()

        return {
            "success": True,
            "bom_name": bom.name,
            "item_code": batch.item_to_manufacture,
            "qty": bom_quantity,
            "uom": uom,
            "item_count": len(bom.items),
            "exists": False,
            "message": f"BOM created successfully: {bom.name}",
        }

    except Exception as e:
        frappe.log_error(f"BOM Creation Error for {batch_name}: {str(e)}")
        return {"success": False, "message": f"Error creating BOM: {str(e)}"}


@frappe.whitelist()
def create_work_order_from_batch(batch_name):
    """Create Work Order from Batch"""
    if not frappe.has_permission("Batch AMB", "write"):
        frappe.throw(_("No permission to create Work Order for Batch AMB"), frappe.PermissionError)
    try:
        batch = frappe.get_doc("Batch AMB", batch_name)

        if not batch.item_to_manufacture:
            return {"success": False, "message": "No item to manufacture specified"}

        wo = frappe.new_doc("Work Order")
        wo.production_item = batch.item_to_manufacture
        wo.qty = batch.planned_qty or batch.batch_quantity or 1
        wo.bom_no = batch.bom_template
        wo.planned_start_date = batch.production_start_date
        wo.company = batch.company or frappe.defaults.get_user_default("Company")

        wo.insert()

        batch.work_order_ref = wo.name
        batch.save()

        return {
            "success": True,
            "work_order": wo.name,
            "message": f"Work Order {wo.name} created successfully",
        }

    except Exception as e:
        frappe.log_error(f"Work Order Creation Error: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def assign_golden_number_to_batch(batch_name):
    """Manual trigger for Golden Number assignment"""
    if not frappe.has_permission("Batch AMB", "write"):
        frappe.throw(_("No permission to modify Batch AMB"), frappe.PermissionError)
    try:
        batch = frappe.get_doc("Batch AMB", batch_name)

        if not batch.custom_golden_number:
            golden_number = "".join(random.choices(string.digits, k=10))
            batch.custom_golden_number = golden_number
            batch.save()

            return {
                "success": True,
                "golden_number": batch.custom_golden_number,
                "message": f"Golden Number {batch.custom_golden_number} assigned successfully",
            }

        return {
            "success": True,
            "golden_number": batch.custom_golden_number,
            "message": f"Golden Number already assigned: {batch.custom_golden_number}",
        }

    except Exception as e:
        frappe.log_error(f"Golden Number Assignment Error: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def update_planned_qty_from_work_order(batch_name):
    """Manual trigger to update planned quantity from Work Order"""
    if not frappe.has_permission("Batch AMB", "write"):
        frappe.throw(_("No permission to modify Batch AMB"), frappe.PermissionError)
    try:
        batch = frappe.get_doc("Batch AMB", batch_name)

        work_order_name = None
        if batch.work_order_ref:
            work_order_name = batch.work_order_ref
        elif batch.work_order:
            work_order_name = batch.work_order

        if work_order_name:
            wo = frappe.get_doc("Work Order", work_order_name)
            batch.planned_qty = wo.qty
            batch.save()

            return {
                "success": True,
                "planned_qty": batch.planned_qty,
                "message": f"Planned quantity updated to {batch.planned_qty}",
            }
        else:
            return {
                "success": False,
                "message": "No work order linked to this batch",
            }

    except Exception as e:
        frappe.log_error(f"Planned Qty Update Error: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def calculate_batch_cost(batch_name):
    """Calculate batch cost for the Calculate Cost button"""
    if not frappe.has_permission("Batch AMB", "read"):
        frappe.throw(_("No permission to read Batch AMB"), frappe.PermissionError)
    try:
        batch = frappe.get_doc("Batch AMB", batch_name)

        material_cost = batch.material_cost or 0
        labor_cost = batch.labor_cost or 0
        overhead_cost = batch.overhead_cost or 0

        total_batch_cost = material_cost + labor_cost + overhead_cost

        batch_quantity = batch.batch_quantity or 1
        cost_per_unit = (
            total_batch_cost / batch_quantity if batch_quantity > 0 else 0
        )

        return {
            "total_batch_cost": total_batch_cost,
            "cost_per_unit": cost_per_unit,
        }

    except Exception as e:
        frappe.log_error(f"Batch Cost Calculation Error: {str(e)}")
        return {"total_batch_cost": 0, "cost_per_unit": 0}


@frappe.whitelist()
def duplicate_batch(source_name):
    """Duplicate a batch - for Duplicate Batch button"""
    if not frappe.has_permission("Batch AMB", "create"):
        frappe.throw(_("No permission to create Batch AMB"), frappe.PermissionError)
    try:
        source_batch = frappe.get_doc("Batch AMB", source_name)
        new_batch = frappe.copy_doc(source_batch)

        new_batch.work_order_ref = None
        new_batch.stock_entry_reference = None
        new_batch.lote_amb_reference = None
        new_batch.custom_generated_batch_name = None
        new_batch.custom_golden_number = None

        new_batch.insert()

        return new_batch.name

    except Exception as e:
        frappe.log_error(f"Batch Duplication Error: {str(e)}")
        frappe.throw(_("Error duplicating batch: {0}").format(str(e)))


@frappe.whitelist()
def check_bom_exists(batch_name):
    """Check if BOM already exists for this batch"""
    if not frappe.has_permission("Batch AMB", "read"):
        frappe.throw(_("No permission to read Batch AMB"), frappe.PermissionError)
    batch = frappe.get_doc("Batch AMB", batch_name)

    existing_bom = frappe.db.get_value(
        "BOM Creator", {"project": batch_name}, ["name", "item_code"]
    )

    if existing_bom:
        return {
            "exists": True,
            "bom_name": existing_bom[0],
            "item_code": existing_bom[1],
        }

    return {"exists": False}


@frappe.whitelist()
def get_work_order_details(work_order):
    """Get work order details"""
    wo = frappe.get_doc("Work Order", work_order)
    return {
        "item_to_manufacture": wo.production_item,
        "planned_qty": wo.qty,
        "company": wo.company,
    }


@frappe.whitelist()
def get_available_containers(warehouse=None):
    """Get available containers"""
    if not frappe.has_permission("Batch AMB", "read"):
        frappe.throw(_("No permission to read Batch AMB"), frappe.PermissionError)
    return []


@frappe.whitelist()
def get_running_batch_announcements(
    include_companies=True, include_plants=True, include_quality=True
):
    """Get running batch announcements for widget"""
    if not frappe.has_permission("Batch AMB", "read"):
        frappe.throw(_("No permission to read Batch AMB"), frappe.PermissionError)
    try:
        batches = frappe.get_all(
            "Batch AMB",
            filters={"docstatus": ["!=", 2]},
            fields=[
                "name",
                "title",
                "item_to_manufacture",
                "item_code",
                "wo_item_name",
                "quality_status",
                "target_plant",
                "production_plant_name",
                "custom_plant_code",
                "custom_batch_level",
                "barrel_count",
                "total_net_weight",
                "wo_start_date",
                "modified",
                "creation",
                "work_order_ref",
                "custom_golden_number",
            ],
            order_by="modified desc",
            limit=50,
        )

        if not batches:
            return {
                "success": True,
                "message": "No active batches",
                "announcements": [],
                "grouped_announcements": {},
                "stats": {"total": 0},
            }

        announcements = []
        grouped = {}
        stats = {
            "total": len(batches),
            "high_priority": 0,
            "quality_check": 0,
            "container_level": 0,
        }

        for batch in batches:
            company = (
                batch.production_plant_name or batch.target_plant or "Unknown"
            )

            announcement = {
                "name": batch.name,
                "title": batch.title or batch.name,
                "batch_code": batch.name,
                "item_code": batch.item_to_manufacture
                or batch.item_code
                or "N/A",
                "status": "Active",
                "company": company,
                "level": batch.custom_batch_level or "Batch",
                "priority": "high"
                if batch.quality_status == "Failed"
                else "medium",
                "quality_status": batch.quality_status or "Pending",
                "content": (
                    f"Item: {batch.wo_item_name or batch.item_code or 'N/A'}\n"
                    f"Plant: {batch.custom_plant_code or 'N/A'}\n"
                    f"Weight: {batch.total_net_weight or 0}\n"
                    f"Barrels: {batch.barrel_count or 0}"
                ),
                "message": f"Level {batch.custom_batch_level or '?'} batch in production",
                "modified": str(batch.modified) if batch.modified else "",
                "creation": str(batch.creation) if batch.creation else "",
                "batch_name": batch.name,
                "work_order": batch.work_order_ref or "N/A",
                "plant": batch.custom_plant_code
                or batch.production_plant_name
                or "N/A",
                "golden_number": batch.custom_golden_number or "",
            }

            announcements.append(announcement)

            if batch.quality_status == "Failed":
                stats["high_priority"] += 1
            if batch.quality_status in ["Pending", "In Testing"]:
                stats["quality_check"] += 1
            if batch.custom_batch_level == "3":
                stats["container_level"] += 1

            if include_companies:
                plant = batch.custom_plant_code or "1"
                if company not in grouped:
                    grouped[company] = {}
                if plant not in grouped[company]:
                    grouped[company][plant] = []
                grouped[company][plant].append(announcement)

        return {
            "success": True,
            "announcements": announcements,
            "grouped_announcements": grouped,
            "stats": stats,
        }

    except Exception as e:
        import traceback

        frappe.log_error(
            f"Widget error: {str(e)}\n{traceback.format_exc()}",
            "Batch Widget Error",
        )
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to load batch data",
        }


@frappe.whitelist()
def get_packaging_from_sales_order(batch_name):
    """Get packaging info from Sales Order and map to Item Codes"""
    if not frappe.has_permission("Batch AMB", "read"):
        frappe.throw(_("No permission to read Batch AMB"), frappe.PermissionError)
    try:
        batch = frappe.get_doc("Batch AMB", batch_name)

        sales_order = None

        if getattr(batch, "sales_order_related", None):
            sales_order = batch.sales_order_related

        if not sales_order and batch.work_order_ref:
            try:
                wo = frappe.get_doc("Work Order", batch.work_order_ref)
                if hasattr(wo, "sales_order") and wo.sales_order:
                    sales_order = wo.sales_order
            except Exception as e:
                frappe.log_error(f"Error fetching WO sales order: {str(e)}")

        if not sales_order and batch.item_to_manufacture:
            try:
                wo_list = frappe.get_all(
                    "Work Order",
                    filters={
                        "production_item": batch.item_to_manufacture,
                        "docstatus": ["!=", 2],
                    },
                    fields=["name", "sales_order"],
                    order_by="creation desc",
                    limit=1,
                )
                if wo_list and wo_list[0].get("sales_order"):
                    sales_order = wo_list[0]["sales_order"]
            except Exception as e:
                frappe.log_error(
                    f"Error searching WO for sales order: {str(e)}"
                )

        if not sales_order:
            return {
                "success": False,
                "message": "No Sales Order linked to this batch",
                "primary": None,
                "secondary": None,
                "net_weight": 0,
                "packages_count": 1,
            }

        so = frappe.get_doc("Sales Order", sales_order)

        primary_item = map_packaging_text_to_item(so.custom_tipo_empaque)
        secondary_item = (
            map_packaging_text_to_item(so.empaque_secundario)
            if so.empaque_secundario
            else None
        )

        net_weight = (
            parse_weight_from_text(so.custom_peso_neto)
            if so.custom_peso_neto
            else 220
        )

        total_weight = (
            batch.total_net_weight or batch.total_quantity or 1000
        )
        packages_count = (
            int(total_weight / net_weight) if net_weight > 0 else 1
        )

        return {
            "success": True,
            "primary": primary_item,
            "primary_name": frappe.db.get_value(
                "Item", primary_item, "item_name"
            )
            if primary_item
            else None,
            "primary_text": so.custom_tipo_empaque,
            "secondary": secondary_item,
            "secondary_name": frappe.db.get_value(
                "Item", secondary_item, "item_name"
            )
            if secondary_item
            else None,
            "secondary_text": so.empaque_secundario,
            "net_weight": net_weight,
            "packages_count": packages_count,
            "sales_order": so.name,
        }

    except Exception as e:
        frappe.log_error(
            f"Error getting packaging: {str(e)}", "Packaging Fetch Error"
        )
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to fetch packaging: {str(e)}",
        }


def map_packaging_text_to_item(packaging_text):
    """Smart mapping from free text to Item Code"""
    if not packaging_text:
        return None

    text_lower = packaging_text.lower()

    PACKAGING_MAP = {
        "220l": "E001",
        "220 l": "E001",
        "barrel blue": "E001",
        "barrel 220": "E001",
        "polyethylene barrel": "E002",
        "reused barrel": "E002",
        "25kg": "E003",
        "25 kg": "E003",
        "25kg drum": "E003",
        "drum 25": "E003",
        "10kg": "E004",
        "10 kg": "E004",
        "10kg drum": "E004",
        "drum 10": "E004",
        "20l": "E005",
        "20 l": "E005",
        "jug": "E005",
        "white jug": "E005",
        "tarima": "E006",
        "pallet 44": "E006",
        "pino real": "E006",
        "euro pallet": "E007",
        "euro": "E007",
        "reused pallet": "E008",
        "44x44": "E008",
        "bolsa": "E009",
        "poly bag": "E009",
        "polietileno": "E009",
        "30x60": "E009",
        "bag": "E009",
    }

    for keyword, item_code in PACKAGING_MAP.items():
        if keyword in text_lower:
            return item_code

    items = frappe.get_all(
        "Item",
        filters={
            "item_group": [
                "in",
                [
                    "FG Packaging Materials",
                    "SFG Packaging Materials",
                    "Raw Materials",
                ],
            ],
            "disabled": 0,
            "item_name": ["like", f"%{packaging_text.split()[0]}%"],
        },
        fields=["name", "item_name"],
        limit=1,
    )

    if items:
        return items[0].name

    return "E001"


def parse_weight_from_text(weight_text):
    """Parse weight from text like '5 Kg', '220', '10.5 kg'"""
    if not weight_text:
        return 0

    numbers = re.findall(r"\d+\.?\d*", str(weight_text))

    if numbers:
        return float(numbers[0])

    return 0


@frappe.whitelist()
def generate_batch_code(parent_batch=None, batch_level=None, work_order=None):
    """Generate batch code for automatic naming"""
    if not frappe.has_permission("Batch AMB", "read"):
        frappe.throw(_("No permission to access Batch AMB"), frappe.PermissionError)
    try:
        if batch_level == "1":
            code = f"BATCH-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
        elif batch_level == "2" and parent_batch:
            parent_code = frappe.db.get_value(
                "Batch AMB", parent_batch, "custom_generated_batch_name"
            ) or "PARENT"
            code = f"{parent_code}-SUB"
        elif batch_level == "3" and parent_batch:
            parent_code = frappe.db.get_value(
                "Batch AMB", parent_batch, "custom_generated_batch_name"
            ) or "PARENT"
            code = f"{parent_code}-CONT"
        else:
            code = f"BATCH-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"

        return {"code": code}

    except Exception as e:
        frappe.log_error(f"Batch Code Generation Error: {str(e)}")
        return {"code": f"BATCH-ERROR-{str(e)[:10]}"}


@frappe.whitelist()
def get_work_order_data(work_order):
    """Get work order data for batch reference"""
    if not frappe.has_permission("Batch AMB", "read"):
        frappe.throw(_("No permission to read Batch AMB"), frappe.PermissionError)
    try:
        wo = frappe.get_doc("Work Order", work_order)
        return {
            "production_item": wo.production_item,
            "qty": wo.qty,
            "bom_no": wo.bom_no,
            "company": wo.company,
            "status": wo.status,
            "planned_start_date": wo.planned_start_date,
            "item_name": wo.item_name,
            "custom_plant_code": getattr(wo, "custom_plant_code", ""),
            "sales_order": getattr(wo, "sales_order", ""),
            "project": getattr(wo, "project", ""),
        }
    except Exception as e:
        frappe.log_error(f"Work Order Data Error: {str(e)}")
        return None


# ============================================
# SERIAL TRACKING INTEGRATION METHODS
# ============================================


@frappe.whitelist()
def schedule_batch(batch_name, scheduled_start):
    """Schedule a batch for processing"""
    if not frappe.has_permission("Batch AMB", "write"):
        frappe.throw(_("No permission to modify Batch AMB"), frappe.PermissionError)
    batch = frappe.get_doc("Batch AMB", batch_name)
    batch.scheduled_start_date = scheduled_start
    batch.processing_status = "Scheduled"
    batch.save()
    return {"status": "success", "message": f"Batch {batch_name} scheduled"}


@frappe.whitelist()
def start_batch_processing(batch_name):
    """Start processing a batch"""
    if not frappe.has_permission("Batch AMB", "write"):
        frappe.throw(_("No permission to modify Batch AMB"), frappe.PermissionError)
    batch = frappe.get_doc("Batch AMB", batch_name)
    batch.processing_status = "In Progress"
    batch.actual_start = now_datetime()
    batch.save()
    return {"status": "success", "message": f"Batch {batch_name} started"}


@frappe.whitelist()
def complete_batch_processing(batch_name, processed_quantity=None):
    """Complete batch processing"""
    if not frappe.has_permission("Batch AMB", "write"):
        frappe.throw(_("No permission to modify Batch AMB"), frappe.PermissionError)
    batch = frappe.get_doc("Batch AMB", batch_name)
    batch.processing_status = "Completed"
    batch.actual_completion = now_datetime()
    if processed_quantity:
        batch.processed_quantity = processed_quantity
    batch.save()
    return {"status": "success", "message": f"Batch {batch_name} completed"}

@frappe.whitelist()
def resolve_container_prefix(batch, default_prefix=None):
    """Resolve container prefix (BRL / IBC / CTE / SMP) based on packaging/plant.

    For now this is hardcoded mapping; later we can move it to a DocType.
    """
    if not frappe.has_permission("Batch AMB", "read"):
        frappe.throw(_("No permission to read Batch AMB"), frappe.PermissionError)
    # Try from default_packaging_type + plant
    packaging_item = getattr(batch, "default_packaging_type", None) or ""
    plant_name = (batch.production_plant_name or "").lower()

    # Simple heuristic mapping – replace with DocType lookup later
    # BRL: barrels / juice
    # IBC: IBC containers
    # CTE: cuñete / drum
    # SMP: sample bags
    prefix = None

    if "ibc" in packaging_item.lower():
        prefix = "IBC"
    elif any(k in packaging_item.lower() for k in ["smp", "sample", "bag", "bolsa"]):
        prefix = "SMP"
    elif any(k in packaging_item.lower() for k in ["cte", "cunete", "cuñete", "drum"]):
        prefix = "CTE"
    elif any(k in plant_name for k in ["juice", "3 (juice)", "3 ( jugo )"]):
        prefix = "BRL"

    # Fallback
    return prefix or default_prefix


@frappe.whitelist()
def generate_serial_numbers(batch_name, quantity=1, prefix=None):
    """Generate serial numbers for batch and add to container_barrels table.

    Serial format (golden hierarchy):
      Level 3/4: <PREFIX>-<GoldenChain>-<NNN>
      where GoldenChain = title (e.g. 0334925261-1-C1) and NNN is 001..999
    """
    if not frappe.has_permission("Batch AMB", "write"):
        frappe.throw(_("No permission to modify Batch AMB"), frappe.PermissionError)
    try:
        batch = frappe.get_doc("Batch AMB", batch_name)

        if isinstance(quantity, str):
            quantity = int(quantity)

        batch_level = batch.custom_batch_level or "1"

        # Use hierarchical title as base (e.g. 0334925261-1-C1)
        # FIXED: Use only title, no prefix
        base_title = batch.title or batch.name

        # Collect existing serials in the child table
        existing_serials = []
        for row in batch.container_barrels:
            if row.barrel_serial_number and row.barrel_serial_number.strip():
                existing_serials.append(row.barrel_serial_number.strip())

        existing_count = len(existing_serials)
        new_serials = []

        for i in range(quantity):
            seq_num = existing_count + i + 1
            # SIMPLE FORMAT: {title}-{sequential_number:03d}
            serial = f"{base_title}-{seq_num:03d}"
            if len(serial) > 50:
                serial = serial[:50]
            new_serials.append(serial)
            row_data = {
                "barrel_serial_number": serial,
                "status": "New",
                "packaging_type": batch.default_packaging_type or "",
                "gross_weight": 0.0,
                "tara_weight": 0.0,
                "net_weight": 0.0,
                "weight_validated": 0,
            }
            batch.append("container_barrels", row_data)

        # Persist a newline list of serials (for non-Level 4 batches)
        if batch_level != "4":
            existing_text = []
            if batch.custom_serial_numbers:
                existing_text = [
                    s.strip()
                    for s in batch.custom_serial_numbers.split("\n")
                    if s.strip()
                ]

            all_text = existing_text + new_serials
            truncated_text = []
            for text in set(all_text):
                if len(text) > 140:
                    truncated_text.append(text[:140])
                else:
                    truncated_text.append(text)

            batch.custom_serial_numbers = "\n".join(sorted(truncated_text))
            batch.custom_last_api_sync = now_datetime()
            batch.custom_serial_tracking_integrated = 1

        # NOTE: Server Script 'validate_var_code39_ok' must be DISABLED in production.
        # The flag below is a safety net - we bypass validation entirely during serial generation.
        # This prevents the Server Script from running on this specific save.
        batch.flags.do_not_validate = True
        batch.flags.ignore_permissions = True
        batch.flags.ignore_mandatory = True
        batch.save()
        batch.flags.do_not_validate = False
        frappe.flags.ignore_permissions = False
        frappe.db.commit()

        return {
            "status": "success",
            "message": f"Generated {len(new_serials)} serial numbers",
            "count": len(new_serials),
            "serial_numbers": new_serials,
        }

    except Exception as e:
        error_msg = f"Error generating serials for {batch_name[:30]}"
        frappe.log_error(
            title=error_msg,
            message=f"Details: {str(e)[:100]}...",
        )
        frappe.throw(_("Failed to generate serial numbers: {0}").format(str(e)[:200]))


@frappe.whitelist()
def integrate_serial_tracking(batch_name):
    """Integrate serial tracking using the real generate_serial_numbers"""
    if not frappe.has_permission("Batch AMB", "write"):
        frappe.throw(_("No permission to modify Batch AMB"), frappe.PermissionError)
    try:
        batch = frappe.get_doc("Batch AMB", batch_name)
        default_qty = int(batch.planned_qty or 5)
        prefix = resolve_container_prefix(batch, default_prefix=None)
        if batch.custom_batch_level == "4" and not prefix:
            prefix = "BRL"

        result = generate_serial_numbers(
            batch_name=batch_name,
            quantity=default_qty,
            prefix=prefix,
        )

        if result.get("status") == "success":
            return {
                "status": "success",
                "message": "Serial tracking integrated successfully",
                "serial_count": result.get("count", 0),
                "details": result,
            }
        else:
            return result
    except Exception as e:
        frappe.log_error(f"Integration error: {str(e)}")
        return {"status": "error", "message": f"Integration failed: {str(e)[:200]}"}
# ============================================
# QUICK ENTRY HELPER METHODS
# ============================================


@frappe.whitelist()
def get_sales_orders_with_work_orders():
    """Get Sales Orders that have linked Work Orders for Quick Entry dropdown."""
    if not frappe.has_permission("Batch AMB", "read"):
        frappe.throw(_("No permission to read Batch AMB"), frappe.PermissionError)
    try:
        work_orders = frappe.get_all(
            "Work Order",
            filters={
                "docstatus": ["!=", 2],
                "sales_order": ["is", "set"],
            },
            fields=["sales_order", "sales_order_item"],
            group_by="sales_order",
            order_by="creation desc",
            limit=50,
        )

        sales_orders = []
        seen = set()
        for wo in work_orders:
            so_name = wo.sales_order
            if so_name and so_name not in seen:
                seen.add(so_name)
                so = frappe.get_value(
                    "Sales Order",
                    so_name,
                    ["name", "customer_name", "transaction_date", "status"],
                    as_dict=True,
                )
                if so:
                    sales_orders.append(so)

        return {"success": True, "sales_orders": sales_orders}

    except Exception as e:
        frappe.log_error(f"Quick Entry - get_sales_orders error: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_work_orders_for_sales_order(sales_order):
    """
    Get Work Orders linked to a Sales Order for Quick Entry cascading.

    Args:
        sales_order: Sales Order name

    Returns:
        dict with work_orders list including production_item, qty, status, project
    """
    try:
        if not sales_order:
            return {"success": False, "message": "No Sales Order provided"}

        so_project = frappe.db.get_value("Sales Order", sales_order, "project")

        filters = {
            "docstatus": ["!=", 2],
            "status": ["not in", ["Stopped", "Cancelled"]],
        }

        if so_project:
            filters["project"] = so_project
        else:
            filters["sales_order"] = sales_order

        work_orders = frappe.get_all(
            "Work Order",
            filters=filters,
            fields=[
                "name",
                "production_item",
                "item_name",
                "qty",
                "status",
                "sales_order",
                "project",
                "planned_start_date",
                "actual_start_date",
                "custom_plant_code",
                "bom_no",
            ],
            order_by="creation desc",
            limit=50,
        )

        return {
            "success": True,
            "work_orders": work_orders,
            "project": so_project,
            "sales_order": sales_order,
        }

    except Exception as e:
        frappe.log_error(f"Quick Entry - get_work_orders error: {str(e)}")
        return {"success": False, "message": str(e)}




    @frappe.whitelist()
    def make_sample_request(self):
        """Create a Sample Request AMB pre-filled from this batch."""
        doc = frappe.new_doc("Sample Request AMB")
        doc.request_type = "External Analysis"
        doc.request_date = frappe.utils.nowdate()

        # Optional: map customer if your Batch AMB has it
        if self.customer:
            doc.customer = self.customer
            doc.customer_name = frappe.db.get_value("Customer", self.customer, "customer_name")

        # Add one sample line for this batch
        item_row = doc.append("samples", {})
        item_row.item = self.item  # adapt to your fieldnames
        item_row.description = self.item_name or ""
        item_row.batch = self.name  # Batch name
        item_row.samples_count = 1
        item_row.qty_per_sample = 1
        item_row.uom = self.stock_uom  # adapt if different

        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)

        return doc.name

#

#

@frappe.whitelist()
def get_quick_entry_defaults(work_order_name):
    """
    Get all defaults needed for Quick Entry from a Work Order.

    This is the main method called when user selects a Work Order
    in the Quick Entry popup. It returns all fields needed to
    create a valid Batch AMB with proper golden number generation.
    """
    if not frappe.has_permission("Batch AMB", "read"):
        frappe.throw(_("No permission to read Batch AMB"), frappe.PermissionError)
    try:
        if not work_order_name:
            return {"success": False, "message": "No Work Order provided"}

        wo = frappe.get_doc("Work Order", work_order_name)

        plant_code = ""
        production_plant = ""
        if hasattr(wo, "custom_plant_code") and wo.custom_plant_code:
            plant_code = wo.custom_plant_code
        if hasattr(wo, "production_plant") and wo.production_plant:
            production_plant = wo.production_plant

        return {
            "success": True,
            "work_order": wo.name,
            "production_item": wo.production_item,
            "item_name": wo.item_name,
            "qty": wo.qty,
            "sales_order": wo.sales_order or "",
            "project": wo.project or "",
            "bom_no": wo.bom_no or "",
            "planned_start_date": str(wo.planned_start_date)
            if wo.planned_start_date
            else "",
            "actual_start_date": str(wo.actual_start_date)
            if wo.actual_start_date
            else "",
            "company": wo.company or "",
            "plant_code": plant_code,
            "production_plant": production_plant,
            "status": wo.status,
        }

    except Exception as e:
        frappe.log_error(f"Quick Entry - get_defaults error: {str(e)}")
        return {"success": False, "message": str(e)}


# ==================== SAMPLE REQUEST BUTTON ==================== 


@frappe.whitelist()
def create_sample_request(batch_name):
    """Create Sample Request from Batch - for the Sample Request button"""
    if not frappe.has_permission("Batch AMB", "write"):
        frappe.throw(_("No permission to create Sample Request for Batch AMB"), frappe.PermissionError)
    try:
        batch = frappe.get_doc("Batch AMB", batch_name)
        
        # Check if sample request already exists for this batch
        existing = frappe.db.get_value(
            "Sample Request AMB",
            {"batch_reference": batch_name},
            "name"
        )
        
        if existing:
            # Open existing sample request
            return {
                "success": True,
                "action": "open",
                "sample_request": existing,
                "message": f"Opening existing Sample Request: {existing}"
            }
        
        # Create new sample request
        sample_request = frappe.new_doc("Sample Request AMB")
        sample_request.batch_reference = batch_name
        sample_request.customer = getattr(batch, 'customer', None)
        sample_request.sales_order = getattr(batch, 'sales_order_related', None)
        sample_request.item = batch.item_to_manufacture or batch.current_item_code
        sample_request.batch_quantity = batch.planned_qty or batch.total_net_weight
        
        sample_request.insert()
        frappe.db.commit()
        
        return {
            "success": True,
            "action": "create",
            "sample_request": sample_request.name,
            "message": f"Created Sample Request: {sample_request.name}"
        }
        
    except Exception as e:
        frappe.log_error(f"Sample Request Creation Error: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_sample_request(batch_name):
    """Get Sample Request for this batch if exists"""
    if not frappe.has_permission("Batch AMB", "read"):
        frappe.throw(_("No permission to read Batch AMB"), frappe.PermissionError)
    try:
        existing = frappe.db.get_value(
            "Sample Request AMB",
            {"batch_reference": batch_name},
            "name",
            order_by="creation desc"
        )
        
        if existing:
            return {
                "success": True,
                "sample_request": existing
            }
        
        return {
            "success": False,
            "message": "No sample request found"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def make_sample_request_from_source(source_doctype, source_name):
    """
    Create a sample request from any source doctype (Lead, Prospect, Opportunity, Quotation, Sales Order)
    Enhanced to fetch comprehensive data from source documents
    """
    if not frappe.has_permission("Batch AMB", "create"):
        frappe.throw(_("No permission to create Sample Request for Batch AMB"), frappe.PermissionError)
    try:
        # Get source document
        source_doc = frappe.get_doc(source_doctype, source_name)
        
        # Create new Sample Request AMB
        sample_request = frappe.new_doc("Sample Request AMB")
        
        # Set request_type based on source doctype
        request_type_map = {
            'Lead': 'Marketing',
            'Prospect': 'Prospect',
            'Opportunity': 'Marketing',
            'Quotation': 'Pre-sample Approved',
            'Sales Order': 'Pre-sample Approved',
            'Batch AMB': 'Representative Sample'
        }
        sample_request.request_type = request_type_map.get(source_doctype, 'Pre-sample Approved')
        sample_request.request_date = frappe.utils.nowdate()
        
        # Get item and other details from source document based on doctype
        customer_name = None
        customer = None
        contact_email = None
        contact_phone = None
        address = None
        
        if source_doctype == "Lead":
            # Get customer name from Lead
            customer_name = source_doc.company_name or source_doc.lead_name
            # Set party type and party for Lead
            sample_request.party_type = 'Lead'
            sample_request.party = source_name
            # Get contact info from Lead
            contact_email = source_doc.email_id
            contact_phone = source_doc.mobile_no
            # Try to get address
            if hasattr(source_doc, 'address') and source_doc.address:
                address = source_doc.address
            
            # DEFAULT ITEM for Lead (no items table) - use item 0307
            default_item = frappe.get_doc('Item', '0307')
            sample_row = sample_request.append('samples', {})
            sample_row.item = '0307'
            sample_row.description = default_item.item_name
            sample_row.uom = 'Kg'
            sample_row.qty_per_sample = 0.020
            sample_row.samples_count = 8
            sample_row.total_qty = 0.160
            sample_row.container_size = '0.020'
            sample_row.container_type = 'BOL020'
            sample_row.lab_notes = '70% Aloe - 30% Gum\n3 samples of retention:\n  Sample 1 - Qty. 1 Distributor Retention\n  Sample 2 - Qty. 1 Customer Retention\n  Sample 3 - Qty. 1 Analysis'
            
        elif source_doctype == "Prospect":
            # Get customer name from Prospect
            customer_name = source_doc.company_name or source_doc.prospect_name
            # Set party type and party for Prospect
            sample_request.party_type = 'Prospect'
            sample_request.party = source_name
            # Get contact info from Prospect
            if hasattr(source_doc, 'email') and source_doc.email:
                contact_email = source_doc.email
            if hasattr(source_doc, 'phone') and source_doc.phone:
                contact_phone = source_doc.phone
            # Try to get address
            if hasattr(source_doc, 'address') and source_doc.address:
                address = source_doc.address
            
            # DEFAULT ITEM for Prospect (no items table) - use item 0307
            default_item = frappe.get_doc('Item', '0307')
            sample_row = sample_request.append('samples', {})
            sample_row.item = '0307'
            sample_row.description = default_item.item_name
            sample_row.uom = 'Kg'
            sample_row.qty_per_sample = 0.020
            sample_row.samples_count = 8
            sample_row.total_qty = 0.160
            sample_row.container_size = '0.020'
            sample_row.container_type = 'BOL020'
            sample_row.lab_notes = '70% Aloe - 30% Gum\n3 samples of retention:\n  Sample 1 - Qty. 1 Distributor Retention\n  Sample 2 - Qty. 1 Customer Retention\n  Sample 3 - Qty. 1 Analysis'
        
        elif source_doctype == "Opportunity":
            # Get customer name from Opportunity
            customer_name = source_doc.customer_name or source_doc.party_name
            # Set party based on opportunity_from (Lead or Customer)
            opportunity_from = getattr(source_doc, 'opportunity_from', 'Customer')
            if opportunity_from == 'Customer':
                customer = source_doc.party_name
                sample_request.party_type = 'Customer'
            else:
                # It's from a Lead
                customer = source_doc.party_name
                sample_request.party_type = 'Lead'
            sample_request.party = customer
            sample_request.opportunity = source_doc.name
            # Get contact info
            if hasattr(source_doc, 'contact_email') and source_doc.contact_email:
                contact_email = source_doc.contact_email
            if hasattr(source_doc, 'phone') and source_doc.phone:
                contact_phone = source_doc.phone
            # Get address
            if hasattr(source_doc, 'customer_address') and source_doc.customer_address:
                address = source_doc.customer_address
            
            # DEFAULT ITEM for Opportunity if no items - use item 0307
            if not (hasattr(source_doc, 'items') and source_doc.items):
                default_item = frappe.get_doc('Item', '0307')
                sample_row = sample_request.append('samples', {})
                sample_row.item = '0307'
                sample_row.description = default_item.item_name
                sample_row.uom = 'Kg'
                sample_row.qty_per_sample = 0.020
                sample_row.samples_count = 8
                sample_row.total_qty = 0.160
                sample_row.container_size = '0.020'
                sample_row.container_type = 'BOL020'
                sample_row.lab_notes = '70% Aloe - 30% Gum\n3 samples of retention:\n  Sample 1 - Qty. 1 Distributor Retention\n  Sample 2 - Qty. 1 Customer Retention\n  Sample 3 - Qty. 1 Analysis'
        
        elif source_doctype == "Quotation":
            # Get customer from Quotation
            customer_name = source_doc.party_name
            if source_doc.party_name:
                # Try to find if party_name is a customer
                customer = frappe.db.get_value("Customer", {"name": source_doc.party_name}, "name")
            sample_request.quotation = source_doc.name
            # Set party type and party
            if customer:
                sample_request.party_type = 'Customer'
                sample_request.party = customer
            # Get contact info from Quotation
            if hasattr(source_doc, 'contact_email') and source_doc.contact_email:
                contact_email = source_doc.contact_email
            if hasattr(source_doc, 'phone') and source_doc.phone:
                contact_phone = source_doc.phone
            # Get address
            if hasattr(source_doc, 'customer_address') and source_doc.customer_address:
                address = source_doc.customer_address
        
        elif source_doctype == "Sales Order":
            # Get customer from Sales Order
            customer_name = source_doc.customer_name
            customer = source_doc.customer
            sample_request.sales_order = source_doc.name
            # Set party type and party
            if customer:
                sample_request.party_type = 'Customer'
                sample_request.party = customer
            # Get contact info from Sales Order
            if hasattr(source_doc, 'contact_email') and source_doc.contact_email:
                contact_email = source_doc.contact_email
            if hasattr(source_doc, 'phone') and source_doc.phone:
                contact_phone = source_doc.phone
            # Get address
            if hasattr(source_doc, 'customer_address') and source_doc.customer_address:
                address = source_doc.customer_address
        
        # Set the values
        sample_request.customer_name = customer_name
        if customer:
            sample_request.customer = customer
        if contact_email:
            sample_request.contact_email = contact_email
        if contact_phone:
            sample_request.contact_phone = contact_phone
        if address:
            sample_request.shipping_address = address
        
        # Add ALL sample rows from source document items
        if hasattr(source_doc, 'items') and source_doc.items:
            for item in source_doc.items:
                sample_row = sample_request.append("samples", {})
                sample_row.item = item.item_code
                sample_row.item_name = item.item_name
                sample_row.samples_count = 1
                sample_row.qty_per_sample = 1
                # Try to get description if available
                if hasattr(item, 'description') and item.description:
                    sample_row.description = item.description
        
        # Note: Do NOT create sample rows automatically for Leads/Prospects
        # User must manually add samples after creation since they need to select items
        # based on their analysis of the customer's needs
        
        # Fallback: If no samples were added, use default item 0307
        if not sample_request.samples:
            default_item = frappe.get_doc('Item', '0307')
            sample_row = sample_request.append('samples', {})
            sample_row.item = '0307'
            sample_row.description = default_item.item_name
            sample_row.uom = 'Kg'
            sample_row.qty_per_sample = 0.020
            sample_row.samples_count = 8
        
        sample_request.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return sample_request.name
        
    except Exception as e:
        frappe.log_error(f"Error creating sample request from {source_doctype}: {str(e)}")
        frappe.throw(_("Failed to create sample request: ") + str(e))
