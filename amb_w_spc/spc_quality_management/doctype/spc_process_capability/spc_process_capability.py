import frappe
from frappe.model.document import Document

class SPCProcessCapability(Document):
    def validate(self):
        if not self.study_name:
            frappe.throw("Field 'Study Name' is required.")
        if not self.parameter:
            frappe.throw("Field 'Parameter' is required.")
        if not self.plant:
            frappe.throw("Field 'Plant' is required.")
        if not self.study_period:
            frappe.throw("Field 'Study Period' is required.")
        if self.study_type and self.study_type not in ['Initial Study', 'Ongoing Monitoring', 'Revalidation', 'Improvement Verification']:
            frappe.throw("Field 'Study Type' must be one of ['Initial Study', 'Ongoing Monitoring', 'Revalidation', 'Improvement Verification'].")
        if self.study_status and self.study_status not in ['Draft', 'In Progress', 'Completed', 'Approved', 'Rejected']:
            frappe.throw("Field 'Study Status' must be one of ['Draft', 'In Progress', 'Completed', 'Approved', 'Rejected'].")
        if not self.sample_size:
            frappe.throw("Field 'Sample Size' is required.")
        if self.sample_size is not None and not isinstance(self.sample_size, int):
            frappe.throw("Field 'Sample Size' must be an integer.")
        if self.subgroup_size is not None and not isinstance(self.subgroup_size, int):
            frappe.throw("Field 'Subgroup Size' must be an integer.")
        if self.target_value is not None and not isinstance(self.target_value, float):
            frappe.throw("Field 'Target Value' must be a float.")
        if self.lower_specification_limit is not None and not isinstance(self.lower_specification_limit, float):
            frappe.throw("Field 'Lower Specification Limit (LSL)' must be a float.")
        if self.upper_specification_limit is not None and not isinstance(self.upper_specification_limit, float):
            frappe.throw("Field 'Upper Specification Limit (USL)' must be a float.")
        if self.tolerance is not None and not isinstance(self.tolerance, float):
            frappe.throw("Field 'Tolerance' must be a float.")
        if self.process_mean is not None and not isinstance(self.process_mean, float):
            frappe.throw("Field 'Process Mean' must be a float.")
        if self.process_std_dev is not None and not isinstance(self.process_std_dev, float):
            frappe.throw("Field 'Process Standard Deviation' must be a float.")
        if self.cp is not None and not isinstance(self.cp, float):
            frappe.throw("Field 'Cp (Potential Capability)' must be a float.")
        if self.cpk is not None and not isinstance(self.cpk, float):
            frappe.throw("Field 'Cpk (Actual Capability)' must be a float.")
        if self.pp is not None and not isinstance(self.pp, float):
            frappe.throw("Field 'Pp (Potential Performance)' must be a float.")
        if self.ppk is not None and not isinstance(self.ppk, float):
            frappe.throw("Field 'Ppk (Actual Performance)' must be a float.")
        if self.sigma_level is not None and not isinstance(self.sigma_level, float):
            frappe.throw("Field 'Sigma Level' must be a float.")
        if self.process_performance_index is not None and not isinstance(self.process_performance_index, float):
            frappe.throw("Field 'Process Performance Index' must be a float.")
        if self.capability_rating and self.capability_rating not in ['Excellent (Cpk > 2.0)', 'Adequate (1.33 < Cpk ≤ 2.0)', 'Marginal (1.0 < Cpk ≤ 1.33)', 'Inadequate (Cpk ≤ 1.0)']:
            frappe.throw("Field 'Capability Rating' must be one of ['Excellent (Cpk > 2.0)', 'Adequate (1.33 < Cpk ≤ 2.0)', 'Marginal (1.0 < Cpk ≤ 1.33)', 'Inadequate (Cpk ≤ 1.0)'].")
        if self.target_capability is not None and not isinstance(self.target_capability, float):
            frappe.throw("Field 'Target Capability (Cpk)' must be a float.")
        if self.defect_rate_ppm is not None and not isinstance(self.defect_rate_ppm, float):
            frappe.throw("Field 'Defect Rate (PPM)' must be a float.")
        if self.normality_test and self.normality_test not in ['Normal', 'Non-Normal', 'Not Tested']:
            frappe.throw("Field 'Normality Test Result' must be one of ['Normal', 'Non-Normal', 'Not Tested'].")
        if self.control_chart_stability and self.control_chart_stability not in ['Stable', 'Unstable', 'Not Assessed']:
            frappe.throw("Field 'Control Chart Stability' must be one of ['Stable', 'Unstable', 'Not Assessed'].")
