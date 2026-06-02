// Customer Acceptable Value — client-side helpers
// Refresh value_text/value_min/value_max visibility per value_type
frappe.ui.form.on("Customer Acceptable Value", {
    refresh(frm) {
        frm.toggle_display(["value_text"],
            frm.doc.value_type === "Choice" || frm.doc.value_type === "Both");
        frm.toggle_display(["value_min", "value_max"],
            frm.doc.value_type === "Numeric Range" || frm.doc.value_type === "Both");
        frm.toggle_display(["unit_of_measurement"],
            frm.doc.value_type !== "Choice");
    },
    value_type(frm) {
        frm.trigger("refresh");
    },
});
