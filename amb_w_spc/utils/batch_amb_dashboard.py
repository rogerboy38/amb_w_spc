# -*- coding: utf-8 -*-
"""
BUG 87F: Dashboard Override for Batch AMB Connections
Adds Sample Request AMB to the Connections section of Batch AMB
"""

import frappe
from frappe import _


def get_data(data):
    """
    Add Sample Request AMB to Batch AMB's connections
    The 'data' parameter contains the dashboard data
    """
    # Ensure transactions list exists
    if 'transactions' not in data:
        data['transactions'] = []
    
    # Modify data in place - append Sample Request
    data['transactions'].append(
        {"label": _("Sample Request"), "items": ["Sample Request AMB"]}
    )
    
    # Add non_standard_fieldnames
    if "non_standard_fieldnames" not in data:
        data["non_standard_fieldnames"] = {}
    data["non_standard_fieldnames"]["Sample Request AMB"] = "batch_reference"
    
    return data