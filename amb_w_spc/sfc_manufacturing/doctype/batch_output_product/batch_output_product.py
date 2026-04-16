# Copyright (c) 2024, AMB and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BatchOutputProduct(Document):
    """Batch Output Product - Child table for tracking batch outputs with traceability.

    Fields:
        - Basic: item_code, item_name, quantity_kg, uom
        - Solids: total_solids_kg, solids_percentage
        - Traceability: golden_number, output_traceability_code, output_golden_number,
                        source_golden_number, source_batch_amb
        - Quality: quality_status, qa_status, coa_status, released_traceability_code
        - Cost: rate, amount, allocated_cost, cost_per_kg
    """
    pass
