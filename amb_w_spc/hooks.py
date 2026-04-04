from . import __version__ as app_version

app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "Your Company"
app_description = "Advanced Manufacturing with SPC"
app_email = "your-email@example.com"
app_license = "MIT"

# Includes in <base>/apps/amb_w_spc/amb_w_spc
app_include_js = "/assets/amb_w_spc/js/amb_w_spc.js"

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
  "Plant Equipment"
]

# Fixtures - EXCLUDE Sensor Skill to prevent install-app freeze at 82%
# Sensor Skill records are created via patch 03_create_sensor_skill_records.py
# by running: bench --site v2.sysmayal.cloud execute amb_w_spc.patches.v15.create_sensor_skill_records.execute
fixtures = [
    {"dt": "DocType", "filters": [["module", "in", [
        "Core SPC",
        "SPC Quality Management",
        "System Integration",
        "Operator Management",
        "Sensor Management",
        "Shop Floor Control",
        "SFC Manufacturing",
        "FDA Compliance",
        "Plant Equipment"
    ]]]}
]

# After install hook
after_install = "amb_w_spc.install.after_install"
