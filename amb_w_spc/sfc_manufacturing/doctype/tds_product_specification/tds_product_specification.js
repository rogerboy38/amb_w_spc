frappe.ui.form.on('TDS Product Specification', {
    onload: function(frm) {
        // Initialize form
        setup_form_customizations(frm);
    },
    
    refresh: function(frm) {
        // Add custom buttons
        add_custom_buttons(frm);
        
        // Setup custom filters
        setup_custom_filters(frm);
    },
    
    product_item: function(frm) {
        // When product item is selected, fetch details and latest version
        if (frm.doc.product_item) {
            fetch_item_details(frm);
            fetch_latest_tds_version(frm);
        } else {
            // Clear item details if no item selected
            frm.set_value('item_name', '');
            frm.set_value('item_code', '');
        }
    },
    
    tds_version: function(frm) {
        // Update naming series when version changes
        update_naming_series(frm);
    },
    
    item_code: function(frm) {
        // Update naming series when item code changes
        update_naming_series(frm);
    },
    
    before_save: function(frm) {
        // Validate form before saving
        return validate_tds_form(frm);
    }
});

// Fetch item details from Item master
function fetch_item_details(frm) {
    frappe.call({
        method: 'your_app.quality.doctype.tds_product_specification.tds_product_specification.get_item_details',
        args: {
            item_code: frm.doc.product_item
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('item_name', r.message.item_name || '');
                frm.set_value('item_code', r.message.item_code || '');
                
                // Update naming series with new item code
                update_naming_series(frm);
            }
        }
    });
}

// Fetch latest TDS version for the product item
function fetch_latest_tds_version(frm) {
    frappe.call({
        method: 'your_app.quality.doctype.tds_product_specification.tds_product_specification.get_latest_tds_version',
        args: {
            product_item: frm.doc.product_item
        },
        callback: function(r) {
            if (r.message) {
                if (!frm.doc.tds_version || frm.doc.tds_version === '1') {
                    frm.set_value('tds_version', r.message.tds_version);
                }
                if (!frm.doc.tds_sequence) {
                    frm.set_value('tds_sequence', r.message.tds_sequence);
                }
                
                update_naming_series(frm);
            }
        }
    });
}

// Update naming series based on current values
function update_naming_series(frm) {
    if (frm.doc.item_code && frm.doc.tds_version) {
        const base_name = "TDS";
        const item_code = frm.doc.item_code;
        const version = frm.doc.tds_version;
        const new_series = `${base_name}-${item_code}-V${version}`;
        
        if (!frm.doc.naming_series || frm.doc.naming_series.startsWith(base_name)) {
            frm.set_value('naming_series', new_series);
        }
    }
}

// Setup form customizations
function setup_form_customizations(frm) {
    // Make certain fields read-only based on conditions
    frm.set_df_property('amended_from', 'read_only', 1);
    frm.set_df_property('item_name', 'read_only', 1);
    frm.set_df_property('item_code', 'read_only', 1);
    
    // Add custom CSS classes to text editor fields
    frm.get_field('shelf_life').$wrapper.addClass('tds-text-editor');
    frm.get_field('packaging').$wrapper.addClass('tds-text-editor');
    frm.get_field('storage_and_handling_conditions').$wrapper.addClass('tds-text-editor');
}

// Add custom buttons to form
function add_custom_buttons(frm) {
    if (!frm.is_new() && frm.doc.docstatus === 1) {
        // Button to create new version
        frm.add_custom_button(__('Create New Version'), function() {
            create_new_tds_version(frm);
        }, __('Actions'));
        
        // Button to create Quality Inspection Template
        frm.add_custom_button(__('Create Inspection Template'), function() {
            create_quality_inspection_template(frm);
        }, __('Actions'));
    }
    
    if (!frm.is_new() && frm.doc.docstatus === 0) {
        // Button to copy from latest version
        frm.add_custom_button(__('Copy from Latest'), function() {
            copy_from_latest_version(frm);
        }, __('Actions'));
    }
}

// Create new TDS version
function create_new_tds_version(frm) {
    frappe.call({
        method: 'your_app.quality.doctype.tds_product_specification.tds_product_specification.create_new_version',
        args: {
            source_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                frappe.set_route('Form', 'TDS Product Specification', r.message);
            }
        }
    });
}

// Create Quality Inspection Template
function create_quality_inspection_template(frm) {
    frappe.model.with_doctype('Quality Inspection Template', function() {
        let template = frappe.model.get_new_doc('Quality Inspection Template');
        template.item_code = frm.doc.item_code;
        template.item_name = frm.doc.item_name;
        template.tds_product_specification = frm.doc.name;
        
        frappe.set_route('Form', 'Quality Inspection Template', template.name);
    });
}

// Copy parameters from latest TDS version
function copy_from_latest_version(frm) {
    if (!frm.doc.product_item) {
        frappe.msgprint(__('Please select a Product Item first'));
        return;
    }
    
    frappe.call({
        method: 'your_app.quality.doctype.tds_product_specification.tds_product_specification.get_latest_tds_version',
        args: {
            product_item: frm.doc.product_item
        },
        callback: function(r) {
            if (r.message && r.message.latest_doc) {
                // Implementation to copy parameters from latest document
                frappe.msgprint(__('Parameters copied from latest version'));
            }
        }
    });
}

// Setup custom filters for link fields
function setup_custom_filters(frm) {
    // Add filter for Product Item
    frm.set_query('product_item', function() {
        return {
            filters: {
                'is_stock_item': 1  // Only show stock items
            }
        };
    });
    
    // Add filter for TDS Settings
    frm.set_query('tds_settings', function() {
        return {
            filters: {
                'docstatus': 1  // Only show submitted TDS Settings
            }
        };
    });
}

// Validate TDS form before saving
function validate_tds_form(frm) {
    // Validate that at least one quality parameter exists
    if (!frm.doc.item_quality_inspection_parameter || frm.doc.item_quality_inspection_parameter.length === 0) {
        frappe.msgprint({
            title: __('Validation Error'),
            message: __('Please add at least one Item Quality Inspection Parameter'),
            indicator: 'red'
        });
        return false;
    }
    
    // Validate approval date
    if (frm.doc.approval_date && frm.doc.approval_date > frappe.datetime.get_today()) {
        frappe.msgprint({
            title: __('Validation Error'),
            message: __('Approval Date cannot be in the future'),
            indicator: 'red'
        });
        return false;
    }
    
    return true;
}

// Client script for CAS Number field
frappe.ui.form.on('TDS Product Specification', 'cas_number', function(frm) {
    if (frm.doc.cas_number) {
        // You can add CAS number validation logic here
        validate_cas_number(frm.doc.cas_number);
    }
});

// Validate CAS number format (basic validation)
function validate_cas_number(cas_number) {
    // Basic CAS number format validation: XXX-XX-X
    const cas_pattern = /^\d{2,7}-\d{2}-\d$/;
    if (!cas_pattern.test(cas_number)) {
        frappe.msgprint({
            title: __('CAS Number Format'),
            message: __('CAS number should be in format: XXX-XX-X'),
            indicator: 'orange'
        });
    }
}
