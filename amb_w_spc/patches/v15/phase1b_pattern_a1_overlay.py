"""Phase 1B-1 Pattern A1 overlay on MiniMax Agent SPC framework (ADR-004 + ADR-003 + amendments).

Implements the 10-artifact unified apply/revert per ubuntuvm pseudocode
(correlation `doc-events-transport-decision-locked` 2026-05-14T17:00Z):

    Custom Fields on SPC Parameter Master (6):
        qip_source, parameter_group, default_l4_spec,
        external_method_reference, default_method, insumos_y_materiales

    Property Setters (2):
        SPC Parameter Master.parameter_name.unique = 1   (ADR-004 §2)
        IQI Parameter.value.depends_on = "eval:!doc.formula_based_criteria"  (ADR-003)

    doc_events wirings (2, Phase 1B-scope only per ADR-004 amendment 2026-05-14T15:30Z):
        SPC Parameter Master → validate → validate_spc_parameter_master
        SPC Specification    → validate → validate_spc_specification

Authoritative spec:
    - cowork-shared/adrs/ADR-004-pattern-a1-overlay-on-minimax-agent-spc-framework.md (§2)
    - cowork-shared/adrs/ADR-003-preserve-structured-numeric-criteria-...md
    - Sandbox commission `sandbox-commission-pattern-a1-overlay-fixture-authoring` 2026-05-14T20:00Z

Execution modes:
    (a) Via bench migrate on VM3 / rehearsal substrate (auto-fires via patches.txt
        entry `amb_w_spc.patches.v15.phase1b_pattern_a1_overlay` → execute() wraps apply())
    (b) Via docker exec + bench console + stdin on prod (sysmayal manually runs apply())

Both modes are idempotent:
    - Custom Fields keyed by `<DocType>-<fieldname>` (Frappe's create_custom_field upserts)
    - Property Setters keyed by `<DocType>-<fieldname>-<property>` (make_property_setter upserts)
    - hooks.py edit gated by content-detection (skip if validate handler string present)

Reverse path (revert()):
    - PK-keyed DELETE of CF/PS rows by name
    - hooks.py restored from .bak-<TS> backup
    - frappe.clear_cache() to invalidate cached hooks

Author: claude-sandbox
Date: 2026-05-14
"""

import os
import shutil
import sys
from datetime import datetime, timezone

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# -----------------------------------------------------------------------------
# Module-level constants
# -----------------------------------------------------------------------------

HOOKS_PATH = "/home/frappe/frappe-bench/apps/amb_w_spc/amb_w_spc/hooks.py"

# Backup timestamp set at apply() time; cached for revert() in same process.
_BACKUP_PATH = None


def _backup_path() -> str:
	"""Return the canonical backup path for hooks.py within this apply/revert cycle.

	First call records timestamp; subsequent calls return same path. Allows revert()
	to find the backup apply() created even if called separately.
	"""
	global _BACKUP_PATH
	if _BACKUP_PATH is None:
		ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
		_BACKUP_PATH = f"{HOOKS_PATH}.bak-phase1b-{ts}"
	return _BACKUP_PATH


# -----------------------------------------------------------------------------
# 6 Custom Field specs (per ADR-004 §2)
# -----------------------------------------------------------------------------

CUSTOM_FIELDS = [
	{
		"fieldname": "qip_source",
		"label": "QIP Source",
		"fieldtype": "Link",
		"options": "Quality Inspection Parameter",
		"unique": 1,
		"reqd": 1,
		"insert_after": "parameter_name",
		"description": "Reverse pointer to source Quality Inspection Parameter. Used as idempotent re-seed key for Phase 1B-4 data migration. Frappe default Link cascade is Restrict — QIP cannot be deleted while any Master references it.",
	},
	{
		"fieldname": "parameter_group",
		"label": "Parameter Group",
		"fieldtype": "Link",
		"options": "Quality Inspection Parameter Group",
		"reqd": 1,
		"insert_after": "qip_source",
		"description": "Phase 1A tree-extended QIP Group reference (L2 discipline branch, per ADR-002 depth-4 hierarchy). Phase 1C wizard reads this to populate L1/L2 selection.",
	},
	{
		"fieldname": "default_l4_spec",
		"label": "Default L4 Spec (Posibles Valores)",
		"fieldtype": "Link",
		"options": "Quality Inspection Parameter",
		"insert_after": "parameter_group",
		# Filter Link picker to is_group=0 (i.e., leaves only — L4 Posibles Valores records,
		# not L3 parent QIP records). Stored as JSON-string filter list per Frappe convention.
		"link_filters": '[["Quality Inspection Parameter","is_group","=",0]]',
		"description": "Recommended default L4 Posibles Valores reference for this parameter (per ADR-002 depth-4 + ADR-004 §2). Filter: is_group=0 (L4 leaves only). Phase 1B-4 seed populates from FoxPro ingest.",
	},
	{
		"fieldname": "external_method_reference",
		"label": "External Method Reference",
		"fieldtype": "Data",
		"length": 140,
		"insert_after": "default_l4_spec",
		"description": "Methodology code (PAM, EPA-6020A, BAM-FDA: CH. *, CPA-***) passthrough from QIP.custom_specification. Phase 2 promotion candidate to Link → Method Catalog if/when that DocType emerges.",
	},
	{
		"fieldname": "default_method",
		"label": "Default Method",
		"fieldtype": "Data",
		"length": 140,
		"insert_after": "external_method_reference",
		"description": "Most-common test method across IQI rows for this parameter (e.g., NMR, UPLC UV, BAM-FDA: CH. 3). Per-product overrides live on SPC Specification.",
	},
	{
		"fieldname": "insumos_y_materiales",
		"label": "Insumos y Materiales (Raw Materials Applicability)",
		"fieldtype": "Check",
		"default": "0",
		"insert_after": "default_method",
		"description": "Flag for raw materials applicability per task #97. Phase 2 raw-material tracking surface reads this.",
	},
]


