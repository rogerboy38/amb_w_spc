import frappe

def get_context(context):
    """
    Context for spc_report_generated_notification
    """
    if not isinstance(context, dict):
        context = {}
    
    # Set appropriate default values based on notification type
    if "alert_new" in "spc_report_generated_notification":
        context.setdefault('subject', 'New SPC Alert Created')
        context.setdefault('message', 'A new SPC quality alert has been triggered.')
    elif "alert_escalation" in "spc_report_generated_notification":
        context.setdefault('subject', 'SPC Alert Escalation')
        context.setdefault('message', 'An SPC alert has been escalated.')
    elif "report_generated" in "spc_report_generated_notification":
        context.setdefault('subject', 'SPC Report Generated') 
        context.setdefault('message', 'An SPC report has been generated.')
    elif "process_capability" in "spc_report_generated_notification":
        context.setdefault('subject', 'Process Capability Study Completed')
        context.setdefault('message', 'A process capability study has been completed.')
    
    return context
