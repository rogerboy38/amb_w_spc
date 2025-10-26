import frappe
from frappe import _
from frappe.utils import nowdate, add_days, add_months, flt
import json

def execute(filters=None):
    """
    Main report execution function for Receiving Operations Dashboard
    """
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(filters)
    summary = get_summary_data(filters)
    
    return columns, data, None, chart, summary

def get_columns():
    """Define report columns"""
    return [
        {
            "fieldname": "purchase_receipt",
            "fieldtype": "Link",
            "label": _("Purchase Receipt"),
            "options": "Purchase Receipt",
            "width": 150
        },
        {
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "label": _("Posting Date"),
            "width": 100
        },
        {
            "fieldname": "supplier",
            "fieldtype": "Link",
            "label": _("Supplier"),
            "options": "Supplier",
            "width": 150
        },
        {
            "fieldname": "total_items",
            "fieldtype": "Int",
            "label": _("Total Items"),
            "width": 80
        },
        {
            "fieldname": "inspection_required",
            "fieldtype": "Int",
            "label": _("Inspection Required"),
            "width": 100
        },
        {
            "fieldname": "direct_placement",
            "fieldtype": "Int",
            "label": _("Direct Placement"),
            "width": 100
        },
        {
            "fieldname": "integration_status",
            "fieldtype": "Data",
            "label": _("Integration Status"),
            "width": 120
        },
        {
            "fieldname": "quality_status",
            "fieldtype": "Data",
            "label": _("Quality Status"),
            "width": 120
        },
        {
            "fieldname": "warehouse_status",
            "fieldtype": "Data",
            "label": _("Warehouse Status"),
            "width": 120
        },
        {
            "fieldname": "batch_count",
            "fieldtype": "Int",
            "label": _("Batch Count"),
            "width": 80
        },
        {
            "fieldname": "total_value",
            "fieldtype": "Currency",
            "label": _("Total Value"),
            "width": 120
        },
        {
            "fieldname": "plant_codes",
            "fieldtype": "Data",
            "label": _("Plant Codes"),
            "width": 100
        }
    ]

def get_data(filters):
    """Get report data based on filters"""
    conditions = get_conditions(filters)
    
    # Main query for Purchase Receipts with integration data
    data = frappe.db.sql(f"""
        SELECT 
            pr.name as purchase_receipt,
            pr.posting_date,
            pr.supplier,
            COUNT(pri_item.name) as total_items,
            SUM(CASE WHEN pri_item.quality_inspection_required = 1 THEN 1 ELSE 0 END) as inspection_required,
            SUM(CASE WHEN pri_item.quality_inspection_required = 0 THEN 1 ELSE 0 END) as direct_placement,
            pri.warehouse_integration_status as integration_status,
            pri.quality_approval_status as quality_status,
            pri.warehouse_placement_status as warehouse_status,
            COUNT(DISTINCT ba.name) as batch_count,
            pr.grand_total as total_value,
            GROUP_CONCAT(DISTINCT pri_item.plant_code) as plant_codes
        FROM `tabPurchase Receipt` pr
        LEFT JOIN `tabPurchase Receipt Integration` pri ON pr.name = pri.purchase_receipt_reference
        LEFT JOIN `tabPurchase Receipt Integration Item` pri_item ON pri.name = pri_item.parent
        LEFT JOIN `tabBatch AMB` ba ON pr.name = ba.purchase_receipt_reference
        WHERE {conditions}
        GROUP BY pr.name
        ORDER BY pr.posting_date DESC
    """, as_dict=True)
    
    # Enhance data with additional calculations
    for row in data:
        # Calculate completion percentages
        if row.total_items > 0:
            if row.inspection_required > 0:
                row.inspection_completion = calculate_inspection_completion(row.purchase_receipt)
            else:
                row.inspection_completion = 100
                
            row.placement_completion = calculate_placement_completion(row.purchase_receipt)
        else:
            row.inspection_completion = 0
            row.placement_completion = 0
            
        # Format status indicators
        row.integration_status = format_status_indicator(row.integration_status)
        row.quality_status = format_status_indicator(row.quality_status)
        row.warehouse_status = format_status_indicator(row.warehouse_status)
        
    return data

