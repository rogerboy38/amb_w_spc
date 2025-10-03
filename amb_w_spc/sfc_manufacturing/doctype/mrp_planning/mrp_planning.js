// Copyright (c) 2025, MiniMax Agent and contributors
// For license information, please see license.txt

frappe.ui.form.on('MRP Planning', {
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.docstatus === 1 && frm.doc.planning_status === "Completed") {
            frm.add_custom_button(__('View Work Orders'), function() {
                frappe.route_options = {"mrp_planning": frm.doc.name};
                frappe.set_route("List", "Work Order");
            });
            
            frm.add_custom_button(__('View Material Requests'), function() {
                frappe.route_options = {"mrp_planning": frm.doc.name};
                frappe.set_route("List", "Material Request");
            });
        }
        
        // Add button to preview production routing
        if (frm.doc.sales_order && frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Preview Production Routing'), function() {
                preview_production_routing(frm);
            }, __('Actions'));
        }
        
        // Add button to populate items from Sales Order
        if (frm.doc.sales_order && frm.doc.docstatus === 0 && (!frm.doc.mrp_items || frm.doc.mrp_items.length === 0)) {
            frm.add_custom_button(__('Populate Items from SO'), function() {
                populate_items_from_sales_order(frm);
            }, __('Actions'));
        }
        
        // Auto-set planning dates
        if (!frm.doc.planned_start_date) {
            frm.set_value('planned_start_date', frappe.datetime.get_today());
        }
        
        if (!frm.doc.required_date && frm.doc.planned_start_date) {
            frm.set_value('required_date', frappe.datetime.add_days(frm.doc.planned_start_date, 7));
        }
    },
    
    sales_order: function(frm) {
        if (frm.doc.sales_order) {
            // Auto-populate company and other details from sales order
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Sales Order',
                    name: frm.doc.sales_order
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('company', r.message.company);
                        frm.set_value('customer', r.message.customer);
                        frm.set_value('delivery_date', r.message.delivery_date);
                        
                        if (r.message.delivery_date && !frm.doc.required_date) {
                            frm.set_value('required_date', r.message.delivery_date);
                        }
                        
                        // Calculate planned start date (work backwards from delivery date)
                        if (r.message.delivery_date && !frm.doc.planned_start_date) {
                            let planned_start = frappe.datetime.add_days(r.message.delivery_date, -7);
                            frm.set_value('planned_start_date', planned_start);
                        }
                    }
                }
            });
        }
    },
    
    planned_start_date: function(frm) {
        if (frm.doc.planned_start_date && !frm.doc.required_date) {
            frm.set_value('required_date', frappe.datetime.add_days(frm.doc.planned_start_date, 7));
        }
    },
    
    onload: function(frm) {
        // Initialize custom CSS
        initialize_custom_css();
    }
});

function populate_items_from_sales_order(frm) {
    if (!frm.doc.sales_order) {
        frappe.msgprint(__('Please select a Sales Order first'));
        return;
    }
    
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Sales Order Item',
            filters: {
                parent: frm.doc.sales_order
            },
            fields: ['item_code', 'item_name', 'qty', 'uom', 'warehouse']
        },
        callback: function(r) {
            if (r.message && r.message.length) {
                // Clear existing items
                frm.clear_table('mrp_items');
                
                // Add new items from sales order
                r.message.forEach(function(item) {
                    let child = frm.add_child('mrp_items');
                    child.item_code = item.item_code;
                    child.item_name = item.item_name;
                    child.qty = item.qty;
                    child.uom = item.uom;
                    child.planned_date = frm.doc.required_date || frappe.datetime.get_today();
                });
                
                frm.refresh_field('mrp_items');
                frappe.msgprint(__('Added {0} items from Sales Order', [r.message.length]));
            } else {
                frappe.msgprint(__('No items found in the selected Sales Order'));
            }
        }
    });
}

function preview_production_routing(frm) {
    if (!frm.doc.sales_order) {
        frappe.msgprint(__('Please select a Sales Order first'));
        return;
    }
    
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Sales Order Item',
            filters: {
                parent: frm.doc.sales_order
            },
            fields: ['item_code', 'item_name', 'qty']
        },
        callback: function(r) {
            if (r.message && r.message.length) {
                let routing_html = '<div class="production-routing">';
                
                r.message.forEach(function(item) {
                    routing_html += `<div class="item-routing">
                        <h5>${item.item_code} - ${item.item_name || ''} (Qty: ${item.qty})</h5>
                        <div class="routing-steps" id="routing-${item.item_code.replace(/[^a-zA-Z0-9]/g, '-')}">
                            <div class="text-center text-muted">
                                <i class="fa fa-spinner fa-spin"></i> Loading routing information...
                            </div>
                        </div>
                    </div>`;
                });
                
                routing_html += '</div>';
                
                let dialog = new frappe.ui.Dialog({
                    title: __('Production Routing Preview - {0}', [frm.doc.sales_order]),
                    size: 'large',
                    fields: [{
                        fieldtype: 'HTML',
                        fieldname: 'routing_html',
                        options: routing_html
                    }],
                    primary_action_label: __('Close'),
                    primary_action: function() {
                        dialog.hide();
                    }
                });
                
                dialog.show();
                
                // Load routing for each item
                r.message.forEach(function(item) {
                    get_item_routing(item.item_code, item.qty, dialog);
                });
            } else {
                frappe.msgprint(__('No items found in the selected Sales Order'));
            }
        }
    });
}

