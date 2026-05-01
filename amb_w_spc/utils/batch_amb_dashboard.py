# -*- coding: utf-8 -*-
"""
BUG 87F: Dashboard Override for Batch AMB Connections
Adds Sample Request AMB and prunes invalid default links.
"""
import frappe
from frappe import _

INVALID = {"Work Order", "Stock Entry", "Quality Inspection"}

def get_data(data):
    if "transactions" not in data:
        data["transactions"] = []

    # Strip invalid default items (no batch_amb column)
    cleaned = []
    for tx in data["transactions"]:
        items = [i for i in tx.get("items", []) if i not in INVALID]
        if items:
            tx["items"] = items
            cleaned.append(tx)
    data["transactions"] = cleaned

    # Append Sample Request
    data["transactions"].append(
        {"label": _("Sample Request"), "items": ["Sample Request AMB"]}
    )

    if "non_standard_fieldnames" not in data:
        data["non_standard_fieldnames"] = {}
    data["non_standard_fieldnames"].update({
        "Sample Request AMB": "batch_reference",
        "COA AMB": "batch_reference",
        "Batch Processing History": "batch_reference",
        "Container Selection": "batch_amb_link",
        "Batch Output Product": "source_batch_amb",
    })

    return data
