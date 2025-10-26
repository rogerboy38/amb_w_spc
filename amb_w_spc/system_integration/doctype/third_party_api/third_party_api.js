frappe.ui.form.on('Third Party API', {
    refresh: function(frm) {
        // Custom functionality for Third Party API
        frm.dashboard.add_indicator(__('Enhanced with SPC'), 'green');
        
        // SPC integration features
        if(frm.doc.spc_enabled || frm.doc.spc_data_sync) {
            frm.dashboard.add_indicator(__('SPC Integration: ACTIVE'), 'blue');
        }
    },
    
    onload: function(frm) {
        // Initialization code
    }
});
