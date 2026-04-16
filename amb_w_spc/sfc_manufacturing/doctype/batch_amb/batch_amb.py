# Copyright (c) 2024, AMB and contributors
# For license information, please see license.txt

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


# ======================================================================
#  DOC_EVENTS WRAPPER FUNCTIONS (required by hooks.py doc_events)
#  These are module-level functions called by Frappe's doc_events system
#  Since doc is NestedSet at runtime (not BatchAMB), we implement
#  the required logic directly here without relying on class methods.
# ======================================================================

# -------------------------------------------------------------------------
# Helper: dual-field compatibility (same pattern as working RPC logic)
# -------------------------------------------------------------------------

def _get_field(doc, primary, alternate):
    """Get field value with dual-field compatibility."""
    val = getattr(doc, primary, None)
    if val is not None:
        return val
    return getattr(doc, alternate, None)


def _set_field(doc, field, value):
    """Safely set a field on doc."""
    setattr(doc, field, value)


def batch_amb_validate(doc, method=None):
    """Validate hook - generate golden number components for Level 1 batches."""
    try:
        # Dual-field: custom_batch_level / custombatchlevel
        level = str(_get_field(doc, 'custom_batch_level', 'custombatchlevel') or "1")
        if level != "1":
            return

        # Dual-field: item_to_manufacture / itemtomanufacture
        item = _get_field(doc, 'item_to_manufacture', 'itemtomanufacture')
        if not item:
            return

        # Extract product_code (first 4 chars of item)
        product_code = (item or "")[:4] or "0000"

        # Dual-field: work_order_ref / workorderref
        wo_ref = _get_field(doc, 'work_order_ref', 'workorderref')

        # Extract consecutive - FIXED: use [:3] not [-3:]
        consecutive = "001"
        if wo_ref:
            try:
                parts = wo_ref.split("-")
                last_part = parts[-1] if parts else ""
                if last_part and last_part.isdigit():
                    consecutive = last_part[:3].zfill(3)
            except Exception:
                pass

        # Dual-field: wo_start_date / wostartdate
        wo_date_val = _get_field(doc, 'wo_start_date', 'wostartdate')

        # Extract year from WO date or Work Order
        year = "24"
        if wo_date_val:
            try:
                if isinstance(wo_date_val, str):
                    parsed_date = datetime.strptime(wo_date_val, "%Y-%m-%d")
                    year = str(parsed_date.year)[-2:]
                else:
                    year = str(wo_date_val.year)[-2:]
            except Exception:
                pass

        # If no WO date, try to get from Work Order doc
        if wo_ref and year == "24":
            try:
                wo_doc = frappe.get_doc("Work Order", wo_ref)
                if wo_doc.planned_start_date:
                    year = str(wo_doc.planned_start_date.year)[-2:]
            except Exception:
                pass

        if year == "24":
            year = datetime.now().strftime("%y")

        # Dual-field: production_plant / productionplant
        production_plant = _get_field(doc, 'production_plant', 'productionplant')

        # Extract plant_code
        plant_code = "1"
        if production_plant:
            plant_mapping = {
                "mix": "1", "dry": "2", "juice": "3",
                "laboratory": "4", "formulated": "5",
            }
            plant_lower = production_plant.lower()
            for plant_type, code in plant_mapping.items():
                if plant_type in plant_lower:
                    plant_code = code
                    break

            # Try to get production_plant_id from the plant doc
            if plant_code == "1":
                try:
                    plant_doc = frappe.get_doc("Production Plant AMB", production_plant)
                    plant_id = getattr(plant_doc, 'production_plant_id', None)
                    if plant_id:
                        plant_code = str(plant_id)
                except Exception:
                    pass

        # Build golden number: product_code(4) + consecutive(3) + year(2) + plant_code(1)
        base_golden_number = f"{product_code}{consecutive}{year}{plant_code}"

        # Set golden number fields
        doc.custom_golden_number = base_golden_number
        doc.custom_generated_batch_name = base_golden_number

        # Decompose into component fields
        doc.custom_product_family = product_code[:2] or "00"
        doc.custom_consecutive = consecutive
        doc.custom_subfamily = product_code[2:4] or "00"

    except Exception as e:
        frappe.log_error(
            title="Batch AMB Validate Error",
            message=f"Error in batch_amb_validate: {str(e)}"
        )


