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

# Modules
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

# DocType overrides
# override_doctype_class = {}

# Document Events - COMMENTED OUT TEMPORARILY
doc_events = {
    # "Sales Order": {
    #     "on_submit": "amb_w_spc.sfc_manufacturing.warehouse_management.sales_order_integration.SalesOrderIntegration.on_sales_order_submit",
    # },
    # "Delivery Note": {
    #     "before_submit": "amb_w_spc.sfc_manufacturing.warehouse_management.delivery_note_integration.DeliveryNoteIntegration.on_delivery_note_before_submit",
    # },
    # Add other doc_events as needed when modules are available
}

# Scheduled Tasks - COMMENTED OUT TEMPORARILY
scheduler_events = {
    # "daily": [
    #     "amb_w_spc.system_integration.scheduler.sync_warehouse_data"
    # ],
}

# Application includes
app_include_css = [
    "/assets/amb_w_spc/css/warehouse_management.css",
    "/assets/amb_w_spc/css/spc_quality.css"
]

app_include_js = [
    "/assets/amb_w_spc/js/warehouse_utils.js"
]

# Boot Session - COMMENTED OUT TEMPORARILY
# boot_session = "amb_w_spc.sfc_manufacturing.warehouse_management.boot.get_warehouse_boot_session"

# Installation
post_install = [
     "amb_w_spc.post_install.run"
]

# Workspaces
workspaces = [
    "SPC Dashboard",
    "SPC Quality Management", 
    "Manufacturing Control"
]

# Fixtures to load during installation
fixtures = [
    {"dt": "Workspace", "filters": [["name", "in", workspaces]]},
    {"dt": "Workflow", "filters": [["name", "in", [
        "SPC Alert Workflow",
        "SPC Corrective Action Workflow",
        "SPC Process Capability Workflow",
        "TDS Product Specification Workflow"
    ]]]},
    {"dt": "Custom Field", "filters": [["module", "=", "AMB W SPC"]]},
]

# Jinja template functions - COMMENTED OUT TEMPORARILY
jinja = {
    "methods": [
        # "amb_w_spc.system_integration.utils.get_user_warehouse_permissions"
    ]
}

# Website routes
website_route_rules = [
    {"from_route": "/warehouse-dashboard", "to_route": "warehouse_dashboard"},
]

# Website context
website_context = {
    "splash_image": "/assets/amb_w_spc/images/warehouse_splash.png"
}

# Override whitelisted methods - COMMENTED OUT TEMPORARILY
# override_whitelisted_methods = {}

# All installation hooks commented out temporarily
# before_install = []
# after_migrate = []

