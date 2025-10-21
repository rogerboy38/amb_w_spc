app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "AMB-Wellness"
app_description = "Advanced Manufacturing, Warehouse Management & Statistical Process Control for ERPNext"
app_email = "fcrm@amb-wellness.com"
app_license = "MIT"
app_version = "2.0.4"

required_apps = ["frappe", "erpnext"]

auto_install_apps = []

# Your core modules - these will appear in modules page
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

doc_events = {
}

scheduler_events = {
}

app_include_css = [
    "/assets/amb_w_spc/css/warehouse_management.css",
    "/assets/amb_w_spc/css/spc_quality.css"
]

app_include_js = [
    "/assets/amb_w_spc/js/warehouse_utils.js"
]

after_install = "amb_w_spc.install.after_install"

# Only include essential fixtures - NO WORKSPACES
fixtures = [
    {"dt": "Workflow", "filters": [["name", "in", [
        "SPC Alert Workflow",
        "SPC Corrective Action Workflow", 
        "SPC Process Capability Workflow",
        "TDS Product Specification Workflow"
    ]]]},
    {"dt": "Custom Field", "filters": [["module", "=", "AMB W SPC"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "AMB W SPC"]]},
]

jinja = {
    "methods": [
    ]
}

website_route_rules = [
    {"from_route": "/warehouse-dashboard", "to_route": "warehouse_dashboard"},
    {"from_route": "/spc-dashboard", "to_route": "spc_dashboard"},
]

website_context = {
    "splash_image": "/assets/amb_w_spc/images/warehouse_splash.png",
    "favicon": "/assets/amb_w_spc/images/favicon.ico"
}

override_whitelisted_methods = {
}

source_parser = {
    "github.com": "frappe.www.doctype.web_page.web_page.get_source"
}
