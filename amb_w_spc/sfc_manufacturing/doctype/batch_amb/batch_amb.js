// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Batch AMB", {
    refresh: function(frm) {
        setup_batch_validations(frm);
        setup_tree_actions(frm);
        setup_custom_buttons(frm);
    },

    is_group: function(frm) {
        toggle_group_fields(frm);
    },

    parent_batch_amb: function(frm) {
        validate_parent_batch(frm);
    },

    item_code: function(frm) {
        update_item_details(frm);
    }
});

function setup_batch_validations(frm) {
    // Initially toggle fields based on is_group
    toggle_group_fields(frm);
    
    // Set field descriptions
    frm.set_df_property('is_group', 'description', 
        'Check this for group batches (can contain child batches). Uncheck for leaf batches (must have parent, item, and work order).');
    
    frm.set_df_property('batch_code', 'description', 
        'Unique identifier for the batch. Auto-generated if left empty.');
}

function toggle_group_fields(frm) {
    const is_group = frm.doc.is_group;
    
    // Fields to show only for non-group batches
    const non_group_fields = [
        'work_order_reference', 'item_code', 'item_name', 
        'quantity', 'uom', 'total_weight', 'net_weight',
        'gross_weight', 'tare_weight', 'packaging_type', 
        'container_serial', 'barrel_count'
    ];
    
    non_group_fields.forEach(field => {
        frm.toggle_display(field, !is_group);
        if (!is_group) {
            frm.set_df_property(field, 'reqd', true);
        } else {
            frm.set_df_property(field, 'reqd', false);
            // Clear values for group batches
            if (frm.doc[field]) {
                frm.set_value(field, '');
            }
        }
    });
    
    // Update parent batch requirements
    if (is_group) {
        frm.set_df_property('parent_batch_amb', 'reqd', false);
        frm.set_df_property('parent_batch_amb', 'description', 'Optional for group batches');
    } else {
        frm.set_df_property('parent_batch_amb', 'reqd', true);
        frm.set_df_property('parent_batch_amb', 'description', 'Required for non-group batches');
    }
}

function validate_parent_batch(frm) {
    if (!frm.doc.is_group && frm.doc.parent_batch_amb) {
        frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'Batch AMB',
                fieldname: 'is_group',
                filters: { name: frm.doc.parent_batch_amb }
            },
            callback: function(r) {
                if (r.message && !r.message.is_group) {
                    frappe.msgprint(__('Parent batch must be a group batch (Is Group checked)'));
                    frm.set_value('parent_batch_amb', '');
                }
            }
        });
    }
}

function update_item_details(frm) {
    if (frm.doc.item_code && !frm.doc.is_group) {
        frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'Item',
                fieldname: 'item_name, stock_uom',
                filters: { name: frm.doc.item_code }
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value('item_name', r.message.item_name);
                    frm.set_value('uom', r.message.stock_uom);
                }
            }
        });
    }
}

function setup_tree_actions(frm) {
    // Add button to go to tree view
    if (!frm.is_new()) {
        frm.add_custom_button(__('View in Tree'), function() {
            frappe.set_route('Tree', 'Batch AMB');
        });
        
        frm.add_custom_button(__('View Children'), function() {
            frappe.call({
                method: 'batch_management.batch_management.doctype.batch_amb.batch_amb.get_child_batches',
                args: {
                    batch_name: frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        show_child_batches(r.message, frm.doc.batch_name);
                    }
                }
            });
        });
    }
}

function setup_custom_buttons(frm) {
    if (!frm.is_new()) {
        // Add quality status quick actions
        frm.add_custom_button(__('Mark as Passed'), function() {
            update_batch_quality(frm, 'Passed');
        });
        
        frm.add_custom_button(__('Mark as Failed'), function() {
            update_batch_quality(frm, 'Failed');
        });
        
        frm.add_custom_button(__('Put on Hold'), function() {
            update_batch_quality(frm, 'Hold');
        });
        
        // Add plant transfer button
        frm.add_custom_button(__('Transfer Plant'), function() {
            show_plant_transfer_dialog(frm);
        });
    }
}

function update_batch_quality(frm, status) {
    frappe.call({
        method: 'batch_management.batch_management.doctype.batch_amb.batch_amb.update_batch_quality',
        args: {
            batch_name: frm.doc.name,
            new_quality_status: status
        },
        callback: function(r) {
            if (!r.exc) {
                frm.reload_doc();
                frappe.show_alert({
                    message: __('Quality status updated to {0}', [status]),
                    indicator: 'green'
                });
            }
        }
    });
}