def batch_amb_before_save(doc, method=None):
    """Before save hook - set title from golden number for Level 1."""
    try:
        # Dual-field: custom_batch_level / custombatchlevel
        level = str(_get_field(doc, 'custom_batch_level', 'custombatchlevel') or "1")

        # Set title based on level
        if level == "1":
            golden_number = getattr(doc, 'custom_golden_number', None)
            if golden_number:
                doc.title = golden_number
            else:
                doc.title = getattr(doc, 'name', None) or "Untitled"

        elif level == "2":
            parent_batch = _get_field(doc, 'parent_batch_amb', 'parentbatchamb')
            if parent_batch:
                try:
                    parent = frappe.get_doc("Batch AMB", parent_batch)
                    parent_gn = getattr(parent, 'custom_golden_number', None) or getattr(parent, 'title', None) or parent.name
                    siblings = frappe.db.count(
                        "Batch AMB",
                        {
                            "parent_batch_amb": parent_batch,
                            "custom_batch_level": "2",
                            "name": ["!=", doc.name],
                        },
                    )
                    doc.title = f"{parent_gn}-{siblings + 1}"
                except Exception:
                    doc.title = f"{doc.name}-L2"
            else:
                doc.title = f"{doc.name}-L2"

        elif level == "3":
            parent_batch = _get_field(doc, 'parent_batch_amb', 'parentbatchamb')
            if parent_batch:
                try:
                    parent = frappe.get_doc("Batch AMB", parent_batch)
                    parent_title = getattr(parent, 'title', None) or parent.name
                    siblings = frappe.db.count(
                        "Batch AMB",
                        {
                            "parent_batch_amb": parent_batch,
                            "custom_batch_level": "3",
                            "name": ["!=", doc.name],
                        },
                    )
                    doc.title = f"{parent_title}-C{siblings + 1}"
                except Exception:
                    doc.title = f"{doc.name}-L3"
            else:
                doc.title = f"{doc.name}-L3"

        elif level == "4":
            parent_batch = _get_field(doc, 'parent_batch_amb', 'parentbatchamb')
            if parent_batch:
                try:
                    parent = frappe.get_doc("Batch AMB", parent_batch)
                    parent_title = getattr(parent, 'title', None) or parent.name
                    siblings = frappe.db.count(
                        "Batch AMB",
                        {
                            "parent_batch_amb": parent_batch,
                            "custom_batch_level": "4",
                            "name": ["!=", doc.name],
                        },
                    )
                    doc.title = f"{parent_title}-{siblings + 1:03d}"
                except Exception:
                    doc.title = f"{doc.name}-L4"
            else:
                doc.title = f"{doc.name}-L4"

        # Safety: trim very long titles
        if getattr(doc, 'title', None) and len(doc.title) > 60:
            doc.title = doc.title[:60]

        # Update planned_qty from Work Order if not set
        wo_ref = _get_field(doc, 'work_order_ref', 'workorderref')
        if wo_ref and getattr(doc, 'planned_qty', None) is None:
            try:
                qty = frappe.db.get_value("Work Order", wo_ref, "qty")
                if qty:
                    doc.planned_qty = qty
            except Exception:
                pass

    except Exception as e:
        frappe.log_error(
            title="Batch AMB Before Save Error",
            message=f"Error in batch_amb_before_save: {str(e)}"
        )


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
        self.validate_batch_level_hierarchy()
        self.validate_barrel_weights()
        self.set_item_details()
        self.validate_processing_dates()
        self.calculate_yield_percentage()

    def before_save(self):
        """Before save hook"""
        self.calculate_totals()
        self.set_batch_naming()
        self.auto_set_title()
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
        """Validate container data"""
        if not self.container_barrels:
            return
        for idx, container in enumerate(self.container_barrels, 1):
            if hasattr(container, "container_id") and not container.container_id:
                container.container_id = f"CNT-{self.name}-{idx:03d}"
    
    def validate_batch_level_hierarchy(self):
        """Validate batch level hierarchy"""
        level = int(self.custom_batch_level or "1")
        if level > 1 and not self.parent_batch_amb:
            frappe.throw(
                _("Parent Batch AMB is required for level {0}").format(level)
            )
        # Validate parent is exactly one level above
        if level > 1 and self.parent_batch_amb:
            parent_level = frappe.db.get_value(
                "Batch AMB", self.parent_batch_amb, "custom_batch_level"
            )
            expected_parent_level = str(level - 1)
            if str(parent_level) != expected_parent_level:
                frappe.throw(
                    _(
                        "Level {0} batch requires a Level {1} parent, "
                        "but {2} is Level {3}"
                    ).format(level, expected_parent_level, self.parent_batch_amb, parent_level)
                )

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
    # Totals and costing
    # -----------------------------

    def calculate_totals(self):
        """Calculate totals"""
        if self.container_barrels:
            self.total_container_qty = sum(
                flt(c.quantity or 0) for c in self.container_barrels
            )
            self.total_containers = len(self.container_barrels)
            self.calculate_container_weights()
        else:
            self.total_container_qty = 0
            self.total_containers = 0

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

        print(f"✅ Generated Golden Number: {base_golden_number}")
        print(
            f"   Product Family: {self.custom_product_family}, "
            f"Subfamily: {self.custom_subfamily}"
        )


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
        try:
            frappe.msgprint(
                f"Generating {quantity} serial numbers for {self.name} with prefix '{prefix}'"
            )
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
            frappe.throw(f"Error generating serial numbers: {str(e)}")

    @frappe.whitelist()
    def get_processing_metrics(self):
        """Get processing metrics for analytics"""
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
    try:
        print(f"🚀 BOM Creation started for batch: {batch_name}")

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

        print(f"📦 Item: {batch.item_to_manufacture}")
        print(f"⚖️ Quantity: {bom_quantity} {uom}")

        existing_bom = frappe.db.get_value(
            "BOM",
            {"item": batch.item_to_manufacture, "is_active": 1},
            "name",
        )

        if existing_bom:
            print(f"⚠️ BOM already exists: {existing_bom}")
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

        print(f"📝 Creating BOM with data: {bom_data}")

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
            print("➕ Added raw material: M033")
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
            print("➕ Added fallback raw material: 0202")

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
                print(f"➕ Added packaging: {packaging_item} x {packages_count}")

        bom.insert()
        frappe.db.commit()

        print(f"✅ BOM created successfully: {bom.name}")

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
        print(f"❌ BOM Creation Error: {str(e)}")
        return {"success": False, "message": f"Error creating BOM: {str(e)}"}


