import frappe
from frappe.model.document import Document

class SpcDataPoint(Document):
    def validate(self):
        if not self.timestamp:
            frappe.throw("Field 'Timestamp / Marca de Tiempo' is required.")
        if not self.parameter:
            frappe.throw("Field 'Parameter / Parámetro' is required.")
        if self.shift and self.shift not in ['Day', 'Evening', 'Night', 'Rotating']:
            frappe.throw("Field 'Shift / Turno' must be one of ['Day', 'Evening', 'Night', 'Rotating'].")
        if not self.measured_value:
            frappe.throw("Field 'Measured Value / Valor Medido' is required.")
        if self.measured_value is not None and not isinstance(self.measured_value, float):
            frappe.throw("Field 'Measured Value / Valor Medido' must be a float.")
        if self.target_value is not None and not isinstance(self.target_value, float):
            frappe.throw("Field 'Target Value / Valor Objetivo' must be a float.")
        if self.upper_control_limit is not None and not isinstance(self.upper_control_limit, float):
            frappe.throw("Field 'Upper Control Limit / Límite Superior de Control' must be a float.")
        if self.lower_control_limit is not None and not isinstance(self.lower_control_limit, float):
            frappe.throw("Field 'Lower Control Limit / Límite Inferior de Control' must be a float.")
        if self.upper_spec_limit is not None and not isinstance(self.upper_spec_limit, float):
            frappe.throw("Field 'Upper Spec Limit / Límite Superior de Especificación' must be a float.")
        if self.lower_spec_limit is not None and not isinstance(self.lower_spec_limit, float):
            frappe.throw("Field 'Lower Spec Limit / Límite Inferior de Especificación' must be a float.")
        if self.x_bar is not None and not isinstance(self.x_bar, float):
            frappe.throw("Field 'X-Bar / Promedio' must be a float.")
        if self.r_value is not None and not isinstance(self.r_value, float):
            frappe.throw("Field 'R Value / Valor de Rango' must be a float.")
        if self.moving_average is not None and not isinstance(self.moving_average, float):
            frappe.throw("Field 'Moving Average / Promedio Móvil' must be a float.")
        if self.moving_range is not None and not isinstance(self.moving_range, float):
            frappe.throw("Field 'Moving Range / Rango Móvil' must be a float.")
        if self.standard_deviation is not None and not isinstance(self.standard_deviation, float):
            frappe.throw("Field 'Standard Deviation / Desviación Estándar' must be a float.")
        if self.subgroup_number is not None and not isinstance(self.subgroup_number, int):
            frappe.throw("Field 'Subgroup Number / Número de Subgrupo' must be an integer.")
        if not self.status:
            frappe.throw("Field 'Status / Estado' is required.")
        if self.status and self.status not in ['Valid', 'Invalid', 'Pending Review']:
            frappe.throw("Field 'Status / Estado' must be one of ['Valid', 'Invalid', 'Pending Review'].")
        if self.validation_status and self.validation_status not in ['Pending', 'Validated', 'Rejected', 'Under Review']:
            frappe.throw("Field 'Validation Status / Estado de Validación' must be one of ['Pending', 'Validated', 'Rejected', 'Under Review'].")
        if self.cp is not None and not isinstance(self.cp, float):
            frappe.throw("Field 'Cp' must be a float.")
        if self.cpk is not None and not isinstance(self.cpk, float):
            frappe.throw("Field 'Cpk' must be a float.")
        if self.pp is not None and not isinstance(self.pp, float):
            frappe.throw("Field 'Pp' must be a float.")
        if self.ppk is not None and not isinstance(self.ppk, float):
            frappe.throw("Field 'Ppk' must be a float.")
        if self.sigma_level is not None and not isinstance(self.sigma_level, float):
            frappe.throw("Field 'Sigma Level / Nivel Sigma' must be a float.")
