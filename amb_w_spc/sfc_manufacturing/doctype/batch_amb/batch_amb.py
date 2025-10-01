import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime, cint
from frappe import _
from frappe.utils.nestedset import NestedSet

class BatchAMB(NestedSet):
    def validate(self):
        """Validate the document before saving"""
        self.validate_batch_code()
        self.calculate_weights()
        self.update_tree_fields()
        self.set_default_dates()
        self.validate_quality_status()
        self.update_tracking_fields()
        super(BatchAMB, self).validate()
        
    def before_save(self):
        """Executed before saving the document"""
        self.generate_barcode_data()
        self.update_batch_hierarchy_level()
        
    def on_update(self):
        """Executed after saving the document"""
        super(BatchAMB, self).on_update()
        self.create_processing_history()
        self.update_parent_batch_totals()
        
    def on_trash(self):
        """Executed when document is trashed"""
        super(BatchAMB, self).on_trash()
        
    def before_submit(self):
        """Executed before submitting the document"""
        self.validate_batch_for_submission()
        
    def on_submit(self):
        """Executed after submitting the document"""
        self.update_batch_status("Active")
        self.create_batch_transition_record()
        
    def on_cancel(self):
        """Executed when document is cancelled"""
        self.update_batch_status("Cancelled")
        self.reverse_parent_batch_totals()
        
    def validate_batch_code(self):
        """Ensure batch code is unique and follows naming convention"""
        if not self.batch_code:
            frappe.throw(_("Batch Code is required"))
            
        if self.batch_code:
            existing = frappe.db.exists("Batch AMB", {
                "batch_code": self.batch_code,
                "name": ["!=", self.name]
            })
            if existing:
                frappe.throw(_("Batch Code {0} already exists in {1}").format(self.batch_code, existing))
    
    def calculate_weights(self):
        """Calculate net weight and validate weight relationships"""
        if self.gross_weight and self.tare_weight:
            self.net_weight = self.gross_weight - self.tare_weight
            
            if self.net_weight < 0:
                frappe.throw(_("Net weight cannot be negative. Check gross and tare weights."))
                
        if self.total_weight and self.quantity:
            if self.total_weight <= 0:
                frappe.throw(_("Total weight must be greater than 0"))
    
    def update_tree_fields(self):
        """Update tree structure fields and validate hierarchy"""
        if self.is_group:
            # Group batches can have children but no manufacturing details
            if self.quantity or self.total_weight:
                frappe.msgprint(_("Group batches should not have quantity or weight values"), alert=True)
        else:
            # Non-group batches must have a parent and can have manufacturing details
            if not self.parent_batch_amb:
                frappe.throw(_("Non-group batches must have a parent batch"))
                
            if not self.quantity:
                frappe.throw(_("Quantity is required for non-group batches"))
            
            self.validate_non_group_batch()
    
    def validate_non_group_batch(self):
        """Additional validation for non-group batches"""
        if not self.item_code:
            frappe.throw(_("Item Code is required for non-group batches"))
        
        if not self.work_order_reference:
            frappe.throw(_("Work Order Reference is required for non-group batches"))
    
    def set_default_dates(self):
        """Set default dates if not provided"""
        if not self.created_date:
            self.created_date = nowdate()
            
        if not self.expiry_date and self.created_date:
            # Set default expiry date (e.g., 1 year from creation)
            from frappe.utils import add_days
            self.expiry_date = add_days(self.created_date, 365)
    
    def validate_quality_status(self):
        """Validate quality status transitions and business rules"""
        if self.quality_status == "Failed" and self.batch_status == "Active":
            frappe.msgprint(
                _("Batch with Failed quality status should not be Active"),
                indicator="orange",
                alert=True
            )
            
        if self.quality_status == "Hold" and not self.get("hold_reason"):
            frappe.msgprint(
                _("Please specify a reason for putting the batch on hold"),
                indicator="yellow",
                alert=True
            )
    
    def update_tracking_fields(self):
        """Update last modified tracking fields"""
        self.last_modified_by = frappe.session.user
        self.last_modified_date = now_datetime()
        
        # Auto-set batch status based on quality status
        if not self.batch_status:
            if self.quality_status == "Passed":
                self.batch_status = "Active"
            elif self.quality_status == "Failed":
                self.batch_status = "Inactive"
            else:
                self.batch_status = "Active"
    
    def generate_barcode_data(self):
        """Generate barcode data if not provided"""
        if not self.barcode_data and self.batch_code:
            # Generate barcode in CODE-39 format
            level = cint(self.custom_batch_level) or 1
            self.barcode_data = f"AMB-{self.batch_code}-L{level}"
    
    def update_batch_hierarchy_level(self):
        """Update batch level based on parent hierarchy"""
        if self.parent_batch_amb:
            parent_level = frappe.db.get_value("Batch AMB", self.parent_batch_amb, "custom_batch_level")
            if parent_level:
                self.custom_batch_level = str(cint(parent_level) + 1)
    
    def create_processing_history(self):
        """Create processing history record on significant changes"""
        if self.is_new():
            # Initial history record for new batches
            self.append("batch_processing_history", {
                "timestamp": now_datetime(),
                "action": "Batch Created",
                "description": f"Batch {self.batch_code} created",
                "user": frappe.session.user,
                "plant": self.current_plant
            })
            return
            
        old_doc = self.get_doc_before_save()
        if not old_doc:
            return
            
        # Track significant field changes
        significant_fields = [
            'current_plant', 'target_plant', 'quality_status', 
            'batch_status', 'quantity', 'total_weight', 'gross_weight', 'tare_weight'
        ]
        
        changes = []
        for field in significant_fields:
            old_value = getattr(old_doc, field, None)
            new_value = getattr(self, field, None)
            if old_value != new_value:
                changes.append(f"{field}: {old_value} → {new_value}")
        
        if changes:
            self.append("batch_processing_history", {
                "timestamp": now_datetime(),
                "action": "Field Updates",
                "description": "; ".join(changes),
                "user": frappe.session.user,
                "plant": self.current_plant
            })
    
    def update_parent_batch_totals(self):
        """Update parent batch totals when child batch changes"""
        if self.parent_batch_amb and not self.is_group:
            self.update_parent_totals(self.parent_batch_amb)
    
    def reverse_parent_batch_totals(self):
        """Reverse parent batch totals when child batch is cancelled"""
        if self.parent_batch_amb and not self.is_group:
            self.update_parent_totals(self.parent_batch_amb, reverse=True)
    
    def update_parent_totals(self, parent_batch, reverse=False):
        """Update totals for parent batch"""
        try:
            parent = frappe.get_doc("Batch AMB", parent_batch)
            factor = -1 if reverse else 1
            
            # Update parent totals (you can customize this logic)
            if self.quantity:
                # Add your parent batch aggregation logic here
                pass
                
            parent.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Error updating parent batch totals: {str(e)}")
    
    def validate_batch_for_submission(self):
        """Validate batch before submission"""
        if not self.quality_status:
            frappe.throw(_("Quality Status is required before submission"))
            
        if self.quality_status == "Pending":
            frappe.throw(_("Cannot submit batch with Pending quality status"))
            
        if not self.batch_code:
            frappe.throw(_("Batch Code is required"))
    
    def update_batch_status(self, status):
        """Update batch status"""
        self.db_set('batch_status', status)
    
    def create_batch_transition_record(self):
        """Create transition record when batch is submitted"""
        self.append("batch_processing_history", {
            "timestamp": now_datetime(),
            "action": "Batch Submitted",
            "description": f"Batch submitted with status: {self.batch_status}",
            "user": frappe.session.user,
            "plant": self.current_plant
        })

