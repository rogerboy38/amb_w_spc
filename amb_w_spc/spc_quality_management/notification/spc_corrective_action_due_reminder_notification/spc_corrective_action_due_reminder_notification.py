import frappe

def get_context(context):
    """
    Context for SPC Corrective Action Due Reminder Notification
    """
    if not isinstance(context, dict):
        context = {}
    
    context.setdefault('subject', 'Corrective Action Due Reminder')
    context.setdefault('message', 'A corrective action is due soon and requires attention.')
    
    return context
