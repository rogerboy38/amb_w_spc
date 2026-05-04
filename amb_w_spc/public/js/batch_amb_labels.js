frappe.ui.form.on("Batch AMB", {
    refresh(frm) {
        if (frm.is_new()) return;

        // Defer button additions until after other refresh handlers
        // (notably the database-stored 'Batch L2' Client Script which
        // calls frm.page.clear_actions()) have completed their button
        // teardown / re-add cycle. Two-tier retry handles late paints.
        const addButtons = () => {
            // Idempotency guard: don't add the same button twice if both
            // the 0ms and 250ms timer fire and the form hasn't been cleared
            // between them.
            if (frm.custom_buttons && frm.custom_buttons[__("Generate Label Cells / Generar Etiquetas")]) {
                return;
            }
            frm.add_custom_button(
                __("Generate Label Cells / Generar Etiquetas"),
                () => generate_label_cells(frm),
                __("Actions"),
            );
            frm.add_custom_button(
                __("Print Recommended Format / Imprimir Formato Recomendado"),
                () => suggest_and_print(frm),
                __("Actions"),
            );
        };

        setTimeout(addButtons, 0);
        setTimeout(addButtons, 250);
    },
});

function generate_label_cells(frm) {
    if (!frm.doc.container_barrels || frm.doc.container_barrels.length === 0) {
        frappe.msgprint({
            title: __("No Container Barrels"),
            message: __("Add at least one container barrel before generating labels."),
            indicator: "orange",
        });
        return;
    }

    const proceed = () => {
        frappe.call({
            method: "amb_w_spc.sfc_manufacturing.api.generate_label_cells_for_batch",
            args: { batch_name: frm.doc.name },
            freeze: true,
            freeze_message: __("Filling label fields..."),
            callback: (r) => {
                if (!r.message) return;
                frm.reload_doc();
                frappe.show_alert({
                    message: __("Updated {0} label fields ({1} preserved)", [
                        r.message.updated,
                        r.message.skipped_existing,
                    ]),
                    indicator: r.message.no_item ? "orange" : "green",
                });
                if (r.message.warning) {
                    frappe.msgprint({
                        title: __("Note"),
                        message: r.message.warning,
                        indicator: "orange",
                    });
                }
            },
        });
    };

    const has_existing = (frm.doc.container_barrels || []).some(
        (r) => r.label_item_name || r.label_lot || r.label_sample_tag
    );

    if (has_existing) {
        frappe.confirm(
            __("Some barrels already have label data. Existing values will be PRESERVED; only empty fields will be filled. Continue?"),
            proceed,
        );
    } else {
        proceed();
    }
}

function suggest_and_print(frm) {
    frappe.call({
        method: "amb_w_spc.sfc_manufacturing.api.get_print_format_for_batch",
        args: { batch_name: frm.doc.name },
        callback: (r) => {
            if (!r.message) return;
            const fmt = r.message.format_name;
            if (r.message.warning) {
                frappe.msgprint({
                    title: __("Print Format"),
                    message: r.message.warning,
                    indicator: "orange",
                });
                return;
            }
            if (!fmt || fmt === "mixed") return;

            const w = window.open(
                `/printview?doctype=${encodeURIComponent(frm.doctype)}` +
                    `&name=${encodeURIComponent(frm.doc.name)}` +
                    `&format=${encodeURIComponent(fmt)}` +
                    `&no_letterhead=0`,
                "_blank",
            );
            if (!w) {
                frappe.msgprint(__("Pop-ups blocked. Allow pop-ups and try again."));
            }
        },
    });
}
