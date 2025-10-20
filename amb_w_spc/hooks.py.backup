app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "AMB-Wellness"
app_description = "Advanced Manufacturing, Warehouse Management & Statistical Process Control for ERPNext"
app_email = "fcrm@amb-wellness.com"
app_license = "MIT"
app_version = "2.0.0"

# Required property for ERPNext
required_apps = ["frappe", "erpnext"]

# Auto-install app after installation
auto_install_apps = []

# Modules - these will be created by patch, not by standard installer
modules = [
    'core_spc',
    'spc_quality_management',
    'sfc_manufacturing',
    'operator_management',
    'shop_floor_control',
    'plant_equipment',
    'real_time_monitoring',
    'sensor_management',
    'system_integration',
    'fda_compliance',
]

# IMPORTANT: Commented out to avoid Frappe v15.84.0 installer bug
# The patch system will handle module creation instead
# after_app_install = []

# DocType overrides
# override_doctype_class = {}

# Document Events - Sales Order Fulfillment & Warehouse Integration
doc_events = {
    "Sales Order": {
        "on_submit": "amb_w_spc.sfc_manufacturing.warehouse_management.sales_order_integration.SalesOrderIntegration.on_sales_order_submit",
        "on_update_after_submit": "amb_w_spc.sfc_manufacturing.warehouse_management.sales_order_integration.SalesOrderIntegration.on_sales_order_submit"
    },
    "Delivery Note": {
        "before_submit": "amb_w_spc.sfc_manufacturing.warehouse_management.delivery_note_integration.DeliveryNoteIntegration.on_delivery_note_before_submit",
        "on_submit": [
            "amb_w_spc.sfc_manufacturing.warehouse_management.delivery_note_integration.DeliveryNoteIntegration.on_delivery_note_submit",
            "amb_w_spc.sfc_manufacturing.warehouse_management.batch_shipment_tracking.BatchShipmentTracking.track_delivery_note_batches"
        ]
    },
    "Stock Entry": {
        "before_save": "amb_w_spc.sfc_manufacturing.warehouse_management.stock_entry.before_save",
        "before_submit": "amb_w_spc.sfc_manufacturing.warehouse_management.stock_entry.before_submit",
        "on_submit": "amb_w_spc.sfc_manufacturing.warehouse_management.stock_entry.on_submit",
        "before_cancel": "amb_w_spc.sfc_manufacturing.warehouse_management.stock_entry.before_cancel",
        "on_update_after_submit": "amb_w_spc.sfc_manufacturing.warehouse_management.stock_entry.on_update_after_submit"
    },
    "Warehouse": {
        "before_save": "amb_w_spc.sfc_manufacturing.warehouse_management.warehouse.before_save"
    },
    "Work Order": {
        "before_save": "amb_w_spc.sfc_manufacturing.warehouse_management.work_order.before_save",
        "on_submit": "amb_w_spc.sfc_manufacturing.warehouse_management.work_order.on_submit"
    },
    "Purchase Receipt": {
        "before_submit": "amb_w_spc.sfc_manufacturing.warehouse_management.purchase_receipt_hooks.purchase_receipt_before_submit",
        "on_submit": [
            "amb_w_spc.sfc_manufacturing.warehouse_management.purchase_receipt_hooks.purchase_receipt_on_submit",
            "amb_w_spc.sfc_manufacturing.doctype.purchase_receipt_integration.purchase_receipt_integration.process_purchase_receipt_integration"
        ]
    },
    "Batch AMB": {
        "after_insert": "amb_w_spc.sfc_manufacturing.warehouse_management.warehouse_batch_integration.WarehouseBatchIntegration.create_stock_entry_batch_history",
        "on_update": "amb_w_spc.sfc_manufacturing.warehouse_management.warehouse_batch_integration.WarehouseBatchIntegration.update_warehouse_bin_batch_tracking"
    },
    "Material Assessment Log": {
        "on_submit": "amb_w_spc.sfc_manufacturing.warehouse_management.warehouse_batch_integration.WarehouseBatchIntegration.create_stock_entry_batch_history"
    }
}