function get_item_routing(item_code, qty, dialog) {
    frappe.call({
        method: 'mrp_planning.get_production_routing',
        args: {
            item_code: item_code
        },
        callback: function(r) {
            let routing_container = $(dialog.body).find(`#routing-${item_code.replace(/[^a-zA-Z0-9]/g, '-')}`);
            
            if (r.message && r.message.status === 'success') {
                let routing_steps = '';
                let routing = r.message.routing;
                
                if (Object.keys(routing).length === 0) {
                    routing_steps = '<div class="text-warning">No production routing found. This item may be a raw material.</div>';
                } else {
                    // Sort routing by level (finished -> intermediate -> raw)
                    let levels = Object.keys(routing).sort().reverse();
                    
                    levels.forEach(function(level, index) {
                        let step = routing[level];
                        let step_qty = (step.qty * qty).toFixed(2);
                        
                        routing_steps += `<div class="routing-step">
                            <div class="step-number">${index + 1}</div>
                            <div class="step-content">
                                <strong>${step.item_code}</strong>
                                <div class="text-small text-muted">
                                    <i class="fa fa-factory"></i> ${step.plant_code} Plant
                                    | <i class="fa fa-cube"></i> Qty: ${step_qty}
                                    | <i class="fa fa-sitemap"></i> Level: ${level.replace('_', ' ').toUpperCase()}
                                </div>
                                ${step.bom ? `<div class="text-small"><i class="fa fa-list-alt"></i> BOM: ${step.bom}</div>` : ''}
                            </div>
                        </div>`;
                        
                        // Add connector line between steps (except for last step)
                        if (index < levels.length - 1) {
                            routing_steps += '<div class="step-connector"><div class="connector-line"></div></div>';
                        }
                    });
                }
                
                routing_container.html(routing_steps);
            } else {
                let error_msg = r.message && r.message.message ? r.message.message : 'Unknown error occurred';
                routing_container.html(`<div class="text-danger">
                    <i class="fa fa-exclamation-triangle"></i> Failed to load routing: ${error_msg}
                </div>`);
            }
        },
        error: function() {
            let routing_container = $(dialog.body).find(`#routing-${item_code.replace(/[^a-zA-Z0-9]/g, '-')}`);
            routing_container.html('<div class="text-danger"><i class="fa fa-exclamation-triangle"></i> Error loading routing information</div>');
        }
    });
}

function initialize_custom_css() {
    // Only add CSS once
    if ($('#mrp-planning-custom-css').length) return;
    
    $('<style id="mrp-planning-custom-css">')
        .prop('type', 'text/css')
        .html(`
            .production-routing {
                max-height: 500px;
                overflow-y: auto;
                padding: 10px;
            }
            .item-routing {
                margin-bottom: 20px;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
                background: #fafbfc;
            }
            .item-routing h5 {
                margin: 0 0 10px 0;
                color: #2e3c4d;
                font-size: 14px;
                font-weight: 600;
            }
            .routing-steps {
                margin-top: 10px;
            }
            .routing-step {
                display: flex;
                align-items: center;
                margin-bottom: 8px;
                padding: 12px;
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .step-number {
                background-color: #007bff;
                color: white;
                border-radius: 50%;
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 15px;
                font-weight: bold;
                font-size: 14px;
                flex-shrink: 0;
            }
            .step-content {
                flex: 1;
            }
            .step-content strong {
                color: #2e3c4d;
                font-size: 13px;
            }
            .text-small {
                font-size: 12px;
            }
            .step-connector {
                display: flex;
                justify-content: center;
                margin: 2px 0;
            }
            .connector-line {
                width: 2px;
                height: 15px;
                background-color: #007bff;
                opacity: 0.5;
            }
            .routing-step:nth-child(odd) .step-number {
                background-color: #28a745;
            }
            .routing-step:nth-child(even) .step-number {
                background-color: #6c757d;
            }
        `)
        .appendTo('head');
}

// Additional utility functions
function format_quantity(qty) {
    return parseFloat(qty).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Export functions for potential reuse
if (typeof window !== 'undefined') {
    window.MRPPlanningUtils = {
        preview_production_routing: preview_production_routing,
        populate_items_from_sales_order: populate_items_from_sales_order,
        format_quantity: format_quantity
    };
}

