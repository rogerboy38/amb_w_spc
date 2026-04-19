// =============================================================================
// BATCH AMB - COMPLETE INTEGRATED CLIENT SCRIPT
// Combines original functionality, BatchL2 enhancements, and Serial Tracking
// Version: 2026-02-14 - Merged Batch L2 client script features (Create Sublot/Container, Bulk Scan, View Batch Tree), route_options support for frappe.new_doc()
// =============================================================================

frappe.ui.form.on('Batch AMB', {
    // ==================== FORM EVENTS ====================

    refresh: function(frm) {
        console.log('🔧 Batch AMB Refresh triggered for:', frm.doc.name);

        // Original functionality
        setup_custom_buttons(frm);
        apply_field_filters(frm);
        setup_field_dependencies(frm);
        show_status_indicators(frm);

        if (!frm.is_new()) {
            frm.add_custom_button(__("New Sample Request"), () => {
                frappe.call({
                    method: "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.create_sample_request",
                    args: { batch_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Creating Sample Request..."),
                    callback(r) {
                        if (!r.exc && r.message) {
                            if (r.message.success) {
                                frappe.set_route("Form", "Sample Request AMB", r.message.sample_request);
                            }
                        } else if (r._server_messages) {
                            frappe.msgprint(r._server_messages);
                        }
                    }
                });
            }, __("Create"));
        }

        // BatchL2 enhancements
        if (should_auto_generate(frm)) {
            generate_batch_code(frm);
        }
        add_level_specific_buttons(frm);
        if (frm.doc.custom_batch_level == '3') {
            update_weight_totals(frm);
        }

        // Serial Tracking functionality
        add_serial_tracking_buttons(frm);

        // Load announcements
        load_batch_announcements(frm);

        // Debug button (optional - remove in production)
        add_debug_button(frm);
    },

    onload: function(frm) {
        console.log('📥 Batch AMB Onload for:', frm.doc.name);

        // Apply defaults from frappe.new_doc() / URL parameters
        if (frm.is_new() && frappe.route_options) {
            console.log('📋 Applying route_options:', frappe.route_options);
            for (let key in frappe.route_options) {
                if (frappe.route_options.hasOwnProperty(key) && frm.fields_dict[key]) {
                    frm.set_value(key, frappe.route_options[key]);
                }
            }
            // Clear route_options after applying
            frappe.route_options = null;
        }

        // Original functionality
        set_default_values(frm);
        load_user_preferences(frm);

        // BatchL2 enhancements
        if (frm.is_new()) {
            const hasPresetLevel = !!(frm.doc.custom_batch_level || (frappe.route_options && frappe.route_options.custom_batch_level));
            const hasPresetParent = !!(frm.doc.parent_batch_amb || (frappe.route_options && frappe.route_options.parent_batch_amb));
        
            if (!hasPresetLevel) {
                frm.set_value('custom_batch_level', '1');
            }
        
            if (!hasPresetParent) {
                frm.set_value('is_group', 1);
            } else {
                frm.set_value('is_group', 0);
            }
        
            configure_level_settings(frm);
        }

        // Initialize barrel management for level 3
        if (frm.doc.custom_batch_level == '3') {
            initialize_barrel_management(frm);
        }
    },

    // ==================== FIELD EVENTS ====================

    work_order: function(frm) {
        if (frm.doc.work_order) {
            frappe.call({
                method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.get_work_order_details',
                args: { work_order: frm.doc.work_order },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('item_to_manufacture', r.message.item_to_manufacture);
                        frm.set_value('item_name', r.message.item_name);
                        frm.set_value('planned_qty', r.message.planned_qty);
                        frm.set_value('company', r.message.company);
                        frm.set_value('bom_no', r.message.bom_no);
                        frm.set_value('source_warehouse', r.message.source_warehouse);
                        frm.set_value('target_warehouse', r.message.target_warehouse);
                        frm.set_value('uom', r.message.uom);

                        frappe.show_alert({
                            message: __('Work Order details loaded'),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    },

    work_order_ref: function(frm) {
        if (frm.doc.work_order_ref) {
            fetch_work_order_data(frm);
        }
    },

    title: function(frm) {
        // When title is set, update barrel serials
        if (frm.doc.title && frm.doc.container_barrels) {
            update_barrel_serials_from_title(frm);
        }
    },

    custom_generated_batch_name: function(frm) {
        // When generated name is set, update barrel serials
        if (frm.doc.custom_generated_batch_name && frm.doc.container_barrels) {
            update_barrel_serials_from_title(frm);
        }
    },
    custom_batch_level: function(frm) {
        if (!frm.is_new()) {
            frappe.msgprint('Cannot change batch level of existing documents. Create a new document for different levels.');
            frm.set_value('custom_batch_level', frm.doc.__original_level || '1');
            return;
        }
        configure_level_settings(frm);
        if (should_auto_generate(frm)) {
            generate_batch_code(frm);
        }
    },
    
    parent_batch_amb: function(frm) {
        if (frm.doc.parent_batch_amb === frm.doc.name) {
            frappe.msgprint(__('A batch cannot be its own parent'));
            frm.set_value('parent_batch_amb', '');
            return;
        }
    
        if (frm.doc.parent_batch_amb) {
            frappe.db.get_value('Batch AMB', frm.doc.parent_batch_amb, 'custom_batch_level')
                .then(r => {
                    const parent_level = cint((r.message && r.message.custom_batch_level) || 1);
                    const child_level = String(parent_level + 1);
                    
                    if (frm.is_new()) {
                        const has_preset_level = !!(
                            frm.doc.custom_batch_level ||
                            (frappe.route_options && frappe.route_options.custom_batch_level)
                        );
                    
                        const has_preset_parent = !!(
                            frm.doc.parent_batch_amb ||
                            (frappe.route_options && frappe.route_options.parent_batch_amb)
                        );
                    
                        if (!has_preset_level) {
                            frm.set_value('custom_batch_level', '1');
                        }
                    
                        frm.set_value('is_group', has_preset_parent ? 0 : 1);
                        configure_level_settings(frm);
                    }
                    if (frm.is_new()) {
                        frm.set_value('custom_batch_level', child_level);
                        frm.set_value('is_group', child_level === '4' ? 0 : 1);
                    }
    
                    configure_level_settings(frm);
    
                    if (should_auto_generate(frm)) {
                        generate_batch_code(frm);
                    }
                });
            return;
        }
    
        if (frm.is_new()) {
            frm.set_value('custom_batch_level', '1');
            frm.set_value('is_group', 1);
            configure_level_settings(frm);
    
            if (should_auto_generate(frm)) {
                generate_batch_code(frm);
            }
        }
    },
        


    default_packaging_type: function(frm) {
        if (frm.doc.default_packaging_type) {
            fetch_default_tara_weight(frm);
        }
    },

    calculate_cost: function(frm) {
        if (frm.doc.calculate_cost) {
            calculate_costs(frm);
        }
    },


    use_containers: function(frm) {
        setup_field_dependencies(frm);
    },
    before_save: function(frm) {
        // Validation for parent reference
        if (frm.doc.parent_batch_amb === frm.doc.name) {
            frappe.throw('A batch cannot be its own parent');
            return false;
        }

        // Parent validation for levels 2-4
        if (parseInt(frm.doc.custom_batch_level || '0', 10) > 1 && !frm.doc.parent_batch_amb) {
            frappe.throw('Parent Batch AMB is required for level ' + frm.doc.custom_batch_level);
            return false;
        }

        // Store original level
        if (!frm.doc.__original_level) {
            frm.doc.__original_level = frm.doc.custom_batch_level;
        }

        // Validate barrel data for level 3
        if (frm.doc.custom_batch_level == '3') {
            validate_barrel_data(frm);
        }

        // Calculate container totals
        calculate_container_totals(frm);

        return true;
    },

    after_save: function(frm) {
        // Refresh the form to get the latest values from the server
        frm.refresh();
    }
});
// ==================== CHILD TABLE: Container Barrels ====================

frappe.ui.form.on('Container Barrels', {
    // Original functionality
    quantity: function(frm, cdt, cdn) {
        calculate_container_totals(frm);
    },

    container_barrels_add: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        // Set default values
        row.status = 'Active';

        // BatchL2 enhancements
        if (frm.doc.default_packaging_type) {
            row.packaging_type = frm.doc.default_packaging_type;
        }

        // CRITICAL FIX: Set default weight values to 0 to avoid validation errors
        row.gross_weight = 0;
        row.tara_weight = 0;
        row.net_weight = 0;
        row.weight_validated = 0;

        // Generate serial number - use immediate generation with safety
        if (frm.doc.title || frm.doc.custom_generated_batch_name) {
            generate_barrel_serial_number_fixed(frm, row);
        } else {
            // Temporary placeholder if no title yet
            const temp_id = frm.doc.container_barrels ? frm.doc.container_barrels.length : 1;
            row.barrel_serial_number = `TEMP-${Date.now()}-${temp_id}`;
        }

        frm.refresh_field('container_barrels');
    },

    container_barrels_remove: function(frm) {
        calculate_container_totals(frm);
        update_weight_totals(frm);
    },

    // BatchL2 enhancements
    barcode_scan_input: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.barcode_scan_input) {
            process_barcode_scan_fixed(frm, cdt, cdn, row.barcode_scan_input);
        }
    },

    gross_weight: function(frm, cdt, cdn) {
        calculate_net_weight_fixed(frm, cdt, cdn);
        update_weight_totals(frm);
    },

    tara_weight: function(frm, cdt, cdn) {
        calculate_net_weight_fixed(frm, cdt, cdn);
        update_weight_totals(frm);
    },

    packaging_type: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.packaging_type) {
            fetch_tara_weight_for_row_fixed(frm, cdt, cdn);
        }
    }
});

// ==================== SAFER HELPER FUNCTIONS ====================
function generate_barrel_serial_number_fixed(frm, row) {
    // FIXED: Don't validate weight, just generate serial
    try {
        const container_code = frm.doc.title || frm.doc.custom_generated_batch_name;

        if (!container_code) {
            // Use temporary serial if no code
            row.barrel_serial_number = `TEMP-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
            return;
        }

        // Find highest existing sequence
        let max_seq = 0;
        const barrels = frm.doc.container_barrels || [];

        barrels.forEach(barrel => {
            if (barrel.barrel_serial_number && barrel.barrel_serial_number.startsWith(container_code + '-C')) {
                const parts = barrel.barrel_serial_number.split('-C');
                if (parts.length > 1 && /^\d+$/.test(parts[1])) {
                    const num = parseInt(parts[1], 10);
                    if (num > max_seq) {
                        max_seq = num;
                    }
                }
            }
        });

        // Generate next number with C prefix (C001, C002, etc.)
        const next_seq = max_seq + 1;
        row.barrel_serial_number = `${container_code}-C${next_seq.toString().padStart(3, '0')}`;

    } catch (error) {
        console.error('Error in generate_barrel_serial_number_fixed:', error);
        // Fallback to timestamp-based serial
        row.barrel_serial_number = `ERR-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
    }
}

// NEW FUNCTION: Update barrel serials when title changes
function update_barrel_serials_from_title(frm) {
    const prefix = frm.doc.title || frm.doc.custom_generated_batch_name;
    if (!prefix || !frm.doc.container_barrels) return;

    let sequence = 1;
    let updated = false;

    frm.doc.container_barrels.forEach(row => {
        // Update only TEMP barrels or barrels without proper serials
        if (!row.barrel_serial_number || row.barrel_serial_number.startsWith('TEMP-')) {
            row.barrel_serial_number = `${prefix}-C${sequence.toString().padStart(3, '0')}`;
            sequence++;
            updated = true;
        }
    });

    if (updated) {
        frm.refresh_field('container_barrels');
        frappe.show_alert({
            message: __('Barrel serial numbers updated from batch title'),
            indicator: 'green'
        });
    }
}

function process_barcode_scan_safe(frm, cdt, cdn, barcode) {
    const row = locals[cdt][cdn];
    if (!barcode || !barcode.trim()) {
        return;
    }

    // Validate format
    if (!validate_code39_format(barcode)) {
        frappe.msgprint({
            title: __('Invalid Barcode'),
            message: __('Invalid CODE-39 format: {0}', [barcode]),
            indicator: 'red'
        });
        frappe.model.set_value(cdt, cdn, 'barcode_scan_input', '');
        return;
    }

    // Set values directly
    row.barrel_serial_number = barcode.trim().toUpperCase();
    row.scan_timestamp = frappe.datetime.now_datetime();
    row.barcode_scan_input = '';

    // Refresh to show changes
    frm.refresh_field('container_barrels');

    // Fetch tara weight if packaging type exists
    if (row.packaging_type) {
        setTimeout(() => {
            fetch_tara_weight_for_row_safe(frm, cdt, cdn);
        }, 100);
    }
}

function fetch_tara_weight_for_row_safe(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.packaging_type) return;

    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Item',
            filters: { name: row.packaging_type },
            fieldname: 'weight_per_unit'
        },
        callback: function(r) {
            if (r.message && r.message.weight_per_unit !== undefined) {
                frappe.model.set_value(cdt, cdn, 'tara_weight', r.message.weight_per_unit);
                // Calculate net weight after a delay
                setTimeout(() => {
                    calculate_net_weight(frm, cdt, cdn);
                    update_weight_totals(frm);
                }, 100);
            }
        },
        error: function(err) {
            console.error('Error fetching tara weight:', err);
        }
    });
}

