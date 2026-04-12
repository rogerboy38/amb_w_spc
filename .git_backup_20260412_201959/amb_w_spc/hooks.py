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
