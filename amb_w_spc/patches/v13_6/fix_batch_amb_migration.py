import frappe

def execute():
    """Fix Batch AMB migration issues"""
    
    # 1. Update workflow states
    frappe.db.sql("""
        UPDATE `tabWorkflow State` 
        SET docstatus = 1 
        WHERE name IN ('Approved', 'Frozen', 'Certificate Shared', 'Auto Approved')
        AND parent = 'TDS Approval Workflow'
    """)
    print("✅ Updated workflow states")
    
    # 2. Update client scripts
    client_scripts = [
        "Sales Order - Sample Request Button",
        "Opportunity - Sample Request Button",
        "Prospect - Sample Request Button",
        "Quotation - Sample Request Button",
        "Lead - Sample Request Button",
        "Batch L2"
    ]
    
    for cs_name in client_scripts:
        if frappe.db.exists("Client Script", cs_name):
            cs = frappe.get_doc("Client Script", cs_name)
            if "amb_w_tds.amb_w_tds.doctype.batch_amb" in cs.script:
                cs.script = cs.script.replace(
                    "amb_w_tds.amb_w_tds.doctype.batch_amb.batch_amb",
                    "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb"
                )
                cs.save()
                print(f"✅ Updated {cs_name}")
    
    frappe.db.commit()
    print("✅ Batch AMB migration patch completed")

if __name__ == "__main__":
    execute()