function calculate_net_weight(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    // Only calculate if both values exist
    if (row.gross_weight !== undefined && row.tara_weight !== undefined) {
        const gross = parseFloat(row.gross_weight) || 0;
        const tara = parseFloat(row.tara_weight) || 0;
        const net_weight = gross - tara;

        // Set the net weight
        frappe.model.set_value(cdt, cdn, 'net_weight', net_weight);

        // Validate (net should be positive and less than gross)
        const weight_validated = (net_weight > 0 && net_weight < gross) ? 1 : 0;
        frappe.model.set_value(cdt, cdn, 'weight_validated', weight_validated);
    }
}

function update_weight_totals(frm) {
    // Don't run if not level 3 or no barrels
    if (frm.doc.custom_batch_level != '3' || !frm.doc.container_barrels) return;

    let total_gross = 0;
    let total_tara = 0;
    let total_net = 0;
    let barrel_count = 0;

    frm.doc.container_barrels.forEach(row => {
        if (row.gross_weight !== undefined && row.gross_weight !== null) {
            total_gross += parseFloat(row.gross_weight) || 0;
        }
        if (row.tara_weight !== undefined && row.tara_weight !== null) {
            total_tara += parseFloat(row.tara_weight) || 0;
        }
        if (row.net_weight !== undefined && row.net_weight !== null) {
            total_net += parseFloat(row.net_weight) || 0;
        }
        if (row.barrel_serial_number) {
            barrel_count += 1;
        }
    });

    // Update form values
    frm.set_value('total_gross_weight', total_gross);
    frm.set_value('total_tara_weight', total_tara);
    frm.set_value('total_net_weight', total_net);
    frm.set_value('barrel_count', barrel_count);
}
// ==================== SERIAL TRACKING FUNCTIONS ====================

