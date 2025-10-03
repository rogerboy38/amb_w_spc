import frappe

def execute():
    """Create modules using v15 compatible method"""
    from amb_w_spc.install import create_modules_v15
    create_modules_v15()
