"""
Archived Server Script: get_running_batch_announcements

V13.6.0 P3 Server Script Migration
Decision: DEL / archived
Script Type: API
Reference DocType: None
Disabled: 1

Runtime status:
  DO NOT IMPORT. Archive only.
"""

ORIGINAL_SCRIPT = """
import frappe
from frappe.utils import getdate

@frappe.whitelist()
def get_running_batch_announcements():
    """
    Get currently running batches for navbar display
    """
    try:
        # Get running batches (Level 1 main batches only)
        running_batches = frappe.get_all(
            'Batch AMB',
            filters={
                'batch_status': 'Running Now',
                'custom_batch_level': '1',
                'docstatus': ['!=', 2]
            },
            fields=[
                'name', 'custom_generated_batch_name', 'work_order_ref',
                'manufacturing_date', 'production_workstation', 'batch_status',
                'sales_order_related', 'creation'
            ],
            order_by='creation desc',
            limit=3
        )
        
        announcements = []
        
        for batch in running_batches:
            try:
                # Get related sub-lots (Level 2)
                sub_lots = frappe.get_all(
                    'Batch AMB',
                    filters={
                        'parent_batch_amb': batch.name,
                        'custom_batch_level': '2'
                    },
                    fields=['custom_generated_batch_name'],
                    limit=1
                )
                
                # Get sales order info
                sales_order = batch.sales_order_related or 'N/A'
                if batch.work_order_ref and sales_order == 'N/A':
                    try:
                        work_order = frappe.get_doc('Work Order', batch.work_order_ref)
                        sales_order = work_order.sales_order if hasattr(work_order, 'sales_order') and work_order.sales_order else 'N/A'
                    except:
                        sales_order = 'N/A'
                
                # Format manufacturing date
                manufacturing_date = 'N/A'
                if batch.manufacturing_date:
                    try:
                        date_obj = getdate(batch.manufacturing_date)
                        manufacturing_date = date_obj.strftime('%Y-%m-%d')
                    except:
                        manufacturing_date = str(batch.manufacturing_date)
                
                # Create announcement text
                announcement_text = f"""🏭 LOTE EN PRODUCCION: {batch.custom_generated_batch_name or batch.name}
📋 ORDEN DE TRABAJO: {batch.work_order_ref or 'N/A'}
📦 NUMERO DE SUB-LOTE: {sub_lots[0].custom_generated_batch_name if sub_lots else 'N/A'}
🛒 PEDIDO DE VENTA: {sales_order}
⚡ STATUS: {batch.batch_status}
📍 ESTACIÓN: {batch.production_workstation or 'N/A'}
📅 FECHA: {manufacturing_date}"""
                
                announcements.append({
                    'title': f'Batch {batch.custom_generated_batch_name or batch.name}',
                    'content': announcement_text,
                    'batch_name': batch.name,
                    'priority': 'high',
                    'timestamp': frappe.utils.now()
                })
                
            except Exception as e:
                frappe.log_error(f"Error processing batch {batch.name}: {str(e)}", "Batch Announcement Error")
                continue
        
        return {
            'success': True,
            'announcements': announcements,
            'count': len(announcements),
            'timestamp': frappe.utils.now()
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_running_batch_announcements: {str(e)}", "Batch Announcement Error")
        return {
            'success': False,
            'error': str(e),
            'announcements': [],
            'count': 0
        }
"""