function add_serial_tracking_buttons(frm) {
    console.log('🔗 Adding serial tracking buttons...');

    // Skip for level 4 batches (they have their own system)
    if (frm.doc.custom_batch_level === '4') {
        console.log('⚠️ Level 4 batch - using existing barrel system, skipping serial tracking buttons');
        return;
    }

    // Integrate Serial Tracking button
    if (!frm.doc.custom_serial_tracking_integrated) {
        frm.add_custom_button(__('🔗 Integrate Serial Tracking'), function() {
            frappe.call({
                method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.integrate_serial_tracking',
                args: {batch_name: frm.doc.name},
                freeze: true,
                freeze_message: __('Connecting to Serial Tracking...'),
                callback: function(r) {
                    console.log('Integration response:', r);
                    if (r.message && r.message.status === 'success') {
                        frappe.show_alert({
                            message: __('✅ Serial Tracking Integrated Successfully!'),
                            indicator: 'green'
                        }, 5);
                        frm.reload_doc();
                    } else {
                        frappe.msgprint({
                            title: __('Integration Failed'),
                            message: r.message ? r.message.message : __('Please try again.'),
                            indicator: 'red'
                        });
                    }
                },
                error: function(err) {
                    console.error('Integration error:', err);
                    frappe.msgprint({
                        title: __('Connection Error'),
                        message: __('Please try again or contact support.'),
                        indicator: 'orange'
                    });
                }
            });
        }, __('🔗 SERIAL TRACKING')).addClass('btn-primary');

        console.log('Added: Integrate Serial Tracking button');
    }

    // Generate Serial Numbers button
    frm.add_custom_button(__('🎫 Generate Serial Numbers'), function() {
        generateSerialNumbers(frm);
    }, __('🔗 SERIAL TRACKING'));

    console.log('Added: Generate Serial Numbers button');

    // Status display
    if (frm.doc.custom_serial_tracking_integrated) {
        var serialCount = 0;
        if (frm.doc.custom_serial_numbers) {
            serialCount = frm.doc.custom_serial_numbers.split('\\n').filter(function(s) {
                return s.trim().length > 0;
            }).length;
        }

        var statusHTML = `
            <div style="
                padding: 15px;
                background: #e8f5e9;
                border-radius: 8px;
                margin: 15px 0;
                border-left: 4px solid #2e7d32;
            ">
                <h5 style="margin: 0 0 10px 0; color: #2e7d32;">
                    <i class="fa fa-check-circle"></i> Serial Tracking Active
                </h5>
                <div style="font-size: 13px; color: #555;">
                    <div style="margin-bottom: 5px;">
                        <strong>📊 Serial Numbers:</strong> ${serialCount}
                    </div>
                    <div style="margin-bottom: 5px;">
                        <strong>🕐 Last Sync:</strong> ${frm.doc.custom_last_api_sync || 'Never'}
                    </div>
                    <div style="margin-bottom: 5px;">
                        <strong>🔗 Status:</strong> ${frm.doc.custom_serial_tracking_integrated ? 'Integrated' : 'Not Integrated'}
                    </div>
                </div>
            </div>
        `;

        frm.dashboard.add_section(statusHTML);
        console.log('Added: Serial Tracking status display');
    }
}

// ==================== GENERATE SERIAL NUMBERS FUNCTION ====================

function generateSerialNumbers(frm) {
    // Check if this is a level 4 batch
    var isLevel4 = frm.doc.custom_batch_level === '4';

    if (isLevel4) {
        // Level 4: Show dialog with prefix field
        frappe.prompt([
            {
                fieldname: 'quantity',
                fieldtype: 'Int',
                label: __('Number of Barrels'),
                description: __('How many barrels do you need?'),
                default: frm.doc.planned_qty || 1,
                reqd: 1
            },
            {
                fieldname: 'prefix',
                fieldtype: 'Data',
                label: __('Serial Prefix'),
                description: __('Prefix for barrel serial numbers (e.g., BRL, DRM, etc.)'),
                default: 'BRL',
                reqd: 1
            }
        ], function(values) {
            if (values.quantity <= 0) {
                frappe.msgprint(__('Quantity must be greater than 0'));
                return;
            }

            frappe.call({
                method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.generate_serial_numbers',
                args: {
                    batch_name: frm.doc.name,
                    quantity: values.quantity,
                    prefix: values.prefix
                },
                freeze: true,
                freeze_message: __('Generating Barrel Serial Numbers...'),
                callback: function(r) {
                    console.log('Generate response:', r);
                    if (r.message && r.message.status === 'success') {
                        frappe.show_alert({
                            message: __('✅ Successfully generated ') + r.message.count + __(' barrel serial numbers.'),
                            indicator: 'green'
                        }, 5);
                        frm.reload_doc();
                    } else {
                        frappe.msgprint({
                            title: __('Error'),
                            message: r.message ? r.message.message : __('Failed to generate serial numbers'),
                            indicator: 'red'
                        });
                    }
                },
                error: function(err) {
                    console.error('Generate error:', err);
                    frappe.msgprint({
                        title: __('Server Error'),
                        message: __('Connection error. Please try again.'),
                        indicator: 'red'
                    });
                }
            });
        }, __('Generate Barrel Serial Numbers'), __('Generate'));

    } else {
        // Levels 1-3: Simple quantity prompt
        frappe.prompt({
            fieldname: 'quantity',
            fieldtype: 'Int',
            label: __('Number of serials to generate'),
            description: __('How many container serial numbers do you need?'),
            default: frm.doc.planned_qty || 1,
            reqd: 1
        }, function(values) {
            if (values.quantity <= 0) {
                frappe.msgprint(__('Quantity must be greater than 0'));
                return;
            }

            frappe.call({
                method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.generate_serial_numbers',
                args: {
                    batch_name: frm.doc.name,
                    quantity: values.quantity
                    // No prefix for non-level 4 batches
                },
                freeze: true,
                freeze_message: __('Generating Serial Numbers...'),
                callback: function(r) {
                    console.log('Generate response:', r);
                    if (r.message && r.message.status === 'success') {
                        frappe.show_alert({
                            message: __('✅ Successfully generated ') + r.message.count + __(' serial numbers.'),
                            indicator: 'green'
                        }, 5);
                        frm.reload_doc();
                    } else {
                        frappe.msgprint({
                            title: __('Error'),
                            message: r.message ? r.message.message : __('Failed to generate serial numbers'),
                            indicator: 'red'
                        });
                    }
                },
                error: function(err) {
                    console.error('Generate error:', err);
                    frappe.msgprint({
                        title: __('Server Error'),
                        message: __('Connection error. Please try again.'),
                        indicator: 'red'
                    });
                }
            });
        });
    }
}

// ==================== DEBUG/HELPER FUNCTIONS ====================

function add_debug_button(frm) {
    frm.add_custom_button(__('🐛 Debug Test'), function() {
        frappe.call({
            method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.fixed_generate_serial_numbers',
            args: {
                batch_name: frm.doc.name,
                quantity: 1
            },
            callback: function(r) {
                console.log('Debug test response:', r);
                if (r.message && r.message.status === 'success') {
                    frappe.show_alert({
                        message: '✅ Debug test successful! Generated ' + r.message.count + ' serials',
                        indicator: 'green'
                    }, 5);
                    frm.reload_doc();
                } else {
                    frappe.msgprint({
                        title: 'Debug Test Failed',
                        message: r.message ? r.message.message : 'Unknown error',
                        indicator: 'red'
                    });
                }
            }
        });
    }, __('Debug'));
}

// ==================== MAIN FUNCTIONALITY ====================

