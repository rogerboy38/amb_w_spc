// Custom Script for SPC Data Point
// File: spc_data_point_client_script.js

frappe.ui.form.on('SPC Data Point', {
    onload: function(frm) {
        // Set default values
        if (frm.is_new()) {
            frm.set_value('timestamp', frappe.datetime.now_datetime());
            frm.set_value('operator', frappe.session.user);
            
            // Set plant from user defaults
            if (frappe.defaults.get_user_default('Company')) {
                frm.set_value('plant', frappe.defaults.get_user_default('Company'));
            }
        }
        
        // Set up filters
        frm.set_query('parameter', function() {
            return {
                filters: {
                    'status': 'Active'
                }
            };
        });
        
        frm.set_query('workstation', function() {
            return {
                filters: {
                    'disabled': 0
                }
            };
        });
    },
    
    validate: function(frm) {
        // Validate measurement value
        if (!frm.doc.measured_value && frm.doc.measured_value !== 0) {
            frappe.throw(__("Measured Value is required"));
        }
        
        // Validate control limits
        if (frm.doc.upper_control_limit && frm.doc.lower_control_limit) {
            if (frm.doc.upper_control_limit <= frm.doc.lower_control_limit) {
                frappe.throw(__("Upper Control Limit must be greater than Lower Control Limit"));
            }
        }
        
        // Validate specification limits
        if (frm.doc.upper_spec_limit && frm.doc.lower_spec_limit) {
            if (frm.doc.upper_spec_limit <= frm.doc.lower_spec_limit) {
                frappe.throw(__("Upper Specification Limit must be greater than Lower Specification Limit"));
            }
        }
        
        // Auto-validate status based on limits
        frm.trigger('auto_validate_status');
    },
    
    auto_validate_status: function(frm) {
        let status = 'Valid';
        let notes = [];
        
        // Check control limits
        if (frm.doc.upper_control_limit && frm.doc.measured_value > frm.doc.upper_control_limit) {
            status = 'Invalid';
            notes.push('Above Upper Control Limit');
        }
        if (frm.doc.lower_control_limit && frm.doc.measured_value < frm.doc.lower_control_limit) {
            status = 'Invalid';
            notes.push('Below Lower Control Limit');
        }
        
        // Check specification limits
        if (frm.doc.upper_spec_limit && frm.doc.measured_value > frm.doc.upper_spec_limit) {
            status = 'Invalid';
            notes.push('Above Upper Specification Limit');
        }
        if (frm.doc.lower_spec_limit && frm.doc.measured_value < frm.doc.lower_spec_limit) {
            status = 'Invalid';
            notes.push('Below Lower Specification Limit');
        }
        
        if (status !== frm.doc.status) {
            frm.set_value('status', status);
        }
        
        if (notes.length > 0 && status === 'Invalid') {
            frm.set_value('validation_notes', notes.join(', '));
        }
    },
    
    parameter: function(frm) {
        // Fetch parameter details and set related fields
        if (frm.doc.parameter) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SPC Parameter Master',
                    name: frm.doc.parameter
                },
                callback: function(r) {
                    if (r.message) {
                        // Get specification limits from active specification
                        frm.trigger('fetch_specification_limits');
                    }
                }
            });
        }
    },
    
    fetch_specification_limits: function(frm) {
        if (frm.doc.parameter) {
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'SPC Specification',
                    filters: {
                        'parameter': frm.doc.parameter,
                        'status': 'Active',
                        'valid_from': ['<=', frappe.datetime.now_date()],
                        'approval_status': 'Approved'
                    },
                    fields: ['name', 'target_value', 'upper_spec_limit', 'lower_spec_limit', 'upper_control_limit', 'lower_control_limit'],
                    order_by: 'valid_from desc',
                    limit: 1
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        const spec = r.message[0];
                        frm.set_value('target_value', spec.target_value);
                        frm.set_value('upper_spec_limit', spec.upper_spec_limit);
                        frm.set_value('lower_spec_limit', spec.lower_spec_limit);
                        frm.set_value('upper_control_limit', spec.upper_control_limit);
                        frm.set_value('lower_control_limit', spec.lower_control_limit);
                    }
                }
            });
        }
    },
    
    measured_value: function(frm) {
        // Trigger validation when measured value changes
        frm.trigger('auto_validate_status');
        
        // Calculate process capability if enabled
        if (frm.doc.process_capability) {
            frm.trigger('calculate_process_capability');
        }
    },
    
    calculate_process_capability: function(frm) {
        if (frm.doc.upper_spec_limit && frm.doc.lower_spec_limit && frm.doc.measured_value) {
            const usl = frm.doc.upper_spec_limit;
            const lsl = frm.doc.lower_spec_limit;
            const mean = frm.doc.measured_value;
            const target = frm.doc.target_value || mean;
            
            // Simplified calculation - in real implementation, you'd need historical data
            // for standard deviation calculation
            const tolerance = usl - lsl;
            const estimated_sigma = tolerance / 6; // Rough estimation
            
            if (estimated_sigma > 0) {
                const cp = tolerance / (6 * estimated_sigma);
                const cpu = (usl - mean) / (3 * estimated_sigma);
                const cpl = (mean - lsl) / (3 * estimated_sigma);
                const cpk = Math.min(cpu, cpl);
                
                frm.set_value('cp', cp);
                frm.set_value('cpk', cpk);
                frm.set_value('sigma_level', 3 * cpk);
            }
        }
    }
});