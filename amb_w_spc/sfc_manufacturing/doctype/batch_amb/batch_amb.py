import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import nowdate, now_datetime

class BatchAMB(Document):
    def validate(self):
        self.validate_batch_hierarchy()
        self.validate_container_data()
        self.calculate_totals()
        self.auto_generate_batch_code()
        self.validate_erpnext_integration()
        self.sync_erpnext_fields()
        self.validate_fda_compliance()
        self.validate_batch_hierarchy_integrity()
        
    def before_save(self):
        # Set workflow state if not set
        if not self.workflow_state:
            self.workflow_state = "Draft"
            
    def after_insert(self):
        """Create related records after insert"""
        self.create_erpnext_batch()
        self.create_spc_batch_record()
        self.create_batch_processing_history()
        
    def on_update(self):
        """Sync with related records on update"""
        self.sync_erpnext_batch()
        self.update_processing_history()
        self.sync_spc_parameters()
        
    def on_submit(self):
        """Handle batch submission"""
        self.validate_batch_completeness()
        self.create_integration_records()
        self.create_batch_processing_history_entry("Batch Submitted")
        
    # ========== ENHANCED INTEGRATION METHODS ==========
    
    def validate_batch_completeness(self):
        """Validate batch is complete before submission"""
        if self.custom_batch_level == "1":
            if not self.manufacturing_date:
                frappe.throw(_("Manufacturing Date is required for Level 1 batches"))
            if not self.expiry_date:
                frappe.throw(_("Expiry Date is required for Level 1 batches"))
        
        if self.custom_batch_level == "3" and not self.container_barrels:
            frappe.throw(_("Container barrels are required for Level 3 batches"))
            
        # Validate SPC requirements for Level 1 batches
        if self.custom_batch_level == "1" and self.spc_batch_record:
            spc_record = frappe.get_doc("SPC Batch Record", self.spc_batch_record)
            if spc_record.batch_status in ["Rejected", "Hold"]:
                frappe.throw(_("Cannot submit batch with SPC status: {0}").format(spc_record.batch_status))

    def create_integration_records(self):
        """Create all integration records on submit"""
        # Create ERPNext Batch for Level 1 if not exists
        if self.custom_batch_level == "1" and not self.erpnext_batch_reference:
            self.create_erpnext_batch()
        
        # Create SPC Record for Level 1 if not exists
        if self.custom_batch_level == "1" and not self.spc_batch_record:
            self.create_spc_batch_record()
        
        # Update all linked records
        self.sync_all_systems()

    def sync_all_systems(self):
        """Sync all integrated systems"""
        self.sync_erpnext_batch()
        self.sync_spc_parameters()
        self.update_batch_quantity()

    def validate_batch_hierarchy_integrity(self):
        """Validate and maintain batch hierarchy integrity"""
        if self.custom_batch_level == "1":
            # Level 1 batches should not have parent
            if self.parent_batch_amb:
                frappe.throw(_("Level 1 batches cannot have a parent batch"))
        else:
            # Sublots must have parent
            if not self.parent_batch_amb:
                frappe.throw(_("Parent Batch AMB is required for level {0} batches").format(
                    self.custom_batch_level))
            
            # Validate parent exists and is correct level
            if not frappe.db.exists("Batch AMB", self.parent_batch_amb):
                frappe.throw(_("Parent Batch AMB {0} does not exist").format(self.parent_batch_amb))
            
            parent_level = frappe.db.get_value("Batch AMB", self.parent_batch_amb, "custom_batch_level")
            if parent_level and int(parent_level) != int(self.custom_batch_level) - 1:
                frappe.throw(_("Parent batch must be level {0} for this level {1} batch").format(
                    int(self.custom_batch_level) - 1, self.custom_batch_level))

    def sync_spc_parameters(self):
        """Sync SPC parameters between systems"""
        if not self.spc_batch_record:
            return
            
        try:
            from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import BatchAMBIntegration
            BatchAMBIntegration.sync_spc_parameters(self)
        except Exception as e:
            frappe.log_error(f"Error syncing SPC parameters: {str(e)}")

    def update_batch_quantity(self):
        """Update batch quantity from integrated systems"""
        try:
            from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import BatchAMBIntegration
            BatchAMBIntegration.update_batch_qty(self.name)
        except Exception as e:
            frappe.log_error(f"Error updating batch quantity: {str(e)}")

    def create_batch_processing_history_entry(self, action, remarks=None):
        """Create processing history entry"""
        try:
            from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import BatchAMBIntegration
            BatchAMBIntegration.create_batch_processing_history(self, action, remarks)
        except Exception as e:
            frappe.log_error(f"Error creating processing history entry: {str(e)}")

    def get_integrated_batch_info(self):
        """Get comprehensive integrated batch information"""
        info = {
            'batch_amb': {
                'name': self.name,
                'level': self.custom_batch_level,
                'workflow_state': self.workflow_state,
                'item': self.item_to_manufacture,
                'quantity': self.batch_qty
            },
            'erpnext': {},
            'spc': {},
            'processing': {}
        }
        
        # ERPNext Integration Info
        if self.erpnext_batch_reference:
            try:
                erp_batch = frappe.get_doc("Batch", self.erpnext_batch_reference)
                info['erpnext'] = {
                    'batch_id': erp_batch.batch_id,
                    'stock_uom': erp_batch.stock_uom,
                    'expiry_date': erp_batch.expiry_date,
                    'manufacturing_date': erp_batch.manufacturing_date
                }
            except Exception:
                info['erpnext']['error'] = 'Batch not found'
        
        # SPC Integration Info
        if self.spc_batch_record:
            try:
                spc_record = frappe.get_doc("SPC Batch Record", self.spc_batch_record)
                info['spc'] = {
                    'status': spc_record.batch_status,
                    'specifications_met': spc_record.specifications_met,
                    'production_date': spc_record.production_date,
                    'reviewer': spc_record.batch_reviewer
                }
            except Exception:
                info['spc']['error'] = 'SPC Record not found'
        
        # Processing History Info
        if self.batch_processing_history:
            try:
                history = frappe.get_doc("Batch Processing History", self.batch_processing_history)
                info['processing'] = {
                    'status': history.status,
                    'start_date': history.start_date,
                    'steps_count': len(history.processing_steps) if history.processing_steps else 0
                }
            except Exception:
                info['processing']['error'] = 'History not found'
        
        return info

    # ========== EXISTING METHODS (ENHANCED) ==========
    
    def create_erpnext_batch(self):
        """Create ERPNext Batch for level 1 batches"""
        from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import BatchAMBIntegration
        
        if self.custom_batch_level == "1" and not self.erpnext_batch_reference:
            BatchAMBIntegration.create_erpnext_batch(self)
    
    def create_spc_batch_record(self):
        """Create SPC Batch Record for FDA compliance"""
        if not self.spc_batch_record and self.custom_batch_level == "1":
            try:
                from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import BatchAMBIntegration
                BatchAMBIntegration.create_spc_batch_record(self)
            except Exception as e:
                frappe.log_error(f"Error creating SPC Batch Record: {str(e)}")
    
    def create_batch_processing_history(self):
        """Create Batch Processing History record"""
        if not self.batch_processing_history:
            try:
                from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import BatchAMBIntegration
                BatchAMBIntegration.create_batch_processing_history(self, "Batch Created")
            except Exception as e:
                frappe.log_error(f"Error creating Batch Processing History: {str(e)}")
    
    def sync_erpnext_batch(self):
        """Sync with ERPNext Batch"""
        from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import BatchAMBIntegration
        
        if self.erpnext_batch_reference:
            BatchAMBIntegration.sync_batch_data(self)
            BatchAMBIntegration.update_batch_qty(self.name)
    
    def update_processing_history(self):
        """Update processing history with current state"""
        if self.batch_processing_history:
            try:
                history = frappe.get_doc("Batch Processing History", self.batch_processing_history)
                history.update({
                    "workflow_state": self.workflow_state,
                    "batch_level": self.custom_batch_level,
                    "last_updated": now_datetime()
                })
                
                # Add history entry for state changes
                if hasattr(history, 'has_value_changed') and history.has_value_changed("workflow_state"):
                    history.append("processing_steps", {
                        "step_name": f"State changed to {self.workflow_state}",
                        "timestamp": now_datetime(),
                        "status": "Completed",
                        "remarks": f"Batch moved to {self.workflow_state} state",
                        "changed_by": frappe.session.user
                    })
                
                history.save()
            except Exception as e:
                frappe.log_error(f"Error updating processing history: {str(e)}")
    
    def validate_fda_compliance(self):
        """Validate FDA compliance requirements"""
        if self.custom_batch_level == "1":
            # Level 1 batches require manufacturing date
            if not self.manufacturing_date:
                frappe.throw(_("Manufacturing Date is required for Level 1 batches for FDA compliance"))
            
            # Validate expiry date is after manufacturing date
            if self.manufacturing_date and self.expiry_date and self.expiry_date <= self.manufacturing_date:
                frappe.throw(_("Expiry Date must be after Manufacturing Date"))
    
    def sync_erpnext_fields(self):
        """Sync ERPNext related fields"""
        if self.item_to_manufacture and not self.item:
            self.item = self.item_to_manufacture
            
        if not self.manufacturing_date:
            self.manufacturing_date = nowdate()
            
    def validate_erpnext_integration(self):
        """Validate ERPNext integration requirements"""
        if self.custom_batch_level == "1" and not self.item_to_manufacture:
            frappe.throw(_("Item to Manufacture is required for Level 1 batches"))
            
        # Validate that ERPNext batch reference is unique
        if self.erpnext_batch_reference:
            existing = frappe.db.exists("Batch AMB", {
                "erpnext_batch_reference": self.erpnext_batch_reference,
                "name": ["!=", self.name]
            })
            if existing:
                frappe.throw(_("ERPNext Batch Reference {0} is already used by {1}").format(
                    self.erpnext_batch_reference, existing))
            
    def validate_batch_hierarchy(self):
        """Validate batch hierarchy rules"""
        if self.parent_batch_amb == self.name:
            frappe.throw(_("A batch cannot be its own parent"))
            
        if int(self.custom_batch_level or 1) > 1 and not self.parent_batch_amb:
            frappe.throw(_("Parent Batch AMB is required for level {0}").format(self.custom_batch_level))
            
        # Validate parent level is one less than current level
        if self.parent_batch_amb and self.custom_batch_level:
            parent_level = frappe.db.get_value("Batch AMB", self.parent_batch_amb, "custom_batch_level")
            if parent_level and int(parent_level) != int(self.custom_batch_level) - 1:
                frappe.throw(_("Parent batch must be level {0} for this level {1} batch").format(
                    int(self.custom_batch_level) - 1, self.custom_batch_level))
    
    def validate_container_data(self):
        """Validate container/barrel data for level 3 batches"""
        if self.custom_batch_level != "3" or not self.container_barrels:
            return
            
        for barrel in self.container_barrels:
            if barrel.barrel_serial_number and not barrel.gross_weight:
                frappe.throw(_("Gross weight is required for barrel {0}").format(barrel.barrel_serial_number))
                
            if barrel.gross_weight and barrel.tara_weight and barrel.net_weight <= 0:
                frappe.throw(_("Net weight cannot be zero or negative for barrel {0}").format(barrel.barrel_serial_number))
    
    def calculate_totals(self):
        """Calculate weight totals for level 3 batches"""
        if self.custom_batch_level != "3" or not self.container_barrels:
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
            if barrel.gross_weight:
                total_gross += barrel.gross_weight
            if barrel.tara_weight:
                total_tara += barrel.tara_weight
            if barrel.net_weight:
                total_net += barrel.net_weight
            if barrel.barrel_serial_number:
                barrel_count += 1
                
        self.total_gross_weight = total_gross
        self.total_tara_weight = total_tara
        self.total_net_weight = total_net
        self.barrel_count = barrel_count
    
    def auto_generate_batch_code(self):
        """Auto-generate batch code if conditions are met"""
        if not self.should_auto_generate():
            return
            
        if self.custom_batch_level == "1":
            self.generate_level_1_batch_code()
        else:
            self.generate_sublot_batch_code()
    
    def should_auto_generate(self):
        """Check if batch code should be auto-generated"""
        return (self.work_order_ref and 
                self.custom_batch_level and 
                (self.custom_plant_code or self.production_plant_name) and
                not self.name)
    
    def generate_level_1_batch_code(self):
        """Generate level 1 batch code"""
        components = self.get_base_components()
        consecutive = str(components['consecutive']).zfill(5)
        plant_code = str(components['plant_code'])
        
        if components['series_type'] == 'P':
            final_batch_code = f"{components['product_code']}-{consecutive}-{plant_code}"
        else:
            final_batch_code = f"{components['product_code']}{consecutive}{plant_code}"
            
        self.name = final_batch_code
        self.custom_generated_batch_name = final_batch_code
        self.custom_consecutive_number = consecutive
    
    def generate_sublot_batch_code(self):
        """Generate sublot batch code for levels 2-4"""
        if not self.parent_batch_amb:
            return
            
        parent_batch = frappe.get_doc("Batch AMB", self.parent_batch_amb)
        parent_code = parent_batch.name
        
        if not parent_code:
            frappe.throw(_("Parent batch does not have a valid batch code"))
            
        next_consecutive = self.get_next_sublot_consecutive(parent_code)
        
        if self.custom_batch_level == "3":
            final_batch_code = f"{parent_code}-C{next_consecutive}"
        else:
            final_batch_code = f"{parent_code}-{next_consecutive}"
            
        self.name = final_batch_code
        self.custom_generated_batch_name = final_batch_code
        self.custom_sublot_consecutive = next_consecutive
    
    def get_base_components(self):
        """Get base components for batch code generation"""
        if not self.work_order_ref:
            return {
                'product_code': '0000',
                'consecutive': 1,
                'plant_code': self.derive_plant_code(),
                'series_type': 'WO'
            }
            
        try:
            wo = frappe.get_doc("Work Order", self.work_order_ref)
            naming = (wo.naming_series or wo.name or "").upper()
            
            is_p_inv = naming.startswith('P-INV')
            is_p_vta = naming.startswith('P-VTA')
            
            if is_p_inv or is_p_vta:
                series_type = 'P'
                product_code = 'P-INV' if is_p_inv else 'P-VTA'
            else:
                series_type = 'WO'
                if wo.production_item:
                    product_code = wo.production_item[:4] if len(wo.production_item) >= 4 else '0000'
                else:
                    product_code = '0000'
            
            consecutive = 1
            if wo.name and wo.name[-5:].isdigit():
                consecutive = int(wo.name[-5:])
                
            return {
                'product_code': product_code,
                'consecutive': consecutive,
                'plant_code': self.derive_plant_code(),
                'series_type': series_type
            }
        except Exception:
            return {
                'product_code': '0000',
                'consecutive': 1,
                'plant_code': self.derive_plant_code(),
                'series_type': 'WO'
            }
    
    def derive_plant_code(self):
        """Derive plant code from available fields"""
        if self.custom_plant_code and str(self.custom_plant_code).isdigit():
            return int(self.custom_plant_code)
            
        if self.production_plant_name:
            import re
            numbers = re.findall(r'\d+', self.production_plant_name)
            if numbers:
                return int(numbers[0])
                
        return 1
    
    def get_next_sublot_consecutive(self, parent_batch_code):
        """Get next consecutive number for sublot"""
        existing_batches = frappe.get_all(
            "Batch AMB",
            filters={
                'parent_batch_amb': self.parent_batch_amb,
                'name': ['!=', self.name or '']
            },
            fields=['name', 'custom_generated_batch_name']
        )
        
        max_consecutive = 0
        for batch in existing_batches:
            batch_name = batch.get('name') or batch.get('custom_generated_batch_name') or ''
            if parent_batch_code in batch_name:
                import re
                pattern = f"^{re.escape(parent_batch_code)}-C?(\\d+)$"
                match = re.match(pattern, batch_name)
                if match:
                    current_consecutive = int(match.group(1))
                    max_consecutive = max(max_consecutive, current_consecutive)
                    
        return max_consecutive + 1

    def create_spc_deviation(self, deviation_type, description, severity="Medium"):
        """Create SPC Batch Deviation record"""
        try:
            deviation = frappe.new_doc("SPC Batch Deviation")
            deviation.update({
                "batch_amb_reference": self.name,
                "deviation_type": deviation_type,
                "description": description,
                "severity": severity,
                "detection_date": now_datetime(),
                "status": "Open"
            })
            deviation.insert()
            
            # Link deviation to batch
            if not self.spc_batch_deviation:
                self.db_set("spc_batch_deviation", deviation.name)
            
            frappe.msgprint(_("SPC Batch Deviation {0} created").format(deviation.name))
            return deviation.name
            
        except Exception as e:
            frappe.log_error(f"Error creating SPC Batch Deviation: {str(e)}")
            return None

