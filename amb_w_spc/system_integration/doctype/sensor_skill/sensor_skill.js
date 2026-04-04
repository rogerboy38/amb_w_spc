// Sensor Skill Client Script
frappe.ui.form.on('Sensor Skill', {
    refresh: function(frm) {
        // Add button to export config
        frm.add_custom_button(__('Export Config'), function() {
            frappe.call({
                method: 'amb_w_spc.system_integration.doctype.sensor_skill.sensor_skill.get_skill_config',
                args: { skill_id: frm.doc.skill_id },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __('Skill Config'),
                            indicator: 'green',
                            message: JSON.stringify(r.message, null, 2)
                        });
                    }
                }
            });
        });

        // Add button to test config
        frm.add_custom_button(__('Test Config'), function() {
            frappe.msgprint(__('Test connection not implemented yet'));
        });
    }
});