def get_conditions(filters):
    """Build WHERE conditions based on filters"""
    conditions = ["pr.docstatus = 1"]  # Only submitted receipts
    
    if filters.get("from_date"):
        conditions.append(f"pr.posting_date >= '{filters.get('from_date')}'")
        
    if filters.get("to_date"):
        conditions.append(f"pr.posting_date <= '{filters.get('to_date')}'")
        
    if filters.get("supplier"):
        conditions.append(f"pr.supplier = '{filters.get('supplier')}'")
        
    if filters.get("plant_code"):
        conditions.append(f"pri_item.plant_code = '{filters.get('plant_code')}'")
        
    if filters.get("integration_status"):
        conditions.append(f"pri.warehouse_integration_status = '{filters.get('integration_status')}'")
        
    return " AND ".join(conditions)

def calculate_inspection_completion(purchase_receipt):
    """Calculate inspection completion percentage"""
    try:
        # Get quality inspections for this receipt
        inspections = frappe.db.sql("""
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN status = 'Accepted' THEN 1 ELSE 0 END) as completed
            FROM `tabQuality Inspection`
            WHERE reference_name = %s AND inspection_type = 'Incoming'
        """, purchase_receipt, as_dict=True)
        
        if inspections and inspections[0].total > 0:
            return (inspections[0].completed / inspections[0].total) * 100
        return 0
        
    except Exception:
        return 0