# Scheduled Tasks for Warehouse Management and Optimization
scheduler_events = {
    "hourly": [
        "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.optimize_warehouse_operations",
        "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.update_pick_task_priorities",
        "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.check_temperature_compliance"
    ],
    "daily": [
        "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.generate_warehouse_performance_report",
        "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.cleanup_expired_pick_tasks",
        "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.validate_warehouse_zones",
        "amb_w_spc.system_integration.scheduler.sync_warehouse_data"
    ],
    "weekly": [
        "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.analyze_warehouse_efficiency",
        "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.generate_warehouse_capacity_report"
    ],
    "monthly": [
        "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.archive_old_warehouse_data",
        "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.generate_warehouse_analytics_report"
    ],
    "cron": {
        "*/15 * * * *": [
            "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.monitor_warehouse_alerts"
        ],
        "0 6 * * *": [
            "amb_w_spc.sfc_manufacturing.warehouse_management.scheduler.start_daily_warehouse_operations"
        ]
    }
}

# Testing
# before_tests = []

# Overriding Methods
# override_whitelisted_methods = {}

# Application includes - CSS and JavaScript assets for warehouse management
app_include_css = [
    "/assets/amb_w_spc/css/warehouse_management.css",
    "/assets/amb_w_spc/css/sales_order_fulfillment.css",
    "/assets/amb_w_spc/css/warehouse_zones.css",
    "/assets/amb_w_spc/css/pick_tasks.css",
    "/assets/amb_w_spc/css/material_assessment.css",
    "/assets/amb_w_spc/css/warehouse_dashboard.css",
    "/assets/amb_w_spc/css/spc_quality.css"
]

app_include_js = [
    "/assets/amb_w_spc/js/stock_entry.js",
    "/assets/amb_w_spc/js/work_order.js",
    "/assets/amb_w_spc/js/warehouse_batch_integration.js",
    "/assets/amb_w_spc/js/warehouse_batch_navbar.js",
    "/assets/amb_w_spc/js/sales_order.js",
    "/assets/amb_w_spc/js/delivery_note.js",
    "/assets/amb_w_spc/js/sales_order_fulfillment.js",
    "/assets/amb_w_spc/js/warehouse_pick_task.js",
    "/assets/amb_w_spc/js/warehouse_zones.js",
    "/assets/amb_w_spc/js/material_assessment_log.js",
    "/assets/amb_w_spc/js/warehouse_dashboard.js",
    "/assets/amb_w_spc/js/purchase_receipt.js",
    "/assets/amb_w_spc/js/warehouse_utils.js"
]

# Boot Session - Include warehouse dashboard data and user permissions
boot_session = "amb_w_spc.sfc_manufacturing.warehouse_management.boot.get_warehouse_boot_session"

# Installation

#after_app_install = [
#    "amb_w_spc.install.post_install_setup"
#]
post_install = [
     "amb_w_spc.post_install.run"
]

# Patches will be automatically executed from patches.txt
# Workspaces
workspaces = [
    "SPC Dashboard",
    "SPC Quality Management", 
    "Manufacturing Control"
]

