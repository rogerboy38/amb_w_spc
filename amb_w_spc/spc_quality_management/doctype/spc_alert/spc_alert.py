import frappe
from frappe.model.document import Document

class SpcAlert(Document):
    def validate(self):
        if not self.alert_id:
            frappe.throw("Field 'Alert ID' is required.")
        if not self.timestamp:
            frappe.throw("Field 'Timestamp' is required.")
        if not self.plant:
            frappe.throw("Field 'Plant' is required.")
        if not self.workstation:
            frappe.throw("Field 'SPC Workstation' is required.")
        if not self.parameter:
            frappe.throw("Field 'Parameter' is required.")
        if not self.alert_type:
            frappe.throw("Field 'Alert Type' is required.")
        if self.alert_type and self.alert_type not in ['Out of Control', 'Trend', 'Shift', 'Run']:
            frappe.throw("Field 'Alert Type' must be one of ['Out of Control', 'Trend', 'Shift', 'Run'].")
        if not self.severity_level:
            frappe.throw("Field 'Severity Level' is required.")
        if self.severity_level and self.severity_level not in ['Low', 'Medium', 'High', 'Critical']:
            frappe.throw("Field 'Severity Level' must be one of ['Low', 'Medium', 'High', 'Critical'].")
        if self.rule_violated and self.rule_violated not in ['Rule 1: One point beyond 3σ', 'Rule 2: Nine points on one side of centerline', 'Rule 3: Six consecutive points increasing/decreasing', 'Rule 4: Fourteen consecutive points alternating', 'Rule 5: Two out of three points beyond 2σ', 'Rule 6: Four out of five points beyond 1σ', 'Rule 7: Fifteen consecutive points within 1σ', 'Rule 8: Eight consecutive points beyond 1σ']:
            frappe.throw("Field 'Rule Violated (Western Electric)' must be one of ['Rule 1: One point beyond 3σ', 'Rule 2: Nine points on one side of centerline', 'Rule 3: Six consecutive points increasing/decreasing', 'Rule 4: Fourteen consecutive points alternating', 'Rule 5: Two out of three points beyond 2σ', 'Rule 6: Four out of five points beyond 1σ', 'Rule 7: Fifteen consecutive points within 1σ', 'Rule 8: Eight consecutive points beyond 1σ'].")
        if self.consecutive_points is not None and not isinstance(self.consecutive_points, int):
            frappe.throw("Field 'Consecutive Points' must be an integer.")
        if self.trend_direction and self.trend_direction not in ['Increasing', 'Decreasing', 'Stable', 'Oscillating']:
            frappe.throw("Field 'Trend Direction' must be one of ['Increasing', 'Decreasing', 'Stable', 'Oscillating'].")
        if self.escalation_level and self.escalation_level not in ['Level 1 - Operator', 'Level 2 - Supervisor', 'Level 3 - Manager', 'Level 4 - Plant Manager']:
            frappe.throw("Field 'Escalation Level' must be one of ['Level 1 - Operator', 'Level 2 - Supervisor', 'Level 3 - Manager', 'Level 4 - Plant Manager'].")
        if not self.alert_status:
            frappe.throw("Field 'Alert Status' is required.")
        if self.alert_status and self.alert_status not in ['Open', 'Acknowledged', 'Investigating', 'Resolved']:
            frappe.throw("Field 'Alert Status' must be one of ['Open', 'Acknowledged', 'Investigating', 'Resolved'].")
