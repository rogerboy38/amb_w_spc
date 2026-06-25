import frappe
from frappe import _
from datetime import timedelta, datetime

# --- helpers ---

_TAG_PRIORITY = [
    ("for_microbiology",  "Microbiological Analysis Sample"),
    ("for_customer",      "Customer Retention Sample"),
    ("for_distributor",   "Distributor Retention Sample"),
    ("for_retention",     "AMB Wellness Retention"),
    ("for_external_lab",  "External Lab Sample"),
]


def _resolve_item(batch) -> str:
    """Return Item code from Batch AMB, with fallback chain."""
    for fld in ("item_on_batch", "current_item_code", "original_item_code"):
        v = getattr(batch, fld, None)
        if v:
            return v
    return ""


def _infer_sample_tag(item_code: str, batch_name: str) -> str:
    """
    Look up any Sample Request AMB Item rows that link to this batch's item
    via the parent Sample Request AMB's batch_reference field. Return the first
    matching priority tag, or "" if none.

    Implemented as a raw DB query so this app does NOT need to import the
    Sample Request AMB doctype (it lives in amb_w_tds).
    """
    if not item_code:
        return ""
    try:
        rows = frappe.db.sql(
            """
            SELECT s.for_microbiology, s.for_customer, s.for_distributor,
                   s.for_retention, s.for_external_lab
            FROM `tabSample Request AMB Item` s
            INNER JOIN `tabSample Request AMB` p ON s.parent = p.name
            WHERE p.batch_reference = %s
              AND s.item = %s
            ORDER BY p.modified DESC
            LIMIT 1
            """,
            (batch_name, item_code),
            as_dict=True,
        )
    except Exception:
        # Sample Request AMB lives in amb_w_tds; if not installed, skip silently
        return ""
    if not rows:
        return ""
    r = rows[0]
    for flag_name, tag_value in _TAG_PRIORITY:
        if r.get(flag_name):
            return tag_value
    return ""


def _format_dmy(d) -> str:
    """Format date or datetime as dd/mm/yy."""
    if not d:
        return ""
    if isinstance(d, str):
        try:
            d = datetime.strptime(d[:10], "%Y-%m-%d")
        except Exception:
            return ""
    return d.strftime("%d/%m/%y")


# --- public API ---

@frappe.whitelist()
def generate_label_cells_for_batch(batch_name: str) -> dict:
    """
    Walks Batch AMB's Container Barrels rows and fills label_* fields where they
    are currently empty. Existing non-empty values are preserved.

    Uses frappe.db.set_value with update_modified=False so we do NOT:
      - trigger Batch AMB's validate() (which recomputes weights)
      - publish a doc_update realtime event (which can hide the Save button)
      - bump the parent's modified timestamp

    Returns: {"updated": int, "skipped_existing": int, "no_item": bool, "warning": str|None}
    """
    if not batch_name:
        frappe.throw(_("Batch AMB name is required"))

    # Fetch only the parent-level fields we need (avoid loading child tables)
    batch_top = frappe.db.get_value(
        "Batch AMB",
        batch_name,
        ["name", "item_on_batch", "current_item_code", "original_item_code",
         "expiry_date", "creation", "custom_golden_number"],
        as_dict=True,
    )
    if not batch_top:
        frappe.throw(_("Batch AMB {0} not found").format(batch_name))

    # Item resolution (item_on_batch -> current_item_code -> original_item_code)
    item_code = ""
    for fld in ("item_on_batch", "current_item_code", "original_item_code"):
        v = batch_top.get(fld)
        if v:
            item_code = v
            break

    item_name = ""
    shelf_life_days = 0
    if item_code:
        item_data = frappe.db.get_value(
            "Item", item_code,
            ["item_name", "shelf_life_in_days"],
            as_dict=True,
        )
        if item_data:
            item_name = item_data.get("item_name") or ""
            shelf_life_days = int(item_data.get("shelf_life_in_days") or 0)

    # M.D. from batch.creation
    md_date = batch_top.get("creation")
    if isinstance(md_date, str):
        try:
            md_date = datetime.strptime(md_date[:10], "%Y-%m-%d")
        except Exception:
            md_date = None
    md_str = _format_dmy(md_date)

    # E.D.: M.D. + shelf_life_in_days, fallback batch.expiry_date
    ed_str = ""
    if md_date and shelf_life_days:
        ed_date = md_date + timedelta(days=shelf_life_days)
        ed_str = _format_dmy(ed_date)
    elif batch_top.get("expiry_date"):
        ed_str = _format_dmy(batch_top["expiry_date"])

    # Sample tag inference (same helper as before)
    inferred_tag = _infer_sample_tag(item_code, batch_name)

    # LOTE = Golden Number (fallback to batch name)
    lot_value = batch_top.get("custom_golden_number") or batch_name

    # Pull only the label_* fields we need to compare against
    rows = frappe.db.get_all(
        "Container Barrels",
        filters={"parent": batch_name, "parenttype": "Batch AMB"},
        fields=["name", "label_item_name", "label_lot",
                "label_manufacture_date", "label_expiration_date",
                "label_sample_tag", "label_is_active"],
        order_by="idx",
    )

    updated = 0
    skipped_existing = 0

    for row in rows:
        updates = {}

        # Per-field fill-when-empty
        if not row.get("label_item_name") and item_name:
            updates["label_item_name"] = item_name
        elif row.get("label_item_name"):
            skipped_existing += 1

        if not row.get("label_lot") or row.get("label_lot") == batch_name:
            updates["label_lot"] = lot_value

        if not row.get("label_manufacture_date") and md_str:
            updates["label_manufacture_date"] = md_str

        if not row.get("label_expiration_date") and ed_str:
            updates["label_expiration_date"] = ed_str

        if not row.get("label_sample_tag") and inferred_tag:
            updates["label_sample_tag"] = inferred_tag

        if row.get("label_is_active") is None:
            updates["label_is_active"] = 1

        if updates:
            frappe.db.set_value(
                "Container Barrels",
                row["name"],
                updates,
                update_modified=False,
            )
            updated += len(updates)

    warning = None
    if not item_code:
        warning = _("No Item linked on this Batch — item_name and expiration_date were not filled. Set item_on_batch and re-run.")

    return {
        "updated": updated,
        "skipped_existing": skipped_existing,
        "no_item": not item_code,
        "warning": warning,
    }


