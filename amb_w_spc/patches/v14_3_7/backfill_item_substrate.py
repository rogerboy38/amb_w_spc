"""Task #70: layered backfill for Item.substrate (Path Y substrate codification).

Rules layered per Alicia 2026-05-29 + cross-tab data analysis:
  Phase 0 — LBL prefix → null (label items, not products)
  Phase 6 — non-product item_groups → null
  Phase 3a — ITEM_XXXX extended → inherit from base item; fall through to other
             rules using the BASE code (not the ITEM_ name) if base substrate
             is empty
  Phase 3b — MIG_QITEM orphans → null (Task #71 cleanup target)
  Phase 3c — A03XX pre-analysis powder → PWD
  Phase 1 — series family from Alicia 2023 codification (03/04/05/09/10/11/13 →
            PWD; 06 → PWDF; 12 → PWD low-arsenic; 07 → split by sub: 1,5 → LQD,
            2-4,6-8 → LQDC, 9-16 → LQDF)
  Phase 1b — 0227 family + name parsing (CONCENTRATE/JUICE keywords, -30X / -1X
             suffix structure)
  Phase 2 — item_group own name (powder/dry 200/aloin powder tokens → PWD;
            liquid/juice/gel → LQD)
  Tiebreaker — Item.custom_plant_code1 + Item.custom_concentration_type
               (existing CFs, distinct values Mix/Dry/Juice/Laboratory/Formulated
               for plant; 1X/10X/20X/30X/200X for concentration)

Empty-when-unsure (Hugh 2026-05-29): if no rule concludes, substrate = NULL.
Picker handles NULL gracefully (no filter applied; full parameter list shown).

Self-bootstrap: Frappe runs patches BEFORE post-fixture sync, so the
Item.substrate CustomField may not yet be installed. Create it if missing
(per [[feedback-link-target-must-exist-or-feature-silent-fails]] L171
defensive pattern); fixture sync immediately after the patch will re-assert it
with the same shape — idempotent.

Idempotency: per-item check that derived value differs from current before
write. Re-running this patch with no DB drift produces zero writes.
"""
import re

import frappe


NON_PRODUCT_GROUPS = {
    "Chemicals", "Consumables", "Raw Materials", "Sample Packaging Materials",
    "Transport", "Utilities", "FG Packaging Materials", "0227-Services",
    "Spare Parts", "Additives", "Analysis", "Labor", "Enzymes",
    "Fresh Raw Materiales", "Subcontracting Dry", "Miscellaneous",
}


def _ensure_custom_field():
    """Bootstrap Item.substrate CF if the fixture sync hasn't run yet."""
    if frappe.db.exists("Custom Field", {"dt": "Item", "fieldname": "substrate"}):
        return False
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    create_custom_field("Item", {
        "fieldname": "substrate",
        "label": "Substrate",
        "fieldtype": "Link",
        "options": "Substrate",
        "insert_after": "custom_concentration_type",
        "module": "Core SPC",
        "in_list_view": 1,
        "in_standard_filter": 1,
        "description": "Material substrate (LQD/LQDC/LQDF/PWD/PWDF). "
                       "Empty = indeterminate; assign manually when building TDS.",
    })
    frappe.db.commit()
    frappe.clear_cache(doctype="Item")
    return True


