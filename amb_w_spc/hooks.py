app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "Your Company"
app_description = "AMB Statistical Process Control"
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

# Fixtures - auto-synced on bench migrate / Frappe Cloud deploy
fixtures = [
    {
        "dt": "Notification",
        "filters": [["module", "=", "SPC Quality Management"]]
    }
]

# After install hook
after_install = "amb_w_spc.setup.after_install"

# ========================================
#  FRONTEND JS INJECTIONS
# ========================================

app_include_js = [
    "/assets/amb_w_spc/js/batch_widget.js",
    "/assets/amb_w_spc/js/sample_request_utils.js",
    "/assets/amb_w_spc/js/sample_request_buttons.js"
]


override_doctype_class = {
    "Batch AMB": "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.BatchAMB"
}

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
