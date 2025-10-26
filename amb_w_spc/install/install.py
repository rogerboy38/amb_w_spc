import frappe

def after_install():
    """Called after app is installed"""
    print("AMB W SPC App installed successfully!")
    # Add any post-installation setup here
    
    # Example: Create default records if needed
    # create_default_records()

def create_default_records():
    """Create default records after installation"""
    pass

def before_install():
    """Called before app is installed"""
    pass

def before_uninstall():
    """Called before app is uninstalled"""
    pass

def after_uninstall():
    """Called after app is uninstalled"""
    pass
