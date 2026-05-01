# -*- coding: utf-8 -*-
"""
Batch AMB Dashboard Configuration - OPTIMIZED v5.2
================================================================================
Version: 5.2 - Added clickable links and interactive tables
Last Updated: 2026-05-01

NEW FEATURES:
1. Clickable links to related documents
2. Interactive tables showing document lists
3. Quick navigation buttons
4. Count badges with links
5. Statistics widgets
================================================================================
"""

from frappe import _
import frappe
from collections import defaultdict

_CACHED_DOCTYPES = None


def _get_available_doctypes(doctypes):
    global _CACHED_DOCTYPES
    if _CACHED_DOCTYPES is None:
        try:
            _CACHED_DOCTYPES = set(frappe.db.get_all("DocType", pluck="name"))
        except Exception:
            _CACHED_DOCTYPES = set()
    return [dt for dt in doctypes if dt in _CACHED_DOCTYPES]


def get_data(data=None):
    """
    Configure optimized dashboard for Batch AMB doctype.
    Includes clickable links and interactive tables.
    """
    if data is None:
        data = {}

    # ============================================
    # NON-STANDARD FIELDNAME MAPPINGS
    # ============================================
    if "non_standard_fieldnames" not in data:
        data["non_standard_fieldnames"] = {}

    data["non_standard_fieldnames"].update({
        "COA AMB": "batch_reference",
        "Sample Request AMB": "batch_reference",
        "Batch Processing History": "batch_reference",
        "Container Selection": "batch_amb_link",
        "Batch Output Product": "source_batch_amb",
    })

    # ============================================
    # TRANSACTIONS - WITH CUSTOM LINKS
    # ============================================
    if "transactions" not in data:
        data["transactions"] = []

    # Quality & Compliance (with link to create new)
    quality_items = _get_available_doctypes(["COA AMB", "Sample Request AMB"])
    if quality_items:
        data["transactions"].append({
            "label": _("Quality & Compliance"),
            "items": quality_items,
            "custom": True,
            "route": "/app/{doctype}/new?batch_amb={doc_name}"
        })

    # Production Tracking
    tracking_items = _get_available_doctypes([
        "Batch Processing History",
        "Container Selection",
        "Batch Output Product"
    ])
    if tracking_items:
        data["transactions"].append({
            "label": _("Production Tracking"),
            "items": tracking_items,
            "custom": True
        })

    # Inventory & Stock
    inventory_items = _get_available_doctypes(["Stock Entry", "Stock Reconciliation"])
    if inventory_items:
        data["transactions"].append({
            "label": _("Inventory & Stock"),
            "items": inventory_items,
            "custom": True
        })

    # Sales & Fulfillment
    sales_items = _get_available_doctypes(["Delivery Note", "Sales Invoice", "Packing Slip"])
    if sales_items:
        data["transactions"].append({
            "label": _("Sales & Fulfillment"),
            "items": sales_items,
            "custom": True
        })

    return data


# ============================================
# CUSTOM DASHBOARD COMPONENTS
# ============================================

@frappe.whitelist()
def get_related_documents(batch_name, doctype):
    """
    Get related documents for a specific doctype.
    Returns formatted HTML for dashboard widget.
    """
    if not batch_name or not doctype:
        return ""
    
    # Define field mappings
    field_mappings = {
        "COA AMB": "batch_reference",
        "Sample Request AMB": "batch_reference",
        "Batch Processing History": "batch_reference",
        "Container Selection": "batch_amb_link",
        "Batch Output Product": "source_batch_amb",
        "Stock Entry": "batch_amb",
        "Stock Reconciliation": "batch_amb",
        "Delivery Note": "batch_amb",
        "Sales Invoice": "batch_amb",
        "Packing Slip": "batch_amb",
    }
    
    fieldname = field_mappings.get(doctype, "batch_reference")
    
    # Get documents
    docs = frappe.get_all(
        doctype,
        filters={fieldname: batch_name},
        fields=["name", "creation", "status", "docstatus"],
        order_by="creation desc",
        limit=10
    )
    
    if not docs:
        return f'<div class="text-muted text-center">No {doctype} found</div>'
    
    # Build HTML table
    html = f'<div class="related-documents-list">'
    html += f'<div class="text-right mb-1"><small>Total: {len(docs)}</small></div>'
    html += f'<div class="table-responsive">'
    html += f'<table class="table table-bordered table-sm">'
    html += f'<thead><tr><th>Document</th><th>Status</th><th>Date</th></tr></thead>'
    html += f'<tbody>'
    
    for doc in docs:
        doc_link = f'<a href="/app/{doctype.lower().replace(" ", "-")}/{doc.name}">{doc.name}</a>'
        status_badge = _get_status_badge(doc.get("status"), doc.get("docstatus"))
        creation_date = frappe.format_date(doc.get("creation"))
        html += f'<tr><td>{doc_link}</td><td>{status_badge}</td><td>{creation_date}</td></tr>'
    
    html += '</tbody></table></div></div>'
    
    return html


