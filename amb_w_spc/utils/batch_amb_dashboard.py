# -*- coding: utf-8 -*-
"""
Batch AMB Dashboard Configuration - v5.3
================================================================================
Version: 5.3 - Work Order Fetched Links
Last Updated: 2026-05-01

FEATURE: Fetch Delivery Note, Sales Invoice, Packing Slip via Work Order
================================================================================
"""

from frappe import _
import frappe
from collections import defaultdict


_CACHED_DOCTYPES = None


def _get_available_doctypes(doctypes):
    """Return only doctypes that actually exist in the DB (cached)."""
    global _CACHED_DOCTYPES
    if _CACHED_DOCTYPES is None:
        try:
            _CACHED_DOCTYPES = set(frappe.db.get_all("DocType", pluck="name"))
        except Exception:
            _CACHED_DOCTYPES = set()
    return [dt for dt in doctypes if dt in _CACHED_DOCTYPES]


def _get_work_order_related_docs(work_order_name):
    """Fetch documents related to a Work Order."""
    if not work_order_name:
        return {"delivery_notes": [], "sales_invoices": [], "packing_slips": []}

    result = {"delivery_notes": [], "sales_invoices": [], "packing_slips": []}

    # Delivery Notes
    try:
        if frappe.db.has_column("Delivery Note", "work_order"):
            dn_list = frappe.get_all(
                "Delivery Note",
                filters={"work_order": work_order_name, "docstatus": 1},
                fields=["name", "status", "posting_date", "docstatus"],
                order_by="posting_date desc",
            )
            for dn in dn_list:
                result["delivery_notes"].append({
                    "name": dn.name,
                    "status": dn.get("status"),
                    "date": dn.get("posting_date"),
                    "docstatus": dn.get("docstatus"),
                    "doctype": "Delivery Note",
                })
    except Exception as e:
        frappe.log_error(f"Error fetching Delivery Notes: {e}", "Batch AMB Dashboard")

    # Sales Invoices
    try:
        if frappe.db.has_column("Sales Invoice", "work_order"):
            si_list = frappe.get_all(
                "Sales Invoice",
                filters={"work_order": work_order_name, "docstatus": 1},
                fields=["name", "status", "posting_date", "docstatus"],
                order_by="posting_date desc",
            )
            for si in si_list:
                result["sales_invoices"].append({
                    "name": si.name,
                    "status": si.get("status"),
                    "date": si.get("posting_date"),
                    "docstatus": si.get("docstatus"),
                    "doctype": "Sales Invoice",
                })
    except Exception as e:
        frappe.log_error(f"Error fetching Sales Invoices: {e}", "Batch AMB Dashboard")

    # Packing Slips (try multiple field names)
    if frappe.db.exists("DocType", "Packing Slip"):
        try:
            for field in ["work_order", "work_order_ref", "against_work_order"]:
                if frappe.db.has_column("Packing Slip", field):
                    ps_list = frappe.get_all(
                        "Packing Slip",
                        filters={field: work_order_name, "docstatus": 1},
                        fields=["name", "status", "posting_date", "docstatus"],
                        order_by="posting_date desc",
                        limit=10,
                    )
                    for ps in ps_list:
                        result["packing_slips"].append({
                            "name": ps.name,
                            "status": ps.get("status"),
                            "date": ps.get("posting_date"),
                            "docstatus": ps.get("docstatus"),
                            "doctype": "Packing Slip",
                        })
                    break
        except Exception as e:
            frappe.log_error(f"Error fetching Packing Slips: {e}", "Batch AMB Dashboard")

    return result


def get_data(data=None):
    """Configure dashboard with Work Order fetched links."""
    if data is None:
        data = {}

    if "non_standard_fieldnames" not in data:
        data["non_standard_fieldnames"] = {}

    data["non_standard_fieldnames"].update({
        "COA AMB": "batch_reference",
        "Sample Request AMB": "batch_reference",
        "Batch Processing History": "batch_reference",
        "Container Selection": "batch_amb_link",
        "Batch Output Product": "source_batch_amb",
        # Work Order related
        "Delivery Note": "work_order",
        "Sales Invoice": "work_order",
        "Packing Slip": "work_order",
    })

    if "transactions" not in data:
        data["transactions"] = []

    # Quality & Compliance
    quality_items = _get_available_doctypes(["COA AMB", "Sample Request AMB"])
    if quality_items:
        data["transactions"].append({
            "label": _("Quality & Compliance"),
            "items": quality_items,
        })

    # Production Tracking
    tracking_items = _get_available_doctypes([
        "Batch Processing History",
        "Container Selection",
        "Batch Output Product",
    ])
    if tracking_items:
        data["transactions"].append({
            "label": _("Production Tracking"),
            "items": tracking_items,
        })

    # Work Order Documents (fetched via Work Order)
    wo_items = _get_available_doctypes([
        "Delivery Note",
        "Sales Invoice",
        "Packing Slip",
    ])
    if wo_items:
        data["transactions"].append({
            "label": _("Work Order Documents"),
            "items": wo_items,
            "custom": True,
            "fetch_via": "work_order_ref",
        })

    # Inventory & Stock
    inventory_items = _get_available_doctypes(["Stock Entry", "Stock Reconciliation"])
    if inventory_items:
        data["transactions"].append({
            "label": _("Inventory & Stock"),
            "items": inventory_items,
        })

    return data


