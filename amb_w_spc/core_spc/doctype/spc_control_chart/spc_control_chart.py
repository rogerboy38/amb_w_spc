import frappe
from frappe.model.document import Document

class SpcControlChart(Document):
    def validate(self):
        if not self.chart_name:
            frappe.throw("Field 'Chart Name / Nombre del Gráfico' is required.")
        if not self.chart_type:
            frappe.throw("Field 'Chart Type / Tipo de Gráfico' is required.")
        if self.chart_type and self.chart_type not in ['X-bar R', 'Individual-Moving Range', 'p-chart', 'c-chart', 'u-chart', 'np-chart', 'CUSUM', 'EWMA', 'X-bar R Chart', 'Individual-MR Chart', 'p-Chart', 'np-Chart', 'c-Chart', 'u-Chart', 'CUSUM Chart', 'EWMA Chart']:
            frappe.throw("Field 'Chart Type / Tipo de Gráfico' must be one of ['X-bar R', 'Individual-Moving Range', 'p-chart', 'c-chart', 'u-chart', 'np-chart', 'CUSUM', 'EWMA', 'X-bar R Chart', 'Individual-MR Chart', 'p-Chart', 'np-Chart', 'c-Chart', 'u-Chart', 'CUSUM Chart', 'EWMA Chart'].")
        if not self.parameter:
            frappe.throw("Field 'Parameter / Parámetro' is required.")
        if self.chart_period and self.chart_period not in ['Real-time', 'Hourly', 'Daily', 'Weekly', 'Monthly']:
            frappe.throw("Field 'Chart Period / Período del Gráfico' must be one of ['Real-time', 'Hourly', 'Daily', 'Weekly', 'Monthly'].")
        if self.sample_size is not None and not isinstance(self.sample_size, int):
            frappe.throw("Field 'Sample Size / Tamaño de Muestra' must be an integer.")
        if self.subgroup_size is not None and not isinstance(self.subgroup_size, int):
            frappe.throw("Field 'Subgroup Size / Tamaño de Subgrupo' must be an integer.")
        if self.rational_subgrouping and self.rational_subgrouping not in ['Time Based', 'Production Based', 'Batch Based', 'Operator Based']:
            frappe.throw("Field 'Rational Subgrouping / Subagrupación Racional' must be one of ['Time Based', 'Production Based', 'Batch Based', 'Operator Based'].")
        if self.data_collection_frequency and self.data_collection_frequency not in ['Continuous', 'Hourly', 'Daily', 'Shift', 'Weekly']:
            frappe.throw("Field 'Data Collection Frequency / Frecuencia de Recolección' must be one of ['Continuous', 'Hourly', 'Daily', 'Shift', 'Weekly'].")
        if self.ucl is not None and not isinstance(self.ucl, float):
            frappe.throw("Field 'Upper Control Limit (UCL) / Límite Superior de Control' must be a float.")
        if self.lcl is not None and not isinstance(self.lcl, float):
            frappe.throw("Field 'Lower Control Limit (LCL) / Límite Inferior de Control' must be a float.")
        if self.center_line is not None and not isinstance(self.center_line, float):
            frappe.throw("Field 'Center Line / Línea Central' must be a float.")
        if self.target_value is not None and not isinstance(self.target_value, float):
            frappe.throw("Field 'Target Value / Valor Objetivo' must be a float.")
        if self.control_limits_method and self.control_limits_method not in ['Historical Data', 'Theoretical', 'SPC Process Capability']:
            frappe.throw("Field 'Control Limits Method / Método de Límites de Control' must be one of ['Historical Data', 'Theoretical', 'SPC Process Capability'].")
        if self.sigma_level is not None and not isinstance(self.sigma_level, float):
            frappe.throw("Field 'Sigma Level / Nivel Sigma' must be a float.")
        if self.calculation_method and self.calculation_method not in ['Standard Deviation', 'Range', 'Moving Range', 'Pooled Standard Deviation']:
            frappe.throw("Field 'Calculation Method / Método de Cálculo' must be one of ['Standard Deviation', 'Range', 'Moving Range', 'Pooled Standard Deviation'].")
        if self.control_period is not None and not isinstance(self.control_period, int):
            frappe.throw("Field 'Control Period (Days) / Período de Control (Días)' must be an integer.")
        if self.recalculation_frequency and self.recalculation_frequency not in ['Real-time', 'Hourly', 'Daily', 'Weekly', 'Monthly']:
            frappe.throw("Field 'Recalculation Frequency / Frecuencia de Recalculo' must be one of ['Real-time', 'Hourly', 'Daily', 'Weekly', 'Monthly'].")
        if self.data_points_limit is not None and not isinstance(self.data_points_limit, int):
            frappe.throw("Field 'Data Points Limit / Límite de Puntos de Datos' must be an integer.")
        if self.time_period and self.time_period not in ['Last 24 Hours', 'Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Custom Range']:
            frappe.throw("Field 'Time Period / Período de Tiempo' must be one of ['Last 24 Hours', 'Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Custom Range'].")
        if self.data_points_to_display is not None and not isinstance(self.data_points_to_display, int):
            frappe.throw("Field 'Data Points to Display / Puntos de Datos a Mostrar' must be an integer.")
        if self.refresh_interval is not None and not isinstance(self.refresh_interval, int):
            frappe.throw("Field 'Refresh Interval (minutes) / Intervalo de Actualización (minutos)' must be an integer.")
        if self.violation_threshold is not None and not isinstance(self.violation_threshold, int):
            frappe.throw("Field 'Violation Threshold / Umbral de Violación' must be an integer.")
        if self.color_coding and self.color_coding not in ['Standard', 'Process State', 'Alert Level']:
            frappe.throw("Field 'Color Coding / Codificación de Colores' must be one of ['Standard', 'Process State', 'Alert Level'].")
        if self.status and self.status not in ['Active', 'Inactive', 'Under Review']:
            frappe.throw("Field 'Status / Estado' must be one of ['Active', 'Inactive', 'Under Review'].")