# Server-side API methods for Tree View
@frappe.whitelist()
def get_children(doctype, parent=None, company=None, is_root=False):
    """Get children for tree view"""
    fields = [
        'name as value', 
        'batch_name as title', 
        'is_group as expandable',
        'batch_code',
        'quality_status',
        'current_plant',
        'batch_status'
    ]
    
    filters = [['docstatus', '<', 2]]  # Not cancelled
    
    if parent and parent != 'All Batches':
        filters.append(['parent_batch_amb', '=', parent])
    else:
        filters.append(['ifnull(`parent_batch_amb`, "")', '=', ''])
    
    if company:
        filters.append(['company', '=', company])
    
    batches = frappe.get_list(doctype, 
        fields=fields,
        filters=filters,
        order_by='name'
    )
    
    return batches

@frappe.whitelist()
def get_all_batch_nodes():
    """Get all batches for tree view"""
    return frappe.get_all("Batch AMB",
        fields=[
            "name", "batch_code", "batch_name", "parent_batch_amb", 
            "is_group", "custom_batch_level", "quality_status", 
            "current_plant", "batch_status"
        ],
        filters={"docstatus": ["<", 2]},
        order_by="lft"
    )

@frappe.whitelist()
def get_batch_tree_data(company=None, plant=None):
    """Get batch data for widget display - grouped by plant and level"""
    filters = {"docstatus": 1}  # Only submitted documents
    
    if company:
        filters["company"] = company
    if plant:
        filters["current_plant"] = plant
    
    batches = frappe.get_all("Batch AMB",
        filters=filters,
        fields=[
            "name", "batch_code", "batch_name", "custom_batch_level", 
            "quality_status", "current_plant", "batch_status", 
            "quantity", "total_weight", "is_group"
        ]
    )
    
    # Group by plant
    plant_data = {}
    for batch in batches:
        plant = batch.current_plant or "Unknown"
        if plant not in plant_data:
            plant_data[plant] = []
        plant_data[plant].append(batch)
    
    return plant_data

