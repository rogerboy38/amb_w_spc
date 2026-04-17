// =============================================================================
// Sample Request Buttons for amb_w_spc
// Contains both utilities and button logic
// Version: 2026-04-17 - Migrated from amb_w_tds
// =============================================================================

// =============================================================================
// PART 1: SampleRequestUtils (Utilities) - Embedded directly
// =============================================================================
window.SampleRequestUtils = {
    hasPermission: function() {
        // Allow anyone with create permission on Sample Request AMB
        return frappe.model.can_create("Sample Request AMB");
    },

    createSampleRequest: function(doctype, docname) {
        if (!this.hasPermission()) {
            frappe.msgprint({
                title: __("Permission Denied"),
                message: __("You don't have permission to create sample requests."),
                indicator: "red"
            });
            return;
        }

        console.log("Creating Sample Request from:", doctype, docname);

        frappe.call({
            method: "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.make_sample_request_from_source",
            args: {
                source_doctype: doctype,
                source_name: docname
            },
            freeze: true,
            freeze_message: __("Creating Sample Request..."),
            callback: function(r) {
                console.log("Sample Request creation response:", r);
                if (!r.exc && r.message) {
                    frappe.set_route("Form", "Sample Request AMB", r.message);
                    frappe.show_alert({
                        message: __("Sample Request created successfully"),
                        indicator: "green"
                    });
                }
            }
        });
    },

    addButtonToForm: function(frm, doctype) {
        if (frm.is_new()) return;

        // Check if button already exists to avoid duplicates
        var button_exists = false;
        if (frm.custom_buttons && frm.custom_buttons["Sample Request"]) {
            button_exists = true;
        }

        if (!button_exists) {
            frm.add_custom_button(
                __("Sample Request"),
                function() {
                    window.SampleRequestUtils.createSampleRequest(doctype, frm.doc.name);
                },
                __("Create")
            );
            console.log("✅ Sample Request button added to", doctype);
        }
    }
};

// ===========================================================================
// PART 2: Button Registration
// ===========================================================================
var TARGET_DOCTYPES = ["Lead", "Prospect", "Opportunity", "Quotation", "Sales Order"];

TARGET_DOCTYPES.forEach(function(doctype) {
    frappe.ui.form.on(doctype, {
        refresh: function(frm) {
            window.SampleRequestUtils.addButtonToForm(frm, doctype);
        }
    });
});

console.log("✅ Sample Request buttons registered for:", TARGET_DOCTYPES.join(", "), "(amb_w_spc)");
