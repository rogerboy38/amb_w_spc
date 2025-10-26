frappe.ui.form.on('Purchase Receipt Integration', {
    refresh: function(frm) {
        // Add custom buttons for enhanced functionality
        if (frm.doc.docstatus === 1) {
            add_action_buttons(frm);
        }
        
        // Auto-refresh integration status
        if (frm.doc.docstatus === 1) {
            refresh_integration_status(frm);
        }
        
        // Color-code status indicators
        setup_status_indicators(frm);
    },
    
    purchase_receipt_reference: function(frm) {
        if (frm.doc.purchase_receipt_reference) {
            load_purchase_receipt_data(frm);
        }
    },
    
    before_submit: function(frm) {
        return validate_before_submit(frm);
    }
});

function add_action_buttons(frm) {
    // View Dashboard button
    frm.add_custom_button(__('View Dashboard'), function() {
        show_receiving_dashboard(frm);
    }, __('Actions'));
    
    // Process Quality Results button
    frm.add_custom_button(__('Process Quality Results'), function() {
        process_quality_results(frm);
    }, __('Actions'));
    
    // Create Put-Away Tasks button
    frm.add_custom_button(__('Create Put-Away Tasks'), function() {
        create_put_away_tasks(frm);
    }, __('Actions'));
    
    // View Integration Status button
    frm.add_custom_button(__('View Integration Status'), function() {
        show_integration_status(frm);
    }, __('Actions'));
    
    // Generate COA button for completed inspections
    if (frm.doc.quality_approval_status === 'Complete') {
        frm.add_custom_button(__('Generate COA'), function() {
            generate_coa_from_receipt(frm);
        }, __('Quality'));
    }
}

function load_purchase_receipt_data(frm) {
    if (!frm.doc.purchase_receipt_reference) return;
    
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Purchase Receipt',
            name: frm.doc.purchase_receipt_reference
        },
        callback: function(r) {
            if (r.message) {
                const pr = r.message;
                
                // Auto-populate fields
                frm.set_value('supplier', pr.supplier);
                frm.set_value('company', pr.company);
                frm.set_value('posting_date', pr.posting_date);
                frm.set_value('posting_time', pr.posting_time);
                frm.set_value('currency', pr.currency);
                frm.set_value('total_amount', pr.grand_total);
                
                // Load items
                load_purchase_receipt_items(frm, pr);
            }
        }
    });
}

function load_purchase_receipt_items(frm, pr) {
    // Clear existing items
    frm.clear_table('items');
    
    // Add items from Purchase Receipt
    pr.items.forEach(function(pr_item) {
        const item = frm.add_child('items');
        item.item_code = pr_item.item_code;
        item.item_name = pr_item.item_name;
        item.description = pr_item.description;
        item.qty = pr_item.qty;
        item.rate = pr_item.rate;
        item.amount = pr_item.amount;
        item.warehouse = pr_item.warehouse;
        
        // Check if quality inspection required
        frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'Item',
                fieldname: 'inspection_required_before_delivery',
                filters: {name: pr_item.item_code}
            },
            callback: function(r) {
                if (r.message) {
                    item.quality_inspection_required = r.message.inspection_required_before_delivery || 0;
                    frm.refresh_field('items');
                }
            }
        });
        
        // Set batch if available
        if (pr_item.batch_no) {
            item.batch_no = pr_item.batch_no;
        }
    });
    
    frm.refresh_field('items');
}

function validate_before_submit(frm) {
    // Validate that all required fields are set
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__('At least one item is required'));
        return false;
    }
    
    // Validate warehouse assignments
    let validation_errors = [];
    
    frm.doc.items.forEach(function(item, idx) {
        if (!item.warehouse) {
            validation_errors.push(__('Row {0}: Warehouse is required', [idx + 1]));
        }
        
        if (!item.qty || item.qty <= 0) {
            validation_errors.push(__('Row {0}: Quantity must be greater than 0', [idx + 1]));
        }
    });
    
    if (validation_errors.length > 0) {
        frappe.msgprint({
            title: __('Validation Errors'),
            message: validation_errors.join('<br>'),
            indicator: 'red'
        });
        return false;
    }
    
    return true;
}

function refresh_integration_status(frm) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.purchase_receipt_integration.purchase_receipt_integration.get_integration_status',
        args: {
            integration_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                const status = r.message.status;
                
                // Update status fields
                frm.set_value('warehouse_integration_status', status.warehouse_integration);
                frm.set_value('quality_system_integration_status', status.quality_integration);
                frm.set_value('batch_tracking_integration_status', status.batch_integration);
                frm.set_value('sap_movement_integration_status', status.sap_integration);
                frm.set_value('fda_compliance_status', status.fda_compliance);
                frm.set_value('temperature_compliance_status', status.temperature_compliance);
            }
        }
    });
}

function setup_status_indicators(frm) {
    // Color-code status fields based on their values
    const status_fields = [
        'warehouse_integration_status',
        'quality_system_integration_status', 
        'batch_tracking_integration_status',
        'sap_movement_integration_status',
        'fda_compliance_status',
        'temperature_compliance_status'
    ];
    
    status_fields.forEach(function(field) {
        const value = frm.doc[field];
        let color = 'gray';
        
        if (value === 'Completed') {
            color = 'green';
        } else if (value === 'Failed') {
            color = 'red';
        } else if (value === 'Pending') {
            color = 'orange';
        }
        
        frm.get_field(field).$wrapper.find('.control-value').css('color', color);
    });
}

function show_receiving_dashboard(frm) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.purchase_receipt_integration.purchase_receipt_integration.get_receiving_dashboard_data',
        callback: function(r) {
            if (r.message && r.message.success) {
                show_dashboard_dialog(r.message);
            }
        }
    });
}