function setup_custom_buttons(frm) {
    console.log('🎯 Setting up custom buttons for:', frm.doc.name);

    // Clear existing buttons
    if (frm.page && frm.page.clear_actions) {
        frm.page.clear_actions();
    }

    if (frm.doc.__islocal) return;

    // Create button groups
    const actions_group = __('Actions');
    const manufacturing_group = __('Manufacturing');
    const view_group = __('View');
    const create_group = __('Create');

    // ========== ACTIONS GROUP ==========

    // Calculate Cost button
    frm.add_custom_button(__('Calculate Cost'), function() {
        frappe.call({
            method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.calculate_batch_cost',
            args: { batch_name: frm.doc.name },
            callback: function(r) {
                if (r.message) {
                    frm.set_value('total_batch_cost', r.message.total_batch_cost);
                    frm.set_value('cost_per_unit', r.message.cost_per_unit);
                    frappe.show_alert({
                        message: __('Costs calculated'),
                        indicator: 'green'
                    });
                }
            }
        });
    }, actions_group);

    // Duplicate Batch button
    frm.add_custom_button(__('Duplicate Batch'), function() {
        frappe.call({
            method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.duplicate_batch',
            args: { source_name: frm.doc.name },
            callback: function(r) {
                if (r.message) {
                    frappe.set_route('Form', 'Batch AMB', r.message);
                }
            }
        });
    }, actions_group);

    // ========== MANUFACTURING GROUP ==========

    // Check for existing BOM and show appropriate button
    if (frm.doc.custom_batch_level && frm.doc.custom_batch_level !== '4') {
        add_bom_button_to_form(frm);
    }

    // Generate MRP Button
    frm.add_custom_button(__('Generate MRP'), function() {
        frappe.call({
            method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.calculate_material_requirements',
            args: {batch_name: frm.doc.name},
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.msgprint({
                        message: __('Material requirements calculated successfully'),
                        title: __('MRP Generated'),
                        indicator: 'green'
                    });
                } else {
                    frappe.msgprint({
                        message: __('Error generating MRP: ' + (r.message?.message || 'Unknown error')),
                        title: __('Error'),
                        indicator: 'red'
                    });
                }
            }
        });
    }, manufacturing_group);

    // Create Work Order Button
    frm.add_custom_button(__('Create Work Order'), function() {
        frappe.call({
            method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.create_work_order_from_batch',
            args: { batch_name: frm.doc.name },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.msgprint({
                        title: __('Work Order Created'),
                        message: __('Work Order {0} created successfully', [r.message.work_order]),
                        indicator: 'green'
                    });
                    frm.reload_doc();
                } else {
                    frappe.msgprint({
                        title: __('Error'),
                        message: __('Failed to create Work Order: ' + (r.message?.message || 'Unknown error')),
                        indicator: 'red'
                    });
                }
            }
        });
    }, manufacturing_group);

    // Assign Golden Number Button
    frm.add_custom_button(__('Assign Golden Number'), function() {
        frappe.call({
            method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.assign_golden_number_to_batch',
            args: { batch_name: frm.doc.name },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.msgprint({
                        title: __('Golden Number Assigned'),
                        message: __('Golden Number {0} assigned successfully', [r.message.golden_number]),
                        indicator: 'green'
                    });
                    frm.reload_doc();
                } else {
                    frappe.msgprint({
                        title: __('Error'),
                        message: __('Failed to assign Golden Number: ' + (r.message?.message || 'Unknown error')),
                        indicator: 'red'
                    });
                }
            }
        });
    }, manufacturing_group);

    // Update Planned Qty Button
    frm.add_custom_button(__('Update Planned Qty'), function() {
        frappe.call({
            method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.update_planned_qty_from_work_order',
            args: { batch_name: frm.doc.name },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.msgprint({
                        title: __('Planned Quantity Updated'),
                        message: __('Planned quantity updated to {0}', [r.message.planned_qty]),
                        indicator: 'green'
                        });
                    frm.reload_doc();
                } else {
                    frappe.msgprint({
                        title: __('Error'),
                        message: __('Failed to update planned quantity: ' + (r.message?.message || 'Unknown error')),
                        indicator: 'red'
                    });
                }
            }
        });
    }, manufacturing_group);

    // ========== CREATE GROUP ==========

    // Create Stock Entry button (if not submitted)
    if (frm.doc.docstatus === 1 && !frm.doc.stock_entry_reference) {
        frm.add_custom_button(__('Create Stock Entry'), function() {
            frappe.confirm(
                __('Create Stock Entry for this batch?'),
                function() {
                    frm.set_value('auto_create_stock_entry', 1);
                    frm.save();
                }
            );
        }, create_group);
    }

    // ========== VIEW GROUP ==========

    // View Stock Entry button
    if (frm.doc.stock_entry_reference) {
        frm.add_custom_button(__('View Stock Entry'), function() {
            frappe.set_route('Form', 'Stock Entry', frm.doc.stock_entry_reference);
        }, view_group);
    }

    // View Lote AMB button
    if (frm.doc.lote_amb_reference) {
        frm.add_custom_button(__('View Lote AMB'), function() {
            frappe.set_route('Form', 'Lote AMB', frm.doc.lote_amb_reference);
        }, view_group);
    }

    // Sample Request button
    frm.add_custom_button(__('Sample Request'), function() {
        frappe.call({
            method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.create_sample_request',
            args: { batch_name: frm.doc.name },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.show_alert({
                        message: __(r.message.message),
                        indicator: 'green'
                    });
                    if (r.message.action === 'open') {
                        frappe.set_route('Form', 'Sample Request AMB', r.message.sample_request);
                    } else {
                        frappe.set_route('Form', 'Sample Request AMB', r.message.sample_request);
                    }
                } else {
                    frappe.msgprint({
                        title: __('Error'),
                        message: r.message ? r.message.message : __('Failed to create sample request'),
                        indicator: 'red'
                    });
                }
            }
        });
    }, actions_group);

    console.log('✅ Custom buttons setup completed');
}

function add_bom_button_to_form(frm) {
    console.log('🎯 add_bom_button_to_form called for:', frm.doc.name);

    if (!frm.doc.item_to_manufacture && !frm.doc.current_item_code) {
        console.log('❌ No item found, skipping BOM button');
        return;
    }

    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.check_bom_exists',
        args: { batch_name: frm.doc.name },
        callback: function(r) {
            console.log('BOM check response:', r.message);
            if (r.message && r.message.exists) {
                frm.add_custom_button(__('View BOM'), function() {
                    frappe.set_route('Form', 'BOM Creator', r.message.bom_name);
                }, __('Manufacturing')).css({'background-color': '#28a745', 'color': 'white'});
                console.log('✅ Added "View BOM" button');
            } else {
                frm.add_custom_button(__('Create BOM'), function() {
                    open_bom_creation_wizard(frm);
                }, __('Manufacturing')).addClass('btn-primary');
                console.log('✅ Added "Create BOM" button');
            }
        },
        error: function(err) {
            console.error('❌ Error checking BOM:', err);
        }
    });
}

// ==================== BATCHL2 ENHANCED FUNCTIONS ====================

function add_level_specific_buttons(frm) {
    // Add buttons based on batch level
	    const currentLevel = frm.doc.custom_batch_level;
    if (!currentLevel) return;

    // Level 1: Create Sublot button
    if (currentLevel === '1') {
        frm.add_custom_button(__('Create Sublot'), function() {
            create_sublot_batch(frm);
        }).addClass('btn-primary');
    }

    // Level 2: Create Sublot + Create Container buttons
    if (currentLevel === '2') {
        frm.add_custom_button(__('Create Sublot'), function() {
            create_sublot_batch(frm);
        });
        frm.add_custom_button(__('Create Container'), function() {
            create_container_batch(frm);
        }).addClass('btn-primary');
    }

    // Level 3: handled by existing code below, plus additional buttons
    if (currentLevel === '3') {
        frm.add_custom_button(__('Create Container'), function() {
            create_container_batch(frm);
        });
        frm.add_custom_button(__('Scan Multiple Barcodes'), function() {
            open_bulk_scan_dialog(frm);
        });
        frm.add_custom_button(__('Generate Barrel Serials'), function() {
            generate_bulk_barrel_serials(frm);
        }).addClass('btn-primary');
    }

    // Level 4: Scan Multiple Barcodes
    if (currentLevel === '4') {
        frm.add_custom_button(__('Scan Multiple Barcodes'), function() {
            open_bulk_scan_dialog(frm);
        }).addClass('btn-primary');
    }

    // Add global buttons for non-level-4
    add_global_buttons(frm);

    // Original Level 3 scanning functionality continues below

    if (frm.doc.custom_batch_level == '3') {
        const scan_group = __('🔍 Scanning');

        // Barrel Scanner button
        frm.add_custom_button(__('Barrel Scanner'), function() {
            frm.set_value('quick_barcode_scan', '');
            frappe.show_alert({
                message: __('Ready for barcode scanning. Use the Quick Barcode Scan field.'),
                indicator: 'blue'
            }, 5);
        }, scan_group);

        // Validate Barrels button
        frm.add_custom_button(__('Validate Barrels'), function() {
            validate_all_barrels(frm);
        }, scan_group);

        // Calculate Totals button
        frm.add_custom_button(__('Calculate Totals'), function() {
            update_weight_totals(frm);
            frappe.show_alert({
                message: __('Weight totals updated'),
                indicator: 'green'
            }, 3);
        }, scan_group);
    }
}