# Fixtures to load during installation - includes all warehouse management components
fixtures = [
    {"dt": "Workspace", "filters": [["name", "in", workspaces]]},
    {"dt": "Workflow", "filters": [["name", "in", [
        "Batch AMB Manufacturing Workflow",
        "SPC Alert Workflow",
        "SPC Corrective Action Workflow",
        "SPC Process Capability Workflow",
        "TDS Product Specification Workflow",
        "Warehouse Pick Task Workflow",
        "Material Assessment Workflow",
        "Quality Inspection Workflow"
    ]]]},
    # Warehouse Management Custom Fields
    {"dt": "Custom Field", "filters": [["module", "=", "AMB W SPC"]]},
    # Core warehouse integration custom fields
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_stock_entry.json",
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_warehouse.json",
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_work_order.json",
    # Warehouse-Batch Integration custom fields
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_warehouse_batch.json",
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_material_assessment_batch.json",
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_work_order_batch.json",
    # Sales Order Fulfillment Integration custom fields
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_sales_order.json",
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_delivery_note.json",
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_item.json",
    # Purchase Receipt Integration custom fields
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_purchase_receipt.json",
    # Additional warehouse DocTypes custom fields
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_batch.json",
    "amb_w_spc/sfc_manufacturing/fixtures/custom_field_bin.json",
    # Property setters for enhanced warehouse functionality
    "amb_w_spc/sfc_manufacturing/fixtures/property_setter_stock_entry.json",
    "amb_w_spc/sfc_manufacturing/fixtures/property_setter_warehouse.json",
    "amb_w_spc/sfc_manufacturing/fixtures/property_setter_work_order.json",
    "amb_w_spc/sfc_manufacturing/fixtures/property_setter_purchase_receipt.json",
    # Roles and permission fixtures
    "amb_w_spc/system_integration/fixtures/warehouse_roles.json",
    "amb_w_spc/system_integration/fixtures/warehouse_permissions.json"
]

# Additional app configurations for warehouse management
# Jinja template functions
jinja = {
    "methods": [
        "amb_w_spc.sfc_manufacturing.warehouse_management.utils.get_warehouse_zones",
        "amb_w_spc.sfc_manufacturing.warehouse_management.utils.get_pick_task_status",
        "amb_w_spc.sfc_manufacturing.warehouse_management.utils.get_material_assessment_status",
        "amb_w_spc.sfc_manufacturing.warehouse_management.utils.get_warehouse_capacity",
        "amb_w_spc.system_integration.utils.get_user_warehouse_permissions"
    ]
}

# Website routes for warehouse dashboards
website_route_rules = [
    {"from_route": "/warehouse-dashboard", "to_route": "warehouse_dashboard"},
    {"from_route": "/pick-tasks", "to_route": "pick_task_dashboard"},
    {"from_route": "/material-assessment", "to_route": "material_assessment_dashboard"}
]

# Website context
website_context = {
    "splash_image": "/assets/amb_w_spc/images/warehouse_splash.png"
}

# Custom report registration
override_whitelisted_methods = {
    "amb_w_spc.sfc_manufacturing.warehouse_management.api.get_warehouse_dashboard_data": "amb_w_spc.sfc_manufacturing.warehouse_management.api.get_warehouse_dashboard_data",
    "amb_w_spc.sfc_manufacturing.warehouse_management.api.get_pick_task_data": "amb_w_spc.sfc_manufacturing.warehouse_management.api.get_pick_task_data",
    "amb_w_spc.sfc_manufacturing.warehouse_management.api.update_pick_task_status": "amb_w_spc.sfc_manufacturing.warehouse_management.api.update_pick_task_status",
    "amb_w_spc.sfc_manufacturing.warehouse_management.api.get_material_assessment_data": "amb_w_spc.sfc_manufacturing.warehouse_management.api.get_material_assessment_data"
}

# Before install hook
before_install = [
    "amb_w_spc.system_integration.installation.validate_system_requirements",
    "amb_w_spc.system_integration.installation.check_erpnext_version"
]

# After migrate hook
after_migrate = [
    "amb_w_spc.patches.v15.install_warehouse_management.execute",
    "amb_w_spc.system_integration.installation.setup_warehouse_permissions",
    "amb_w_spc.system_integration.installation.create_default_warehouse_zones"
]

# App initialization functions
def on_doctype_update():
    """Setup workflow integration for warehouse management"""
    from amb_w_spc.system_integration.workflows.setup import setup_warehouse_workflows
    setup_warehouse_workflows()

def after_app_install():
    """Post-installation setup for warehouse management"""
    from amb_w_spc.system_integration.installation.post_install import run_warehouse_post_install
    run_warehouse_post_install()

# Error handlers for warehouse operations
on_session_creation = "amb_w_spc.system_integration.permissions.setup_user_warehouse_context"
