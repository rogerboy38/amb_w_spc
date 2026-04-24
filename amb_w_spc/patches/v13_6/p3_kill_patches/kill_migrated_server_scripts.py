# -*- coding: utf-8 -*-
# ==========================================================
# amb_w_spc.patches.v13_6.p3_kill_patches.kill_migrated_server_scripts
# ==========================================================
# V13.6.0 P3 — Server Script migration kill-patch.
# Deletes Server Script DB rows whose logic has been migrated
# into in-code hooks (doctype_events / api / override_whitelisted_methods)
# OR archived verbatim under docs/legacy/.
#
# Runs automatically on `bench migrate` (listed in patches.txt).
# Pre-kill backups live under /tmp/p3-artifacts/ (full Frappe
# backup + server_scripts_full_dump.json + per-row body files).
# ==========================================================
import frappe


def execute():
    scripts_to_delete = [
        "Manual History Entries",
        "History Tracking",
        "Complex Workflow Management",
        "validate_var_code39_ok",
        "batch_announcements_for_navbar_widget",
        "Batch AMB Custom Tree API",
        "Prevent NestedSet Processing",
        "Batch and Serial",
        "Create Sample Request from Lead",
        "animal_trial",
        "get_running_batch_announcements",
        "on_update_validate",
        "validate_event",
        "batch_amb_validate_data",
        "batch_amb_custom_tree_api_old",
        "batch_amb_custom_tree_api",
        "Batch AMB Tree API",
        "Batch AMB Tree Handler2",
        "Batch AMB Tree Handler",
        "Disable Batch AMB NestedSet",
        "Batch AMB Before Delete",
        "Batch AMB After Save",
        "Batch AMB Validations",
        "Batch AMB Penca",
        "Batch PENCA",
        "batch_naming_amb",
        "Batch L1",
        "batch_naming_amb_old",
        "Fix Batch AMB Data",
    ]

    deleted = 0
    missing = 0
    failed  = 0
    for script_name in scripts_to_delete:
        try:
            frappe.delete_doc("Server Script", script_name, force=True)
            frappe.db.commit()
            print(f"OK     deleted  : {script_name}")
            deleted += 1
        except frappe.DoesNotExistError:
            print(f"SKIP   not found : {script_name}")
            missing += 1
        except Exception as e:
            print(f"FAIL             : {script_name} -> {e}")
            failed += 1

    total = len(scripts_to_delete)
    print(f"P3 kill-patch (amb_w_spc): total={total} deleted={deleted} missing={missing} failed={failed}")
