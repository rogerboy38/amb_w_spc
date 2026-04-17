// =============================================================================
// Sample Request Utilities for amb_w_spc
// Shared utilities for creating Sample Request buttons across multiple doctypes
// Version: 2026-04-17 - Migrated from amb_w_tds
// =============================================================================

window.SampleRequestUtils = {
    /**
     * Check if user has permission to create sample requests
     */
    hasPermission: function() {
        var allowed_roles = ["System Manager", "RND Manager", "Manufacturing Manager"];
        var user_roles = frappe.user_roles || [];
        return allowed_roles.some(function(role) {
            return user_roles.indexOf(role) !== -1;
        });
    },

    /**
     * Create a sample request from any doctype
     * @param {string} doctype - Source doctype (Lead, Prospect, Opportunity, Quotation, Sales Order)
     * @param {string} docname - Document name
     */
    createSampleRequest: function(doctype, docname) {
        if (!this.hasPermission()) {
            frappe.msgprint({
                title: __("Permission Denied"),
                message: __("You don't have permission to create sample requests."),
                indicator: "red"
            });
            return;
        }

        frappe.call({
            method: "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.make_sample_request_from_source",
            args: {
                source_doctype: doctype,
                source_name: docname
            },
            freeze: true,
            freeze_message: __("Creating Sample Request..."),
            callback: function(r) {
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

    /**
     * Add the Sample Request button to a form
     * @param {object} frm - Form object
     * @param {string} doctype - Doctype name
     */
    addButtonToForm: function(frm, doctype) {
        if (frm.is_new()) return;
        if (!this.hasPermission()) return;

        frm.add_custom_button(
            __("Sample Request"),
            function() {
                window.SampleRequestUtils.createSampleRequest(doctype, frm.doc.name);
            },
            __("Create")
        );
    }
};

console.log("✅ SampleRequestUtils loaded (amb_w_spc)");
