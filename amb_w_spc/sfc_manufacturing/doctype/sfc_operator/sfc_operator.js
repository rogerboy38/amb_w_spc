// Copyright (c) 2025, MiniMax Agent and contributors
// For license information, please see license.txt

frappe.ui.form.on('SFC Operator', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.doc.__islocal) {
            // Clock In/Out buttons
            if (frm.doc.is_active) {
                frm.add_custom_button(__('Clock In'), function() {
                    let d = new frappe.ui.Dialog({
                        title: __('Clock In'),
                        fields: [
                            {
                                label: __('Workstation'),
                                fieldname: 'workstation',
                                fieldtype: 'Link',
                                options: 'Workstation',
                                reqd: 1
                            }
                        ],
                        primary_action_label: __('Clock In'),
                        primary_action: function() {
                            let values = d.get_values();
                            frappe.call({
                                method: 'clock_in',
                                doc: frm.doc,
                                args: {
                                    workstation: values.workstation
                                },
                                callback: function(r) {
                                    if (r.message) {
                                        frappe.msgprint(__('Clocked in successfully'));
                                        frm.reload_doc();
                                    }
                                }
                            });
                            d.hide();
                        }
                    });
                    d.show();
                }, __('Actions'));
                
                frm.add_custom_button(__('Clock Out'), function() {
                    frappe.call({
                        method: 'clock_out',
                        doc: frm.doc,
                        callback: function(r) {
                            if (r.message) {
                                frappe.msgprint(__('Clocked out successfully'));
                                frm.reload_doc();
                            }
                        }
                    });
                }, __('Actions'));
            }
            
            // View attendance
            frm.add_custom_button(__('View Attendance'), function() {
                frappe.route_options = {
                    'operator': frm.doc.name
                };
                frappe.set_route('List', 'SFC Operator Attendance');
            });
            
            // View transactions
            frm.add_custom_button(__('View Transactions'), function() {
                frappe.route_options = {
                    'operator': frm.doc.name
                };
                frappe.set_route('List', 'SFC Transaction');
            });
        }
        
        // Set status indicator
        if (frm.doc.is_active) {
            frm.dashboard.set_headline(__('Status: Active'));
        } else {
            frm.dashboard.set_headline(__('Status: Inactive'));
        }
    },
    
    employee: function(frm) {
        if (frm.doc.employee) {
            // Auto-populate fields from employee
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Employee',
                    name: frm.doc.employee
                },
                callback: function(r) {
                    if (r.message) {
                        if (!frm.doc.operator_name) {
                            frm.set_value('operator_name', r.message.employee_name);
                        }
                        if (!frm.doc.department) {
                            frm.set_value('department', r.message.department);
                        }
                    }
                }
            });
        }
    }
});

frappe.ui.form.on('SFC Operator Skill', {
    skill: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.skill && !row.skill_level) {
            frappe.model.set_value(cdt, cdn, 'skill_level', 3); // Default to intermediate
        }
    }
});