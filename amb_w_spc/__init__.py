__version__ = '1.0.0'

# Shim para frappe.amb_w_spc - Soluciona el bug de migración
import sys
import frappe

# Registrar el módulo en el namespace de frappe si no existe
frappe_module = sys.modules.get('frappe')
if frappe_module and not hasattr(frappe_module, 'amb_w_spc'):
    import importlib
    real_module = importlib.import_module('amb_w_spc')
    setattr(frappe_module, 'amb_w_spc', real_module)
