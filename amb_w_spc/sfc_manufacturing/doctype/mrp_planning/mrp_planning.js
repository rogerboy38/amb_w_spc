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
        
        // Add warehouse integration buttons for submitted documents
        if (frm.doc.docstatus === 1 && frm.doc.planning_status === "Completed") {
            frm.add_custom_button(__('Warehouse Status'), function() {
                show_warehouse_status(frm);
            }, __('Warehouse Operations'));
            
            frm.add_custom_button(__('Update Zone Status'), function() {
                update_all_zone_statuses(frm);
            }, __('Warehouse Operations'));
            
            frm.add_custom_button(__('Warehouse Zones Mapping'), function() {
                show_warehouse_zones_mapping(frm);
            }, __('Warehouse Operations'));
            
            frm.add_custom_button(__('Work Order Operations'), function() {
                show_work_order_operations(frm);
            }, __('Warehouse Operations'));
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
            
            /* Warehouse Integration Styles */
            .warehouse-status-container {
                max-height: 600px;
                overflow-y: auto;
                padding: 15px;
            }
            .section-header {
                margin: 20px 0 10px 0;
                padding-bottom: 5px;
                border-bottom: 2px solid #e0e0e0;
            }
            .section-header h4 {
                margin: 0;
                color: #2e3c4d;
                font-size: 16px;
            }
            .work-orders-grid, .assessments-grid, .stock-entries-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }
            .work-order-card, .assessment-card, .stock-entry-card {
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .wo-header, .assessment-header, .se-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }
            .zone-badge, .status-badge {
                color: white;
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            }
            .wo-details, .assessment-details, .se-details {
                font-size: 12px;
                color: #666;
            }
            .wo-details div, .assessment-details div, .se-details div {
                margin-bottom: 3px;
            }
            .progress-bar {
                height: 6px;
                background-color: #e0e0e0;
                border-radius: 3px;
                margin-top: 10px;
                overflow: hidden;
            }
            .progress-fill {
                height: 100%;
                transition: width 0.3s ease;
            }
            .warehouse-mapping-container {
                padding: 15px;
            }
            .plant-section {
                margin-bottom: 25px;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
            }
            .plant-header {
                margin: 0 0 15px 0;
                color: #2e3c4d;
                font-size: 16px;
            }
            .zones-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 10px;
            }
            .zone-card {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 12px;
                text-align: center;
            }
            .zone-type {
                font-weight: bold;
                font-size: 12px;
                color: #495057;
                margin-bottom: 5px;
            }
            .warehouse-name {
                font-size: 14px;
                color: #007bff;
            }
            .work-order-operations {
                padding: 15px;
            }
            .wo-operation-card {
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 10px;
            }
            .wo-info strong {
                font-size: 14px;
                color: #2e3c4d;
            }
            .wo-meta {
                font-size: 12px;
                color: #666;
                margin-top: 3px;
            }
            .wo-actions {
                display: flex;
                gap: 8px;
            }
            .wo-actions button {
                font-size: 11px;
                padding: 4px 8px;
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

// Warehouse Integration Functions
function show_warehouse_status(frm) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.mrp_planning.mrp_planning.get_mrp_warehouse_status',
        args: {
            mrp_planning_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                display_warehouse_status_dialog(r.message, frm);
            } else {
                frappe.msgprint(__('Failed to load warehouse status: {0}', [r.message.message || 'Unknown error']));
            }
        }
    });
}