function should_auto_generate(frm) {
    return frm.is_new() && (
        (frm.doc.custom_batch_level == '1' && !frm.doc.title) ||
        (frm.doc.custom_batch_level == '2' && frm.doc.parent_batch_amb) ||
        (frm.doc.custom_batch_level == '3' && frm.doc.parent_batch_amb && !frm.doc.custom_generated_batch_name)
    );
}

function generate_batch_code(frm) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.generate_batch_code',
        args: {
            parent_batch: frm.doc.parent_batch_amb,
            batch_level: frm.doc.custom_batch_level,
            work_order: frm.doc.work_order_ref
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('custom_generated_batch_name', r.message.code);
                if (!frm.doc.title) {
                    frm.set_value('title', r.message.code);
                }
            }
        }
    });
}

function configure_level_settings(frm) {
    // Configure form settings based on batch level
    const level = parseInt(frm.doc.custom_batch_level || '1', 10);

    switch(level) {
        case 1:
            // Level 1 - Root level
            frm.set_df_property('parent_batch_amb', 'hidden', 1);
            frm.set_df_property('container_level_3_section', 'hidden', 0);
            break;
        case 2:
            // Level 2 - Intermediate level
            frm.set_df_property('parent_batch_amb', 'hidden', 0);
            frm.set_df_property('container_level_3_section', 'hidden', 0);
            break;
        case 3:
            // Level 3 - Container level
            frm.set_df_property('parent_batch_amb', 'hidden', 0);
            frm.set_df_property('container_level_3_section', 'hidden', 0);
            break;
        case 4:
            // Level 4 - Final product level
            frm.set_df_property('parent_batch_amb', 'hidden', 0);
            frm.set_df_property('container_level_3_section', 'hidden', 0);
            break;
    }
}

// ==================== BARREL MANAGEMENT FUNCTIONS ====================

function initialize_barrel_management(frm) {
    // Initialize barrel management for Level 3 batches
    if (!frm.doc.container_barrels) {
        frm.doc.container_barrels = [];
    }
}

function process_quick_barcode_scan(frm) {
    const barcode = frm.doc.quick_barcode_scan;
    if (!barcode) return;

    if (!validate_code39_format(barcode)) {
        frappe.msgprint('Invalid CODE-39 barcode format');
        frm.set_value('quick_barcode_scan', '');
        return;
    }

    const row = frm.add_child('container_barrels');
    row.barrel_serial_number = barcode;
    row.packaging_type = frm.doc.default_packaging_type || 'Barrel';
    row.scan_timestamp = frappe.datetime.now_datetime();
    if (row.packaging_type) {
        fetch_tara_weight_for_row(frm, row.doctype, row.name);
    }
    frm.refresh_field('container_barrels');
    frm.set_value('quick_barcode_scan', '');
    setTimeout(function() { frm.scroll_to_field('container_barrels'); }, 300);
}

function process_barcode_scan(frm, cdt, cdn, barcode) {
    const row = locals[cdt][cdn];
    if (!validate_code39_format(barcode)) {
        frappe.msgprint('Invalid CODE-39 barcode format');
        frappe.model.set_value(cdt, cdn, 'barcode_scan_input', '');
        return;
    }
    frappe.model.set_value(cdt, cdn, 'barrel_serial_number', barcode);
    frappe.model.set_value(cdt, cdn, 'scan_timestamp', frappe.datetime.now_datetime());
    frappe.model.set_value(cdt, cdn, 'barcode_scan_input', '');
    if (row.packaging_type) {
        fetch_tara_weight_for_row(frm, cdt, cdn);
    }
}

function generate_barrel_serial_number(frm, row) {
    const container_code = frm.doc.title || frm.doc.custom_generated_batch_name;
    if (!container_code) return;

    let max_seq = 0;
    (frm.doc.container_barrels || []).forEach(barrel => {
        if (barrel.barrel_serial_number && barrel.barrel_serial_number.startsWith(container_code)) {
            const match = barrel.barrel_serial_number.match(/-([0-9]+)$/);
            if (match) {
                max_seq = Math.max(max_seq, parseInt(match[1], 10));
            }
        }
    });

    const next_seq = (max_seq + 1).toString().padStart(3, '0');
    row.barrel_serial_number = `${container_code}-${next_seq}`;
}

function fetch_tara_weight_for_row(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.packaging_type) return;

    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Item',
            name: row.packaging_type
        },
        callback: function(r) {
            if (r.message && r.message.weight_per_unit) {
                frappe.model.set_value(cdt, cdn, 'tara_weight', r.message.weight_per_unit);
                calculate_net_weight(frm, cdt, cdn);
            }
        }
    });
}

function fetch_default_tara_weight(frm) {
    if (!frm.doc.default_packaging_type) return;

    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Item',
            name: frm.doc.default_packaging_type
        },
        callback: function(r) {
            if (r.message && r.message.weight_per_unit) {
                // Update all existing barrels with new default
                (frm.doc.container_barrels || []).forEach(row => {
                    if (!row.tara_weight) {
                        frappe.model.set_value(row.doctype, row.name, 'tara_weight', r.message.weight_per_unit);
                        calculate_net_weight(frm, row.doctype, row.name);
                    }
                });
            }
        }
    });
}

function calculate_net_weight(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (row.gross_weight && row.tara_weight) {
        const net_weight = row.gross_weight - row.tara_weight;
        frappe.model.set_value(cdt, cdn, 'net_weight', net_weight);
        frappe.model.set_value(cdt, cdn, 'weight_validated', net_weight > 0 && net_weight < row.gross_weight ? 1 : 0);
    }
}

function update_weight_totals(frm) {
    if (frm.doc.custom_batch_level != '3' || !frm.doc.container_barrels) return;

    let total_gross = 0, total_tara = 0, total_net = 0, barrel_count = 0;
    frm.doc.container_barrels.forEach(row => {
        if (row.gross_weight) total_gross += row.gross_weight;
        if (row.tara_weight) total_tara += row.tara_weight;
        if (row.net_weight) total_net += row.net_weight;
        if (row.barrel_serial_number) barrel_count += 1;
    });
    frm.set_value('total_gross_weight', total_gross);
    frm.set_value('total_tara_weight', total_tara);
    frm.set_value('total_net_weight', total_net);
    frm.set_value('barrel_count', barrel_count);
}

// ==================== VALIDATION FUNCTIONS ====================

