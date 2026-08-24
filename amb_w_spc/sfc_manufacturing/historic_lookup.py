# Copyright (c) 2026, AMB and contributors
"""B-3b item 2 — resolve any HISTORIC number to its current Batch AMB.

⭐ QUERIES BOTH CARRIERS (I-3). A historic number may be a `lote_real` (the
scalar) or a `lote_de_venta` (a child-table row), and an operator holding a
number off an old document does not know which they have. A lookup that reads
only the scalar answers "not found" for every sales lot — a false negative that
reads exactly like a genuine absence.

⛔ ADDITIVE AND READ-ONLY. It resolves; it never mints, derives or writes.
"""

import frappe

BATCH = "Batch AMB"
CHILD = "Batch Historic Sales Lot"


def resolve_historic_number(number, include_golden=False):
    """Return the matching Batch AMB names with WHERE each match was found.

    Returns `{"scalar": [...], "sales_lot": [...], "golden": [...]}`.

    ⚠ The carrier is returned, not just the names. "Found" is not one fact:
    a number matching a `lote_real` means this lot WAS that lot; a number
    matching a sales lot means this lot was SOLD AS that. Collapsing them into
    one list would answer a question nobody asked.

    ⚠ `include_golden` is off by default and is not a historic carrier — it is
    offered only so a caller can tell "this is a current golden, not a historic
    number" apart from "no match anywhere", which are different answers.
    """
    value = (number or "").strip()
    out = {"scalar": [], "sales_lot": [], "golden": []}
    if not value:
        return out

    out["scalar"] = [
        r[0] for r in frappe.db.sql(
            f"select name from `tab{BATCH}` where custom_historic_lot_real = %s", (value,)
        )
    ]
    out["sales_lot"] = [
        r[0] for r in frappe.db.sql(
            f"""select distinct parent from `tab{CHILD}`
                where sales_lot = %s and parenttype = %s""", (value, BATCH)
        )
    ]
    if include_golden:
        out["golden"] = [
            r[0] for r in frappe.db.sql(
                f"select name from `tab{BATCH}` where custom_golden_number = %s", (value,)
            )
        ]
    return out


def find_batch(number):
    """The single-answer convenience: one Batch AMB name, or None.

    ⛔ Returns None when the number matches MORE THAN ONE batch. An ambiguous
    historic number is a finding, not a value to pick from — silently taking the
    first would attach a document to whichever row sorted first.
    """
    hits = resolve_historic_number(number)
    names = set(hits["scalar"]) | set(hits["sales_lot"])
    return names.pop() if len(names) == 1 else None
