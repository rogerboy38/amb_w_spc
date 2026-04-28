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
    
    // Update net_weight and chain visual refresh + parent totals
    frappe.model.set_value(cdt, cdn, 'net_weight', net_weight).then(() => {
        // Force the grid row to repaint so net_weight cell updates visually
        // without waiting for save (set_value alone does not always repaint
        // a sibling cell while another cell in the same row is being edited).
        if (frm.fields_dict.container_barrels && frm.fields_dict.container_barrels.grid) {
            frm.fields_dict.container_barrels.grid.refresh_row(cdn);
        }
        // Recompute parent totals against the now-committed net_weight.
        frm.trigger('update_weight_totals');
    });
}
