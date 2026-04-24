"""
V13.6.0 P3 Migration: batch_announcements_for_navbar_widget
Original Server Script: batch_announcements_for_navbar_widget
Type: Whitelisted API
"""

import frappe

import frappe

@frappe.whitelist()
def get_running_batch_announcements():
    """Get running batch announcements for navbar widget"""
    try:
        # Check if Batch AMB doctype exists
        if not frappe.db.exists("DocType", "Batch AMB"):
            return {"success": False, "message": "Batch AMB doctype not found"}

        # Get running batches
        running_batches = frappe.get_all("Batch AMB", 
            filters={"quality_status": "Running"}, 
            fields=["name", "title", "batch_id", "production_status", "priority", "start_time"]
        )

        announcements = []
        for batch in running_batches:
            announcements.append({
                "title": batch.title or batch.name,
                "content": f"🔧 Batch: {batch.batch_id or 'N/A'}\n⏱ Status: {batch.production_status or 'Running'}\n🕐 Started: {batch.start_time or 'N/A'}",
                "priority": batch.priority or "medium"
            })

        return {
            "success": True,
            "announcements": announcements,
            "count": len(announcements)
        }

    except Exception as e:
        frappe.log_error("Batch Announcements Error", str(e))
        return {"success": False, "message": str(e)}
