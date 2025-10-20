// Copyright (c) 2024, MiniMax Agent and contributors
// For license information, please see license.txt

frappe.ui.form.on('mrp_planning_material', {
    refresh(frm) {
        // Add any custom client-side logic here
    },
    
    material_item(frm) {
        // Auto-fetch item name when item is selected
        if (frm.doc.material_item) {
            frappe.db.get_value('Item', frm.doc.material_item, 'item_name')
                .then(r => {
                    if (r.message) {
                        frm.set_value('material_item_name', r.message.item_name);
                    }
                });
        }
    },
    
    required_qty(frm) {
        // Calculate shortage when required quantity changes
        calculate_shortage(frm);
    },
    
    available_qty(frm) {
        // Calculate shortage when available quantity changes
        calculate_shortage(frm);
    }
});

function calculate_shortage(frm) {
    const required = frm.doc.required_qty || 0;
    const available = frm.doc.available_qty || 0;
    const shortage = Math.max(0, required - available);
    frm.set_value('shortage_qty', shortage);
}