@frappe.whitelist()
def get_child_batches(batch_name):
    """Get all child batches for a given batch"""
    return frappe.get_all("Batch AMB",
        filters={"parent_batch_amb": batch_name},
        fields=[
            "name", "batch_code", "batch_name", "custom_batch_level", 
            "quality_status", "batch_status", "quantity", "total_weight"
        ]
    )

@frappe.whitelist()
def create_child_batch(parent_batch, batch_data):
    """Create a child batch under parent batch"""
    if isinstance(batch_data, str):
        import json
        batch_data = json.loads(batch_data)
    
    parent = frappe.get_doc("Batch AMB", parent_batch)
    if not parent.is_group:
        frappe.throw(_("Parent batch {0} is not a group batch").format(parent_batch))
    
    child_batch = frappe.new_doc("Batch AMB")
    child_batch.update(batch_data)
    child_batch.parent_batch_amb = parent_batch
    child_batch.insert()
    
    frappe.msgprint(_("Child batch {0} created successfully").format(child_batch.name))
    return child_batch.name

@frappe.whitelist()
def transfer_batch_plant(batch_name, new_plant, target_plant=None):
    """Transfer batch to a new plant"""
    batch = frappe.get_doc("Batch AMB", batch_name)
    old_plant = batch.current_plant
    
    batch.current_plant = new_plant
    if target_plant:
        batch.target_plant = target_plant
    
    # Add to processing history
    batch.append("batch_processing_history", {
        "timestamp": now_datetime(),
        "action": "Plant Transfer",
        "description": f"Transferred from {old_plant} to {new_plant}",
        "user": frappe.session.user,
        "plant": new_plant
    })
    
    batch.save()
    
    frappe.msgprint(_("Batch {0} transferred from {1} to {2}").format(batch.batch_code, old_plant, new_plant))
    return batch.name

@frappe.whitelist()
def update_batch_quality(batch_name, new_quality_status, notes=None):
    """Update batch quality status with notes"""
    batch = frappe.get_doc("Batch AMB", batch_name)
    old_status = batch.quality_status
    
    batch.quality_status = new_quality_status
    
    # Add to processing history
    description = _("Quality status changed from {0} to {1}").format(old_status, new_quality_status)
    if notes:
        description += f". Notes: {notes}"
    
    batch.append("batch_processing_history", {
        "timestamp": now_datetime(),
        "action": "Quality Update",
        "description": description,
        "user": frappe.session.user,
        "plant": batch.current_plant
    })
    
    batch.save()
    
    frappe.msgprint(_("Batch {0} quality status updated to {1}").format(batch.batch_code, new_quality_status))
    return batch.name

@frappe.whitelist()
def get_batch_quality_summary(batch_name):
    """Get quality status summary for a batch and its children"""
    def get_quality_counts(batch_name):
        children = frappe.get_all("Batch AMB",
            filters={"parent_batch_amb": batch_name},
            fields=["quality_status", "name", "is_group"]
        )
        
        counts = {"Pending": 0, "Passed": 0, "Failed": 0, "Hold": 0, "Total": 0}
        for child in children:
            counts["Total"] += 1
            if child.quality_status in counts:
                counts[child.quality_status] += 1
            if child.is_group:
                child_counts = get_quality_counts(child.name)
                for status in counts:
                    counts[status] += child_counts[status]
        
        return counts
    
    batch = frappe.get_doc("Batch AMB", batch_name)
    if batch.is_group:
        return get_quality_counts(batch_name)
    else:
        return {batch.quality_status: 1, "Total": 1}

@frappe.whitelist()
def scan_batch_barcode(barcode_data):
    """Process barcode scan and return batch information"""
    if not barcode_data:
        return {"success": False, "message": "No barcode data provided"}
    
    try:
        # Parse barcode data (assuming format: AMB-{batch_code}-L{level})
        if barcode_data.startswith("AMB-"):
            parts = barcode_data.split("-")
            if len(parts) >= 3:
                batch_code = parts[1]
                
                # Find batch by code
                batch = frappe.get_all("Batch AMB",
                    filters={"batch_code": batch_code},
                    fields=["name", "batch_code", "batch_name", "quality_status", "batch_status", "current_plant"]
                )
                
                if batch:
                    return {
                        "success": True,
                        "batch": batch[0],
                        "message": f"Batch {batch_code} found"
                    }
                else:
                    return {"success": False, "message": f"Batch with code {batch_code} not found"}
        
        return {"success": False, "message": "Invalid barcode format"}
        
    except Exception as e:
        frappe.log_error(f"Barcode scan error: {str(e)}")
        return {"success": False, "message": f"Error processing barcode: {str(e)}"}