@frappe.whitelist()
def create_work_order_from_batch(batch_name):
    """Create Work Order from Batch"""
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
        frappe.throw(f"Error duplicating batch: {str(e)}")


@frappe.whitelist()
def check_bom_exists(batch_name):
    """Check if BOM already exists for this batch"""
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
    return []


@frappe.whitelist()
def get_running_batch_announcements(
    include_companies=True, include_plants=True, include_quality=True
):
    """Get running batch announcements for widget"""
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
    batch = frappe.get_doc("Batch AMB", batch_name)
    batch.scheduled_start_date = scheduled_start
    batch.processing_status = "Scheduled"
    batch.save()
    return {"status": "success", "message": f"Batch {batch_name} scheduled"}


@frappe.whitelist()
def start_batch_processing(batch_name):
    """Start processing a batch"""
    batch = frappe.get_doc("Batch AMB", batch_name)
    batch.processing_status = "In Progress"
    batch.actual_start = now_datetime()
    batch.save()
    return {"status": "success", "message": f"Batch {batch_name} started"}


@frappe.whitelist()
def complete_batch_processing(batch_name, processed_quantity=None):
    """Complete batch processing"""
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
    try:
        batch = frappe.get_doc("Batch AMB", batch_name)

        if isinstance(quantity, str):
            quantity = int(quantity)

        batch_level = batch.custom_batch_level or "1"

        # Use hierarchical title as base (e.g. 0334925261-1-C1)
        base_title = batch.title or batch.custom_golden_number or batch.name

        # Resolve prefix based on packaging/plant, unless explicitly passed in
        resolved_prefix = prefix or resolve_container_prefix(batch, default_prefix=None)

        # Collect existing serials in the child table
        existing_serials = []
        for row in batch.container_barrels:
            if row.barrel_serial_number and row.barrel_serial_number.strip():
                existing_serials.append(row.barrel_serial_number.strip())

        existing_count = len(existing_serials)
        new_serials = []

        for i in range(quantity):
            seq_num = existing_count + i + 1

            # Level 3/4: PREFIX-GoldenChain-NNN (e.g. BRL-0334925261-1-C1-001)
            if batch_level in ("3", "4") and resolved_prefix:
                serial = f"{resolved_prefix}-{base_title}-{seq_num:03d}"
            else:
                # Generic fallback: GoldenChain-NNN
                serial = f"{base_title}-{seq_num:03d}"

            if len(serial) > 50:
                serial = serial[:50]

            new_serials.append(serial)

            row_data = {
                "barrel_serial_number": serial,
                "status": "Empty",
                "packaging_type": batch.default_packaging_type or "",
                "batch_amb": batch_name,
                "item_code": batch.item_to_manufacture
                or getattr(batch, "current_item_code", "")
                or "",
                "created_date": nowdate(),
                "parent": batch.name,
                "parentfield": "container_barrels",
                "parenttype": "Batch AMB",
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

        batch.save(ignore_permissions=True)
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
        frappe.throw(f"Failed to generate serial numbers: {str(e)[:200]}")


@frappe.whitelist()
def integrate_serial_tracking(batch_name):
    """Integrate serial tracking using the real generate_serial_numbers"""
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


# ============================================================
# STANDALONE HOOK FUNCTIONS (Required by hooks.py doc_events)
# These functions are called by doc_events regardless of the
# actual controller class resolution (fixes NestedSet issue)
# ============================================================

def batch_amb_validate(doc, method=None):
    """Hook for validate event - ensures Golden Number is generated."""
    _set_batch_naming_on_doc(doc)


def batch_amb_before_save(doc, method=None):
    """Hook for before_save event - ensures Golden Number is generated."""
    _set_batch_naming_on_doc(doc)


def _set_batch_naming_on_doc(doc):
    """
    Core standalone function that works both as a hook and with NestedSet.
    It prefers the rich class method when possible, otherwise runs robust fallback logic.
    """
    try:
        # If we have a full BatchAMB instance, use its rich method
        if isinstance(doc, BatchAMB):
            doc.set_batch_naming()
            return

        # Otherwise, ensure we have a proper document and call the method
        if not getattr(doc, 'name', None) or not frappe.db.exists("Batch AMB", doc.name):
            # We only have a partial doc (e.g. from quick entry)
            _run_golden_number_logic(doc)
            return

        # Load full document to use the complete logic with logging
        full_doc = frappe.get_doc("Batch AMB", doc.name)
        full_doc.set_batch_naming()

        # Sync changes back to the original doc object (important for hooks)
        for field in [
            "custom_golden_number", "custom_generated_batch_name", "custom_product_family",
            "custom_consecutive", "custom_subfamily", "title"
        ]:
            if hasattr(full_doc, field):
                setattr(doc, field, getattr(full_doc, field))

    except Exception as e:
        frappe.log_error(f"Golden Number Hook Error: {str(e)}", "Batch AMB Golden Number Hook")
        # Fallback to basic logic if anything fails
        _run_golden_number_logic(doc)


def _run_golden_number_logic(doc):
    """Pure logic version (used as last resort fallback)."""
    import re
    from datetime import datetime

    level = str(
        getattr(doc, "custom_batch_level", None)
        or getattr(doc, "custombatchlevel", None)
        or "1"
    )
    if level != "1":
        return

    item = (
        getattr(doc, "item_to_manufacture", None)
        or getattr(doc, "itemtomanufacture", None)
        or ""
    ).strip()

    if not item:
        return

    product_code = (item or "")[:4].zfill(4)
    wo_ref = (
        getattr(doc, "work_order_ref", None)
        or getattr(doc, "workorderref", None)
        or ""
    ).strip()

    consecutive = "001"
    year = datetime.now().strftime("%y")

    if wo_ref:
        try:
            parts = wo_ref.split("-")
            last_part = parts[-1] if parts else ""
            consecutive = (last_part[:3] if last_part else "001").zfill(3)
        except Exception:
            pass

        try:
            wo_doc = frappe.get_doc("Work Order", wo_ref)
            if getattr(wo_doc, "planned_start_date", None):
                year = str(wo_doc.planned_start_date.year)[-2:]
        except Exception:
            pass

    # Plant Code Resolution
    plant_code = "1"
    direct_plant_id = getattr(doc, "production_plant_id", None)
    if direct_plant_id:
        plant_code = str(int(direct_plant_id))

    if plant_code == "1":
        plant_name = (
            getattr(doc, "production_plant_name", None)
            or getattr(doc, "productionplantname", None)
            or ""
        )
        if plant_name:
            plant_match = re.match(r"(\d+)", str(plant_name))
            if plant_match:
                plant_code = plant_match.group(1)
            else:
                plant_lower = str(plant_name).lower()
                mapping = {"mix": "1", "dry": "2", "juice": "3", "laboratory": "4", "formulated": "5"}
                for key, code in mapping.items():
                    if key in plant_lower:
                        plant_code = code
                        break

    golden_number = f"{product_code}{consecutive}{year}{plant_code}"

    doc.custom_golden_number = golden_number
    doc.custom_generated_batch_name = golden_number
    doc.custom_product_family = product_code[:2] or "00"
    doc.custom_consecutive = consecutive
    doc.custom_subfamily = product_code[2:4] or "00"
    doc.title = golden_number