function validate_barrel_data(frm) {
    // Validate barrel data before save
    if (!frm.doc.container_barrels || frm.doc.container_barrels.length === 0) {
        frappe.msgprint('Container barrels are required for Level 3 batches');
        return false;
    }

    // Check for duplicate serials (ignore TEMP serials)
    const serials = [];
    const duplicates = [];
    frm.doc.container_barrels.forEach(row => {
        if (row.barrel_serial_number && !row.barrel_serial_number.startsWith('TEMP-')) {
            if (serials.includes(row.barrel_serial_number)) {
                duplicates.push(row.barrel_serial_number);
            } else {
                serials.push(row.barrel_serial_number);
            }
        }
    });

    if (duplicates.length > 0) {
        frappe.throw('Duplicate barrel serial numbers found: ' + duplicates.join(', '));
        return false;
    }

    return true;
}
function validate_all_barrels(frm) {
    // Validate all barrels and show results
    let valid = 0;
    let invalid = 0;
    const issues = [];

    (frm.doc.container_barrels || []).forEach((row, index) => {
        if (!row.barrel_serial_number) {
            invalid++;
            issues.push(`Row ${index + 1}: Missing serial number`);
        } else if (!validate_code39_format(row.barrel_serial_number)) {
            invalid++;
            issues.push(`Row ${index + 1}: Invalid format (${row.barrel_serial_number})`);
        } else {
            valid++;
        }
    });

    if (issues.length > 0) {
        frappe.msgprint('Validation Issues:<br>' + issues.join('<br>'), 'Invalid');
    } else {
        frappe.msgprint(`All barrels validated successfully! Valid: ${valid}, Total: ${valid + invalid}`, 'Valid');
    }
}

function validate_code39_format(barcode) {
    const s = String(barcode || '').toUpperCase();
    // Allowed: A-Z 0-9 and - . space $ / + % *
    return /^[A-Z0-9\-\.\s$\/+%*]+$/.test(s);
}

// ==================== ORIGINAL HELPER FUNCTIONS ====================

function load_batch_announcements(frm) {
    console.log('📢 Loading batch announcements...');
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.get_running_batch_announcements',
        args: {},
        callback: function(r) {
            if (r.message && r.message.success) {
                console.log('Announcements loaded:', r.message.announcements);
                display_announcements(frm, r.message.announcements);
            } else {
                console.error('Failed to load announcements:', r.message);
                display_announcements(frm, []);
            }
        },
        error: function(err) {
            console.error('Error loading announcements:', err);
            display_announcements(frm, []);
        }
    });
}

function display_announcements(frm, announcements) {
    // Clear existing announcements
    const announcement_container = $('.batch-announcements');
    if (announcement_container.length === 0) {
        // Create container if it doesn't exist
        frm.dashboard.add_section(
            __('Batch Announcements'),
            '<div class="batch-announcements"></div>'
        );
    }

    const container = $('.batch-announcements');
    container.empty();

    if (!announcements || announcements.length === 0) {
        container.html('<div class="alert alert-warning">No running batches found</div>');
        return;
    }

    let html = '<div class="announcement-list">';
    announcements.forEach(announcement => {
					// FIX: Enrich announcement with missing fields for display
			if (!announcement.batch_name) announcement.batch_name = announcement.name;
			if (!announcement.work_order) {
				// Fallback: if this is the current batch, use frm.doc
				if (announcement.name === frm.doc.name) {
					announcement.work_order = frm.doc.work_order_ref || frm.doc.work_order || 'N/A';
					announcement.plant = frm.doc.production_plant_name || frm.doc.custom_plant_code || 'N/A';
					announcement.golden_number = frm.doc.custom_golden_number || '';
				}
			}
			if (!announcement.plant) announcement.plant = announcement.company || 'N/A';
			if (!announcement.golden_number) announcement.golden_number = announcement.title || '';
        html += `
            <div class="announcement-item">
                <strong>${announcement.batch_name || announcement.name}</strong>
                <br>Work Order: ${announcement.work_order || 'N/A'}
                <br>Plant: ${announcement.plant || 'N/A'}
                <br>Status: <span class="label label-${get_status_class(announcement.status)}">${announcement.status}</span>
                <br>Quality: <span class="label label-${get_quality_class(announcement.quality_status)}">${announcement.quality_status}</span>
                ${announcement.golden_number ? `<br>Golden Number: ${announcement.golden_number}` : ''}
            </div>
        `;
    });
    html += '</div>';

    container.html(html);
}

function get_status_class(status) {
    const statusMap = {
        'Running': 'success',
        'In Progress': 'info',
        'Active': 'info',
        'Approved': 'success',
        'Draft': 'default',
        'Completed': 'success',
        'Cancelled': 'danger'
    };
    return statusMap[status] || 'default';
}

function get_quality_class(quality) {
    const qualityMap = {
        'Passed': 'success',
        'Failed': 'danger',
        'Pending': 'warning',
        'In Testing': 'info'
    };
    return qualityMap[quality] || 'default';
}

function apply_field_filters(frm) {
    // Filter work orders
    frm.set_query('work_order', function() {
        return {
            filters: {
                'status': ['not in', ['Completed', 'Stopped', 'Cancelled']],
                'docstatus': 1
            }
        };
    });

    // Filter items to manufacture
    frm.set_query('item_to_manufacture', function() {
        return {
            filters: {
                'is_stock_item': 1,
                'disabled': 0
            }
        };
    });

    // Filter warehouses
    frm.set_query('source_warehouse', function() {
        return {
            filters: {
                'is_group': 0,
                'disabled': 0,
                'company': frm.doc.company
            }
        };
    });

    frm.set_query('target_warehouse', function() {
        return {
            filters: {
                'is_group': 0,
                'disabled': 0,
                'company': frm.doc.company
            }
        };
    });
}

function setup_field_dependencies(frm) {
    // Show/hide fields based on conditions

    // Cost calculation fields
    frm.toggle_display('labor_cost', frm.doc.calculate_cost);
    frm.toggle_display('overhead_cost', frm.doc.calculate_cost);
    frm.toggle_display('total_batch_cost', frm.doc.calculate_cost);
    frm.toggle_display('cost_per_unit', frm.doc.calculate_cost);

    // Container section
    // frm.toggle_display("container_barrels", frm.doc.use_containers); // Always show container_barrels
    frm.toggle_display('total_containers', frm.doc.use_containers);
    frm.toggle_display('total_container_qty', frm.doc.use_containers);
}

function show_status_indicators(frm) {
    if (frm.doc.batch_status) {
        let color = {
            'Draft': 'gray',
            'In Progress': 'orange',
            'Completed': 'green',
            'On Hold': 'yellow',
            'Cancelled': 'red'
        }[frm.doc.batch_status] || 'gray';

        frm.dashboard.set_headline_alert(
            __('Status: {0}', [frm.doc.batch_status]),
            color
        );
    }

    // Quality status indicator
    if (frm.doc.quality_status) {
        let indicator = {
            'Passed': 'green',
            'Failed': 'red',
            'Pending': 'orange',
            'In Testing': 'blue'
        }[frm.doc.quality_status] || 'gray';

        frm.add_custom_button(
            __(frm.doc.quality_status),
            function() {},
            null,
            indicator
        );
    }
}

function set_default_values(frm) {
    if (frm.doc.__islocal) {
        // Set default company
        if (!frm.doc.company) {
            frm.set_value('company', frappe.defaults.get_default('company'));
        }

        // Set default production start date
        if (!frm.doc.production_start_date) {
            frm.set_value('production_start_date', frappe.datetime.get_today());
        }

        // Set default status
        if (!frm.doc.batch_status) {
            frm.set_value('batch_status', 'Draft');
        }
    }
}

function load_user_preferences(frm) {
	// Load user's preferred warehouses using frappe.defaults (safe API)
	var default_wh = frappe.defaults.get_user_default('Warehouse');
	if (default_wh && !frm.doc.target_warehouse) {
		frm.set_value('target_warehouse', default_wh);
	}
}

function calculate_container_totals(frm) {
    if (!frm.doc.container_barrels) return;

    let total_qty = 0;
    let total_containers = 0;
    let total_gross = 0, total_tara = 0, total_net = 0, barrel_count = 0;

    frm.doc.container_barrels.forEach(function(row) {
        // Original quantity calculation
        if (row.quantity) {
            total_qty += flt(row.quantity);
        }
        total_containers++;

        // BatchL2 weight calculations
        if (row.gross_weight) total_gross += row.gross_weight;
        if (row.tara_weight) total_tara += row.tara_weight;
        if (row.net_weight) total_net += row.net_weight;
        if (row.barrel_serial_number) barrel_count += 1;
    });

    // Update original fields
    frm.set_value('total_container_qty', total_qty);
    frm.set_value('total_containers', total_containers);

    // Update BatchL2 fields
    frm.set_value('total_gross_weight', total_gross);
    frm.set_value('total_tara_weight', total_tara);
    frm.set_value('total_net_weight', total_net);
    frm.set_value('barrel_count', barrel_count);
}