# Whitelisted methods for client-side calls
@frappe.whitelist()
def get_erpnext_batch_info(batch_amb_name):
    """Get ERPNext Batch information for client-side"""
    from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import get_batch_stock_info
    return get_batch_stock_info(batch_amb_name)

@frappe.whitelist()
def create_erpnext_batch(batch_amb_name):
    """Manually create ERPNext Batch"""
    batch_amb = frappe.get_doc("Batch AMB", batch_amb_name)
    batch_amb.create_erpnext_batch()
    return {"success": True, "batch_reference": batch_amb.erpnext_batch_reference}

@frappe.whitelist()
def create_spc_deviation(batch_amb_name, deviation_type, description, severity="Medium"):
    """Create SPC Batch Deviation"""
    batch_amb = frappe.get_doc("Batch AMB", batch_amb_name)
    deviation_id = batch_amb.create_spc_deviation(deviation_type, description, severity)
    return {"success": bool(deviation_id), "deviation_id": deviation_id}

@frappe.whitelist()
def get_batch_hierarchy(batch_name):
    """Get complete hierarchy for a batch"""
    batch = frappe.get_doc("Batch AMB", batch_name)
    
    hierarchy = {
        'current': {
            'name': batch.name,
            'level': batch.custom_batch_level,
            'parent': batch.parent_batch_amb,
            'workflow_state': batch.workflow_state
        },
        'children': [],
        'parents': []
    }
    
    # Get children
    children = frappe.get_all(
        "Batch AMB",
        filters={'parent_batch_amb': batch_name},
        fields=['name', 'custom_batch_level', 'workflow_state']
    )
    hierarchy['children'] = children
    
    # Get parent hierarchy
    current_parent = batch.parent_batch_amb
    while current_parent:
        parent = frappe.get_doc("Batch AMB", current_parent)
        hierarchy['parents'].append({
            'name': parent.name,
            'level': parent.custom_batch_level,
            'workflow_state': parent.workflow_state
        })
        current_parent = parent.parent_batch_amb
    
    return hierarchy

