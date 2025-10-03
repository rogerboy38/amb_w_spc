# batch_integration_api.py
import frappe
from frappe import _

@frappe.whitelist()
def get_batch_hierarchy_tree(batch_name=None):
    """Get complete batch hierarchy tree"""
    if batch_name:
        # Get specific batch hierarchy
        return get_specific_batch_hierarchy(batch_name)
    else:
        # Get all level 1 batches with their hierarchies
        return get_all_batch_hierarchies()

def get_specific_batch_hierarchy(batch_name):
    """Get hierarchy for a specific batch"""
    batch = frappe.get_doc("Batch AMB", batch_name)
    
    hierarchy = {
        'current': get_batch_info(batch),
        'parents': get_parent_hierarchy(batch),
        'children': get_child_hierarchy(batch)
    }
    
    return hierarchy

def get_all_batch_hierarchies():
    """Get all batch hierarchies organized by plant"""
    level1_batches = frappe.get_all("Batch AMB", 
        filters={"custom_batch_level": "1"},
        fields=["name", "production_plant_name", "item_to_manufacture", "workflow_state"]
    )
    
    hierarchies = {}
    for batch in level1_batches:
        plant = batch.production_plant_name or "Unknown Plant"
        if plant not in hierarchies:
            hierarchies[plant] = []
        
        hierarchy = get_specific_batch_hierarchy(batch.name)
        hierarchies[plant].append(hierarchy)
    
    return hierarchies

def get_batch_info(batch):
    """Get batch information for hierarchy"""
    return {
        'name': batch.name,
        'level': batch.custom_batch_level,
        'workflow_state': batch.workflow_state,
        'item': batch.item_to_manufacture,
        'plant': batch.production_plant_name,
        'quantity': batch.batch_qty,
        'net_weight': batch.total_net_weight
    }

def get_parent_hierarchy(batch):
    """Get parent hierarchy"""
    parents = []
    current_parent = batch.parent_batch_amb
    
    while current_parent:
        parent = frappe.get_doc("Batch AMB", current_parent)
        parents.append(get_batch_info(parent))
        current_parent = parent.parent_batch_amb
    
    return parents

def get_child_hierarchy(batch):
    """Get child hierarchy recursively"""
    children = frappe.get_all("Batch AMB",
        filters={"parent_batch_amb": batch.name},
        fields=["name"]
    )
    
    child_data = []
    for child in children:
        child_doc = frappe.get_doc("Batch AMB", child.name)
        child_info = get_batch_info(child_doc)
        child_info['children'] = get_child_hierarchy(child_doc)
        child_data.append(child_info)
    
    return child_data

@frappe.whitelist()
def get_batch_dashboard_data():
    """Get data for batch management dashboard"""
    from amb_w_spc.sfc_manufacturing.integration.batch_amb_integration import BatchAMBIntegration
    
    # Get batch statistics
    stats_query = """
        SELECT 
            COUNT(*) as total_batches,
            COUNT(CASE WHEN custom_batch_level = '1' THEN 1 END) as level1_batches,
            COUNT(CASE WHEN custom_batch_level = '2' THEN 1 END) as level2_batches, 
            COUNT(CASE WHEN custom_batch_level = '3' THEN 1 END) as level3_batches,
            COUNT(CASE WHEN workflow_state = 'Quality Approved' THEN 1 END) as approved_batches,
            COUNT(CASE WHEN workflow_state IN ('Pending QC Review', 'SPC Review Required') THEN 1 END) as pending_review,
            COUNT(CASE WHEN workflow_state = 'Rejected' THEN 1 END) as rejected_batches
        FROM `tabBatch AMB`
        WHERE custom_batch_level IN ('1', '2', '3')
    """
    
    stats = frappe.db.sql(stats_query, as_dict=True)[0]
    
    # Get recent batches
    recent_batches = frappe.get_all("Batch AMB",
        filters={"custom_batch_level": ["in", ["1", "2", "3"]]},
        fields=["name", "custom_batch_level", "workflow_state", "item_to_manufacture", "production_plant_name", "creation"],
        order_by="creation DESC",
        limit=10
    )
    
    # Get plant distribution
    plant_distribution = frappe.db.sql("""
        SELECT production_plant_name as plant, COUNT(*) as batch_count
        FROM `tabBatch AMB` 
        WHERE production_plant_name IS NOT NULL AND custom_batch_level IN ('1', '2', '3')
        GROUP BY production_plant_name
        ORDER BY batch_count DESC
    """, as_dict=True)
    
    return {
        'statistics': stats,
        'recent_batches': recent_batches,
        'plant_distribution': plant_distribution,
        'last_updated': now_datetime()
    }
