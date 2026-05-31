"""Task #15 / Task #12 trailing fix — Diacetyl Rhein QIPG NSM reposition.

Context: vpt-docker browser-verify post-v14_3_10 + v14_3_11 surfaced that the
`Physicochemical Diacetyl Rhein` QIPG ends up with lft/rgt values OUTSIDE
`Physicochemical` L2's subtree range, even though:
  - custom_parameter_group_child = 'Physicochemical' (correct parent label)
  - old_parent = 'Physicochemical' (NSM audit field)
  - The QIPG controller (amb_w_spc/overrides/quality_inspection_parameter_group.py)
    declares `nsm_parent_field = "custom_parameter_group_child"` as a class attr
  - Property Setter `Quality Inspection Parameter Group-main-nsm_parent_field`
    sets the same field at DocType-meta level

Observed vpt-docker state per Hugh's report:
  - Physicochemical: lft=1390, rgt=1751
  - Physicochemical Diacetyl Rhein: lft=713, rgt=714 (OUTSIDE Physicochemical's subtree)

VM3 baseline (this site) was verified clean: Diacetyl Rhein at (713, 714) IS
INSIDE Physicochemical (462, 825). The bug is site-state-dependent; root cause
likely transport-timing related (insertion happened at one point in tree
evolution, subsequent rebuilds didn't re-place the node).

This patch is a defensive NSM-repositioning patch:
  - Idempotency-first: only fires if Diacetyl Rhein is actually outside
    Physicochemical's subtree (no-op on VM3 + any site already correct)
  - Conservative: uses Frappe's documented public NSM APIs only

Corrections to original L186 hypothesis ('use old_parent as parent_field'):
  1. `rebuild_tree()` in Frappe 16.17.5 takes ONE argument only — passing
     a second arg raises TypeError. Verified via inspect.signature on this
     bench + Task #11 commit `4d64e7a` patch comment which explicitly
     documents this trap.
  2. `old_parent` is an NSM AUDIT field (records the previous parent for
     change-detection), NOT the active parent pointer. The active parent
     field for QIPG is `custom_parameter_group_child` (per Property Setter +
     controller class attr). rebuild_tree reads this via meta.nsm_parent_field.
  3. The Property Setter `Quality Inspection Parameter Group-main-nsm_parent_field=
     custom_parameter_group_child` already configures rebuild_tree to use
     the correct field — so v14_3_11 STEP 5 used the CORRECT parent_field;
     the rebuild didn't reposition Diacetyl Rhein for a different reason.

Fix strategy:
  STEP 1 — Idempotency check: verify Diacetyl Rhein actually outside Physicochemical
  STEP 2 — Ensure Property Setter present + value correct (defensive, in case
           the fixture didn't apply on the target site)
  STEP 3 — Clear meta cache to ensure rebuild_tree reads latest Property Setter
  STEP 4 — rebuild_tree (Frappe 16.17.5 1-arg signature)
  STEP 5 — Verify Diacetyl Rhein now inside Physicochemical
  STEP 6 — If still outside, escalate via update_nsm() on the single node
           as a last-resort surgical fix; assert containment

References:
  - L186 cand: rebuild_tree single-arg signature + meta.nsm_parent_field
    source (NOT 'old_parent' as Hugh's hypothesis suggested)
  - feedback_nestedset_nsm_parent_field (L150): NestedSet parent field
    setting + rebuild_tree behavior

Author: claude-sandbox @ VMBox3
Date: 2026-05-31
Task: #12 / #15 (v14_3_10 STEP 1 + v14_3_11 STEP 5 NSM positioning followthrough)
"""
import frappe
from frappe.utils.nestedset import rebuild_tree


QIPG = "Quality Inspection Parameter Group"
DIACETYL = "Physicochemical Diacetyl Rhein"
PHYSICOCHEMICAL = "Physicochemical"


def _is_contained(child_lft_rgt, parent_lft_rgt):
    return parent_lft_rgt[0] <= child_lft_rgt[0] and child_lft_rgt[1] <= parent_lft_rgt[1]


def execute():
    phy = frappe.db.get_value(QIPG, PHYSICOCHEMICAL, ["lft", "rgt"])
    dia = frappe.db.get_value(QIPG, DIACETYL, ["lft", "rgt"])

    if not phy or not dia:
        print(f"v14_3_12: SKIP — required QIPG missing. "
              f"{PHYSICOCHEMICAL}={phy}, {DIACETYL}={dia}")
        return

    # STEP 1 — Idempotency check
    if _is_contained(dia, phy):
        print(f"v14_3_12: SKIP — {DIACETYL} already inside {PHYSICOCHEMICAL} subtree. "
              f"phy={phy}, dia={dia}")
        return

    print(f"v14_3_12: {DIACETYL} NSM out of subtree. phy={phy}, dia={dia}")

    # STEP 2 — Ensure Property Setter present + value correct (defensive)
    ps_name = frappe.db.exists("Property Setter", {
        "doc_type": QIPG,
        "property": "nsm_parent_field",
    })
    if not ps_name:
        print(f"v14_3_12: Property Setter for nsm_parent_field MISSING — creating.")
        doc = frappe.get_doc({
            "doctype": "Property Setter",
            "doctype_or_field": "DocType",
            "doc_type": QIPG,
            "property": "nsm_parent_field",
            "value": "custom_parameter_group_child",
            "property_type": "Data",
        })
        doc.insert(ignore_permissions=True)
    else:
        current_value = frappe.db.get_value("Property Setter", ps_name, "value")
        if current_value != "custom_parameter_group_child":
            print(f"v14_3_12: Property Setter has wrong value '{current_value}' "
                  f"— updating to 'custom_parameter_group_child'.")
            frappe.db.set_value(
                "Property Setter", ps_name, "value",
                "custom_parameter_group_child", update_modified=False,
            )
        else:
            print(f"v14_3_12: Property Setter present + correct ({ps_name})")

    # STEP 3 — Clear meta cache to ensure rebuild_tree reads latest Property Setter
    frappe.clear_cache(doctype=QIPG)

    # STEP 4 — rebuild_tree (Frappe 16.17.5 1-arg signature)
    rebuild_tree(QIPG)
    frappe.db.commit()

    # STEP 5 — Verify reposition
    new_phy = frappe.db.get_value(QIPG, PHYSICOCHEMICAL, ["lft", "rgt"])
    new_dia = frappe.db.get_value(QIPG, DIACETYL, ["lft", "rgt"])
    print(f"v14_3_12: post-rebuild_tree {PHYSICOCHEMICAL}={new_phy}, {DIACETYL}={new_dia}")

    if _is_contained(new_dia, new_phy):
        print(f"v14_3_12: ✓ {DIACETYL} now inside {PHYSICOCHEMICAL} subtree after rebuild_tree")
        return

    # STEP 6 — Last-resort: surgical update_nsm on the single node
    print(f"v14_3_12: rebuild_tree insufficient — escalating to single-node update_nsm")
    from frappe.utils.nestedset import update_nsm
    doc = frappe.get_doc(QIPG, DIACETYL)
    update_nsm(doc)
    frappe.db.commit()

    final_phy = frappe.db.get_value(QIPG, PHYSICOCHEMICAL, ["lft", "rgt"])
    final_dia = frappe.db.get_value(QIPG, DIACETYL, ["lft", "rgt"])
    print(f"v14_3_12: post-update_nsm {PHYSICOCHEMICAL}={final_phy}, {DIACETYL}={final_dia}")

    assert _is_contained(final_dia, final_phy), \
        f"NSM containment STILL failed after rebuild_tree + update_nsm: " \
        f"phy={final_phy}, dia={final_dia}"
    print(f"v14_3_12: ✓ {DIACETYL} now inside {PHYSICOCHEMICAL} subtree after update_nsm fallback")