@frappe.whitelist()
def get_work_order_documents(batch_name):
    """API: fetch Work Order related documents for a batch."""
    if not batch_name:
        return {"delivery_notes": [], "sales_invoices": [], "packing_slips": []}

    work_order = frappe.db.get_value("Batch AMB", batch_name, "work_order_ref")
    if not work_order:
        return {"delivery_notes": [], "sales_invoices": [], "packing_slips": [], "work_order": None}

    wo_docs = _get_work_order_related_docs(work_order)
    wo_docs["work_order"] = work_order
    return wo_docs


@frappe.whitelist()
def get_batch_quick_stats(batch_name):
    """API: quick connection stats for a batch."""
    stats = {
        "coa_count": frappe.db.count("COA AMB", {"batch_reference": batch_name}),
        "sample_count": frappe.db.count("Sample Request AMB", {"batch_reference": batch_name}),
        "history_count": frappe.db.count("Batch Processing History", {"batch_reference": batch_name}),
        "container_count": frappe.db.count("Container Selection", {"batch_amb_link": batch_name}),
        "output_count": frappe.db.count("Batch Output Product", {"source_batch_amb": batch_name}),
        "work_order": frappe.db.get_value("Batch AMB", batch_name, "work_order_ref"),
    }

    if stats["work_order"]:
        wo_docs = _get_work_order_related_docs(stats["work_order"])
        stats["delivery_note_count"] = len(wo_docs["delivery_notes"])
        stats["sales_invoice_count"] = len(wo_docs["sales_invoices"])
        stats["packing_slip_count"] = len(wo_docs["packing_slips"])
    else:
        stats["delivery_note_count"] = 0
        stats["sales_invoice_count"] = 0
        stats["packing_slip_count"] = 0

    stats["total_connections"] = (
        stats["coa_count"] + stats["sample_count"] + stats["history_count"]
        + stats["container_count"] + stats["output_count"]
        + stats["delivery_note_count"] + stats["sales_invoice_count"] + stats["packing_slip_count"]
    )
    return stats


@frappe.whitelist()
def get_related_documents(batch_name, doctype):
    """API: HTML-rendered list of related documents for a specific doctype."""
    if not batch_name or not doctype:
        return ""

    field_mappings = {
        "COA AMB": "batch_reference",
        "Sample Request AMB": "batch_reference",
        "Batch Processing History": "batch_reference",
        "Container Selection": "batch_amb_link",
        "Batch Output Product": "source_batch_amb",
    }

    if doctype in ["Delivery Note", "Sales Invoice", "Packing Slip"]:
        work_order = frappe.db.get_value("Batch AMB", batch_name, "work_order_ref")
        if not work_order:
            return '<div class="text-muted text-center">No Work Order linked</div>'
        if doctype == "Delivery Note":
            docs = frappe.get_all(
                "Delivery Note",
                filters={"work_order": work_order},
                fields=["name", "status", "posting_date", "docstatus"],
                limit=10,
            )
        elif doctype == "Sales Invoice":
            docs = frappe.get_all(
                "Sales Invoice",
                filters={"work_order": work_order},
                fields=["name", "status", "posting_date", "docstatus"],
                limit=10,
            )
        else:
            docs = []
    else:
        fieldname = field_mappings.get(doctype, "batch_reference")
        docs = frappe.get_all(
            doctype,
            filters={fieldname: batch_name},
            fields=["name", "status", "posting_date", "docstatus"],
            limit=10,
        )

    if not docs:
        return f'<div class="text-muted text-center">No {doctype} found</div>'

    html = '<div class="related-documents-list">'
    html += f'<div class="text-right mb-1"><small>Total: {len(docs)}</small></div>'
    html += '<div class="table-responsive">'
    html += '<table class="table table-bordered table-sm">'
    html += '<thead><tr><th>Document</th><th>Status</th><th>Date</th></tr></thead>'
    html += '<tbody>'
    for doc in docs:
        doc_link = f'<a href="/app/{doctype.lower().replace(" ", "-")}/{doc.name}">{doc.name}</a>'
        status_badge = _get_status_badge(doc.get("status"), doc.get("docstatus"))
        creation_date = frappe.format_date(doc.get("posting_date") or doc.get("creation"))
        html += f'<tr><td>{doc_link}</td><td>{status_badge}</td><td>{creation_date}</td></tr>'
    html += '</tbody></table></div></div>'
    return html