def _get_status_badge(status, docstatus):
    """Return formatted status badge."""
    if docstatus == 1:
        return '<span class="label label-success">Submitted</span>'
    elif docstatus == 2:
        return '<span class="label label-danger">Cancelled</span>'
    elif status:
        status_lower = status.lower()
        if "pending" in status_lower:
            return '<span class="label label-warning">Pending</span>'
        elif "approved" in status_lower or "completed" in status_lower:
            return '<span class="label label-success">Approved</span>'
        elif "draft" in status_lower:
            return '<span class="label label-default">Draft</span>'
    return '<span class="label label-info">Open</span>'


@frappe.whitelist()
def get_dashboard_links(batch_name):
    """
    Get quick action links for the dashboard.
    Returns HTML with buttons to create new documents.
    """
    if not batch_name:
        return ""
    
    actions = [
        {"label": "Create COA AMB", "doctype": "COA AMB", "icon": "fa-file-text"},
        {"label": "Create Sample Request", "doctype": "Sample Request AMB", "icon": "fa-edit"},
        {"label": "Create Stock Entry", "doctype": "Stock Entry", "icon": "fa-database"},
        {"label": "Create Delivery Note", "doctype": "Delivery Note", "icon": "fa-truck"},
    ]
    
    html = '<div class="quick-actions" style="margin-bottom: 15px;">'
    html += '<div class="btn-group btn-group-sm">'
    
    for action in actions:
        url = f'/app/{action["doctype"].lower().replace(" ", "-")}/new?batch_amb={batch_name}'
        html += f'<a href="{url}" class="btn btn-primary">'
        html += f'<i class="{action["icon"]}"></i> {action["label"]}'
        html += f'</a>'
    
    html += '</div></div>'
    
    return html


@frappe.whitelist()
def get_batch_stats_widget(batch_name):
    """
    Generate statistics widget for batch dashboard.
    Returns HTML with count cards for each related doctype.
    """
    stats = {
        "coa_count": frappe.db.count("COA AMB", {"batch_reference": batch_name}),
        "sample_count": frappe.db.count("Sample Request AMB", {"batch_reference": batch_name}),
        "history_count": frappe.db.count("Batch Processing History", {"batch_reference": batch_name}),
        "container_count": frappe.db.count("Container Selection", {"batch_amb_link": batch_name}),
        "output_count": frappe.db.count("Batch Output Product", {"source_batch_amb": batch_name}),
    }
    
    html = '<div class="batch-stats-widget">'
    html += '<div class="row">'
    
    widgets = [
        {"label": "COA AMB", "count": stats["coa_count"], "icon": "fa-file-text-o", "color": "#428bca", "doctype": "COA AMB"},
        {"label": "Sample Requests", "count": stats["sample_count"], "icon": "fa-edit", "color": "#5cb85c", "doctype": "Sample Request AMB"},
        {"label": "Processing History", "count": stats["history_count"], "icon": "fa-clock-o", "color": "#f0ad4e", "doctype": "Batch Processing History"},
        {"label": "Containers", "count": stats["container_count"], "icon": "fa-cube", "color": "#9b59b6", "doctype": "Container Selection"},
        {"label": "Output Products", "count": stats["output_count"], "icon": "fa-cubes", "color": "#5bc0de", "doctype": "Batch Output Product"},
    ]
    
    for w in widgets:
        count_url = f'/app/{w["doctype"].lower().replace(" ", "-")}?batch_reference={batch_name}'
        html += f'''<div class="col-xs-6 col-sm-4 col-md-2">
            <div class="widget-box" style="background: {w['color']}10; border: 1px solid {w['color']}50; border-radius: 6px; padding: 10px; text-align: center; margin-bottom: 5px;">
                <div><i class="fa {w['icon']}" style="font-size: 18px; color: {w['color']};"></i></div>
                <a href="{count_url}" style="font-size: 22px; font-weight: bold; color: {w['color']};">{w['count']}</a>
                <div style="font-size: 10px; color: #666;">{w['label']}</div>
            </div>
        </div>'''
    
    html += '</div></div>'
    return html


