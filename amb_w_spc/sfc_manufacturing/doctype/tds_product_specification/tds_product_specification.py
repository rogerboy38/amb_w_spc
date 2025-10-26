import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime
from frappe import _

class TDSProductSpecification(Document):
    def validate(self):
        """Validate the document before saving"""
        self.validate_item_details()
        self.update_version_control()
        self.set_default_naming_series()
        self.validate_approval_date()
        self.validate_required_parameters()
        self.update_tds_sequence()
        
    def before_save(self):
        """Executed before saving the document"""
        self.auto_increment_version()
        self.update_workflow_state()
        
    def on_update(self):
        """Executed after saving the document"""
        self.send_workflow_notifications()
        
    def before_submit(self):
        """Executed before submitting the document"""
        self.validate_for_submission()
        
    def on_submit(self):
        """Executed after submitting the document"""
        self.update_status("Approved")
        self.create_quality_inspection_template()
        self.update_tds_settings()
        
    def on_cancel(self):
        """Executed when document is cancelled"""
        self.update_status("Cancelled")
        self.revert_sequence()
        
    def validate_item_details(self):
        """Validate and fetch item details"""
        if self.product_item:
            try:
                item = frappe.get_doc("Item", self.product_item)
                self.item_name = item.item_name
                self.item_code = item.item_code
                
                if not item.is_stock_item:
                    frappe.msgprint(
                        _("Selected item is not a stock item. Please verify."),
                        alert=True,
                        indicator="orange"
                    )
            except frappe.DoesNotExistError:
                frappe.throw(_("Item {0} does not exist").format(self.product_item))
        else:
            frappe.throw(_("Product Item is required"))
    
    def update_version_control(self):
        """Update TDS version control information"""
        if not self.tds_version:
            # Auto-generate version number if not set
            self.tds_version = self.generate_version_number()
        
        if not self.tds_sequence:
            # Get next sequence number
            self.tds_sequence = self.get_next_sequence()
    
    def set_default_naming_series(self):
        """Set default naming series if not provided"""
        if not self.naming_series:
            base_name = "TDS"
            item_code = self.item_code or "ITEM"
            version = self.tds_version or "1"
            self.naming_series = f"{base_name}-{item_code}-V{version}"
    
    def validate_approval_date(self):
        """Validate approval date"""
        if self.approval_date and self.approval_date > nowdate():
            frappe.throw(_("Approval Date cannot be in the future"))
    
    def validate_required_parameters(self):
        """Validate that required parameters are set"""
        if not self.item_quality_inspection_parameter:
            frappe.throw(_("At least one Quality Inspection Parameter is required"))
        
        # Validate each parameter
        for param in self.item_quality_inspection_parameter:
            if not param.specification:
                frappe.throw(_("Specification is required for all parameters"))
            if not param.value:
                frappe.throw(_("Value is required for all parameters"))
    
    def update_tds_sequence(self):
        """Update TDS sequence in settings"""
        if self.tds_sequence and self.item_code and self.docstatus == 0:
            self.update_tds_settings_sequence()
    
    def auto_increment_version(self):
        """Auto-increment version when significant changes are made"""
        if self.is_new() or self.workflow_state == "Draft":
            return
            
        old_doc = self.get_doc_before_save()
        if old_doc and old_doc.workflow_state != "Draft" and self.workflow_state == "Draft":
            # Document was amended, increment version
            try:
                current_version = float(self.tds_version or "1")
                new_version = current_version + 0.1
                self.tds_version = f"{new_version:.1f}"
                
                frappe.msgprint(
                    _("TDS version updated to {0} due to amendment").format(self.tds_version),
                    alert=True,
                    indicator="blue"
                )
            except ValueError:
                self.tds_version = "1.1"
    
    def update_workflow_state(self):
        """Update workflow state based on document status"""
        if self.docstatus == 1 and self.workflow_state != "Approved":
            self.workflow_state = "Approved"
        elif self.docstatus == 2 and self.workflow_state != "Cancelled":
            self.workflow_state = "Cancelled"
    
    def send_workflow_notifications(self):
        """Send notifications for workflow state changes"""
        if self.is_new():
            return
            
        old_doc = self.get_doc_before_save()
        if old_doc and old_doc.workflow_state != self.workflow_state:
            self.notify_next_approvers()
    
    def notify_next_approvers(self):
        """Notify users who can take the next action"""
        try:
            next_actions = self.get_next_workflow_actions()
            
            for action in next_actions:
                roles = [role.strip() for role in action.allowed.split(',')]
                for role in roles:
                    # Get users with this role
                    users = frappe.get_all("Has Role", 
                        filters={"role": role},
                        fields=["parent"], 
                        distinct=True)
                    
                    for user in users:
                        self.send_workflow_email(user.parent, action)
        except Exception as e:
            frappe.log_error(f"Workflow notification error: {str(e)}")
    
    def send_workflow_email(self, user, action):
        """Send workflow notification email"""
        try:
            subject = _("Action Required: TDS {0} requires {1}").format(self.name, action.action)
            message = _("""
            <p>Dear User,</p>
            <p>Technical Data Sheet <strong>{0}</strong> for product <strong>{1}</strong> requires your action.</p>
            <p><strong>Current State:</strong> {2}</p>
            <p><strong>Required Action:</strong> {3}</p>
            <p><strong>Product:</strong> {1} ({4})</p>
            <p><strong>Version:</strong> {5}</p>
            <br>
            <p>Please review the document and take appropriate action.</p>
            <p><a href="{6}/app/tds-product-specification/{0}">View Document</a></p>
            """).format(
                self.name, self.item_name, self.workflow_state, 
                action.action, self.item_code, self.tds_version,
                frappe.utils.get_url()
            )
            
            frappe.sendmail(
                recipients=user,
                subject=subject,
                message=message,
                now=True
            )
        except Exception as e:
            frappe.log_error(f"Workflow email error: {str(e)}")
    
    def get_next_workflow_actions(self):
        """Get possible next workflow actions for current state"""
        return frappe.get_all("Workflow Transition",
            filters={"state": self.workflow_state},
            fields=["action", "next_state", "allowed"]
        )
    
    def validate_for_submission(self):
        """Validate document before submission"""
        if not self.approval_date:
            frappe.throw(_("Approval Date is required before submission"))
            
        if not self.item_quality_inspection_parameter:
            frappe.throw(_("Quality Inspection Parameters are required before submission"))
    
    def update_status(self, status):
        """Update document status"""
        self.db_set('status', status)
    
    def create_quality_inspection_template(self):
        """Create quality inspection template from TDS parameters"""
        if not self.item_quality_inspection_parameter:
            return
        
        try:
            # Check if template already exists
            existing_template = frappe.db.exists("Quality Inspection Template", {
                "tds_product_specification": self.name
            })
            
            if existing_template:
                frappe.msgprint(_("Quality Inspection Template {0} already exists").format(existing_template))
                return
            
            template = frappe.new_doc("Quality Inspection Template")
            template.item_code = self.item_code
            template.item_name = self.item_name
            template.tds_product_specification = self.name
            template.description = _("Auto-generated from TDS {0}").format(self.name)
            
            # Add parameters from TDS
            for param in self.item_quality_inspection_parameter:
                template.append("item_quality_inspection_parameter", {
                    "specification": param.specification,
                    "value": param.value,
                    "acceptance_criteria": param.acceptance_criteria
                })
            
            template.insert()
            frappe.msgprint(_("Quality Inspection Template {0} created").format(template.name))
            
        except Exception as e:
            frappe.log_error(f"Error creating Quality Inspection Template: {str(e)}")
    
    def update_tds_settings(self):
        """Update TDS Settings with the latest sequence number"""
        if self.tds_sequence and self.item_code:
            try:
                # Check if TDS Settings exists for this item
                settings_name = frappe.db.get_value("TDS Settings", {"item_code": self.item_code})
                
                if settings_name:
                    # Update existing settings
                    frappe.db.set_value("TDS Settings", settings_name, "last_sequence_used", self.tds_sequence)
                else:
                    # Create new TDS Settings
                    settings = frappe.new_doc("TDS Settings")
                    settings.item_code = self.item_code
                    settings.last_sequence_used = self.tds_sequence
                    settings.insert()
            except Exception as e:
                frappe.log_error(f"Error updating TDS Settings: {str(e)}")
    
    def revert_sequence(self):
        """Revert sequence when document is cancelled"""
        if self.tds_sequence and self.item_code:
            try:
                # Get the previous sequence number
                previous_seq = frappe.db.sql("""
                    SELECT MAX(tds_sequence) 
                    FROM `tabTDS Product Specification` 
                    WHERE product_item = %s AND name != %s AND docstatus = 1
                """, (self.product_item, self.name))
                
                previous_sequence = previous_seq[0][0] or 0
                
                # Update TDS Settings with previous sequence
                settings_name = frappe.db.get_value("TDS Settings", {"item_code": self.item_code})
                if settings_name:
                    frappe.db.set_value("TDS Settings", settings_name, "last_sequence_used", previous_sequence)
            except Exception as e:
                frappe.log_error(f"Error reverting sequence: {str(e)}")
    
    def generate_version_number(self):
        """Generate version number based on your format"""
        if not self.approval_date or not self.item_code or not self.tds_sequence:
            return "1.0"
        
        date_parts = str(self.approval_date).split('-')
        version = f"V1.{self.item_code}-Date:{date_parts[0][-2:]}/{date_parts[1]}/{date_parts[2]}*{str(self.tds_sequence).zfill(4)}"
        return version
    
    def get_next_sequence(self):
        """Get next sequence number for TDS"""
        try:
            # Check if TDS Settings exists
            settings = frappe.db.get_value("TDS Settings", {"item_code": self.item_code}, "last_sequence_used")
            if settings is not None:
                return settings + 1
            else:
                return 1
        except Exception as e:
            frappe.log_error(f"Error getting next sequence: {str(e)}")
            return 1
    
    def update_tds_settings_sequence(self):
        """Update TDS Settings with current sequence"""
        try:
            settings_name = frappe.db.get_value("TDS Settings", {"item_code": self.item_code})
            if settings_name:
                current_max = frappe.db.get_value("TDS Settings", settings_name, "last_sequence_used") or 0
                if self.tds_sequence > current_max:
                    frappe.db.set_value("TDS Settings", settings_name, "last_sequence_used", self.tds_sequence)
        except Exception as e:
            frappe.log_error(f"Error updating TDS settings sequence: {str(e)}")