def derive_substrate(item, current_substrate_map):
    """Return derived substrate code (string) or None.

    `current_substrate_map` is a dict {item_name: substrate or None} used for
    Phase 3a base-item inheritance lookup. Built from the live DB snapshot
    before this run, so order-of-iteration doesn't matter — an ITEM_ pointing
    at a base whose substrate is set in DB will read it via the map.
    """
    name = item.get("name") or ""
    ig = item.get("item_group") or ""
    item_name = (item.get("item_name") or "").upper()
    plant = (item.get("custom_plant_code1") or "").strip()
    conc = (item.get("custom_concentration_type") or "").strip()

    # Phase 0: LBL prefix
    if name.startswith("LBL"):
        return None

    # Phase 6: Non-product item_groups
    if ig in NON_PRODUCT_GROUPS:
        return None

    # Phase 3a: ITEM_XXXX extended — inherit from base; fall through using base code
    name_for_rules = name
    if name.startswith("ITEM_"):
        parts = name.split("_")
        if len(parts) >= 2:
            base_code = parts[1][:4]
            base_substrate = current_substrate_map.get(base_code)
            if base_substrate:
                return base_substrate
            name_for_rules = base_code

    # Phase 3b: MIG_QITEM orphans
    if name.startswith("MIG_QITEM"):
        return None

    # Phase 3c: A03XX pre-analysis powder
    if re.match(r"^A03\d{2}", name_for_rules):
        return "PWD"

    # Phase 1: Series family from Alicia 2023 codification.
    #
    # Brief proposed `^0?(\d{2})(\d{2})` but Python's greedy `0?` mis-routes
    # 10+ digit sublot derivations: "0303042251" matches as fam="30" sub="30"
    # instead of fam="03" sub="03" because greedy 0? consumes the leading
    # zero, and the overall regex succeeds without backtracking. Result:
    # sublot-derivation items in Products group (61 such items on VM3 audit)
    # fall through Phase 1, miss Phase 2 token match ("Products" lacks
    # powder/liquid token), and land on tiebreaker Mix-plant → PWDF when they
    # should match their 4-char base's family rule.
    #
    # Fix: take literal first-4-char window as fam(2) + sub(2). Leading zeros
    # always live inside fam. Sublot derivations route through the same family
    # rule as their 4-char base. Verified across all 7 sample anchors.
    m = re.match(r"^(\d{2})(\d{2})", name_for_rules)
    if m:
        fam = m.group(1)
        sub = m.group(2)
        if fam in ("03", "04", "05", "09", "10", "11", "13"):
            return "PWD"
        if fam == "06":
            return "PWDF"
        if fam == "12":
            return "PWD"  # low-arsenic powder
        if fam == "07":
            sub_num = int(sub) if sub.isdigit() else 0
            if sub_num in (1, 5):
                return "LQD"
            if 2 <= sub_num <= 4 or 6 <= sub_num <= 8:
                return "LQDC"
            if 9 <= sub_num <= 16:
                return "LQDF"

    # Phase 1b: 0227 family + name parsing
    if name_for_rules.startswith("0227"):
        if "CONCENTRATE" in item_name or "CONCENTRADO" in item_name:
            return "LQDC"
        if "JUICE" in item_name or "JUGO" in item_name:
            return "LQD"
        if "-30" in name_for_rules:
            return "LQDC"
        if "-1" in name_for_rules:
            return "LQD"

    # Phase 2: Item Group own name tokens
    ig_lower = ig.lower()
    if any(t in ig_lower for t in ("powder", "dry 200", "aloin powder")):
        return "PWD"
    if any(t in ig_lower for t in ("liquid", "juice", "gel")):
        return "LQD"

    # Tiebreaker: Plant + Concentration
    if plant == "Mix" and conc == "200X":
        return "PWD"
    if plant == "Mix":
        return "PWDF"
    if plant == "Dry":
        return "PWD"
    if plant == "Juice":
        if conc == "1X" or not conc:
            return "LQD"
        if conc in ("10X", "20X", "30X"):
            return "LQDC"
    if plant == "Formulated":
        return "PWDF" if conc == "200X" else "LQDF"
    if plant == "Laboratory":
        if conc == "200X":
            return "PWD"

    return None


def execute():
    bootstrapped = _ensure_custom_field()
    if bootstrapped:
        print("Path Y backfill: self-bootstrapped Item.substrate CustomField "
              "(fixture sync had not yet installed it).")

    # Snapshot all items. Sort so non-ITEM_ items derive FIRST and update
    # current_map as we go — ITEM_ items at the end can then inherit from the
    # freshly-derived base substrates in the same pass. This makes the patch
    # idempotent: a second run sees the converged state and produces 0 writes.
    # (Without ordered single-pass propagation, ITEM_ items' Phase 3a inheritance
    # reads a start-of-run snapshot where bases are still NULL, falls through to
    # default rules, then converges on a SECOND run when the snapshot includes
    # the bases' new substrates — non-idempotent.)
    items = frappe.db.sql(
        """
        SELECT name, item_name, item_group,
               custom_plant_code1, custom_concentration_type, substrate
        FROM `tabItem`
        WHERE disabled = 0
        """,
        as_dict=True,
    )
    items.sort(key=lambda it: (1 if (it.name or "").startswith("ITEM_") else 0, it.name or ""))
    current_map = {it.name: it.substrate for it in items}

    writes = 0
    null_to_value = 0
    value_to_value = 0
    unchanged = 0

    for it in items:
        derived = derive_substrate(it, current_map)
        if derived == it.substrate:
            unchanged += 1
            continue
        # Only write when value actually changes
        frappe.db.set_value("Item", it.name, "substrate", derived, update_modified=False)
        # Propagate the new value into the in-memory map so subsequent ITEM_
        # extended items can inherit from it in the same pass.
        current_map[it.name] = derived
        writes += 1
        if it.substrate is None:
            null_to_value += 1
        else:
            value_to_value += 1

    frappe.db.commit()

    # Distribution probe
    dist = dict(frappe.db.sql(
        """
        SELECT IFNULL(substrate, 'NULL'), COUNT(*)
        FROM `tabItem` WHERE disabled = 0
        GROUP BY substrate
        """
    ))

    print(
        f"Path Y backfill: scanned {len(items)} items; "
        f"{writes} writes ({null_to_value} NULL->set, {value_to_value} value->value), "
        f"{unchanged} already-correct."
    )
    print(f"Path Y distribution: {dist}")
