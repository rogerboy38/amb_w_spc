frappe.ui.form.on('Batch AMB', {
    refresh: function(frm) {
        // Add custom button to create SPC Data Points
        frm.add_custom_button(__('Create SPC Data Point'), function() {
            frappe.model.open_mapped_doc({
                method: "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.create_spc_data_point",
                frm: frm
            });
        }, __("SPC Actions"));
        
        // Add button to view related data points
        frm.add_custom_button(__('View SPC Data'), function() {
            frappe.set_route('List', 'SPC Data Point', {
                'batch_reference': frm.doc.name
            });
        }, __("SPC Actions"));
        
        // Auto-set production date if empty
        if (!frm.doc.production_date) {
            frm.set_value('production_date', frappe.datetime.get_today());
        }
    },
    
    item_code: function(frm) {
        // Auto-fetch item name when item code is selected
        if (frm.doc.item_code) {
            frappe.db.get_value('Item', frm.doc.item_code, 'item_name')
                .then(r => {
                    if (r.message) {
                        frm.set_value('item_name', r.message.item_name);
                    }
                });
        }
    },
    
    validate: function(frm) {
        // Validate that expiry date is after production date
        if (frm.doc.production_date && frm.doc.expiry_date) {
            if (frm.doc.expiry_date < frm.doc.production_date) {
                frappe.msgprint(__('Expiry Date cannot be before Production Date'));
                frappe.validated = false;
            }
        }
        
        // Validate quantity is positive
        if (frm.doc.quantity && frm.doc.quantity < 0) {
            frappe.msgprint(__('Quantity cannot be negative'));
            frappe.validated = false;
        }
    },
    
    onload: function(frm) {
        // Set up grid formatters for SPC Parameters table
        frm.fields_dict['spc_parameters'].grid.wrapper.find('.grid-row').each(function() {
            var doc = frappe.get_doc(this);
            if (doc && doc.target_value) {
                // Add color coding based on target value
                if (doc.target_value > 0) {
                    $(this).find('[data-fieldname="target_value"]').css('color', 'green');
                }
            }
        });
    }
});

// Custom function to fetch parameter details
frappe.ui.form.on('SPC Parameter Specification', {
    parameter: function(frm, cdt, cdn) {
        var child = locals[cdt][cdn];
        if (child.parameter) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'SPC Parameter Master',
                    name: child.parameter
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'parameter_name', r.message.parameter_name);
                        if (!child.target_value) {
                            frappe.model.set_value(cdt, cdn, 'target_value', r.message.target_value);
                        }
                        if (!child.upper_spec_limit) {
                            frappe.model.set_value(cdt, cdn, 'upper_spec_limit', r.message.upper_spec_limit);
                        }
                        if (!child.lower_spec_limit) {
                            frappe.model.set_value(cdt, cdn, 'lower_spec_limit', r.message.lower_spec_limit);
                        }
                    }
                }
            });
        }
    }
});