# -----------------------------------------------------------------------------
# 2 Property Setter specs
# -----------------------------------------------------------------------------

PROPERTY_SETTERS = [
	{
		"doctype": "SPC Parameter Master",
		"fieldname": "parameter_name",
		"property": "unique",
		"value": "1",
		"property_type": "Check",
		"_note": "ADR-004 §2 — enforce UNIQUE on parameter_name. Phase 1A 2A research confirmed 82/82 distinct QIPs.parameter values.",
	},
	{
		"doctype": "Item Quality Inspection Parameter",
		"fieldname": "value",
		"property": "depends_on",
		"value": "eval:!doc.formula_based_criteria",
		"property_type": "Code",
		"_note": "ADR-003 — restore direct authoring of acceptance criterion text when numeric=1. Original core depends_on was 'eval:(!doc.formula_based_criteria && !doc.numeric)'; this overlay narrows to formula-only hide.",
	},
]


# -----------------------------------------------------------------------------
# 2 doc_events wiring specs (ADR-004 amendment 15:30Z — Phase 1B-scope only)
# -----------------------------------------------------------------------------

DOC_EVENTS_WIRING = [
	{
		"doctype": "SPC Parameter Master",
		"event": "validate",
		"handler": "amb_w_spc.core_spc.spc_server_validations.validate_spc_parameter_master",
	},
	{
		"doctype": "SPC Specification",
		"event": "validate",
		"handler": "amb_w_spc.core_spc.spc_server_validations.validate_spc_specification",
	},
]


# -----------------------------------------------------------------------------
# Main apply() — 10 artifacts in one in-context transaction
# -----------------------------------------------------------------------------

def apply():
	"""Apply Pattern A1 overlay — 10 artifacts in one in-context transaction.

	Idempotent: re-runs are no-ops where state matches; reapplies missing pieces only.
	"""
	print("=" * 70)
	print("Phase 1B-1 Pattern A1 overlay — apply() starting")
	print(f"  Backup path: {_backup_path()}")
	print("=" * 70)

	# ---- 1. Six Custom Fields on SPC Parameter Master ----
	print("\n[1/4] Creating 6 Custom Fields on SPC Parameter Master")
	for spec in CUSTOM_FIELDS:
		fieldname = spec["fieldname"]
		cf_name = f"SPC Parameter Master-{fieldname}"
		if frappe.db.exists("Custom Field", cf_name):
			print(f"  ✓ exists, skip: {cf_name}")
			continue
		create_custom_field("SPC Parameter Master", spec.copy())
		print(f"  + created: {cf_name}  ({spec['fieldtype']})")

	# ---- 2. Two Property Setters ----
	print("\n[2/4] Applying 2 Property Setters")
	for spec in PROPERTY_SETTERS:
		ps_name = f"{spec['doctype']}-{spec['fieldname']}-{spec['property']}"
		# make_property_setter is upsert-idempotent by composite key
		make_property_setter(
			doctype=spec["doctype"],
			fieldname=spec["fieldname"],
			property=spec["property"],
			value=spec["value"],
			property_type=spec["property_type"],
		)
		print(f"  + applied: {ps_name} = {spec['value']!r}")

	# ---- 3. doc_events wiring via hooks.py file edit (in-context) ----
	print("\n[3/4] Wiring doc_events in hooks.py (in-context append-coda pattern)")
	_patch_hooks_py_idempotent()

	# ---- 4. Force Frappe to reload hooks + verify wiring is live ----
	print("\n[4/4] Reloading Frappe cache + verifying wiring")
	frappe.clear_cache()
	frappe.db.commit()
	import importlib
	if "amb_w_spc.hooks" in sys.modules:
		importlib.reload(sys.modules["amb_w_spc.hooks"])

	# Smoke assertion — the 2 doc_events handlers must be discoverable via Frappe's hook resolver
	for spec in DOC_EVENTS_WIRING:
		hooks = frappe.get_hooks("doc_events", {}).get(spec["doctype"], {})
		validate_handlers = hooks.get(spec["event"], [])
		if isinstance(validate_handlers, str):
			validate_handlers = [validate_handlers]
		assert spec["handler"] in validate_handlers, (
			f"FAIL: {spec['doctype']}.{spec['event']} → {spec['handler']} not in resolver "
			f"(found: {validate_handlers!r})"
		)
		print(f"  ✓ verified: {spec['doctype']}.{spec['event']} → {spec['handler']}")

	# Custom Field + Property Setter sanity check (post-write read)
	cf_count = frappe.db.count("Custom Field", filters={"dt": "SPC Parameter Master", "fieldname": ("in", [c["fieldname"] for c in CUSTOM_FIELDS])})
	ps_count = frappe.db.count("Property Setter", filters={"name": ("in", [f"{p['doctype']}-{p['fieldname']}-{p['property']}" for p in PROPERTY_SETTERS])})
	print(f"  ✓ Custom Fields landed: {cf_count}/6")
	print(f"  ✓ Property Setters landed: {ps_count}/2")
	assert cf_count == 6, f"Custom Field count mismatch: {cf_count}/6"
	assert ps_count == 2, f"Property Setter count mismatch: {ps_count}/2"

	print("\n" + "=" * 70)
	print("apply() complete — 10 artifacts in place")
	print(f"hooks.py backup at: {_backup_path()}")
	print("=" * 70)


