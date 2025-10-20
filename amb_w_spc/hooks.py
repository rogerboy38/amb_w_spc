app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "AMB-Wellness"
app_description = "Advanced Manufacturing, Warehouse Management & Statistical Process Control for ERPNext"
app_email = "fcrm@amb-wellness.com"
app_license = "MIT"
app_version = "2.0.3"

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

# Document Events - Minimal working set
doc_events = {
    # Basic events that don't require complex dependencies
    "Sales Order": {
        "on_submit": "amb_w_spc.sfc_manufacturing.api.sfc_operations.on_sales_order_submit",
    },
}

# Scheduled Tasks - Minimal working set
scheduler_events = {
    "daily": [
        "amb_w_spc.sfc_manufacturing.scheduler.daily_cleanup",
    ],
}

# Application includes
app_include_css = [
    "/assets/amb_w_spc/css/warehouse_management.css",
    "/assets/amb_w_spc/css/spc_quality.css"
]

app_include_js = [
    "/assets/amb_w_spc/js/warehouse_utils.js"
]

# Boot Session - Simple implementation
boot_session = "amb_w_spc.system_integration.permissions.get_boot_info"

# Installation hooks
before_install = "amb_w_spc.install.before_install"
after_install = "amb_w_spc.install.after_install"
before_uninstall = "amb_w_spc.install.before_uninstall"

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
    {"dt": "Property Setter", "filters": [["module", "=", "AMB W SPC"]]},
]

# Jinja template functions
jinja = {
    "methods": [
        "amb_w_spc.system_integration.utils.get_app_version",
    ]
}

# Website routes
website_route_rules = [
    {"from_route": "/warehouse-dashboard", "to_route": "warehouse_dashboard"},
    {"from_route": "/spc-dashboard", "to_route": "spc_dashboard"},
]

# Website context
website_context = {
    "splash_image": "/assets/amb_w_spc/images/warehouse_splash.png",
    "favicon": "/assets/amb_w_spc/images/favicon.ico"
}

# Override whitelisted methods
override_whitelisted_methods = {
    "amb_w_spc.sfc_manufacturing.api.sfc_operations.get_dashboard_data": "amb_w_spc.sfc_manufacturing.api.sfc_operations.get_dashboard_data",
}

# Migration hooks
after_migrate = [
    "amb_w_spc.system_integration.installation.install_spc_system.install_spc_system"
]

# Testing
before_tests = "amb_w_spc.install.before_tests"

# Source parser
source_parser = {
    "github.com": "frappe.www.doctype.web_page.web_page.get_source"
}
