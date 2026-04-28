frappe.ui.form.on("Container Barrels", {
    gross_weight: function(frm, cdt, cdn) {
        calculate_and_update(frm, cdt, cdn);
    },
    tara_weight: function(frm, cdt, cdn) {
        calculate_and_update(frm, cdt, cdn);
    }
});

function calculate_and_update(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    
    // Calculate net weight
    let net_weight = (row.gross_weight || 0) - (row.tara_weight || 0);
    
    // Ensure not negative
    if (net_weight < 0) {
        net_weight = 0;
        frappe.show_alert({
            message: __('Net weight cannot be negative. Check gross and tara values.'),
            indicator: 'orange'
        });
    }
    
    // Use frappe.model.set_value for proper reactivity
    frappe.model.set_value(cdt, cdn, 'net_weight', net_weight);
    
    // Trigger parent form update
    if (typeof update_weight_totals === "function") update_weight_totals(frm);
}