# -----------------------------------------------------------------------------
# revert() — reverse of apply(); PK-keyed DELETE + hooks.py restore
# -----------------------------------------------------------------------------

def revert():
	"""Reverse of apply() — PK-keyed DELETE of CF/PS rows + hooks.py restore from backup.

	Idempotent: re-runs are no-ops where state already reverted.
	"""
	print("=" * 70)
	print("Phase 1B-1 Pattern A1 overlay — revert() starting")
	print("=" * 70)

	# ---- 1. PK DELETE Custom Fields (by canonical name) ----
	print("\n[1/3] Deleting 6 Custom Fields")
	for spec in CUSTOM_FIELDS:
		cf_name = f"SPC Parameter Master-{spec['fieldname']}"
		if frappe.db.exists("Custom Field", cf_name):
			frappe.delete_doc("Custom Field", cf_name, force=1, ignore_permissions=True)
			print(f"  - deleted: {cf_name}")
		else:
			print(f"  ⊘ already gone: {cf_name}")

	# ---- 2. PK DELETE Property Setters (by canonical name) ----
	print("\n[2/3] Deleting 2 Property Setters")
	for spec in PROPERTY_SETTERS:
		ps_name = f"{spec['doctype']}-{spec['fieldname']}-{spec['property']}"
		if frappe.db.exists("Property Setter", ps_name):
			frappe.delete_doc("Property Setter", ps_name, force=1, ignore_permissions=True)
			print(f"  - deleted: {ps_name}")
		else:
			print(f"  ⊘ already gone: {ps_name}")

	# ---- 3. Restore hooks.py from backup ----
	print("\n[3/3] Restoring hooks.py from backup")
	_unpatch_hooks_py()

	# ---- Reload cache ----
	frappe.clear_cache()
	frappe.db.commit()

	print("\n" + "=" * 70)
	print("revert() complete — Pattern A1 overlay removed")
	print("=" * 70)


# -----------------------------------------------------------------------------
# hooks.py append-coda + restore (helpers)
# -----------------------------------------------------------------------------

# Sentinel marker so we can detect + replace the coda block on re-apply or revert
_CODA_BEGIN = "# === Phase 1B-1 Pattern A1 overlay — doc_events wiring (ADR-004 amendment) ==="
_CODA_END = "# === end Phase 1B-1 Pattern A1 overlay ==="


