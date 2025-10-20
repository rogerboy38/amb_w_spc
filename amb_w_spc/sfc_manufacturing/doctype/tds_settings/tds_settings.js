// TDS Settings Client Script
frappe.ui.form.on('TDS Settings', {
    onload: function(frm) {
        // Initialize form
        setup_tds_settings_form(frm);
    },
    
    refresh: function(frm) {
        // Add custom buttons
        setup_tds_settings_buttons(frm);
        
        // Load current settings info
        load_settings_info(frm);
    },
    
    naming_series: function(frm) {
        // Auto-update sequence if naming series changes
        update_sequence_from_naming_series(frm);
    },
    
    prefix: function(frm) {
        // Update naming series when prefix changes
        update_naming_series_from_prefix(frm);
    },
    
    auto_increment_sequence: function(frm) {
        // Show/hide sequence controls based on auto-increment setting
        toggle_sequence_controls(frm);
    }
});

// Form Setup
function setup_tds_settings_form(frm) {
    console.log('Setting up TDS Settings form');
    
    // Ensure this is a single doctype
    if (frm.is_new()) {
        frm.set_value('prefix', 'TDS-SET');
        frm.set_value('auto_increment_sequence', 1);
        frm.set_value('strict_validation', 1);
        frm.set_value('enable_version_history', 1);
    }
}

// Button Setup
function setup_tds_settings_buttons(frm) {
    // Clear existing buttons
    frm.page.clear_icons();
    frm.page.clear_actions();
    
    // Add utility buttons
    frm.add_custom_button(__('🔄 Generate Next Series'), function() {
        generate_next_naming_series(frm);
    });
    
    frm.add_custom_button(__('➕ Increment Sequence'), function() {
        increment_sequence_manual(frm);
    });
    
    frm.add_custom_button(__('📤 Apply to All TDS'), function() {
        apply_settings_to_all_tds(frm);
    });
    
    frm.add_custom_button(__('ℹ️ Settings Info'), function() {
        show_settings_info(frm);
    });
}

// Load Settings Information
function load_settings_info(frm) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.tds_settings.tds_settings.get_tds_settings',
        callback: function(r) {
            if (r.message && r.message.success) {
                console.log('TDS Settings loaded:', r.message.settings);
                update_settings_display(frm, r.message.version_info);
            }
        }
    });
}

// Update Settings Display
function update_settings_display(frm, version_info) {
    if (version_info) {
        var info_html = `
            <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                <h5>📊 Version Control Info</h5>
                <p><strong>Current Sequence:</strong> ${version_info.current_sequence}</p>
                <p><strong>Next Version:</strong> ${version_info.next_version}</p>
                <p><strong>Naming Series:</strong> ${version_info.naming_series}</p>
            </div>
        `;
        
        // Display in form or console
        console.log('Version Control Info:', version_info);
    }
}

// Generate Next Naming Series
function generate_next_naming_series(frm) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.tds_settings.tds_settings.generate_next_naming_series',
        callback: function(r) {
            if (r.message && r.message.success) {
                frm.set_value('naming_series', r.message.naming_series);
                frm.set_value('last_sequence_used', r.message.next_sequence - 1);
                
                frappe.show_alert({
                    message: __('Generated next naming series: {0}', [r.message.naming_series]),
                    indicator: 'green'
                });
            } else {
                frappe.msgprint({
                    title: __('Generation Failed'),
                    message: __('Could not generate naming series'),
                    indicator: 'red'
                });
            }
        }
    });
}

// Manual Sequence Increment
function increment_sequence_manual(frm) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.tds_settings.tds_settings.increment_sequence',
        callback: function(r) {
            if (r.message && r.message.success) {
                frm.set_value('last_sequence_used', r.message.new_sequence);
                frm.refresh_field('last_sequence_used');
                
                frappe.show_alert({
                    message: __('Sequence incremented to: {0}', [r.message.new_sequence]),
                    indicator: 'green'
                });
            }
        }
    });
}

// Apply Settings to All TDS
function apply_settings_to_all_tds(frm) {
    frappe.confirm(
        __('Are you sure you want to apply these settings to all TDS Product Specification documents?'),
        function() {
            frappe.call({
                method: 'amb_w_spc.sfc_manufacturing.doctype.tds_settings.tds_settings.apply_settings_to_all_tds',
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('Settings applied to {0} TDS documents', [r.message.updated_count]),
                            indicator: 'green'
                        });
                    } else {
                        frappe.msgprint({
                            title: __('Application Failed'),
                            message: __('Could not apply settings to TDS documents'),
                            indicator: 'red'
                        });
                    }
                }
            });
        }
    );
}

// Show Settings Information
function show_settings_info(frm) {
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.tds_settings.tds_settings.get_tds_settings',
        callback: function(r) {
            if (r.message && r.message.success) {
                var settings = r.message.settings;
                var version_info = r.message.version_info;
                
                var message = `
                    <div style="margin: 10px 0;">
                        <h4>📋 TDS Settings Information</h4>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                            <div>
                                <h5>Version Control</h5>
                                <p><strong>Current Sequence:</strong> ${version_info.current_sequence}</p>
                                <p><strong>Next Version:</strong> ${version_info.next_version}</p>
                                <p><strong>Prefix:</strong> ${version_info.prefix}</p>
                                <p><strong>Naming Series:</strong> ${version_info.naming_series}</p>
                            </div>
                            <div>
                                <h5>Settings</h5>
                                <p><strong>Auto Increment:</strong> ${settings.auto_increment_sequence ? 'Yes' : 'No'}</p>
                                <p><strong>Strict Validation:</strong> ${settings.strict_validation ? 'Yes' : 'No'}</p>
                                <p><strong>Version History:</strong> ${settings.enable_version_history ? 'Enabled' : 'Disabled'}</p>
                                <p><strong>Require Approval:</strong> ${settings.require_approval ? 'Yes' : 'No'}</p>
                            </div>
                        </div>
                    </div>
                `;
                
                frappe.msgprint({
                    title: __('TDS Settings Info'),
                    message: message,
                    indicator: 'blue'
                });
            }
        }
    });
}

// Update Sequence from Naming Series
function update_sequence_from_naming_series(frm) {
    var naming_series = frm.doc.naming_series;
    if (naming_series && frm.doc.auto_increment_sequence) {
        // Extract sequence number from naming series
        var numbers = naming_series.match(/\d+/g);
        if (numbers && numbers.length > 0) {
            var sequence = parseInt(numbers[numbers.length - 1]);
            if (!isNaN(sequence) && sequence > frm.doc.last_sequence_used) {
                frm.set_value('last_sequence_used', sequence);
            }
        }
    }
}

// Update Naming Series from Prefix
function update_naming_series_from_prefix(frm) {
    if (frm.doc.prefix && !frm.doc.naming_series) {
        var year = new Date().getFullYear();
        var sequence = (frm.doc.last_sequence_used || 0) + 1;
        var padded_sequence = sequence.toString().padStart(5, '0');
        
        var new_naming_series = `${frm.doc.prefix}-${year}-${padded_sequence}`;
        frm.set_value('naming_series', new_naming_series);
    }
}

// Toggle Sequence Controls
function toggle_sequence_controls(frm) {
    // You can add logic to show/hide manual sequence controls
    // based on auto_increment_sequence setting
    console.log('Auto increment:', frm.doc.auto_increment_sequence);
}

console.log('TDS Settings Client Script loaded successfully');
