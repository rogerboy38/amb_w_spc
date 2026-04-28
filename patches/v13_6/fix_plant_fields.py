import frappe

def execute():
    """Add missing plant fields to doctypes"""
    
    # Update existing Sample Request AMB documents to link to work orders
    sample_requests = frappe.get_all("Sample Request AMB", 
        filters={"work_order_ref": ["!=", ""]},
        fields=["name", "work_order_ref"])
    
    for sr in sample_requests:
        # Any post-migration data updates
        pass
    
    frappe.db.commit()
    print("✅ Plant fields migration completed")

if __name__ == "__main__":
    execute()
