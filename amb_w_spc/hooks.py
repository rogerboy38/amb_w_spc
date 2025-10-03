app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "AMB-Wellness"
app_description = "Advanced Manufacturing & Statistical Process Control for ERPNext"
app_email = "fcrm@amb-wellness.com"
app_license = "MIT"
app_version = "1.0.1"

# Required property for ERPNext
required_apps = ["erpnext"]

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
    'fda_compliance'
]

# IMPORTANT: Commented out to avoid Frappe v15.84.0 installer bug
# The patch system will handle module creation instead
# after_app_install = []

# DocType overrides
# override_doctype_class = {}

# Document Events
# doc_events = {}

# Scheduled Tasks
# scheduler_events = {}

# Testing
# before_tests = []

# Overriding Methods
# override_whitelisted_methods = {}

# Boot Session
# boot_session = []

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

# Fixtures to load during installation
fixtures = [
    {"dt": "Workspace", "filters": [["name", "in", workspaces]]},
    {"dt": "Workflow", "filters": [["name", "in", [
        "Batch AMB Manufacturing Workflow",
        "SPC Alert Workflow",
        "SPC Corrective Action Workflow",
        "SPC Process Capability Workflow",
        "TDS Product Specification Workflow"
    ]]]}
]

# Add workflow integration to app initialization
def on_doctype_update():
    """Setup workflow integration"""