@frappe.whitelist()
def get_batch_quick_stats(batch_name):
    """
    Get quick stats as JSON for AJAX calls.
    """
    return {
        "coa_count": frappe.db.count("COA AMB", {"batch_reference": batch_name}),
        "sample_count": frappe.db.count("Sample Request AMB", {"batch_reference": batch_name}),
        "history_count": frappe.db.count("Batch Processing History", {"batch_reference": batch_name}),
        "container_count": frappe.db.count("Container Selection", {"batch_amb_link": batch_name}),
        "output_count": frappe.db.count("Batch Output Product", {"source_batch_amb": batch_name}),
        "total_connections": frappe.db.count("COA AMB", {"batch_reference": batch_name}) +
                          frappe.db.count("Sample Request AMB", {"batch_reference": batch_name}) +
                          frappe.db.count("Batch Processing History", {"batch_reference": batch_name}) +
                          frappe.db.count("Container Selection", {"batch_amb_link": batch_name}) +
                          frappe.db.count("Batch Output Product", {"source_batch_amb": batch_name}),
    }


# ============================================
# DIAGNOSTIC FUNCTIONS
# ============================================

def verify_connections(batch_name=None):
    """Verify and display connections with clickable links."""
    if batch_name:
        _verify_single_batch(batch_name)
    else:
        _verify_all_batches()


def _verify_single_batch(batch_name):
    """Detailed verification with clickable links."""
    if not frappe.db.exists("Batch AMB", batch_name):
        print(f"❌ Batch '{batch_name}' not found")
        return

    batch = frappe.get_doc("Batch AMB", batch_name)
    level = batch.get("custom_batch_level", "N/A")
    golden = batch.get("custom_golden_number", "N/A")

    print(f"\n{'═'*70}")
    print(f"  📦 BATCH: {batch_name}")
    print(f"  📊 Level: {level} | Golden: {golden}")
    print(f"{'═'*70}")

    connections = [
        ("COA AMB", "batch_reference", "📄", "/app/coa-amb"),
        ("Sample Request AMB", "batch_reference", "📋", "/app/sample-request-amb"),
        ("Batch Processing History", "batch_reference", "⏱️", "/app/batch-processing-history"),
        ("Container Selection", "batch_amb_link", "📦", "/app/container-selection"),
        ("Batch Output Product", "source_batch_amb", "🏭", "/app/batch-output-product"),
    ]

    total_connections = 0
    
    for doctype, field, icon, base_url in connections:
        docs = frappe.get_all(doctype, filters={field: batch_name}, fields=["name"], limit=5)
        count = len(docs)
        total_connections += count
        
        if count > 0:
            print(f"\n  ✅ {icon} {doctype}: {count}")
            for doc in docs:
                doc_url = f"{base_url}/{doc['name']}"
                print(f"     → /app/{doctype.lower().replace(' ', '-')}/{doc['name']}")
        else:
            print(f"  ➖ {icon} {doctype}: 0")

    print(f"\n{'─'*70}")
    print(f"  📊 Total Connections: {total_connections}")
    print(f"  🔗 View batch: /app/batch-amb/{batch_name}")
    print(f"{'═'*70}")