function display_warehouse_status_dialog(data, frm) {
    let status_html = '<div class="warehouse-status-container">';
    
    // Work Orders Section
    status_html += '<div class="section-header"><h4><i class="fa fa-cogs"></i> Work Orders</h4></div>';
    status_html += '<div class="work-orders-grid">';
    
    data.work_orders.forEach(function(wo) {
        let zone_color = wo.custom_current_zone_status === 'Green Zone' ? '#28a745' : '#dc3545';
        let completion = wo.custom_material_completion_percentage || 0;
        
        status_html += `<div class="work-order-card" style="border-left: 4px solid ${zone_color};">
            <div class="wo-header">
                <strong>${wo.name}</strong>
                <span class="zone-badge" style="background-color: ${zone_color}">${wo.custom_current_zone_status || 'Unknown'}</span>
            </div>
            <div class="wo-details">
                <div><i class="fa fa-factory"></i> Plant: ${wo.plant_code}</div>
                <div><i class="fa fa-layer-group"></i> Level: ${wo.production_level}</div>
                <div><i class="fa fa-percentage"></i> Completion: ${completion.toFixed(1)}%</div>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${completion}%; background-color: ${zone_color};"></div>
            </div>
        </div>`;
    });
    
    status_html += '</div>';
    
    // Material Assessments Section
    status_html += '<div class="section-header"><h4><i class="fa fa-clipboard-list"></i> Material Assessments</h4></div>';
    status_html += '<div class="assessments-grid">';
    
    data.assessments.forEach(function(assessment) {
        let status_color = assessment.zone_status === 'Green Zone' ? '#28a745' : '#ffc107';
        status_html += `<div class="assessment-card">
            <div class="assessment-header">
                <strong>${assessment.name}</strong>
                <span class="status-badge" style="background-color: ${status_color}">${assessment.zone_status}</span>
            </div>
            <div class="assessment-details">
                <div><i class="fa fa-calendar"></i> ${frappe.datetime.str_to_user(assessment.assessment_date)}</div>
                <div><i class="fa fa-percentage"></i> ${(assessment.completion_percentage || 0).toFixed(1)}%</div>
                ${assessment.work_order ? `<div><i class="fa fa-link"></i> WO: ${assessment.work_order}</div>` : ''}
            </div>
        </div>`;
    });
    
    status_html += '</div>';
    
    // Stock Entries Section
    status_html += '<div class="section-header"><h4><i class="fa fa-exchange-alt"></i> Stock Entries</h4></div>';
    status_html += '<div class="stock-entries-grid">';
    
    data.stock_entries.forEach(function(se) {
        let status_text = se.docstatus === 1 ? 'Submitted' : (se.docstatus === 0 ? 'Draft' : 'Cancelled');
        let status_color = se.docstatus === 1 ? '#28a745' : (se.docstatus === 0 ? '#17a2b8' : '#dc3545');
        
        status_html += `<div class="stock-entry-card">
            <div class="se-header">
                <strong>${se.name}</strong>
                <span class="status-badge" style="background-color: ${status_color}">${status_text}</span>
            </div>
            <div class="se-details">
                <div><i class="fa fa-barcode"></i> SAP: ${se.custom_sap_movement_type || 'N/A'}</div>
                <div><i class="fa fa-map-marker-alt"></i> Zone: ${se.custom_zone_status || 'N/A'}</div>
                <div><i class="fa fa-link"></i> WO: ${se.custom_work_order_reference || 'N/A'}</div>
            </div>
        </div>`;
    });
    
    status_html += '</div></div>';
    
    let dialog = new frappe.ui.Dialog({
        title: __('Warehouse Integration Status - {0}', [frm.doc.name]),
        size: 'extra-large',
        fields: [{
            fieldtype: 'HTML',
            fieldname: 'status_html',
            options: status_html
        }],
        primary_action_label: __('Close'),
        primary_action: function() {
            dialog.hide();
        }
    });
    
    dialog.show();
}

function update_all_zone_statuses(frm) {
    frappe.confirm(
        __('This will update zone statuses for all work orders in this MRP Planning. Continue?'),
        function() {
            frappe.call({
                method: 'amb_w_spc.sfc_manufacturing.doctype.mrp_planning.mrp_planning.update_all_zone_statuses',
                args: {
                    mrp_planning_name: frm.doc.name
                },
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.msgprint(__('Zone statuses updated successfully'));
                        frm.reload_doc();
                    } else {
                        frappe.msgprint(__('Zone status update failed: {0}', [r.message.message || 'Unknown error']));
                    }
                }
            });
        }
    );
}

function show_warehouse_zones_mapping(frm) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.mrp_planning.mrp_planning.get_warehouse_zones_mapping',
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                display_warehouse_mapping_dialog(r.message.warehouse_mapping);
            } else {
                frappe.msgprint(__('Failed to load warehouse mapping: {0}', [r.message.message || 'Unknown error']));
            }
        }
    });
}