def calculate_placement_completion(purchase_receipt):
    """Calculate warehouse placement completion percentage"""
    try:
        # Check stock entries for this receipt
        stock_entries = frappe.db.sql("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN docstatus = 1 THEN 1 ELSE 0 END) as completed
            FROM `tabStock Entry`
            WHERE custom_purchase_receipt_reference = %s
        """, purchase_receipt, as_dict=True)
        
        if stock_entries and stock_entries[0].total > 0:
            return (stock_entries[0].completed / stock_entries[0].total) * 100
        return 0
        
    except Exception:
        return 0

def format_status_indicator(status):
    """Format status with color indicators"""
    if not status:
        return "N/A"
        
    status_colors = {
        "Completed": "🟢",
        "Pending": "🟡", 
        "Failed": "🔴",
        "Complete": "🟢",
        "Partial": "🟡",
        "Rejected": "🔴"
    }
    
    color = status_colors.get(status, "⚪")
    return f"{color} {status}"

def get_chart_data(filters):
    """Generate chart data for dashboard"""
    # Get data for charts
    date_range = get_date_range(filters)
    
    # Daily receiving volume chart
    daily_data = frappe.db.sql(f"""
        SELECT 
            pr.posting_date,
            COUNT(*) as receipt_count,
            SUM(pr.grand_total) as total_value,
            COUNT(DISTINCT pr.supplier) as supplier_count
        FROM `tabPurchase Receipt` pr
        WHERE pr.posting_date >= '{date_range['from_date']}'
        AND pr.posting_date <= '{date_range['to_date']}'
        AND pr.docstatus = 1
        GROUP BY pr.posting_date
        ORDER BY pr.posting_date
    """, as_dict=True)
    
    # Plant-wise distribution
    plant_data = frappe.db.sql(f"""
        SELECT 
            pri_item.plant_code,
            COUNT(DISTINCT pr.name) as receipt_count,
            SUM(pri_item.qty) as total_quantity,
            SUM(pri_item.amount) as total_value
        FROM `tabPurchase Receipt` pr
        JOIN `tabPurchase Receipt Integration` pri ON pr.name = pri.purchase_receipt_reference
        JOIN `tabPurchase Receipt Integration Item` pri_item ON pri.name = pri_item.parent
        WHERE pr.posting_date >= '{date_range['from_date']}'
        AND pr.posting_date <= '{date_range['to_date']}'
        AND pr.docstatus = 1
        GROUP BY pri_item.plant_code
    """, as_dict=True)
    
    return {
        "data": {
            "labels": [d.posting_date.strftime("%Y-%m-%d") for d in daily_data],
            "datasets": [
                {
                    "name": "Receipt Count",
                    "values": [d.receipt_count for d in daily_data]
                },
                {
                    "name": "Total Value",
                    "values": [d.total_value for d in daily_data]
                }
            ]
        },
        "type": "line",
        "height": 250,
        "colors": ["#7cd6fd", "#743ee2"]
    }

def get_summary_data(filters):
    """Generate summary statistics"""
    date_range = get_date_range(filters)
    
    # Overall statistics
    summary_stats = frappe.db.sql(f"""
        SELECT 
            COUNT(DISTINCT pr.name) as total_receipts,
            SUM(pr.grand_total) as total_value,
            COUNT(DISTINCT pr.supplier) as unique_suppliers,
            AVG(pr.grand_total) as avg_receipt_value,
            COUNT(DISTINCT pri_item.item_code) as unique_items,
            SUM(pri_item.qty) as total_quantity
        FROM `tabPurchase Receipt` pr
        LEFT JOIN `tabPurchase Receipt Integration` pri ON pr.name = pri.purchase_receipt_reference
        LEFT JOIN `tabPurchase Receipt Integration Item` pri_item ON pri.name = pri_item.parent
        WHERE pr.posting_date >= '{date_range['from_date']}'
        AND pr.posting_date <= '{date_range['to_date']}'
        AND pr.docstatus = 1
    """, as_dict=True)[0]
    
    # Integration statistics
    integration_stats = frappe.db.sql(f"""
        SELECT 
            SUM(CASE WHEN pri.warehouse_integration_status = 'Completed' THEN 1 ELSE 0 END) as warehouse_completed,
            SUM(CASE WHEN pri.quality_system_integration_status = 'Completed' THEN 1 ELSE 0 END) as quality_completed,
            SUM(CASE WHEN pri.batch_tracking_integration_status = 'Completed' THEN 1 ELSE 0 END) as batch_completed,
            COUNT(*) as total_integrations
        FROM `tabPurchase Receipt Integration` pri
        JOIN `tabPurchase Receipt` pr ON pr.name = pri.purchase_receipt_reference
        WHERE pr.posting_date >= '{date_range['from_date']}'
        AND pr.posting_date <= '{date_range['to_date']}'
        AND pr.docstatus = 1
    """, as_dict=True)[0]
    
    # Quality inspection statistics
    quality_stats = frappe.db.sql(f"""
        SELECT 
            COUNT(*) as total_inspections,
            SUM(CASE WHEN status = 'Accepted' THEN 1 ELSE 0 END) as passed_inspections,
            SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) as failed_inspections
        FROM `tabQuality Inspection` qi
        WHERE qi.report_date >= '{date_range['from_date']}'
        AND qi.report_date <= '{date_range['to_date']}'
        AND qi.inspection_type = 'Incoming'
    """, as_dict=True)[0]
    
    return [
        {
            "value": summary_stats.total_receipts or 0,
            "label": "Total Receipts",
            "datatype": "Int"
        },
        {
            "value": summary_stats.total_value or 0,
            "label": "Total Value",
            "datatype": "Currency"
        },
        {
            "value": summary_stats.unique_suppliers or 0,
            "label": "Suppliers",
            "datatype": "Int"
        },
        {
            "value": summary_stats.unique_items or 0,
            "label": "Unique Items",
            "datatype": "Int"
        },
        {
            "value": f"{((integration_stats.warehouse_completed or 0) / max(integration_stats.total_integrations or 1, 1)) * 100:.1f}%",
            "label": "Warehouse Integration",
            "datatype": "Percent"
        },
        {
            "value": f"{((quality_stats.passed_inspections or 0) / max(quality_stats.total_inspections or 1, 1)) * 100:.1f}%", 
            "label": "Quality Pass Rate",
            "datatype": "Percent"
        }
    ]

def get_date_range(filters):
    """Get date range for queries"""
    if filters.get("from_date") and filters.get("to_date"):
        return {
            "from_date": filters["from_date"],
            "to_date": filters["to_date"]
        }
    else:
        # Default to last 30 days
        to_date = nowdate()
        from_date = add_days(to_date, -30)
        return {
            "from_date": from_date,
            "to_date": to_date
        }

# Additional utility functions for dashboard

@frappe.whitelist()
def get_receiving_kpis(from_date=None, to_date=None):
    """Get key performance indicators for receiving operations"""
    try:
        if not from_date:
            from_date = add_days(nowdate(), -7)
        if not to_date:
            to_date = nowdate()
            
        # Calculate KPIs
        kpis = {}
        
        # Receipt processing time
        avg_processing_time = frappe.db.sql("""
            SELECT AVG(DATEDIFF(pri.modified, pr.posting_date)) as avg_days
            FROM `tabPurchase Receipt` pr
            JOIN `tabPurchase Receipt Integration` pri ON pr.name = pri.purchase_receipt_reference
            WHERE pr.posting_date BETWEEN %s AND %s
            AND pri.docstatus = 1
        """, (from_date, to_date))[0][0]
        
        kpis["avg_processing_time"] = avg_processing_time or 0
        
        # Quality inspection efficiency
        qi_efficiency = frappe.db.sql("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Accepted' THEN 1 ELSE 0 END) as passed,
                AVG(DATEDIFF(CURDATE(), report_date)) as avg_inspection_time
            FROM `tabQuality Inspection`
            WHERE report_date BETWEEN %s AND %s
            AND inspection_type = 'Incoming'
        """, (from_date, to_date), as_dict=True)[0]
        
        kpis["quality_pass_rate"] = (qi_efficiency.passed / max(qi_efficiency.total, 1)) * 100 if qi_efficiency.total else 0
        kpis["avg_inspection_time"] = qi_efficiency.avg_inspection_time or 0
        
        # Warehouse placement efficiency
        placement_stats = frappe.db.sql("""
            SELECT 
                COUNT(DISTINCT pr.name) as total_receipts,
                SUM(CASE WHEN pri.warehouse_placement_status = 'Complete' THEN 1 ELSE 0 END) as completed_placements
            FROM `tabPurchase Receipt` pr
            LEFT JOIN `tabPurchase Receipt Integration` pri ON pr.name = pri.purchase_receipt_reference
            WHERE pr.posting_date BETWEEN %s AND %s
            AND pr.docstatus = 1
        """, (from_date, to_date), as_dict=True)[0]
        
        kpis["placement_efficiency"] = (placement_stats.completed_placements / max(placement_stats.total_receipts, 1)) * 100 if placement_stats.total_receipts else 0
        
        # Temperature compliance
        temp_compliance = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_temp_items,
                SUM(CASE WHEN pri.temperature_compliance_status = 'Completed' THEN 1 ELSE 0 END) as compliant_items
            FROM `tabPurchase Receipt Integration` pri
            JOIN `tabPurchase Receipt` pr ON pr.name = pri.purchase_receipt_reference
            WHERE pr.posting_date BETWEEN %s AND %s
            AND pri.temperature_compliance_status IS NOT NULL
        """, (from_date, to_date), as_dict=True)[0]
        
        kpis["temperature_compliance"] = (temp_compliance.compliant_items / max(temp_compliance.total_temp_items, 1)) * 100 if temp_compliance.total_temp_items else 100
        
        return {"success": True, "kpis": kpis}
        
    except Exception as e:
        frappe.log_error(f"Error calculating receiving KPIs: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_plant_performance_summary(from_date=None, to_date=None):
    """Get performance summary by plant code"""
    try:
        if not from_date:
            from_date = add_days(nowdate(), -30)
        if not to_date:
            to_date = nowdate()
            
        plant_performance = frappe.db.sql("""
            SELECT 
                pri_item.plant_code,
                COUNT(DISTINCT pr.name) as receipt_count,
                SUM(pri_item.qty) as total_quantity,
                SUM(pri_item.amount) as total_value,
                AVG(pri_item.qty) as avg_quantity_per_receipt,
                COUNT(DISTINCT pri_item.item_code) as unique_items,
                SUM(CASE WHEN pri_item.quality_inspection_required = 1 THEN 1 ELSE 0 END) as inspection_items,
                SUM(CASE WHEN pri_item.current_zone_status = 'Green Zone' THEN 1 ELSE 0 END) as green_zone_items
            FROM `tabPurchase Receipt` pr
            JOIN `tabPurchase Receipt Integration` pri ON pr.name = pri.purchase_receipt_reference
            JOIN `tabPurchase Receipt Integration Item` pri_item ON pri.name = pri_item.parent
            WHERE pr.posting_date BETWEEN %s AND %s
            AND pr.docstatus = 1
            GROUP BY pri_item.plant_code
            ORDER BY total_value DESC
        """, (from_date, to_date), as_dict=True)
        
        # Calculate additional metrics
        for plant in plant_performance:
            plant.avg_value_per_receipt = plant.total_value / max(plant.receipt_count, 1)
            plant.inspection_percentage = (plant.inspection_items / max(plant.receipt_count, 1)) * 100
            plant.green_zone_percentage = (plant.green_zone_items / max(plant.receipt_count, 1)) * 100
            
        return {"success": True, "plant_performance": plant_performance}
        
    except Exception as e:
        frappe.log_error(f"Error getting plant performance: {str(e)}")
        return {"success": False, "error": str(e)}