# Server-side API methods
@frappe.whitelist()
def get_next_sequence(item_code):
    """Get next sequence number for TDS"""
    if not item_code:
        return 1
    
    try:
        # Check if TDS Settings exists
        settings = frappe.db.get_value("TDS Settings", {"item_code": item_code}, "last_sequence_used")
        if settings is not None:
            return settings + 1
        else:
            # Create new TDS Settings
            settings_doc = frappe.new_doc("TDS Settings")
            settings_doc.item_code = item_code
            settings_doc.last_sequence_used = 0
            settings_doc.insert()
            return 1
    except Exception as e:
        frappe.log_error(f"Error getting next sequence: {str(e)}")
        return 1

@frappe.whitelist()
def get_item_details(item_code):
    """Fetch item details for the given item code"""
    if not item_code:
        return {}
    
    try:
        item = frappe.get_doc("Item", item_code)
        return {
            'item_name': item.item_name,
            'item_code': item.item_code,
            'description': item.description,
            'stock_uom': item.stock_uom,
            'is_stock_item': item.is_stock_item
        }
    except Exception as e:
        frappe.log_error(f"Error fetching item details: {str(e)}")
        return {}

@frappe.whitelist()
def get_latest_tds_version(product_item):
    """Get the latest TDS version for a product item"""
    if not product_item:
        return {"tds_version": "1", "tds_sequence": 1}
    
    try:
        latest_tds = frappe.db.sql("""
            SELECT tds_version, tds_sequence 
            FROM `tabTDS Product Specification` 
            WHERE product_item = %s AND docstatus = 1
            ORDER BY creation DESC 
            LIMIT 1
        """, product_item, as_dict=True)
        
        if latest_tds:
            return {
                "tds_version": latest_tds[0].tds_version,
                "tds_sequence": (latest_tds[0].tds_sequence or 0) + 1
            }
        else:
            return {"tds_version": "1", "tds_sequence": 1}
            
    except Exception as e:
        frappe.log_error(f"Error fetching latest TDS version: {str(e)}")
        return {"tds_version": "1", "tds_sequence": 1}

