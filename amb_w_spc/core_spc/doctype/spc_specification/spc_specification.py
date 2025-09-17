import frappe
from frappe.model.document import Document

class SpcSpecification(Document):
    def validate(self):
        if not self.specification_name:
            frappe.throw("Field 'Specification Name / Nombre de Especificación' is required.")
        if not self.parameter:
            frappe.throw("Field 'Parameter / Parámetro' is required.")
        if not self.revision:
            frappe.throw("Field 'Revision / Revisión' is required.")
        if self.version is not None and not isinstance(self.version, float):
            frappe.throw("Field 'Version / Versión' must be a float.")
        if self.upper_spec_limit is not None and not isinstance(self.upper_spec_limit, float):
            frappe.throw("Field 'Upper Spec Limit / Límite Superior de Especificación' must be a float.")
        if self.lower_spec_limit is not None and not isinstance(self.lower_spec_limit, float):
            frappe.throw("Field 'Lower Spec Limit / Límite Inferior de Especificación' must be a float.")
        if self.target_value is not None and not isinstance(self.target_value, float):
            frappe.throw("Field 'Target Value / Valor Objetivo' must be a float.")
        if self.nominal_value is not None and not isinstance(self.nominal_value, float):
            frappe.throw("Field 'Nominal Value / Valor Nominal' must be a float.")
        if self.tolerance is not None and not isinstance(self.tolerance, float):
            frappe.throw("Field 'Tolerance (+/-) / Tolerancia (+/-)' must be a float.")
        if self.tolerance_plus is not None and not isinstance(self.tolerance_plus, float):
            frappe.throw("Field 'Tolerance Plus / Tolerancia Positiva' must be a float.")
        if self.tolerance_minus is not None and not isinstance(self.tolerance_minus, float):
            frappe.throw("Field 'Tolerance Minus / Tolerancia Negativa' must be a float.")
        if self.measurement_type and self.measurement_type not in ['Variable', 'Attribute']:
            frappe.throw("Field 'Measurement Type / Tipo de Medición' must be one of ['Variable', 'Attribute'].")
        if self.cpk_target is not None and not isinstance(self.cpk_target, float):
            frappe.throw("Field 'Cpk Target / Objetivo Cpk' must be a float.")
        if self.cp_target is not None and not isinstance(self.cp_target, float):
            frappe.throw("Field 'Cp Target / Objetivo Cp' must be a float.")
        if self.ppk_target is not None and not isinstance(self.ppk_target, float):
            frappe.throw("Field 'Ppk Target / Objetivo Ppk' must be a float.")
        if self.pp_target is not None and not isinstance(self.pp_target, float):
            frappe.throw("Field 'Pp Target / Objetivo Pp' must be a float.")
        if self.sigma_level is not None and not isinstance(self.sigma_level, float):
            frappe.throw("Field 'Sigma Level / Nivel Sigma' must be a float.")
        if self.defect_rate_target is not None and not isinstance(self.defect_rate_target, float):
            frappe.throw("Field 'Defect Rate Target (PPM) / Objetivo de Tasa de Defectos (PPM)' must be a float.")
        if self.process_sigma_target is not None and not isinstance(self.process_sigma_target, float):
            frappe.throw("Field 'Process Sigma Target / Objetivo Sigma del Proceso' must be a float.")
        if self.minimum_cpk is not None and not isinstance(self.minimum_cpk, float):
            frappe.throw("Field 'Minimum Cpk / Cpk Mínimo' must be a float.")
        if self.minimum_cp is not None and not isinstance(self.minimum_cp, float):
            frappe.throw("Field 'Minimum Cp / Cp Mínimo' must be a float.")
        if self.approval_status and self.approval_status not in ['Draft', 'Pending Review', 'Reviewed', 'Approved', 'Rejected', 'Obsolete', 'Pending Approval']:
            frappe.throw("Field 'Approval Status / Estado de Aprobación' must be one of ['Draft', 'Pending Review', 'Reviewed', 'Approved', 'Rejected', 'Obsolete', 'Pending Approval'].")
        if self.status and self.status not in ['Draft', 'Active', 'Inactive', 'Obsolete']:
            frappe.throw("Field 'Status / Estado' must be one of ['Draft', 'Active', 'Inactive', 'Obsolete'].")
        if self.specification_source and self.specification_source not in ['Customer Requirement', 'Industry Standard', 'Internal Standard', 'Regulatory Requirement']:
            frappe.throw("Field 'Specification Source / Fuente de Especificación' must be one of ['Customer Requirement', 'Industry Standard', 'Internal Standard', 'Regulatory Requirement'].")
        if self.quality_characteristic and self.quality_characteristic not in ['Critical', 'Major', 'Minor']:
            frappe.throw("Field 'Quality Characteristic / Característica de Calidad' must be one of ['Critical', 'Major', 'Minor'].")
        if self.criticality_level and self.criticality_level not in ['High', 'Medium', 'Low']:
            frappe.throw("Field 'Criticality Level / Nivel de Criticidad' must be one of ['High', 'Medium', 'Low'].")
        if self.measurement_uncertainty is not None and not isinstance(self.measurement_uncertainty, float):
            frappe.throw("Field 'Measurement Uncertainty (%) / Incertidumbre de Medición (%)' must be a float.")
        if self.sampling_plan and self.sampling_plan not in ['100% Inspection', 'Statistical Sampling', 'Skip Lot', 'Reduced Inspection']:
            frappe.throw("Field 'Sampling Plan / Plan de Muestreo' must be one of ['100% Inspection', 'Statistical Sampling', 'Skip Lot', 'Reduced Inspection'].")
        if self.inspection_frequency and self.inspection_frequency not in ['Every Unit', 'Every Hour', 'Every Shift', 'Daily', 'Weekly', 'Batch Based']:
            frappe.throw("Field 'Inspection Frequency / Frecuencia de Inspección' must be one of ['Every Unit', 'Every Hour', 'Every Shift', 'Daily', 'Weekly', 'Batch Based'].")
