app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "Your Company"
app_description = "Advanced Manufacturing with SPC"
app_email = "your-email@example.com"
app_license = "MIT"
app_version = "1.0.0"

# Apps to include in the site
app_include = [
    "Core SPC",
    "SPC Quality Management",
    "System Integration",
    "Operator Management",
    "Sensor Management",
    "Shop Floor Control",
    "SFC Manufacturing",
    "FDA Compliance",
    "Plant Equipment",
    "Real Time Monitoring"
]

# List of modules (must match directory names)
modules = [
    "core_spc",
    "spc_quality_management",
    "sfc_manufacturing",
    "operator_management",
    "shop_floor_control",
    "plant_equipment",
    "real_time_monitoring",
    "sensor_management",
    "system_integration",
    "fda_compliance"
]

# No fixtures for now
fixtures = []

def after_install():
    print("AMB W SPC App installed successfully!")

# ========================================
#  DOCUMENT EVENTS (Batch AMB Golden Number)
# ========================================

doc_events = {
    # ---- Batch AMB: Golden number auto-generation via amb_w_spc controller
    "Batch AMB": {
        "validate": [
            "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.batch_amb_validate",
        ],
        "before_save": [
            "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.batch_amb_before_save",
        ],
    },
}
