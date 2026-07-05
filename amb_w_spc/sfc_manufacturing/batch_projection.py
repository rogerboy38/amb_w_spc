"""Batch AMB → native Batch projection core — Phase 1 (plan 2026-07-05 §2).

Contract (design doc §1, D2-final §4b):
  * Batch AMB is the controller / aggregate root; native ERPNext Batch is a
    one-way, read-only projection it emits.
  * Projection source = ``Batch Output Product`` rows on the STOCK-CARRYING
    level (L2 sub-lot). One stocked output row = one native Batch.
  * batch_id = row.output_golden_number, else row.output_traceability_code,
    else (single-output sub-lots only) ``<golden>-N``.
  * Nothing but the controller writes native Batch (validate-hook guard +
    read-only permissions). Projected batches are disabled, never deleted.

Behavior flag (transport "inert first" pattern, plan §5.1/§6.3):
  site_config ``batch_amb_projection_enabled`` — 0/absent = fully inert
  (no projection, no guard: legacy behavior byte-identical).
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate

from amb_w_spc.sfc_manufacturing.golden_number import GOLDEN_RE, SUBLOT_ID_RE

#: only sub-lots (L2) carry stock — the level guard (design §4b)
STOCK_CARRYING_LEVEL = "2"

#: Batch AMB has two Table fields pointing at Batch Output Product
OUTPUT_TABLE_FIELDS = ("output_products", "batch_output_products")

#: frappe.flags / doc.flags key that marks controller-originated writes
CONTROLLER_FLAG = "batch_amb_controller"


class BatchControllerGuardError(frappe.ValidationError):
    pass


def is_projection_enabled():
    return bool(cint(frappe.conf.get("batch_amb_projection_enabled")))


# ---------------------------------------------------------------------------
# 1.4 controller-only guard (doc_events: Batch.validate)
# ---------------------------------------------------------------------------

def batch_controller_guard(doc, method=None):
    """Reject any native Batch create/edit that does not come from the
    controller (or from framework maintenance contexts)."""
    if not is_projection_enabled():
        return
    if frappe.flags.get(CONTROLLER_FLAG) or doc.flags.get(CONTROLLER_FLAG):
        return
    if (
        frappe.flags.in_migrate
        or frappe.flags.in_patch
        or frappe.flags.in_install
        or frappe.flags.in_fixtures
        or frappe.flags.in_setup_wizard
    ):
        return
    frappe.throw(
        _(
            "Native Batch is a read-only projection emitted by Batch AMB "
            "(controller-only guard, Phase 1 item 1.4). Create or edit the "
            "lot in Batch AMB instead."
        ),
        BatchControllerGuardError,
    )


# ---------------------------------------------------------------------------
# 1.2 projection (doc_events: Batch AMB.after_insert / on_update)
# ---------------------------------------------------------------------------

def project_batch_amb_outputs(doc, method=None):
    """Project native Batches from the stocked output rows of a sub-lot.

    Idempotent: re-firing on the same document finds the existing Batch
    (via row.batch_no, then Batch.custom_batch_output_row, then batch_id)
    and syncs instead of duplicating. Level guard: only L2 emits.
    """
    if not is_projection_enabled():
        return
    if str(doc.custom_batch_level or "") != STOCK_CARRYING_LEVEL:
        return  # level guard — L1/L3/L4 never emit batches
    rows = _stocked_output_rows(doc)
    results = []
    for row in rows:
        results.append(_project_output_row(doc, row, single_output=len(rows) == 1))
    _update_projection_summary(doc.name)
    return results


def _stocked_output_rows(doc):
    rows, seen = [], set()
    for table_field in OUTPUT_TABLE_FIELDS:
        for row in doc.get(table_field) or []:
            if row.name in seen:
                continue
            seen.add(row.name)
            if row.item_code and flt(row.quantity_kg) > 0 and (row.quality_status or "") != "Rejected":
                rows.append(row)
    return rows


def _sublot_suffix(doc):
    """N in ``<golden>-N``: sublot consecutive, else title suffix, else 1."""
    n = cint(doc.get("custom_sublot_consecutive"))
    if n:
        return n
    golden = doc.custom_golden_number or ""
    title = doc.title or ""
    if golden and title.startswith(golden + "-"):
        tail = title[len(golden) + 1:].split("-")[0]
        if tail.isdigit():
            return int(tail)
    return 1


def _resolve_batch_id(doc, row, single_output):
    supplied = (row.output_golden_number or "").strip() or (row.output_traceability_code or "").strip()
    if supplied:
        # F2 (audit 2026-07-05): a row-supplied id becomes the immutable
        # native Batch name (guard blocks edits, tombstone never deletes) —
        # validate the shape and reject with an honest error. No silent
        # fallthrough past a malformed value, no minting unvalidated names.
        if GOLDEN_RE.match(supplied) or SUBLOT_ID_RE.match(supplied):
            return supplied, None
        return None, (
            "row-supplied batch id {0!r} matches neither the golden shape "
            "CCCCFFFYYP nor <golden>-N — row not projected; fix the output "
            "row (it will surface as an AMB→native orphan in "
            "batch-amb-reconcile until then)".format(supplied)
        )
    golden = (doc.custom_golden_number or "").strip()
    if single_output and GOLDEN_RE.match(golden):
        return f"{golden}-{_sublot_suffix(doc)}", None
    return None, (
        "no output_golden_number/output_traceability_code and the "
        "<golden>-N fallback only applies to single-output sub-lots"
    )


def _projection_dates(doc, row):
    mfg = getdate(doc.get("wo_start_date") or doc.get("manufacturing_date") or doc.creation)
    expiry = row.expiry_date
    if not expiry and row.item_code:
        shelf_life = cint(frappe.db.get_value("Item", row.item_code, "shelf_life_in_days"))
        if shelf_life:
            expiry = add_days(mfg, shelf_life)
    return mfg, expiry


def _find_existing_batch(row, batch_id):
    if row.batch_no and frappe.db.exists("Batch", row.batch_no):
        return row.batch_no
    return (
        frappe.db.get_value("Batch", {"custom_batch_output_row": row.name})
        or (batch_id and frappe.db.get_value("Batch", {"batch_id": batch_id}))
        or None
    )


def _golden_decomposition(batch_id, doc):
    golden = batch_id.split("-")[0] if batch_id else ""
    if not GOLDEN_RE.match(golden):
        golden = (doc.custom_golden_number or "").strip()
    if not GOLDEN_RE.match(golden):
        return {}
    return {
        "custom_golden_number": golden,
        "custom_product_family": golden[0:2],
        "custom_subfamily": golden[2:4],
        "custom_consecutive": golden[4:7],
        "custom_batch_year": golden[7:9],
        "custom_plant_code": golden[9],
    }


def _project_output_row(doc, row, single_output):
    """Create or sync ONE native Batch for one stocked output row."""
    batch_id, skip_reason = _resolve_batch_id(doc, row, single_output)
    if not batch_id:
        return {"row": row.name, "action": "skipped", "reason": skip_reason}

    mfg, expiry = _projection_dates(doc, row)
    field_values = {
        "item": row.item_code,
        "manufacturing_date": mfg,
        "expiry_date": expiry,
        # a live output row means a live batch — re-adopting a previously
        # tombstoned/disabled batch re-enables it (controller is truth)
        "disabled": 0,
        "reference_doctype": "Batch AMB",
        "reference_name": doc.name,
        "custom_batch_amb": doc.name,
        "custom_batch_output_row": row.name,
    }
    field_values.update(_golden_decomposition(batch_id, doc))

    existing = _find_existing_batch(row, batch_id)
    if existing:
        batch = frappe.get_doc("Batch", existing)
        # item is identity once SLEs may exist — sync dates/links only
        changed = {}
        for fieldname, value in field_values.items():
            if fieldname == "item":
                continue
            current = batch.get(fieldname)
            if (current or None) != (value or None) and str(current or "") != str(value or ""):
                changed[fieldname] = value
        if changed:
            batch.flags[CONTROLLER_FLAG] = True
            batch.update(changed)
            batch.save(ignore_permissions=True)
        action = "synced" if changed else "unchanged"
    else:
        batch = frappe.new_doc("Batch")
        batch.batch_id = batch_id
        batch.update(field_values)
        batch.flags[CONTROLLER_FLAG] = True
        batch.insert(ignore_permissions=True)
        action = "created"

    if row.batch_no != batch.name:
        frappe.db.set_value(
            "Batch Output Product", row.name, "batch_no", batch.name,
            update_modified=False,
        )
        row.batch_no = batch.name

    return {"row": row.name, "action": action, "batch": batch.name,
            "batch_id": batch.batch_id, "changed": sorted(changed) if existing else None}


def _update_projection_summary(batch_amb_name):
    """Maintain the read-only erpnext_batches counter on Batch AMB (1.1)."""
    count = frappe.db.count("Batch", {"custom_batch_amb": batch_amb_name})
    frappe.db.set_value(
        "Batch AMB", batch_amb_name, "erpnext_batches", count,
        update_modified=False,
    )


def disable_projected_batches(doc, method=None):
    """Batch AMB on_trash: disable (never delete) projected batches and
    tombstone the links so the AMB doc can be removed (design §1.4)."""
    if not is_projection_enabled():
        return
    for name in frappe.get_all("Batch", filters={"custom_batch_amb": doc.name}, pluck="name"):
        batch = frappe.get_doc("Batch", name)
        batch.flags[CONTROLLER_FLAG] = True
        batch.disabled = 1
        batch.description = (
            (batch.description or "")
            + f"\n[projection tombstone] controller Batch AMB {doc.name} deleted "
            + frappe.utils.now()
        ).strip()
        batch.custom_batch_amb = None
        batch.custom_batch_output_row = None
        batch.reference_doctype = None
        batch.reference_name = None
        batch.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# 1.5 backfill + BOM-F-0303 placeholder clear (bench execute entry points)
# ---------------------------------------------------------------------------

def backfill_projection(dry_run=1):
    """Project native Batches for existing Batch AMB sub-lots where output
    rows exist. Idempotent; dry-run reports the plan without writing.

    bench --site <site> execute \
        amb_w_spc.sfc_manufacturing.batch_projection.backfill_projection \
        --kwargs "{'dry_run': 1}"
    """
    dry_run = cint(dry_run)
    report = {
        "action": "backfill_projection",
        "dry_run": bool(dry_run),
        "enabled_flag": is_projection_enabled(),
        "timestamp": frappe.utils.now(),
        "docs": [],
    }
    for name in frappe.get_all(
        "Batch AMB", filters={"custom_batch_level": STOCK_CARRYING_LEVEL},
        order_by="name", pluck="name",
    ):
        doc = frappe.get_doc("Batch AMB", name)
        rows = _stocked_output_rows(doc)
        entry = {
            "batch_amb": name,
            "golden": doc.custom_golden_number,
            "eligible_output_rows": len(rows),
        }
        if not rows:
            entry["result"] = "skipped — no stocked output rows"
        elif dry_run:
            entry["result"] = [
                {"row": r.name, "item": r.item_code,
                 "batch_id": _resolve_batch_id(doc, r, single_output=len(rows) == 1)[0]}
                for r in rows
            ]
        else:
            entry["result"] = project_batch_amb_outputs(doc)
        report["docs"].append(entry)

    if not dry_run:
        frappe.db.commit()
    print(json.dumps(report, indent=2, default=str))
    return report


def clear_bom_formula_placeholder(dry_run=1, placeholder="BOM-F-0303"):
    """Clear the BOM-F-0303 placeholder from Batch AMB rows (plan 1.5).

    Downgraded cleanup per Hugh 2026-07-05 (design §4c): the field stays,
    the placeholder value goes; real BOM Formula links arrive with B1.
    """
    dry_run = cint(dry_run)
    rows = frappe.get_all(
        "Batch AMB", filters={"bom_formula": placeholder}, pluck="name", order_by="name"
    )
    report = {
        "action": "clear_bom_formula_placeholder",
        "placeholder": placeholder,
        "dry_run": bool(dry_run),
        "timestamp": frappe.utils.now(),
        "rows": rows,
        "cleared": 0,
    }
    if not dry_run:
        for name in rows:
            frappe.db.set_value("Batch AMB", name, "bom_formula", None,
                                update_modified=False)
            report["cleared"] += 1
        frappe.db.commit()
    print(json.dumps(report, indent=2, default=str))
    return report


# ---------------------------------------------------------------------------
# 1.1 schema setup (custom fields) + 1.4 permission tightening
# ---------------------------------------------------------------------------

def ensure_projection_schema():
    """Create the additive Phase 1 custom fields and tighten Batch perms.

    Idempotent (create_custom_fields upserts; perm updates are absolute).
    Run once on dev via bench execute, then export-fixtures captures the
    result for transport. Additive only — Batch AMB's 110 fields are not
    restructured (standing guidance, design §4c).
    """
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields({
        "Batch": [
            {
                "fieldname": "custom_projection_section",
                "fieldtype": "Section Break",
                "label": "Batch AMB Projection",
                "insert_after": "description",
                "collapsible": 1,
            },
            {
                "fieldname": "custom_batch_amb",
                "fieldtype": "Link",
                "options": "Batch AMB",
                "label": "Batch AMB (Controller)",
                "insert_after": "custom_projection_section",
                "read_only": 1,
                "in_standard_filter": 1,
            },
            {
                "fieldname": "custom_batch_output_row",
                "fieldtype": "Data",
                "label": "Batch Output Product Row",
                "insert_after": "custom_batch_amb",
                "read_only": 1,
            },
        ],
        "Batch AMB": [
            {
                "fieldname": "erpnext_batches",
                "fieldtype": "Int",
                "label": "ERPNext Batches",
                "insert_after": "custom_golden_number",
                "read_only": 1,
                "description": "Native Batches projected from this lot's output rows",
            },
        ],
    }, update=True)

    # golden P covers plants 1-5; the pre-existing Select stopped at 2
    plant_cf = frappe.db.get_value(
        "Custom Field", {"dt": "Batch", "fieldname": "custom_plant_code"},
        ["name", "options"], as_dict=True,
    )
    if plant_cf and plant_cf.options != "1\n2\n3\n4\n5":
        frappe.db.set_value("Custom Field", plant_cf.name, "options", "1\n2\n3\n4\n5")

    # 1.4 users read-only on native Batch: strip write/create/delete/submit
    # from every Custom DocPerm role row (the custom matrix replaces the
    # standard one). The controller writes with ignore_permissions.
    for perm in frappe.get_all("Custom DocPerm", filters={"parent": "Batch"}, pluck="name"):
        for right in ("write", "create", "delete", "submit", "amend"):
            frappe.db.set_value("Custom DocPerm", perm, right, 0, update_modified=False)

    frappe.clear_cache(doctype="Batch")
    frappe.clear_cache(doctype="Batch AMB")
    frappe.db.commit()
    print(json.dumps({
        "action": "ensure_projection_schema",
        "batch_custom_fields": frappe.get_all(
            "Custom Field", filters={"dt": "Batch"}, pluck="fieldname", order_by="fieldname"),
        "batch_amb_erpnext_batches": bool(frappe.db.exists(
            "Custom Field", {"dt": "Batch AMB", "fieldname": "erpnext_batches"})),
        "batch_docperms": frappe.get_all(
            "Custom DocPerm", filters={"parent": "Batch"},
            fields=["role", "read", "write", "create", "delete"]),
    }, indent=2, default=str))


# ---------------------------------------------------------------------------
# 1.6 reconciliation (read-only; wrapped by `bench batch-amb-reconcile`)
# ---------------------------------------------------------------------------

def reconcile():
    """AMB ↔ native diff: counts, orphans both ways, field drift.

    Read-only. Returns the healthcheck dict (JSON-safe)."""
    result = {
        "healthcheck": "batch-amb-reconcile",
        "timestamp": frappe.utils.now(),
        "projection_enabled": is_projection_enabled(),
        "counts": {},
        "orphans_amb_to_native": [],   # eligible output rows without a live native Batch
        "orphans_native_to_amb": [],   # projected Batches whose AMB anchor is gone
        "drift": [],                   # linked pairs whose fields disagree
    }

    sublots = frappe.get_all(
        "Batch AMB", filters={"custom_batch_level": STOCK_CARRYING_LEVEL},
        order_by="name", pluck="name",
    )
    eligible_rows = 0
    linked_rows = 0
    for name in sublots:
        doc = frappe.get_doc("Batch AMB", name)
        rows = _stocked_output_rows(doc)
        eligible_rows += len(rows)
        for row in rows:
            if not row.batch_no or not frappe.db.exists("Batch", row.batch_no):
                result["orphans_amb_to_native"].append({
                    "batch_amb": name, "row": row.name, "item": row.item_code,
                    "batch_no": row.batch_no or None,
                    "reason": "eligible output row has no live native Batch",
                })
                continue
            linked_rows += 1
            batch = frappe.db.get_value(
                "Batch",
                row.batch_no,
                ["name", "item", "manufacturing_date", "expiry_date",
                 "disabled", "custom_batch_amb", "custom_batch_output_row"],
                as_dict=True,
            )
            expected_mfg, expected_expiry = _projection_dates(doc, row)
            for check, got, want in (
                ("item", batch.item, row.item_code),
                ("custom_batch_amb", batch.custom_batch_amb, name),
                ("custom_batch_output_row", batch.custom_batch_output_row, row.name),
                ("manufacturing_date", str(batch.manufacturing_date or ""), str(expected_mfg or "")),
                ("expiry_date", str(batch.expiry_date or ""), str(expected_expiry or "")),
                ("disabled", cint(batch.disabled), 0),
            ):
                if got != want:
                    result["drift"].append({
                        "batch": batch.name, "batch_amb": name, "row": row.name,
                        "field": check, "native": got, "expected_from_amb": want,
                    })

    projected = frappe.get_all(
        "Batch", filters={"custom_batch_amb": ["is", "set"]},
        fields=["name", "batch_id", "custom_batch_amb", "custom_batch_output_row", "disabled"],
        order_by="name",
    )
    for batch in projected:
        problem = None
        if not frappe.db.exists("Batch AMB", batch.custom_batch_amb):
            problem = "custom_batch_amb points to a missing Batch AMB"
        elif batch.custom_batch_output_row and not frappe.db.exists(
            "Batch Output Product", batch.custom_batch_output_row
        ):
            problem = "custom_batch_output_row points to a missing output row"
        if problem:
            result["orphans_native_to_amb"].append({
                "batch": batch.name, "batch_id": batch.batch_id,
                "custom_batch_amb": batch.custom_batch_amb, "reason": problem,
            })

    result["counts"] = {
        "batch_amb_total": frappe.db.count("Batch AMB"),
        "batch_amb_sublots": len(sublots),
        "eligible_output_rows": eligible_rows,
        "output_rows_linked_to_live_batch": linked_rows,
        "native_batches_total": frappe.db.count("Batch"),
        "native_batches_projected": len(projected),
        "orphans_amb_to_native": len(result["orphans_amb_to_native"]),
        "orphans_native_to_amb": len(result["orphans_native_to_amb"]),
        "drift": len(result["drift"]),
    }
    result["clean"] = not (
        result["orphans_amb_to_native"] or result["orphans_native_to_amb"] or result["drift"]
    )
    return result
