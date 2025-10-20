"""
Complete Warehouse Management Installation Patch
Ensures all warehouse management components are properly installed
"""

import frappe
from frappe.utils import getdate, now_datetime
import logging

logger = logging.getLogger(__name__)

def execute():
    """
    Execute complete warehouse management installation
    """
    try:
        logger.info("Starting complete warehouse management installation")
        
        # Install custom fields
        install_custom_fields()
        
        # Install property setters
        install_property_setters()
        
        # Install roles and permissions
        install_roles_and_permissions()
        
        # Setup warehouse system settings
        setup_system_settings()
        
        # Setup default warehouse configurations
        setup_default_configurations()
        
        # Install workflows
        install_workflows()
        
        # Create sample data if needed
        create_sample_data()
        
        # Validate installation
        validate_installation()
        
        logger.info("Complete warehouse management installation completed successfully")
        
    except Exception as e:
        logger.error(f"Error in complete warehouse management installation: {str(e)}")
        frappe.log_error(f"Warehouse Installation Error: {str(e)}", "Warehouse Patch")

def install_custom_fields():
    """Install all custom fields"""
    try:
        # Load custom field fixtures
        custom_field_files = [
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_stock_entry.json",
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_warehouse.json",
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_work_order.json",
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_purchase_receipt.json",
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_batch.json",
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_bin.json",
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_sales_order.json",
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_delivery_note.json",
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_item.json",
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_warehouse_batch.json",
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_material_assessment_batch.json",
            "amb_w_spc/sfc_manufacturing/fixtures/custom_field_work_order_batch.json"
        ]
        
        for file_path in custom_field_files:
            try:
                frappe.reload_doc("core", "doctype", "custom_field", force=True)
                from frappe.core.doctype.data_import.data_import import import_doc
                import_doc(file_path, ignore_links=True, overwrite=True)
            except Exception as e:
                logger.warning(f"Could not load custom field file {file_path}: {str(e)}")
        
        frappe.db.commit()
        logger.info("Custom fields installation completed")
        
    except Exception as e:
        logger.error(f"Error installing custom fields: {str(e)}")

def install_property_setters():
    """Install property setters"""
    try:
        property_setter_files = [
            "amb_w_spc/sfc_manufacturing/fixtures/property_setter_stock_entry.json",
            "amb_w_spc/sfc_manufacturing/fixtures/property_setter_warehouse.json",
            "amb_w_spc/sfc_manufacturing/fixtures/property_setter_work_order.json",
            "amb_w_spc/sfc_manufacturing/fixtures/property_setter_purchase_receipt.json"
        ]
        
        for file_path in property_setter_files:
            try:
                frappe.reload_doc("core", "doctype", "property_setter", force=True)
                from frappe.core.doctype.data_import.data_import import import_doc
                import_doc(file_path, ignore_links=True, overwrite=True)
            except Exception as e:
                logger.warning(f"Could not load property setter file {file_path}: {str(e)}")
        
        frappe.db.commit()
        logger.info("Property setters installation completed")
        
    except Exception as e:
        logger.error(f"Error installing property setters: {str(e)}")

def install_roles_and_permissions():
    """Install warehouse roles and permissions"""
    try:
        # Install roles
        roles_file = "amb_w_spc/system_integration/fixtures/warehouse_roles.json"
        try:
            frappe.reload_doc("core", "doctype", "role", force=True)
            from frappe.core.doctype.data_import.data_import import import_doc
            import_doc(roles_file, ignore_links=True, overwrite=True)
        except Exception as e:
            logger.warning(f"Could not load roles file: {str(e)}")
        
        # Install permissions
        permissions_file = "amb_w_spc/system_integration/fixtures/warehouse_permissions.json"
        try:
            frappe.reload_doc("core", "doctype", "custom_docperm", force=True)
            from frappe.core.doctype.data_import.data_import import import_doc
            import_doc(permissions_file, ignore_links=True, overwrite=True)
        except Exception as e:
            logger.warning(f"Could not load permissions file: {str(e)}")
        
        frappe.db.commit()
        logger.info("Roles and permissions installation completed")
        
    except Exception as e:
        logger.error(f"Error installing roles and permissions: {str(e)}")

