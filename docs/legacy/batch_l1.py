"""
Archived Server Script: Batch L1

V13.6.0 P3 Server Script Migration
Decision: DEL / archived
Script Type: DocType Event
Reference DocType: Batch AMB
Disabled: 1

Runtime status:
  DO NOT IMPORT. Archive only.
"""

ORIGINAL_SCRIPT = """
# Run this once in Console (Developer Tools)
if not frappe.db.exists("Server Script", "batch_naming_amb"):
    frappe.get_doc({
        "doctype": "Server Script",
        "name": "batch_naming_amb",
        "script_type": "DocType Event",
        "doctype_event": "Before Save",
        "reference_doctype": "Batch AMB",
        "script": """
if not doc.name:
    year = frappe.utils.getdate().strftime("%y")
    
    # Get last batch for current year
    last_batch = frappe.get_all("Batch AMB",
        filters={"creation": (">=", f"{year}-01-01")},
        fields=["name"],
        order_by="creation DESC",
        limit=1
    )
    
    # Calculate next consecutive number
    if last_batch and last_batch[0].name.startswith(f"AMB-{year}-"):
        last_num = int(last_batch[0].name.split("-")[-1])
        consecutive = last_num + 1
    else:
        consecutive = 1
    
    # Format: AMB-YY-001
    doc.name = f"AMB-{year}-{str(consecutive).zfill(3)}"
    doc.consecutive_number = consecutive
"""
    }).insert()
#import frappe

#@frappe.whitelist()
def get_running_batch_announcements():
    """Get running batch announcements for navbar widget"""
    try:
        # Check if Batch AMB doctype exists
        if not frappe.db.exists("DocType", "Batch AMB"):
            return {"success": False, "message": "Batch AMB doctype not found"}
        
        # Get running batches
        running_batches = frappe.get_all("Batch AMB",
            filters={"status": "Running"},
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
"""
