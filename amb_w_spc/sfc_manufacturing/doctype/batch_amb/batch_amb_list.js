frappe.listview_settings['Batch AMB'] = {
    add_fields: ["quality_status", "production_date", "item_code"],
    get_indicator: function(doc) {
        // Color code based on quality status
        var status_color = {
            "Pending": "orange",
            "Approved": "green", 
            "Rejected": "red",
            "Quarantine": "yellow"
        };
        
        if (status_color[doc.quality_status]) {
            return [__(doc.quality_status), status_color[doc.quality_status], "quality_status,=," + doc.quality_status];
        }
    },
    
    onload: function(listview) {
        // Add custom button to create multiple batches
        listview.page.add_menu_item(__('Create Multiple Batches'), function() {
            frappe.prompt([
                {
                    fieldname: 'count',
                    fieldtype: 'Int',
                    label: __('Number of Batches'),
                    default: 5,
                    reqd: 1
                },
                {
                    fieldname: 'item_code',
                    fieldtype: 'Link',
                    label: __('Item Code'),
                    options: 'Item',
                    reqd: 1
                }
            ], function(values) {
                frappe.call({
                    method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.create_multiple_batches',
                    args: {
                        count: values.count,
                        item_code: values.item_code
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint(__('Created {0} batches', [r.message]));
                            listview.refresh();
                        }
                    }
                });
            }, __('Create Multiple Batches'), __('Create'));
        });
        
        // Add filter for recent batches
        listview.page.add_menu_item(__('Batches Created Today'), function() {
            listview.filter_area.add([[doc.doctype, 'production_date', '=', frappe.datetime.get_today()]]);
        });
    },
    
    button: {
        // Custom button to approve selected batches
        approve_batches: function() {
            let selected_batches = listview.get_checked_items();
            if (selected_batches.length === 0) {
                frappe.msgprint(__('Please select batches to approve'));
                return;
            }
            
            frappe.confirm(
                __('Are you sure you want to approve {0} batches?', [selected_batches.length]),
                function() {
                    frappe.call({
                        method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.bulk_approve_batches',
                        args: {
                            batches: selected_batches.map(b => b.name)
                        },
                        callback: function(r) {
                            frappe.msgprint(__('Approved {0} batches', [r.message]));
                            listview.refresh();
                        }
                    });
                }
            );
        }
    }
};

// Add the custom button to toolbar
frappe.listview_settings['Batch AMB'].button = {
    approve_batches: {
        label: __('Approve Selected'),
        condition: function() {
            return true; // Show always for now
        },
        action: function() {
            frappe.listview_settings['Batch AMB'].button.approve_batches();
        }
    }
};