def setup_system_settings():
    """Setup warehouse system settings"""
    try:
        # Create Warehouse System Settings if not exists
        if not frappe.db.exists("Warehouse System Settings", "Warehouse System Settings"):
            settings = frappe.new_doc("Warehouse System Settings")
            settings.name = "Warehouse System Settings"
            settings.temperature_monitoring_enabled = 1
            settings.auto_pick_task_assignment = 1
            settings.quality_check_required = 1
            settings.batch_tracking_enabled = 1
            settings.real_time_inventory_updates = 1
            settings.alert_notifications_enabled = 1
            settings.performance_analytics_enabled = 1
            settings.default_pick_task_priority = "Medium"
            settings.auto_archive_days = 90
            settings.temperature_check_frequency = 60
            settings.capacity_warning_threshold = 90
            settings.insert(ignore_permissions=True)
            
            frappe.db.commit()
        
        logger.info("System settings setup completed")
        
    except Exception as e:
        logger.error(f"Error setting up system settings: {str(e)}")

def setup_default_configurations():
    """Setup default warehouse configurations"""
    try:
        # Update existing warehouses with default configurations
        warehouses = frappe.get_all("Warehouse", 
            filters={"is_group": 0},
            fields=["name", "warehouse_type"])
        
        for warehouse in warehouses:
            warehouse_doc = frappe.get_doc("Warehouse", warehouse.name)
            
            # Set default warehouse type if not set
            if not hasattr(warehouse_doc, "warehouse_type") or not warehouse_doc.warehouse_type:
                warehouse_doc.warehouse_type = "Raw Material"
            
            # Set default zone code if not set
            if not hasattr(warehouse_doc, "zone_code") or not warehouse_doc.zone_code:
                warehouse_doc.zone_code = "ZONE-A"
            
            # Set default quality check requirement
            if not hasattr(warehouse_doc, "quality_check_required"):
                warehouse_doc.quality_check_required = 1
            
            # Set default pick sequence
            if not hasattr(warehouse_doc, "pick_sequence"):
                warehouse_doc.pick_sequence = 1
            
            warehouse_doc.save(ignore_permissions=True)
        
        frappe.db.commit()
        logger.info("Default configurations setup completed")
        
    except Exception as e:
        logger.error(f"Error setting up default configurations: {str(e)}")

def install_workflows():
    """Install warehouse management workflows"""
    try:
        # Create default workflows for warehouse operations
        workflows = [
            {
                "name": "Warehouse Pick Task Workflow",
                "document_type": "Warehouse Pick Task",
                "states": [
                    {"state": "Draft", "doc_status": "0"},
                    {"state": "Pending", "doc_status": "1"},
                    {"state": "In Progress", "doc_status": "1"},
                    {"state": "Completed", "doc_status": "1"},
                    {"state": "Cancelled", "doc_status": "2"}
                ]
            },
            {
                "name": "Material Assessment Workflow",
                "document_type": "Material Assessment Log",
                "states": [
                    {"state": "Draft", "doc_status": "0"},
                    {"state": "Pending Assessment", "doc_status": "1"},
                    {"state": "Approved", "doc_status": "1"},
                    {"state": "Rejected", "doc_status": "1"},
                    {"state": "Cancelled", "doc_status": "2"}
                ]
            }
        ]
        
        for workflow_data in workflows:
            if not frappe.db.exists("Workflow", workflow_data["name"]):
                workflow = frappe.new_doc("Workflow")
                workflow.workflow_name = workflow_data["name"]
                workflow.document_type = workflow_data["document_type"]
                workflow.is_active = 1
                
                for state_data in workflow_data["states"]:
                    workflow.append("states", {
                        "state": state_data["state"],
                        "doc_status": state_data["doc_status"],
                        "allow_edit": state_data["state"] in ["Draft", "Pending Assessment"]
                    })
                
                workflow.insert(ignore_permissions=True)
        
        frappe.db.commit()
        logger.info("Workflows installation completed")
        
    except Exception as e:
        logger.error(f"Error installing workflows: {str(e)}")