function show_plant_transfer_dialog(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Transfer Batch to Another Plant'),
        fields: [
            {
                fieldname: 'new_plant',
                fieldtype: 'Select',
                label: __('New Plant'),
                options: 'Mix Plant\nDry Plant\nJuice Plant\nLaboratory\nFormulated Plant',
                reqd: 1
            },
            {
                fieldname: 'target_plant',
                fieldtype: 'Select',
                label: __('Target Plant'),
                options: 'Mix Plant\nDry Plant\nJuice Plant\nLaboratory\nFormulated Plant'
            }
        ],
        primary_action_label: __('Transfer'),
        primary_action: function() {
            let data = dialog.get_values();
            if (data) {
                frappe.call({
                    method: 'batch_management.batch_management.doctype.batch_amb.batch_amb.transfer_batch_plant',
                    args: {
                        batch_name: frm.doc.name,
                        new_plant: data.new_plant,
                        target_plant: data.target_plant
                    },
                    callback: function(r) {
                        if (!r.exc) {
                            dialog.hide();
                            frm.reload_doc();
                            frappe.show_alert({
                                message: __('Batch transferred successfully'),
                                indicator: 'green'
                            });
                        }
                    }
                });
            }
        }
    });
    
    dialog.show();
}

function show_child_batches(children, parent_name) {
    let dialog = new frappe.ui.Dialog({
        title: __('Child Batches of {0}', [parent_name]),
        fields: [
            {
                fieldname: 'children_html',
                fieldtype: 'HTML'
            }
        ]
    });
    
    let html = `<div class="padding"><h5>${__('Child Batches')}</h5>`;
    
    if (children.length > 0) {
        html += `<table class="table table-bordered table-hover">
            <thead>
                <tr>
                    <th>${__('Batch Code')}</th>
                    <th>${__('Batch Name')}</th>
                    <th>${__('Level')}</th>
                    <th>${__('Quality Status')}</th>
                    <th>${__('Quantity')}</th>
                    <th>${__('Actions')}</th>
                </tr>
            </thead>
            <tbody>`;
        
        children.forEach(child => {
            let status_class = '';
            switch(child.quality_status) {
                case 'Passed': status_class = 'text-success'; break;
                case 'Failed': status_class = 'text-danger'; break;
                case 'Hold': status_class = 'text-warning'; break;
                default: status_class = 'text-muted';
            }
            
            html += `<tr>
                <td>${child.batch_code || ''}</td>
                <td>${child.batch_name || ''}</td>
                <td>${child.custom_batch_level || ''}</td>
                <td class="${status_class}">${child.quality_status || ''}</td>
                <td>${child.quantity || ''}</td>
                <td>
                    <button class="btn btn-xs btn-default" onclick="frappe.set_route('Form', 'Batch AMB', '${child.name}')">
                        ${__('Open')}
                    </button>
                </td>
            </tr>`;
        });
        
        html += `</tbody></table>`;
    } else {
        html += `<p class="text-muted">${__('No child batches found')}</p>`;
    }
    
    html += `</div>`;
    
    dialog.fields_dict.children_html.$wrapper.html(html);
    dialog.show();
}

// Tree view enhancement
frappe.treeview_settings["Batch AMB"] = {
    breadcrumb: "Batch Management",
    title: __("Batch Hierarchy"),
    get_tree_nodes: 'batch_management.batch_management.doctype.batch_amb.batch_amb.get_children',
    filters: [
        {
            fieldname: "company",
            fieldtype:"Select",
            options: erpnext.utils.get_tree_options("company"),
            label: __("Company")
        }
    ],
    menu_items: [
        {
            label: __("New Batch"),
            action: function() {
                frappe.new_doc("Batch AMB");
            },
            condition: 'frappe.boot.user.can_create.indexOf("Batch AMB") !== -1'
        }
    ],
    fields: [
        {
            fieldtype: 'Data',
            fieldname: 'batch_code',
            label: __('Batch Code'),
            reqd: true
        },
        {
            fieldtype: 'Data', 
            fieldname: 'batch_name',
            label: __('Batch Name')
        }
    ],
    onload: function(treeview) {
        treeview.make_tree();
        
        // Add refresh button
        treeview.page.add_inner_button(__('Refresh Tree'), function() {
            treeview.tree.load();
        }, __('Actions'));
        
        // Add expand/collapse buttons
        treeview.page.add_inner_button(__('Expand All'), function() {
            treeview.tree.expand_all();
        }, __('Actions'));
        
        treeview.page.add_inner_button(__('Collapse All'), function() {
            treeview.tree.collapse_all();
        }, __('Actions'));
    }
};
