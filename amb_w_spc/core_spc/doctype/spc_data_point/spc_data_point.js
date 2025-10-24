frappe.ui.form.on('SPC Data Point', {
    refresh: function(frm) {
        // Add button to view parameter details
        if (frm.doc.parameter) {
            frm.add_custom_button(__('View Parameter'), function() {
                frappe.set_route('Form', 'SPC Parameter Master', frm.doc.parameter);
            }, __("Actions"));
        }
        
        // Add button to view batch details
        if (frm.doc.batch_reference) {
            frm.add_custom_button(__('View Batch'), function() {
                frappe.set_route('Form', 'Batch AMB', frm.doc.batch_reference);
            }, __("Actions"));
        }
        
        // Auto-set measurement time if empty
        if (!frm.doc.measurement_time) {
            frm.set_value('measurement_time', frappe.datetime.now_datetime());
        }
    },
    
    parameter: function(frm) {
        // Auto-fetch parameter details
        if (frm.doc.parameter) {
            frappe.db.get_value('SPC Parameter Master', frm.doc.parameter, 'parameter_name')
                .then(r => {
                    if (r.message) {
                        frm.set_value('parameter_name', r.message.parameter_name);
                    }
                });
        }
    },
    
    data_value: function(frm) {
        // Auto-assess quality status based on parameter limits
        if (frm.doc.parameter && frm.doc.data_value) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SPC Parameter Master',
                    name: frm.doc.parameter
                },
                callback: function(r) {
                    if (r.message) {
                        let param = r.message;
                        let value = frm.doc.data_value;
                        
                        if (param.upper_spec_limit && param.lower_spec_limit) {
                            if (value > param.upper_spec_limit || value < param.lower_spec_limit) {
                                frm.set_value('quality_status', 'Out of Control');
                                frappe.show_alert({
                                    message: __('Value is outside specification limits!'),
                                    indicator: 'red'
                                });
                            } else {
                                frm.set_value('quality_status', 'In Control');
                            }
                        }
                    }
                }
            });
        }
    },
    
    batch_reference: function(frm) {
        // Auto-fetch batch details
        if (frm.doc.batch_reference) {
            frappe.db.get_value('Batch AMB', frm.doc.batch_reference, ['item_code', 'production_date'])
                .then(r => {
                    if (r.message) {
                        // You could set custom fields here if needed
                        console.log('Batch details:', r.message);
                    }
                });
        }
    }
});