def _get_status_badge(status, docstatus):
    """Return formatted status badge HTML."""
    if docstatus == 1:
        return '<span class="label label-success">Submitted</span>'
    if docstatus == 2:
        return '<span class="label label-danger">Cancelled</span>'
    if status:
        s = status.lower()
        if "pending" in s:
            return '<span class="label label-warning">Pending</span>'
        if "approved" in s or "completed" in s:
            return '<span class="label label-success">Approved</span>'
        if "draft" in s:
            return '<span class="label label-default">Draft</span>'
    return '<span class="label label-info">Open</span>'


def verify_connections(batch_name=None):
    """CLI helper: verify connections for a batch or all batches."""
    if batch_name:
        _verify_single_batch(batch_name)
    else:
        _verify_all_batches()


def _verify_single_batch(batch_name):
    if not frappe.db.exists("Batch AMB", batch_name):
        print(f"Batch '{batch_name}' not found")
        return
    batch = frappe.get_doc("Batch AMB", batch_name)
    work_order = batch.get("work_order_ref")
    print("=" * 70)
    print(f"  BATCH: {batch_name}")
    print(f"  Level: {batch.get('custom_batch_level', 'N/A')}")
    print(f"  Work Order: {work_order or 'None'}")
    print("=" * 70)
    connections = [
        ("COA AMB", "batch_reference"),
        ("Sample Request AMB", "batch_reference"),
        ("Batch Processing History", "batch_reference"),
        ("Container Selection", "batch_amb_link"),
        ("Batch Output Product", "source_batch_amb"),
    ]
    total = 0
    for doctype, field in connections:
        count = frappe.db.count(doctype, {field: batch_name})
        total += count
        print(f"  {doctype}: {count}")
    if work_order:
        wo_docs = _get_work_order_related_docs(work_order)
        total += (
            len(wo_docs["delivery_notes"])
            + len(wo_docs["sales_invoices"])
            + len(wo_docs["packing_slips"])
        )
        for dn in wo_docs["delivery_notes"]:
            print(f"  Delivery Note: /app/delivery-note/{dn['name']}")
        for si in wo_docs["sales_invoices"]:
            print(f"  Sales Invoice: /app/sales-invoice/{si['name']}")
        for ps in wo_docs["packing_slips"]:
            print(f"  Packing Slip: /app/packing-slip/{ps['name']}")
    print(f"  Total Connections: {total}")


def _verify_all_batches():
    batches = frappe.get_all(
        "Batch AMB",
        fields=["name", "custom_batch_level", "work_order_ref"],
        limit=30,
    )
    stats = defaultdict(int)
    batches_with_connections = 0
    for batch in batches:
        name = batch["name"]
        work_order = batch.get("work_order_ref")
        counts = {
            "coa": frappe.db.count("COA AMB", {"batch_reference": name}),
            "sr": frappe.db.count("Sample Request AMB", {"batch_reference": name}),
            "hist": frappe.db.count("Batch Processing History", {"batch_reference": name}),
            "cont": frappe.db.count("Container Selection", {"batch_amb_link": name}),
            "out": frappe.db.count("Batch Output Product", {"source_batch_amb": name}),
        }
        if work_order:
            wo_docs = _get_work_order_related_docs(work_order)
            counts["dn"] = len(wo_docs["delivery_notes"])
            counts["si"] = len(wo_docs["sales_invoices"])
            counts["ps"] = len(wo_docs["packing_slips"])
        total = sum(counts.values())
        if total > 0:
            batches_with_connections += 1
            for k, v in counts.items():
                stats[k] += v
    print(f"Batches with connections: {batches_with_connections}/{len(batches)}")
    for k, v in stats.items():
        print(f"  {k.upper()}: {v}")


def check_dashboard_status():
    """Return dashboard configuration status for diagnostics."""
    result = {"dashboard_configured": False, "field_mappings": {}, "transactions": []}
    try:
        test_data = get_data({})
        result["dashboard_configured"] = True
        result["field_mappings"] = test_data.get("non_standard_fieldnames", {})
        result["transactions"] = test_data.get("transactions", [])
        result["message"] = "Dashboard v5.3 ready (Work Order fetching enabled)"
    except Exception as e:
        result["message"] = f"Error: {str(e)}"
    return result


def print_dashboard_info():
    print("BATCH AMB DASHBOARD v5.3 - Work Order Fetched Links")


if __name__ == "__main__":
    print_dashboard_info()
    status = check_dashboard_status()
    print(f"Status: {status.get('message')}")