@frappe.whitelist()
def get_print_format_for_batch(batch_name: str) -> dict:
    """
    Inspect container_barrels[*].barrel_serial_number prefixes to recommend
    the right Print Designer format.

    SMP-prefix -> "Label Small 8 (Container)"  (8 cells per page)
    BRL-prefix -> "Label 4 (Container)"        (4 cells per page, with barcode)
    Mixed     -> returns "mixed" with a warning
    Unknown   -> "" with a warning

    Returns: {"format_name": str, "prefix": str, "warning": str|None}
    """
    if not batch_name:
        frappe.throw(_("Batch AMB name is required"))

    rows = frappe.db.sql(
        """
        SELECT barrel_serial_number FROM `tabContainer Barrels`
        WHERE parent = %s AND parenttype = 'Batch AMB'
          AND IFNULL(label_is_active, 1) = 1
        """,
        (batch_name,),
        as_dict=True,
    )
    serials = [r.get("barrel_serial_number") or "" for r in rows]
    serials = [s for s in serials if s]

    if not serials:
        return {"format_name": "", "prefix": "", "warning": _("No active barrels to print.")}

    prefixes = set()
    for s in serials:
        upper = s.upper()
        if upper.startswith("SMP"):
            prefixes.add("SMP")
        elif upper.startswith("BRL"):
            prefixes.add("BRL")
        elif upper.startswith("CTE"):
            prefixes.add("CTE")
        else:
            prefixes.add("OTHER")

    if len(prefixes) > 1:
        return {
            "format_name": "mixed",
            "prefix": ",".join(sorted(prefixes)),
            "warning": _("Barrels have mixed prefixes ({0}); split into separate prints or pick a format manually.").format(",".join(sorted(prefixes))),
        }

    prefix = prefixes.pop()
    if prefix == "SMP":
        return {"format_name": "Label Small 8 (Container)", "prefix": "SMP", "warning": None}
    if prefix == "BRL":
        return {"format_name": "Label 4 (Container)", "prefix": "BRL", "warning": None}
    if prefix == "CTE":
        return {"format_name": "Label 8 (Cunete)", "prefix": "CTE", "warning": None}
    return {"format_name": "", "prefix": "OTHER", "warning": _("Unknown serial prefix; pick a format manually.")}
