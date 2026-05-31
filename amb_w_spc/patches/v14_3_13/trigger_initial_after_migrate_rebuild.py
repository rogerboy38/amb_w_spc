"""Trigger initial after_migrate rebuild for fixing existing vpt-docker state.

Context: v14_3_12 attempted a patch-level rebuild_tree to reposition the
orphaned `Physicochemical Diacetyl Rhein` QIPG inside `Physicochemical` L2's
subtree. But patches run BEFORE sync_fixtures in Frappe's migrate cycle
(frappe/migrate.py: patches → sync_fixtures → after_migrate). Task #9's
411-record QIPG canonical fixture re-runs rebuild_tree after v14_3_12,
repositioning Physicochemical's lft/rgt without recomputing the non-fixture
Diacetyl Rhein QIPG's lft/rgt — leaving the orphan at its old position.

v14_3_13 fix (this commit):
  1. Register after_migrate hook in amb_w_spc/hooks.py:
       after_migrate = ["amb_w_spc.amb_w_spc.utils.tree_consistency.rebuild_qipg_tree"]
  2. This patch triggers the same rebuild during the current migrate cycle
     to fix existing state on sites already affected (vpt-docker, hostinger-
     vpp). Future migrates auto-run the rebuild via the hook.

The hook + patch trigger together provide:
  - One-time fix for already-deployed sites (this patch runs during bench
    migrate, AFTER all patches + sync_fixtures complete in patches.txt order;
    the after_migrate hook then runs AGAIN at the proper Frappe-migrate
    sequence position — but rebuild_tree is idempotent so duplication is safe)
  - Continuous protection for future migrates that introduce new non-fixture
    QIPGs (the hook fires automatically post-sync_fixtures)

Author: claude-sandbox @ VMBox3
Date: 2026-05-31
Task: #15 / #12 (v14_3_10 → v14_3_11 → v14_3_12 → v14_3_13 trailing fix sequence)
References: L186 (rebuild_tree signature), L187 (migrate ordering)
"""
from amb_w_spc.utils.tree_consistency import rebuild_qipg_tree


def execute():
    rebuild_qipg_tree()