function calculate_costs(frm) {
    if (!frm.doc.calculate_cost) return;

    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.calculate_batch_cost',
        args: { batch_name: frm.doc.name },
        callback: function(r) {
            if (r.message) {
                frm.set_value('total_batch_cost', r.message.total_batch_cost);
                frm.set_value('cost_per_unit', r.message.cost_per_unit);
            }
        }
    });
}

function fetch_work_order_data(frm) {
    // Work order reference functionality for BatchL2
    if (frm.doc.work_order_ref) {
        frappe.call({
            method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.get_work_order_data',
            args: { work_order: frm.doc.work_order_ref },
            callback: function(r) {
                if (r.message) {
                    // Process work order data for batch generation
                    console.log('Work order data loaded:', r.message);
											// FIX: Actually populate batch fields from WO data
						var d = r.message;
						if (d.production_item) frm.set_value('item_to_manufacture', d.production_item);
						if (d.item_name) frm.set_value('wo_item_name', d.item_name);
						if (d.qty) frm.set_value('planned_qty', d.qty);
						if (d.planned_start_date) frm.set_value('wo_start_date', d.planned_start_date);
						if (d.company) frm.set_value('company', d.company);
						if (d.custom_plant_code) frm.set_value('production_plant_name', d.custom_plant_code);
						if (d.sales_order) frm.set_value('sales_order_related', d.sales_order);
						frappe.show_alert({message: __('Work Order data loaded'), indicator: 'green'});
                }
            }
        });
    }
}

// ==================== BOM CREATION ====================

function open_bom_creation_wizard(frm) {
    console.log('🚀 Opening simplified BOM wizard');

    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.get_packaging_from_sales_order',
        args: { batch_name: frm.doc.name },
        callback: function(r) {
            var pkg = r.message || {};

            var dialog = new frappe.ui.Dialog({
                title: __('Create BOM'),
                fields: [
                    {
                        fieldtype: 'HTML',
                        fieldname: 'info',
                        options: '<div style="padding: 10px; background: #f8f9fa; border-radius: 5px; margin-bottom: 15px;">' +
                                '<p><strong>Batch:</strong> ' + frm.doc.name + '</p>' +
                                '<p><strong>Item:</strong> ' + (frm.doc.item_to_manufacture || frm.doc.current_item_code) + '</p>' +
                                '</div>'
                    },
                    {
                        fieldtype: 'Link',
                        fieldname: 'primary_packaging',
                        label: __('Primary Packaging'),
                        options: 'Item',
                        default: pkg.primary || 'E001'
                    },
                    {
                        fieldtype: 'Float',
                        fieldname: 'net_weight',
                        label: __('Net Weight per Package (Kg)'),
                        default: pkg.net_weight || 220
                    }
                ],
                primary_action_label: __('Create BOM'),
                primary_action: function(values) {
                    create_bom_with_options(frm, values, dialog);
                }
            });

            dialog.show();
        }
    });
}

function create_bom_with_options(frm, options, dialog) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.create_bom_with_wizard',
        args: {
            batch_name: frm.doc.name,
            options: options
        },
        freeze: true,
        freeze_message: __('Creating BOM...'),
        callback: function(r) {
            dialog.hide();
            if (r.message) {
                frappe.msgprint({
                    title: __('BOM Created'),
                    message: __('BOM created successfully: ') + r.message.bom_name,
                    indicator: 'green'
                });
                frm.reload_doc();
            }
        }
    });
}

// ==================== INITIALIZATION ====================

// Add some CSS for announcements
function add_announcement_styles() {
    const style = `
        .batch-announcements {
            margin: 10px 0;
        }
        .announcement-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .announcement-item {
            border: 1px solid #d1d8dd;
            border-radius: 4px;
            padding: 10px;
            margin: 5px 0;
            background: #fafbfc;
        }
        .announcement-item:hover {
            background: #f0f4f7;
        }
        .label {
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
        }
        .label-success { background: #5cb85c; color: white; }
        .label-info { background: #5bc0de; color: white; }
        .label-warning { background: #f0ad4e; color: white; }
        .label-danger { background: #d9534f; color: white; }
        .label-default { background: #777; color: white; }
    `;

    if (!$('#batch-amb-styles').length) {
        $('<style id="batch-amb-styles">' + style + '</style>').appendTo('head');
    }
}

// Initialize styles when DOM is ready
$(document).ready(function() {
    add_announcement_styles();
    console.log('✅ Batch AMB Enhanced Script with Serial Tracking loaded');
});

// ==================== FIXED HELPER FUNCTIONS ====================

function process_barcode_scan_fixed(frm, cdt, cdn, barcode) {
    const row = locals[cdt][cdn];
    if (!barcode || !barcode.trim()) return;

    barcode = barcode.trim().toUpperCase();

    // Validate format if not a temp code
    if (!barcode.startsWith('TEMP-') && !validate_code39_format(barcode)) {
        frappe.msgprint({
            title: __('Invalid Barcode'),
            message: __('Invalid CODE-39 format: {0}', [barcode]),
            indicator: 'red'
        });
        row.barcode_scan_input = '';
        frm.refresh_field('container_barrels');
        return;
    }

    // Set the barcode as serial number
    row.barrel_serial_number = barcode;
    row.scan_timestamp = frappe.datetime.now_datetime();
    row.barcode_scan_input = '';

    frm.refresh_field('container_barrels');

    // Fetch tara weight if packaging type exists
    if (row.packaging_type) {
        fetch_tara_weight_for_row_fixed(frm, cdt, cdn);
    }
}

function fetch_tara_weight_for_row_fixed(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.packaging_type) return;

    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Item',
            filters: { name: row.packaging_type },
            fieldname: 'weight_per_unit'
        },
        callback: function(r) {
            if (r.message && r.message.weight_per_unit !== undefined) {
                row.tara_weight = parseFloat(r.message.weight_per_unit) || 0;
                calculate_net_weight_fixed(frm, cdt, cdn);
                update_weight_totals(frm);
                frm.refresh_field('container_barrels');
            }
        }
    });
}

function calculate_net_weight_fixed(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    const gross = parseFloat(row.gross_weight) || 0;
    const tara = parseFloat(row.tara_weight) || 0;
    const net_weight = gross - tara;

    row.net_weight = net_weight;

    // Only validate if gross weight > 0
    if (gross > 0) {
        row.weight_validated = (net_weight > 0 && net_weight < gross) ? 1 : 0;
    } else {
        row.weight_validated = 0;
    }
}

// ==================== BATCH L2 MERGED FUNCTIONS ====================

// Create Sublot Batch (Level 2) from parent
function create_sublot_batch(frm) {
    const parentLevel = cint(frm.doc.custom_batch_level || 1);
    const childLevel = String(parentLevel + 1);

    if (parentLevel >= 4) {
        frappe.msgprint(__('Cannot create a sublot from Level 4 batch.'));
        return;
    }

    frappe.new_doc('Batch AMB', {
        parent_batch_amb: frm.doc.name,
        custom_batch_level: childLevel,
        item_to_manufacture: frm.doc.item_to_manufacture || '',
        work_order_ref: frm.doc.work_order_ref || '',
        company: frm.doc.company || '',
        production_plant: frm.doc.production_plant || '',
        is_group: childLevel === '4' ? 0 : 1
    });
}

