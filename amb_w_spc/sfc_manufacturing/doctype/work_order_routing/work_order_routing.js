// Copyright (c) 2025, MiniMax Agent and contributors
// For license information, please see license.txt

frappe.ui.form.on('Work Order Routing', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.doc.__islocal && frm.doc.status !== 'Completed') {
            frm.add_custom_button(__('View SFC Transactions'), function() {
                frappe.route_options = {
                    'work_order': frm.doc.work_order
                };
                frappe.set_route('List', 'SFC Transaction');
            });
            
            frm.add_custom_button(__('Production Dashboard'), function() {
                frappe.set_route('query-report', 'SFC Production Dashboard', {
                    'work_order': frm.doc.work_order
                });
            });
        }
        
        // Set up operation grid
        frm.fields_dict.operations.grid.wrapper.find('.grid-add-row').text('Add Operation');
    },
    
    work_order: function(frm) {
        if (frm.doc.work_order) {
            // Auto-populate routing from work order if available
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Work Order',
                    name: frm.doc.work_order
                },
                callback: function(r) {
                    if (r.message && r.message.bom_no) {
                        frm.set_value('bom_no', r.message.bom_no);
                        frm.set_value('item_code', r.message.production_item);
                        frm.set_value('qty', r.message.qty);
                    }
                }
            });
        }
    },
    
    validate: function(frm) {
        // Client-side validation
        let sequences = [];
        let has_duplicates = false;
        
        frm.doc.operations.forEach(function(operation) {
            if (sequences.includes(operation.sequence)) {
                has_duplicates = true;
                frappe.msgprint(__('Duplicate sequence number {0} found', [operation.sequence]));
            }
            sequences.push(operation.sequence);
        });
        
        if (has_duplicates) {
            frappe.validated = false;
        }
    }
});

frappe.ui.form.on('Work Order Routing Operation', {
    operation: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.operation) {
            // Auto-populate operation details from Operation master
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Operation',
                    name: row.operation
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'operation_time', r.message.hour_rate || 1.0);
                        frappe.model.set_value(cdt, cdn, 'workstation', r.message.workstation);
                    }
                }
            });
        }
    },
    
    sequence: function(frm, cdt, cdn) {
        // Auto-sort operations by sequence
        setTimeout(function() {
            frm.doc.operations.sort(function(a, b) {
                return (a.sequence || 0) - (b.sequence || 0);
            });
            frm.refresh_field('operations');
        }, 100);
    }
});