function display_warehouse_mapping_dialog(mapping) {
    let mapping_html = '<div class="warehouse-mapping-container">';
    
    Object.keys(mapping).forEach(function(plant) {
        mapping_html += `<div class="plant-section">
            <h4 class="plant-header"><i class="fa fa-industry"></i> ${plant.toUpperCase()} Plant</h4>
            <div class="zones-grid">`;
        
        Object.keys(mapping[plant]).forEach(function(zone_type) {
            let warehouse_name = mapping[plant][zone_type];
            mapping_html += `<div class="zone-card">
                <div class="zone-type">${zone_type.replace('_', ' ').toUpperCase()}</div>
                <div class="warehouse-name">${warehouse_name}</div>
            </div>`;
        });
        
        mapping_html += '</div></div>';
    });
    
    mapping_html += '</div>';
    
    let dialog = new frappe.ui.Dialog({
        title: __('Warehouse Zones Mapping'),
        size: 'large',
        fields: [{
            fieldtype: 'HTML',
            fieldname: 'mapping_html',
            options: mapping_html
        }],
        primary_action_label: __('Close'),
        primary_action: function() {
            dialog.hide();
        }
    });
    
    dialog.show();
}

function show_work_order_operations(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Work Order',
            filters: {
                mrp_planning: frm.doc.name
            },
            fields: ['name', 'production_item', 'plant_code', 'custom_current_zone_status']
        },
        callback: function(r) {
            if (r.message) {
                display_work_order_operations_dialog(r.message, frm);
            }
        }
    });
}

function display_work_order_operations_dialog(work_orders, frm) {
    let operations_html = '<div class="work-order-operations">';
    
    work_orders.forEach(function(wo) {
        operations_html += `<div class="wo-operation-card">
            <div class="wo-info">
                <strong>${wo.name}</strong>
                <div class="wo-meta">${wo.production_item} | ${wo.plant_code} | ${wo.custom_current_zone_status || 'Unknown'}</div>
            </div>
            <div class="wo-actions">
                <button class="btn btn-sm btn-primary" onclick="trigger_warehouse_operation('${wo.name}', 'pick_request')">Pick Request</button>
                <button class="btn btn-sm btn-info" onclick="trigger_warehouse_operation('${wo.name}', 'zone_update')">Update Zone</button>
                <button class="btn btn-sm btn-success" onclick="trigger_warehouse_operation('${wo.name}', 'stock_entry')">Stock Entry</button>
            </div>
        </div>`;
    });
    
    operations_html += '</div>';
    
    let dialog = new frappe.ui.Dialog({
        title: __('Work Order Warehouse Operations'),
        size: 'large',
        fields: [{
            fieldtype: 'HTML',
            fieldname: 'operations_html',
            options: operations_html
        }],
        primary_action_label: __('Close'),
        primary_action: function() {
            dialog.hide();
        }
    });
    
    dialog.show();
    
    // Make trigger_warehouse_operation globally available
    window.trigger_warehouse_operation = function(work_order_name, operation_type) {
        frappe.call({
            method: 'amb_w_spc.sfc_manufacturing.doctype.mrp_planning.mrp_planning.trigger_warehouse_operations',
            args: {
                work_order_name: work_order_name,
                operation_type: operation_type
            },
            callback: function(r) {
                if (r.message && r.message.status === 'success') {
                    frappe.msgprint(__('Operation {0} completed successfully for {1}', [operation_type, work_order_name]));
                    dialog.hide();
                    frm.reload_doc();
                } else {
                    frappe.msgprint(__('Operation failed: {0}', [r.message.message || 'Unknown error']));
                }
            }
        });
    };
}

// Export functions for potential reuse
if (typeof window !== 'undefined') {
    window.MRPPlanningUtils = {
        preview_production_routing: preview_production_routing,
        populate_items_from_sales_order: populate_items_from_sales_order,
        format_quantity: format_quantity,
        show_warehouse_status: show_warehouse_status,
        update_all_zone_statuses: update_all_zone_statuses,
        show_warehouse_zones_mapping: show_warehouse_zones_mapping,
        show_work_order_operations: show_work_order_operations
    };
}

