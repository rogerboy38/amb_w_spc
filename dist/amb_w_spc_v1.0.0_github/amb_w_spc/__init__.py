__version__ = "1.0.0"

"""
AMB W SPC - Advanced Manufacturing Business Workforce Statistical Process Control

A comprehensive Frappe/ERPNext application for manufacturing quality control,
statistical process control, and shop floor management.

Key Features:
- Statistical Process Control (SPC) with real-time monitoring
- Shop Floor Control (SFC) for manufacturing operations
- Operator management and skill tracking
- Real-time sensor data integration
- FDA compliance and quality management
- Process capability analysis
- Alert management and corrective actions
"""

import frappe

def get_version():
    return __version__

def connect():
    return frappe.connect()

# App configuration
app_name = "amb_w_spc"
app_title = "AMB W SPC"
app_publisher = "AMB Systems"
app_description = "Advanced Manufacturing Business - Workforce Statistical Process Control"
app_email = "info@ambsystems.com"
app_license = "MIT"

# Version compatibility
required_apps = [
    "frappe>=15.0.0",
    "erpnext>=15.0.0"
]

# Installation hooks
installation_hooks = [
    "amb_w_spc.install.before_install",
    "amb_w_spc.install.after_install"
]