"""D1a golden-number generator — Phase 1 item 1.3 (plan 2026-07-05).

Golden lot code: ``CCCC FFF YY P`` (10 digits)
  CCCC  product code — first 4 chars of item_to_manufacture
  FFF   consecutive  — per (CCCC, YY) counter, self-seeded from the
        historical maximum across ALL three registers (lot-items,
        native Batches, Batch AMB goldens); replaces the legacy
        WO-number-derived consecutive
  YY    2-digit year (WO start date, else today)
  P     plant code (1 Mix · 2 Dry · 3 Juice · 4 Laboratory · 5 Formulated)

Collision surface (D1a, design §2): a candidate golden is rejected if it
already exists as a lot-item name (bare ``0705110231`` or prefixed
``ITEM_0705110231``), as a native Batch batch_id/name (including sub-lot
ids ``<golden>-N``), or as another Batch AMB's golden number.

All queries are read-only; generation itself never writes.
"""

import re

import frappe
from frappe import _

GOLDEN_RE = re.compile(r"^\d{10}$")

#: plant name → plant digit (design §4b D2)
PLANT_CODE_MAP = {
    "mix": "1",
    "dry": "2",
    "juice": "3",
    "laboratory": "4",
    "formulated": "5",
}


class GoldenNumberError(frappe.ValidationError):
    pass


def extract_product_code(item_code):
    """CCCC = first 4 characters of the item code, zero-padded."""
    code = (item_code or "").strip()[:4]
    return code.zfill(4) if code else ""


def normalize_year(yy):
    return str(yy or "").strip()[-2:].zfill(2)


def normalize_plant_code(plant_code):
    """Single leading digit only (strips suffixes like ``3 (Juice)``)."""
    m = re.match(r"\d", str(plant_code or "").strip())
    return m.group() if m else "1"


def _max_fff(cccc, yy):
    """Historical max FFF for (CCCC, YY) across the three registers.

    Re-runs the 2026-07-05 historical-max SUBSTR survey at generation
    time, so the counter is always seeded from live data and needs no
    stored state.
    """
    pattern_core = f"^{cccc}[0-9]{{3}}{yy}[0-9]"
    queries = (
        # bare 10-digit lot-item names
        ("SELECT MAX(CAST(SUBSTR(name, 5, 3) AS UNSIGNED)) FROM `tabItem` "
         "WHERE name REGEXP %s", pattern_core + "$"),
        # ITEM_-prefixed lot-item names
        ("SELECT MAX(CAST(SUBSTR(name, 10, 3) AS UNSIGNED)) FROM `tabItem` "
         "WHERE name REGEXP %s", "^ITEM_" + pattern_core[1:] + "$"),
        # native Batch ids, including sub-lot ids <golden>-N
        ("SELECT MAX(CAST(SUBSTR(batch_id, 5, 3) AS UNSIGNED)) FROM `tabBatch` "
         "WHERE batch_id REGEXP %s", pattern_core + "(-[0-9]+)?$"),
        # Batch AMB golden numbers
        ("SELECT MAX(CAST(SUBSTR(custom_golden_number, 5, 3) AS UNSIGNED)) "
         "FROM `tabBatch AMB` WHERE custom_golden_number REGEXP %s",
         pattern_core + "$"),
    )
    max_fff = 0
    for sql, pattern in queries:
        value = frappe.db.sql(sql, (pattern,))[0][0]
        if value and int(value) > max_fff:
            max_fff = int(value)
    return max_fff


def next_consecutive(cccc, yy):
    """Next FFF for (CCCC, YY): historical max across all registers + 1."""
    return _max_fff(cccc, normalize_year(yy)) + 1


def has_collision(golden, exclude_batch_amb=None):
    """True if `golden` is already taken in any register (D1a check)."""
    if frappe.db.exists("Item", golden) or frappe.db.exists("Item", f"ITEM_{golden}"):
        return True
    if frappe.db.exists("Batch", golden) or frappe.db.exists("Batch", {"batch_id": golden}):
        return True
    # sub-lot ids <golden>-N also reserve the golden
    if frappe.db.sql(
        "SELECT name FROM `tabBatch` WHERE batch_id LIKE %s LIMIT 1",
        (golden + "-%",),
    ):
        return True
    holder = frappe.db.get_value("Batch AMB", {"custom_golden_number": golden}, "name")
    if holder and holder != exclude_batch_amb:
        return True
    return False


def generate_golden_number(item_code, plant_code, yy=None, exclude_batch_amb=None):
    """Mint the next free golden number for (item family, year, plant).

    The FFF counter is scoped to (CCCC, YY) — the plant digit does not
    partition the sequence. Candidates are advanced past collisions.
    """
    cccc = extract_product_code(item_code)
    if not cccc:
        frappe.throw(_("Cannot generate golden number without an item code"),
                     GoldenNumberError)
    yy = normalize_year(yy or frappe.utils.nowdate()[2:4])
    plant = normalize_plant_code(plant_code)

    fff = next_consecutive(cccc, yy)
    while fff <= 999:
        golden = f"{cccc}{str(fff).zfill(3)}{yy}{plant}"
        if not has_collision(golden, exclude_batch_amb=exclude_batch_amb):
            return golden
        fff += 1
    frappe.throw(
        _("Golden number consecutive exhausted for family {0} year {1}").format(cccc, yy),
        GoldenNumberError,
    )