def _verify_all_batches():
    """Summary verification for all batches."""
    try:
        batches = frappe.get_all(
            "Batch AMB",
            fields=["name", "custom_batch_level"],
            limit=50
        )
    except Exception as e:
        print(f"❌ Error fetching batches: {e}")
        return

    print(f"\n{'═'*70}")
    print(f"  🔍 BATCH AMB CONNECTIONS - SUMMARY")
    print(f"{'═'*70}")

    stats = defaultdict(int)
    batches_with_connections = 0

    for batch in batches:
        name = batch["name"]
        level = batch.get("custom_batch_level", "N/A")

        try:
            counts = {
                "coa": frappe.db.count("COA AMB", {"batch_reference": name}),
                "sr": frappe.db.count("Sample Request AMB", {"batch_reference": name}),
                "hist": frappe.db.count("Batch Processing History", {"batch_reference": name}),
                "cont": frappe.db.count("Container Selection", {"batch_amb_link": name}),
                "out": frappe.db.count("Batch Output Product", {"source_batch_amb": name}),
            }

            total = sum(counts.values())
            if total > 0:
                batches_with_connections += 1
                for k, v in counts.items():
                    stats[k] += v

                print(f"\n  📦 {name} (L{level})")
                for k, v in counts.items():
                    if v > 0:
                        icons = {"coa": "📄", "sr": "📋", "hist": "⏱️", "cont": "📦", "out": "🏭"}
                        print(f"     {icons[k]} {k.upper()}: {v}")

        except Exception as e:
            print(f"  ⚠️ Error checking {name}: {e}")

    print(f"\n{'─'*70}")
    print(f"  📊 STATISTICS:")
    print(f"     • Batches with connections: {batches_with_connections}/{len(batches)}")
    print(f"     📄 COA AMB: {stats['coa']}")
    print(f"     📋 Sample Request: {stats['sr']}")
    print(f"     ⏱️ Processing History: {stats['hist']}")
    print(f"     📦 Container: {stats['cont']}")
    print(f"     🏭 Output: {stats['out']}")
    print(f"{'═'*70}")


def check_dashboard_status():
    """Check dashboard configuration status."""
    result = {
        "batch_amb_exists": False,
        "dashboard_configured": False,
        "field_mappings": {},
        "transactions": [],
        "stats_enabled": False,
        "cache_status": "unknown",
        "links_enabled": True,
    }

    try:
        result["batch_amb_exists"] = frappe.db.exists("DocType", "Batch AMB")
        
        if not result["batch_amb_exists"]:
            result["message"] = "Batch AMB doctype not found"
            return result

        test_data = get_data({})
        result["dashboard_configured"] = True
        result["field_mappings"] = test_data.get("non_standard_fieldnames", {})
        result["transactions"] = test_data.get("transactions", [])
        result["stats_enabled"] = True
        result["cache_status"] = "active" if _CACHED_DOCTYPES else "cold"
        result["message"] = "Dashboard v5.2 ready with clickable links"
        
    except Exception as e:
        result["message"] = f"Error: {str(e)}"

    return result


def print_dashboard_info():
    """Print formatted dashboard information."""
    print("\n" + "═"*70)
    print("  📊 BATCH AMB DASHBOARD - OPTIMIZED v5.2")
    print("═"*70)
    print("\n  🔗 FIELD MAPPINGS:")
    print("     • COA AMB → batch_reference")
    print("     • Sample Request AMB → batch_reference")
    print("     • Batch Processing History → batch_reference")
    print("     • Container Selection → batch_amb_link")
    print("     • Batch Output Product → source_batch_amb")

    print("\n  📂 TRANSACTION GROUPS:")
    print("     1. Quality & Compliance (COA AMB, Sample Request AMB)")
    print("     2. Production Tracking (History, Container, Output)")
    print("     3. Inventory & Stock (Stock Entry, Reconciliation)")
    print("     4. Sales & Fulfillment (Delivery, Invoice, Packing)")

    print("\n  ✨ NEW FEATURES v5.2:")
    print("     • get_related_documents() - HTML table widget")
    print("     • get_dashboard_links() - Quick action buttons")
    print("     • get_batch_stats_widget() - Stats cards")
    print("     • get_batch_quick_stats() - JSON for AJAX")
    print("     • Clickable document links in verification")
    print("═"*70)


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print_dashboard_info()
    status = check_dashboard_status()
    print(f"\n  Status: {status.get('message')}")
    print(f"  Cache: {status.get('cache_status', 'unknown')}")
    print(f"  Links: {status.get('links_enabled', False)}")