def _patch_hooks_py_idempotent():
	"""Pre-edit backup + content-detection-idempotent append of doc_events coda.

	If the coda is already present (sentinel markers match), no edit. Otherwise:
	1. Back up current hooks.py to `<HOOKS_PATH>.bak-phase1b-<TS>`
	2. Append coda block that registers the 2 doc_events handlers using list-append
	   (preserving any existing doc_events handlers for these DocTypes)
	"""
	with open(HOOKS_PATH, "r") as f:
		content = f.read()

	if _CODA_BEGIN in content and _CODA_END in content:
		print("  ✓ hooks.py: coda already present, skip")
		return

	# Backup current file before any edit
	backup_target = _backup_path()
	if not os.path.exists(backup_target):
		shutil.copy2(HOOKS_PATH, backup_target)
		print(f"  + backed up hooks.py → {backup_target}")

	# Append-coda pattern — uses list semantics matching the existing convention in this hooks.py
	# (Batch AMB.validate is already a list; new entries match shape).
	coda_lines = [
		"",
		"",
		_CODA_BEGIN,
		"# Apply 2 Phase-1B-scope validators from amb_w_spc.core_spc.spc_server_validations:",
		"#   SPC Parameter Master.validate    → validate_spc_parameter_master",
		"#   SPC Specification.validate       → validate_spc_specification",
		"# Phase 2 validators (SPC Control Chart, SPC Data Point, alerts/analytics) deferred",
		"# per ADR-004 amendment 2026-05-14T15:30Z + basket task #107.",
		"# This coda is reversible via the .bak file written by the overlay patch.",
		"try:",
		"    doc_events  # may already exist higher in this file",
		"except NameError:",
		"    doc_events = {}",
		"for _spc_dt, _spc_handler in [",
	]
	for spec in DOC_EVENTS_WIRING:
		coda_lines.append(f'    ({spec["doctype"]!r}, {spec["handler"]!r}),')
	coda_lines.extend([
		"]:",
		"    _spc_entry = doc_events.setdefault(_spc_dt, {})",
		'    _spc_existing = _spc_entry.get("validate", [])',
		"    if isinstance(_spc_existing, str):",
		"        _spc_existing = [_spc_existing]",
		"    if _spc_handler not in _spc_existing:",
		"        _spc_existing.append(_spc_handler)",
		'    _spc_entry["validate"] = _spc_existing',
		"# Cleanup helper-local names — keep hooks.py module namespace tidy",
		"del _spc_dt, _spc_handler, _spc_entry, _spc_existing",
		_CODA_END,
		"",
	])
	coda = "\n".join(coda_lines)

	with open(HOOKS_PATH, "w") as f:
		f.write(content + coda)
	print(f"  + appended doc_events coda to hooks.py ({len(coda)} chars)")


def _unpatch_hooks_py():
	"""Restore hooks.py from the .bak file written by _patch_hooks_py_idempotent.

	If no backup exists (revert called without prior apply in this process / new shell),
	fall back to manual coda-section removal via sentinel markers.
	"""
	backup_target = _backup_path()
	if os.path.exists(backup_target):
		shutil.copy2(backup_target, HOOKS_PATH)
		print(f"  + restored hooks.py from {backup_target}")
		return

	# Fallback: backup not found (e.g., revert called from fresh shell after a different process applied)
	# Find any .bak-phase1b-* file matching our pattern; use the most recent one.
	import glob
	candidates = sorted(glob.glob(f"{HOOKS_PATH}.bak-phase1b-*"), reverse=True)
	if candidates:
		shutil.copy2(candidates[0], HOOKS_PATH)
		print(f"  + restored hooks.py from {candidates[0]} (fallback discovery)")
		return

	# Last resort: surgical coda removal via sentinel markers
	print("  ⚠ no backup found; attempting surgical coda removal via sentinel markers")
	with open(HOOKS_PATH, "r") as f:
		content = f.read()
	begin = content.find(_CODA_BEGIN)
	end = content.find(_CODA_END)
	if begin == -1 or end == -1:
		print("  ⊘ coda sentinels not found in hooks.py — nothing to remove")
		return
	end_inclusive = end + len(_CODA_END)
	# Also strip leading whitespace/newlines that were added before the coda block
	pre = content[:begin].rstrip()
	post = content[end_inclusive:].lstrip("\n")
	with open(HOOKS_PATH, "w") as f:
		f.write(pre + "\n" + post)
	print("  + surgically removed coda block via sentinels")


# -----------------------------------------------------------------------------
# patches.txt-compatible execute() wrapper
# -----------------------------------------------------------------------------

def execute():
	"""Frappe patches.txt entry point — wraps apply() for `bench migrate` invocation.

	Registered in `apps/amb_w_spc/amb_w_spc/patches.txt` as:
	    amb_w_spc.patches.v15.phase1b_pattern_a1_overlay

	Phase 1A 2A/2B/2C established this pattern (bare dotted-module-path, not `execute:` prefix).
	"""
	apply()


# -----------------------------------------------------------------------------
# Standalone-script entry point (for docker exec + bench console + stdin pattern)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
	# Allows `python phase1b_pattern_a1_overlay.py apply|revert` if frappe.init was set up.
	# Normal deploy ceremony uses `import phase1b_pattern_a1_overlay; phase1b_pattern_a1_overlay.apply()`
	# from inside bench console (which already has frappe initialized).
	if len(sys.argv) > 1 and sys.argv[1] == "revert":
		revert()
	else:
		apply()
