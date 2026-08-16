"""D1a golden-number generator — Phase 1 item 1.3 (plan 2026-07-05).

Golden lot code: ``CCCC FFF YY P`` (10 digits)
  CCCC  product code — first 4 chars of item_to_manufacture
  FFF   consecutive  — per (CCCC, YY) counter, self-seeded from the
        historical maximum across ALL three registers (lot-items,
        native Batches, Batch AMB goldens); replaces the legacy
        WO-number-derived consecutive
  YY    2-digit year — THE MINT CLOCK (Q-G ruled b, 2026-08-16): the year
        the lot identity comes into existence; never a WO date
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

GOLDEN_RE = re.compile(r"^\d{10}$", re.ASCII)

#: sub-lot batch id shape ``<golden>-N`` (design §4b D2)
SUBLOT_ID_RE = re.compile(r"^\d{10}-\d+$", re.ASCII)

#: Rung 4 fuse floor — the OLDEST legacy YY observed across all four golden
#: registers (bare items 20-25 · ITEM_-prefixed 20-25 · native Batches 23-26
#: · Batch AMB 23/26; measured 2026-08-16 on the bench copy of prod, GATE-0
#: re-confirms on prod at ship time). Legacy YY is never reinterpreted (K3);
#: the fuse discriminates format, it rewrites nothing.
GOLDEN_YY_FLOOR = 20


def mint_year_yy():
    """THE mint clock (Q-G ruled b): YY = the year the identity is minted."""
    from datetime import datetime
    return datetime.now().strftime("%y")


def yy_in_window(yy):
    """Self-maintaining year fuse: GOLDEN_YY_FLOOR <= YY <= next year.

    The UPPER bound is derived from the clock at call time — never a
    hardcoded ceiling that rots. Non-numeric input is simply out of window.
    """
    from datetime import datetime
    try:
        val = int(str(yy))
    except (TypeError, ValueError):
        return False
    return GOLDEN_YY_FLOOR <= val <= (datetime.now().year + 1) % 100


def wo_tail_consecutive(wo_ref):
    """FFF candidate from a WO reference: [:3] of the FINAL hyphen segment
    (the counter under the deployed series MFG-WO-.###.YY.) — FIXED: [:3],
    never [-3:]. Empty/odd input degrades to \"001\", as at both mint sites."""
    try:
        parts = (wo_ref or "").split("-")
        last_part = parts[-1] if parts else ""
        return (last_part[:3] if last_part else "001").zfill(3)
    except Exception:
        return "001"

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
