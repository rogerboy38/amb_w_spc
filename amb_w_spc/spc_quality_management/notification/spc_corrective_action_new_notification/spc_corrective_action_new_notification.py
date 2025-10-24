import frappe

def get_context(context):
    """
    Context for SPC Corrective Action New Notification
    This provides the template context for the notification
    """
    # context should be a dictionary that Frappe can use
    if not isinstance(context, dict):
        context = {}
    
    # Set default values that Frappe expects
    context.setdefault('subject', 'New Corrective Action Created')
    context.setdefault('message', 'A new corrective action has been created and requires attention.')
    
    return context
