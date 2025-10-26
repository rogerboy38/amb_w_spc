// Custom Script for SPC Parameter Master
// File: spc_parameter_master_client_script.js

frappe.ui.form.on('SPC Parameter Master', {
    onload: function(frm) {
        // Set default company if not set
        if (!frm.doc.company && frappe.defaults.get_user_default('Company')) {
            frm.set_value('company', frappe.defaults.get_user_default('Company'));
        }
        
        // Set creation info
        if (frm.is_new()) {
            frm.set_value('created_by', frappe.session.user);
            frm.set_value('creation_info', `Created on ${frappe.datetime.now_datetime()} by ${frappe.session.user}`);
        }
    },
    
    validate: function(frm) {
        // Validate parameter code format (alphanumeric only)
        if (frm.doc.parameter_code) {
            const codePattern = /^[A-Za-z0-9_-]+$/;
            if (!codePattern.test(frm.doc.parameter_code)) {
                frappe.throw(__("Parameter Code must contain only letters, numbers, hyphens, and underscores"));
            }
        }
        
        // Validate precision for numeric data types
        if (frm.doc.data_type === 'Numeric' && (!frm.doc.default_precision || frm.doc.default_precision < 0)) {
            frappe.throw(__("Default Precision must be specified and >= 0 for Numeric data types"));
        }
    },
    
    before_save: function(frm) {
        // Update modified info
        frm.set_value('modified_by', frappe.session.user);
        frm.set_value('last_modified', frappe.datetime.now_datetime());
    },
    
    data_type: function(frm) {
        // Clear precision if data type is not numeric
        if (frm.doc.data_type !== 'Numeric') {
            frm.set_value('default_precision', '');
        } else {
            // Set default precision for numeric types
            if (!frm.doc.default_precision) {
                frm.set_value('default_precision', 2);
            }
        }
    },
    
    parameter_code: function(frm) {
        // Convert to uppercase for consistency
        if (frm.doc.parameter_code) {
            frm.set_value('parameter_code', frm.doc.parameter_code.toUpperCase());
        }
    }
});