@frappe.whitelist()
def get_batch_comprehensive_info(batch_name):
    """Get comprehensive information about a batch"""
    batch = frappe.get_doc("Batch AMB", batch_name)
    
    info = {
        'basic_info': {
            'name': batch.name,
            'level': batch.custom_batch_level,
            'workflow_state': batch.workflow_state,
            'item': batch.item_to_manufacture,
            'work_order': batch.work_order_ref
        },
        'erpnext_integration': {
            'erpnext_batch': batch.erpnext_batch_reference,
            'stock_balance': batch.batch_qty
        },
        'fda_compliance': {
            'spc_batch_record': batch.spc_batch_record,
            'spc_batch_deviation': batch.spc_batch_deviation
        },
        'processing': {
            'processing_history': batch.batch_processing_history
        },
        'containers': {
            'barrel_count': batch.barrel_count,
            'total_net_weight': batch.total_net_weight
        }
    }
    
    return info

@frappe.whitelist()
def sync_batch_systems(batch_amb_name):
    """Manual sync of all batch systems"""
    try:
        batch_amb = frappe.get_doc("Batch AMB", batch_amb_name)
        batch_amb.sync_all_systems()
        frappe.msgprint(_("All batch systems synchronized successfully"))
        return {'success': True}
    except Exception as e:
        frappe.log_error(f"Error syncing batch systems: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def get_integrated_batch_info(batch_amb_name):
    """Get comprehensive integrated batch information"""
    try:
        batch_amb = frappe.get_doc("Batch AMB", batch_amb_name)
        return batch_amb.get_integrated_batch_info()
    except Exception as e:
        frappe.log_error(f"Error getting integrated batch info: {str(e)}")
        return {'error': str(e)}

@frappe.whitelist()
def validate_batch_completeness(batch_amb_name):
    """Validate batch completeness before submission"""
    try:
        batch_amb = frappe.get_doc("Batch AMB", batch_amb_name)
        batch_amb.validate_batch_completeness()
        return {'success': True, 'message': 'Batch is complete and ready for submission'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