function create_container_batch(frm) {
    const parentLevel = cint(frm.doc.custom_batch_level || 1);
    let childLevel = null;

    if (parentLevel === 2) {
        childLevel = '3';
    } else if (parentLevel === 3) {
        childLevel = '4';
    } else {
        frappe.msgprint(__('Create Container is only valid from Level 2 or Level 3.'));
        return;
    }

    frappe.new_doc('Batch AMB', {
        parent_batch_amb: frm.doc.name,
        custom_batch_level: childLevel,
        item_to_manufacture: frm.doc.item_to_manufacture || '',
        work_order_ref: frm.doc.work_order_ref || '',
        company: frm.doc.company || '',
        production_plant: frm.doc.production_plant || '',
        is_group: childLevel === '4' ? 0 : 1
    });
}
// Create Container Batch (Level 3) from parent
function create_container_batch(frm) {
    var parent_level = parseInt(frm.doc.custom_batch_level || '1', 10);
    var child_level = String(parent_level + 1);

    frappe.new_doc('Batch AMB', {
        'custom_batch_level': child_level,
        'parent_batch_amb': frm.doc.name,
        'work_order_ref': frm.doc.work_order_ref,
        'sales_order_related': frm.doc.sales_order_related,
        'item_to_manufacture': frm.doc.item_to_manufacture,
        'production_plant_name': frm.doc.production_plant_name,
        'production_plant': frm.doc.production_plant,
        'original_item_code': frm.doc.original_item_code || frm.doc.item_code,
        'current_item_code': frm.doc.current_item_code || frm.doc.item_code
    });
}

// Add global buttons (View Batch Tree)
function add_global_buttons(frm) {
    if (frm.doc.custom_batch_level && frm.doc.custom_batch_level !== '4') {
        frm.add_custom_button(__('View Batch Tree'), function() {
            show_batch_hierarchy(frm);
        });
    }
}

// Show batch hierarchy (placeholder)
function show_batch_hierarchy(frm) {
    if (frm.doc.parent_batch_amb) {
        frappe.set_route('Tree', 'Batch AMB', {'batch_amb': frm.doc.parent_batch_amb});
    } else {
        frappe.set_route('Tree', 'Batch AMB', {'batch_amb': frm.doc.name});
    }
}

// Open bulk barcode scan dialog
function open_bulk_scan_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Bulk Barcode Scanning'),
        fields: [{
            fieldtype: 'Small Text',
            fieldname: 'barcode_list',
            label: __('Scan Multiple Barcodes (one per line)'),
            reqd: 1
        }],
        primary_action_label: __('Process Barcodes'),
        primary_action: function() {
            const barcodes = dialog.get_value('barcode_list').split('\n').filter(b => b.trim());
            process_bulk_barcodes(frm, barcodes);
            dialog.hide();
        }
    });
    dialog.show();
}

// Process bulk barcodes
function process_bulk_barcodes(frm, barcodes) {
    frappe.msgprint(__('Processing {0} barcodes...', [barcodes.length]));
}

// Generate bulk barrel serials dialog
// Generate barrel serials - enhanced with Packaging Type + tara
function generate_bulk_barrel_serials(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Generate Barrel Serial Numbers'),
        fields: [
            {
                fieldtype: 'Int',
                fieldname: 'barrel_count',
                label: __('Number of Barrels'),
                reqd: 1,
                default: frm.doc.barrel_count || 1
            },
            {
                fieldtype: 'Link',
                fieldname: 'packaging_type',
                label: __('Packaging Type'),
                options: 'Item',
                reqd: 1,
                default: frm.doc.default_packaging_type || 'E001',
                get_query: function() {
                    return {
                        filters: {
                            item_group: ['in', [
                                'FG Packaging Materials',
                                'SFG Packaging Materials',
                                'Sample Packaging Materials',
                                'Consumables',
                            'Raw Materials'
                            ]],
                            disabled: 0
                        }
                    };
                },
                change: function() {
                    const pkg = dialog.get_value('packaging_type');
                    if (pkg) {
                        frappe.db.get_value('Item', pkg, ['item_name', 'weight_per_unit', 'weight_uom'], function(r) {
                            if (r) {
                                const name_lower = (r.item_name || '').toLowerCase();
                                let prefix = 'BRL';

                                if (
                                    name_lower.includes('sample') ||
                                    name_lower.includes('bolsa') ||
                                    name_lower.includes('bag')
                                ) {
                                    prefix = 'SMP';
                                } else if (
                                    name_lower.includes('ibc') ||
                                    name_lower.includes('tote')
                                ) {
                                    prefix = 'IBC';
                                } else if (
                                    name_lower.includes('drum') ||
                                    name_lower.includes('cunete') ||
                                    name_lower.includes('cuete') ||
                                    name_lower.includes('cuñete') ||
                                    name_lower.includes('pail')
                                ) {
                                    prefix = 'CTE';
                                }

                                dialog.set_value('prefix', prefix);
                                dialog.set_value('tara_weight', r.weight_per_unit || 0);
                                dialog.fields_dict.tara_weight.set_description(
                                    __('From Item: {0} ({1} {2})', [
                                        r.item_name,
                                        r.weight_per_unit || 0,
                                        r.weight_uom || 'Kg'
                                    ])
                                );
                            }
                        });
                    }
                }
            },
            {
                fieldtype: 'Data',
                fieldname: 'prefix',
                label: __('Serial Prefix'),
                default: 'BRL',
                description: __('Editable: BRL=Barrel, SMP=Sample, IBC=Tote, CTE=Drum/Pail')
            },
            {
                fieldtype: 'Float',
                fieldname: 'tara_weight',
                label: __('Tara Weight (kg)'),
                default: 0,
                read_only: 1,
                description: __('Auto-filled from Item Weight Per Unit')
            }
        ],
        primary_action_label: __('Generate Serials'),
        primary_action: function() {
            const barrel_count = dialog.get_value('barrel_count');
            const prefix = dialog.get_value('prefix');
            const packaging_type = dialog.get_value('packaging_type');
            const tara_weight = dialog.get_value('tara_weight');

            if (!barrel_count || !packaging_type || !prefix) {
                frappe.msgprint(__('Please complete all required fields'));
                return;
            }

            if (typeof generate_serials_l2 !== 'function') {
                frappe.msgprint(__('generate_serials_l2 is not available in this page script'));
                console.error('generate_serials_l2 is not defined');
                return;
            }

            console.log('Generating serials with:', {
                barrel_count,
                prefix,
                packaging_type,
                tara_weight
            });

            frm.save().then(() => {
                dialog.hide();
                generate_serials_l2(frm, barrel_count, prefix, packaging_type, tara_weight);
            });
            
        }
    });

    dialog.show();

    // Trigger packaging change to load defaults
    if (dialog.get_value('packaging_type')) {
        dialog.fields_dict.packaging_type.set_value(dialog.get_value('packaging_type'));
    }
}

// Generate barrel serials - calls backend API
function generate_serials_l2(frm, count, prefix, packaging_type, tara_weight) {
    if (count <= 0) {
        frappe.msgprint(__('Number of barrels must be greater than 0'));
        return;
    }
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.generate_serial_numbers',
        args: {
            batch_name: frm.doc.name,
            quantity: count,
            prefix: prefix,
            packaging_type: packaging_type,
            tara_weight: tara_weight
        },
        freeze: true,
        freeze_message: __('Generating Barrel Serials...'),
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                frappe.show_alert({
                    message: __('Successfully generated ') + r.message.count + __(' barrel serial numbers.'),
                    indicator: 'green'
                }, 5);

                frm.reload_doc().then(() => {
                    frm.doc.__unsaved = 0;
                    frm.dirty = false;
                    if (frm.page && frm.page.clear_indicator) frm.page.clear_indicator();
                    frm.refresh();
                });
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message ? r.message.message : __('Failed to generate barrel serials'),
                    indicator: 'red'
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Error'),
                message: __('Failed to generate barrel serial numbers: ') + (r.message || r),
                indicator: 'red'
            });
        }
    });
}