function show_dashboard_dialog(data) {
    const dialog = new frappe.ui.Dialog({
        title: __('Receiving Operations Dashboard'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'dashboard_html'
            }
        ]
    });
    
    // Build dashboard HTML
    let html = `
        <div class="receiving-dashboard">
            <div class="row">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-header">Summary (Last 7 Days)</div>
                        <div class="card-body">
                            <p><strong>Total Receipts:</strong> ${data.summary.total_receipts}</p>
                            <p><strong>Total Value:</strong> ${format_currency(data.summary.total_value)}</p>
                            <p><strong>Submitted:</strong> ${data.summary.submitted_receipts}</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">Recent Receipts</div>
                        <div class="card-body">
                            <table class="table table-bordered">
                                <thead>
                                    <tr>
                                        <th>Receipt</th>
                                        <th>Supplier</th>
                                        <th>Date</th>
                                        <th>Value</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
    `;
    
    data.recent_receipts.forEach(function(receipt) {
        html += `
            <tr>
                <td><a href="#Form/Purchase Receipt/${receipt.name}">${receipt.name}</a></td>
                <td>${receipt.supplier}</td>
                <td>${receipt.posting_date}</td>
                <td>${format_currency(receipt.grand_total)}</td>
                <td>${get_receipt_status(receipt)}</td>
            </tr>
        `;
    });
    
    html += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    dialog.fields_dict.dashboard_html.$wrapper.html(html);
    dialog.show();
}

function process_quality_results(frm) {
    // Get items requiring quality inspection
    const inspection_items = frm.doc.items.filter(item => item.quality_inspection_required);
    
    if (inspection_items.length === 0) {
        frappe.msgprint(__('No items require quality inspection'));
        return;
    }
    
    const dialog = new frappe.ui.Dialog({
        title: __('Process Quality Inspection Results'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'inspection_html'
            },
            {
                fieldtype: 'Button',
                fieldname: 'process_all',
                label: __('Process All Results')
            }
        ],
        primary_action: function() {
            // Process all inspection results
            process_all_inspection_results(frm, inspection_items);
            dialog.hide();
        },
        primary_action_label: __('Process Results')
    });
    
    // Build inspection items HTML
    let html = '<div class="inspection-items">';
    
    inspection_items.forEach(function(item, idx) {
        html += `
            <div class="card mb-3">
                <div class="card-header">
                    <strong>${item.item_code}</strong> - ${item.item_name}
                </div>
                <div class="card-body">
                    <p><strong>Quantity:</strong> ${item.qty}</p>
                    <p><strong>Warehouse:</strong> ${item.warehouse}</p>
                    ${item.quality_inspection ? 
                        `<p><strong>Quality Inspection:</strong> <a href="#Form/Quality Inspection/${item.quality_inspection}">${item.quality_inspection}</a></p>` : 
                        '<p><em>Quality Inspection not yet created</em></p>'
                    }
                    <div class="mt-2">
                        <button class="btn btn-success btn-sm" onclick="approve_item('${item.name}')">Approve</button>
                        <button class="btn btn-danger btn-sm" onclick="reject_item('${item.name}')">Reject</button>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    
    dialog.fields_dict.inspection_html.$wrapper.html(html);
    dialog.show();
}

function create_put_away_tasks(frm) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.purchase_receipt_integration.purchase_receipt_integration.create_put_away_tasks',
        args: {
            integration_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint({
                    title: __('Put-Away Tasks Created'),
                    message: __('Created {0} put-away tasks', [r.message.task_count]),
                    indicator: 'green'
                });
                frm.reload_doc();
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.error || __('Failed to create put-away tasks'),
                    indicator: 'red'
                });
            }
        }
    });
}

function show_integration_status(frm) {
    frappe.route_options = {
        "reference_doctype": "Purchase Receipt Integration",
        "reference_name": frm.doc.name
    };
    frappe.set_route("List", "Integration Status Log");
}

function generate_coa_from_receipt(frm) {
    // Get items that passed quality inspection
    const approved_items = frm.doc.items.filter(item => 
        item.quality_inspection_required && item.quality_approval_status === 'Approved'
    );
    
    if (approved_items.length === 0) {
        frappe.msgprint(__('No approved items found for COA generation'));
        return;
    }
    
    // Create COA for each approved item
    approved_items.forEach(function(item) {
        frappe.call({
            method: 'amb_w_spc.sfc_manufacturing.doctype.coa_amb.coa_amb.create_coa_from_purchase_receipt',
            args: {
                item_code: item.item_code,
                purchase_receipt_integration: frm.doc.name,
                quality_inspection: item.quality_inspection
            },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.msgprint({
                        title: __('COA Created'),
                        message: __('COA {0} created for item {1}', [r.message.coa_name, item.item_code]),
                        indicator: 'green'
                    });
                }
            }
        });
    });
}

// Utility functions
function format_currency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount || 0);
}

function get_receipt_status(receipt) {
    if (receipt.submitted_integrations > 0) {
        return '<span class="label label-success">Integrated</span>';
    } else if (receipt.integration_count > 0) {
        return '<span class="label label-warning">Processing</span>';
    } else {
        return '<span class="label label-default">Pending</span>';
    }
}

// Global functions for quality processing
window.approve_item = function(item_name) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.purchase_receipt_integration.purchase_receipt_integration.approve_inspection_item',
        args: {
            item_name: item_name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint(__('Item approved and moved to production warehouse'));
            }
        }
    });
};

window.reject_item = function(item_name) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.purchase_receipt_integration.purchase_receipt_integration.reject_inspection_item',
        args: {
            item_name: item_name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint(__('Item rejected and moved to rejection warehouse'));
            }
        }
    });
};