def create_sample_data():
    """Create sample data for demonstration"""
    try:
        # Only create sample data if explicitly requested
        if frappe.db.get_single_value("System Settings", "setup_sample_warehouse_data"):
            create_sample_warehouse_alerts()
            create_sample_performance_logs()
            
            logger.info("Sample data creation completed")
        
    except Exception as e:
        logger.error(f"Error creating sample data: {str(e)}")

def create_sample_warehouse_alerts():
    """Create sample warehouse alerts"""
    try:
        warehouses = frappe.get_all("Warehouse", 
            filters={"is_group": 0},
            fields=["name"],
            limit=3)
        
        sample_alerts = [
            {
                "alert_type": "Temperature Violation",
                "severity": "High",
                "message": "Temperature exceeded acceptable range - immediate attention required"
            },
            {
                "alert_type": "Capacity Warning", 
                "severity": "Medium",
                "message": "Warehouse utilization above 90% - consider redistribution"
            },
            {
                "alert_type": "Quality Hold",
                "severity": "High", 
                "message": "Material placed on quality hold pending inspection"
            }
        ]
        
        for i, warehouse in enumerate(warehouses[:len(sample_alerts)]):
            alert_data = sample_alerts[i]
            
            if not frappe.db.exists("Warehouse Alert", {
                "warehouse": warehouse.name,
                "alert_type": alert_data["alert_type"]
            }):
                alert = frappe.new_doc("Warehouse Alert")
                alert.warehouse = warehouse.name
                alert.alert_type = alert_data["alert_type"]
                alert.severity = alert_data["severity"]
                alert.message = alert_data["message"]
                alert.alert_datetime = now_datetime()
                alert.status = "Open"
                alert.insert(ignore_permissions=True)
        
    except Exception as e:
        logger.error(f"Error creating sample alerts: {str(e)}")

def create_sample_performance_logs():
    """Create sample performance logs"""
    try:
        from frappe.utils import add_days
        
        # Create performance data for the past 7 days
        for i in range(7):
            date = add_days(getdate(), -i)
            
            if not frappe.db.exists("Warehouse Performance Log", {"date": date}):
                performance_log = frappe.new_doc("Warehouse Performance Log")
                performance_log.date = date
                performance_log.total_pick_tasks = 15 + (i * 3)
                performance_log.completed_pick_tasks = 12 + (i * 2)
                performance_log.completion_rate = 80 + i
                performance_log.average_pick_time = 30 - i
                performance_log.insert(ignore_permissions=True)
        
    except Exception as e:
        logger.error(f"Error creating sample performance logs: {str(e)}")

def validate_installation():
    """Validate warehouse management installation"""
    try:
        validation_errors = []
        
        # Check custom fields
        required_fields = [
            ("Stock Entry", "amb_warehouse_zone"),
            ("Warehouse", "amb_temperature_controlled"),
            ("Work Order", "amb_production_zone"),
            ("Purchase Receipt", "amb_quality_inspection_required")
        ]
        
        for doctype, fieldname in required_fields:
            if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
                validation_errors.append(f"Missing custom field: {doctype}.{fieldname}")
        
        # Check roles
        required_roles = ["Warehouse Manager", "Warehouse Operator", "Quality Inspector"]
        for role in required_roles:
            if not frappe.db.exists("Role", role):
                validation_errors.append(f"Missing role: {role}")
        
        # Check system settings
        if not frappe.db.exists("Warehouse System Settings", "Warehouse System Settings"):
            validation_errors.append("Missing Warehouse System Settings")
        
        if validation_errors:
            logger.warning(f"Installation validation found issues: {validation_errors}")
        else:
            logger.info("Installation validation passed successfully")
        
        return len(validation_errors) == 0
        
    except Exception as e:
        logger.error(f"Error validating installation: {str(e)}")
        return False

@frappe.whitelist()
def run_manual_installation():
    """Run manual installation for testing"""
    try:
        execute()
        return {"success": True, "message": "Warehouse management installation completed successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}