@frappe.whitelist()
def create_new_version(source_name):
    """Create a new version of TDS from existing one"""
    try:
        source_doc = frappe.get_doc("TDS Product Specification", source_name)
        new_doc = frappe.copy_doc(source_doc)
        
        # Increment version
        try:
            current_version = float(source_doc.tds_version or "1")
            new_version = current_version + 0.1
            new_doc.tds_version = f"{new_version:.1f}"
        except ValueError:
            new_doc.tds_version = "1.1"
        
        # Update sequence
        new_doc.tds_sequence = (source_doc.tds_sequence or 0) + 1
        
        # Reset workflow state and status
        new_doc.workflow_state = "Draft"
        new_doc.status = "Draft"
        new_doc.approval_date = None
        
        new_doc.insert()
        
        frappe.msgprint(_("New TDS version {0} created successfully").format(new_doc.name))
        return new_doc.name
        
    except Exception as e:
        frappe.log_error(f"Error creating new TDS version: {str(e)}")
        frappe.throw(_("Failed to create new TDS version"))

@frappe.whitelist()
def validate_parameters(parameters):
    """Validate quality inspection parameters"""
    if isinstance(parameters, str):
        import json
        parameters = json.loads(parameters)
    
    errors = []
    for i, param in enumerate(parameters):
        if not param.get('specification'):
            errors.append(f"Parameter {i+1}: Specification is required")
        if not param.get('value'):
            errors.append(f"Parameter {i+1}: Value is required")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }
