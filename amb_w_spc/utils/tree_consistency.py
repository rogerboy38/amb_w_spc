"""Tree-consistency utilities — post-fixture-sync NSM rebuild for QIPG.

Background (L187): Frappe `bench migrate` ordering is:
  1. Patches (pre_model_sync / model_sync / post_model_sync)
  2. sync_fixtures()
  3. after_migrate hooks

Task #9's QIPG fixture (`amb_w_spc/fixtures/quality_inspection_parameter_group.json`)
contains 411 canonical records. sync_fixtures applies them as UPDATEs on
populated sites — but the underlying NSM rebuild_tree call repositions L2
boundaries (Physicochemical, Microbiological, etc.) based on the fixture
records ONLY. Non-fixture QIPGs (those created by patches like v14_3_10
STEP 1's `Physicochemical Diacetyl Rhein`) are NOT in the fixture array, so
their lft/rgt aren't recomputed — they stay at their stale pre-fixture-sync
positions while the L2 ranges shift around them.

Result: A QIPG created by v14_3_10 STEP 1 is correctly placed inside
Physicochemical's subtree at insert-time. Then sync_fixtures shifts
Physicochemical to a new lft/rgt range. The patch-created QIPG keeps its
old lft/rgt — now OUTSIDE Physicochemical's new range. Browser-verified
on vpt-docker (sysmayal .ack 2026-05-31): Diacetyl Rhein orphaned at
(713, 714) while Physicochemical moved to (1390, 1751).

v14_3_12 attempted to fix this with a patch-level rebuild_tree, but
patches run BEFORE sync_fixtures, so v14_3_12's rebuild_tree was undone
by the subsequent sync_fixtures rebuild.

Fix: register `after_migrate` hook that runs rebuild_tree AFTER both
patches AND sync_fixtures complete. Non-fixture QIPGs get repositioned
relative to the final, fixture-aligned L2 boundaries.

Defensive: idempotent — rebuild_tree is itself idempotent; safe on every
migrate. Canary log if Diacetyl Rhein ends up outside Physicochemical
even AFTER rebuild (would surface a deeper issue).
"""
import frappe
from frappe.utils.nestedset import rebuild_tree


QIPG = "Quality Inspection Parameter Group"
PROPERTY_SETTER_NAME = f"{QIPG}-main-nsm_parent_field"


def rebuild_qipg_tree():
    """Idempotent post-fixture-sync NSM rebuild for QIPG.

    Registered as `after_migrate` hook in amb_w_spc/hooks.py so it fires
    AFTER patches + sync_fixtures complete on every `bench migrate`. Repositions
    non-fixture QIPGs (patch-created) inside their custom_parameter_group_child
    parent's NSM range.

    Defensive checks:
      - Property Setter `nsm_parent_field=custom_parameter_group_child` present
        (without it, rebuild_tree falls back to scrub-default parent field
        which doesn't exist on QIPG → silent no-op)
      - Clear meta cache so latest Property Setter value is read
      - Verify Diacetyl Rhein containment as canary; log error if rebuild
        didn't restore it (would surface a deeper issue)

    See L187 (banked 2026-05-31).
    """
    if not frappe.db.exists("Property Setter", PROPERTY_SETTER_NAME):
        frappe.log_error(
            f"L187 / after_migrate: nsm_parent_field Property Setter "
            f"'{PROPERTY_SETTER_NAME}' missing — skipping rebuild. Without it, "
            f"rebuild_tree falls back to scrub-default parent field which doesn't "
            f"exist on QIPG. Re-install Property Setter via fixture sync of "
            f"amb_w_spc/fixtures/property_setter.json.",
            "rebuild_qipg_tree",
        )
        return

    frappe.clear_cache(doctype=QIPG)
    rebuild_tree(QIPG)
    frappe.db.commit()

    # Canary: verify Diacetyl Rhein (Task #15 v14_3_10's reverse-ship leaf) is
    # inside Physicochemical's subtree. If not, a deeper issue exists.
    phy = frappe.db.get_value(QIPG, "Physicochemical", ["lft", "rgt"])
    dia = frappe.db.get_value(QIPG, "Physicochemical Diacetyl Rhein", ["lft", "rgt"])
    if phy and dia and not (phy[0] <= dia[0] and dia[1] <= phy[1]):
        frappe.log_error(
            f"L187 canary FAILED: Diacetyl Rhein lft/rgt={dia} not inside "
            f"Physicochemical lft/rgt={phy}. rebuild_tree completed but did "
            f"not reposition the orphan node. Investigate: (a) is Diacetyl "
            f"Rhein's custom_parameter_group_child still 'Physicochemical'? "
            f"(b) is meta.nsm_parent_field correctly set? (c) is the QIPG "
            f"controller class loaded (override_doctype_class hook)?",
            "rebuild_qipg_tree",
        )
