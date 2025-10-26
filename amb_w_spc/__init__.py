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

# Load compatibility layer early
try:
    from amb_w_spc.compat import patch_frappe_utils
    patch_frappe_utils()
except ImportError:
    # Compatibility module might not be available during initial install
    pass
