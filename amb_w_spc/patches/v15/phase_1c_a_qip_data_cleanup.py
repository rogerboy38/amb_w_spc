"""Phase 1C-A QIP data cleanup — bulk-assign parameter_group from FoxPro ANALISIS + populate Posibles Valores choices.

Reads canonical FoxPro extract at:
    /media/sf_E_DRIVE/Claude/local-agent-mode-sessions/foxpro-staging/extracts/parameter_group_and_choices.json

For each entry, looks up the QIP master record by `parameter` field (FoxPro DESCRIP).
If found:
  - assigns parameter_group from FoxPro 'group' field (mapped to canonical QIP Group)
    — only if currently empty (don't overwrite manual assignments)
  - populates custom_choices from 'choices' list (\\n-separated)
  - sets custom_is_numeric=1 for params without choices

If not found: append to not_found list (logged + reported).

Authoritative spec: cowork-ops directive `phase-1c-a-qip-data-cleanup-ceremony` (2026-05-18T17:15Z).
Alicia QE approved 2026-05-18T17:00Z via Phase 1C mockup v3.

Author: claude-sandbox
Date: 2026-05-18
"""

import json
from pathlib import Path

import frappe


DATA_FILE = "/media/sf_E_DRIVE/Claude/local-agent-mode-sessions/foxpro-staging/extracts/parameter_group_and_choices.json"

# Map FoxPro 'group' tokens → canonical Quality Inspection Parameter Group names (per Phase 1A QIPG tree).
# QIP Groups on canonical tree include: Organoleptic, Physicochemical, Microbiological, Other Analysis,
# Pesticides, Contaminant, Nutrients (some have product-line suffixes — handled by LIKE fallback below).
GROUP_NAME_MAP = {
	"organoleptic": "Organoleptic",
	"physicochemical": "Physicochemical",
	"microbiological": "Microbiological",
	"other analysis": "Other Analysis",
	"pesticides": "Pesticides",
	"contaminant": "Contaminant",
	"nutrients": "Nutrients",
	"total aloe vera nutrients": "Total Aloe Vera Nutrients",
}


def execute():
	"""Frappe patches.txt entry point."""

	if not Path(DATA_FILE).exists():
		frappe.log_error(
			f"Phase 1C-A: data file missing at {DATA_FILE}",
			"Phase 1C-A Migration",
		)
		print(f"FAIL: data file missing at {DATA_FILE}")
		return

	with open(DATA_FILE) as f:
		data = json.load(f)

	print(f"Phase 1C-A QIP data cleanup — processing {len(data)} entries from FoxPro extract")

	assigned_group = 0
	populated_choices = 0
	set_numeric = 0
	not_found = []
	group_resolution_failures = []

	for param_name, info in data.items():
		# Look up QIP record by 'parameter' field (FoxPro DESCRIP)
		# Try exact match first
		qip_name = frappe.db.get_value(
			"Quality Inspection Parameter",
			{"parameter": param_name},
			"name",
		)
		if not qip_name:
			# Try case-insensitive fuzzy match
			candidates = frappe.db.sql(
				"""
				SELECT name FROM `tabQuality Inspection Parameter`
				WHERE UPPER(parameter) = UPPER(%s) LIMIT 1
				""",
				(param_name,),
			)
			qip_name = candidates[0][0] if candidates else None

		if not qip_name:
			not_found.append(param_name)
			continue

		qip = frappe.get_doc("Quality Inspection Parameter", qip_name)

		# Resolve parameter_group via map → existence check → LIKE fallback
		canonical_group = GROUP_NAME_MAP.get(info.get("group"))
		if canonical_group and not frappe.db.exists("Quality Inspection Parameter Group", canonical_group):
			# Try LIKE match (e.g., "Organoleptic LQD" or product-line-suffixed variant)
			existing = frappe.db.sql(
				"""
				SELECT name FROM `tabQuality Inspection Parameter Group`
				WHERE name LIKE %s LIMIT 1
				""",
				(f"%{canonical_group}%",),
			)
			if existing:
				canonical_group = existing[0][0]
			else:
				group_resolution_failures.append((param_name, info.get("group")))
				canonical_group = None

		# Only update parameter_group if currently empty (don't overwrite manual assignments)
		if canonical_group and not qip.parameter_group:
			qip.parameter_group = canonical_group
			assigned_group += 1

		# Populate Posibles Valores choices (only if currently empty)
		choices = info.get("choices", [])
		if choices and not getattr(qip, "custom_choices", None):
			qip.custom_choices = "\n".join(choices)
			populated_choices += 1

		# Set custom_is_numeric=1 for params WITHOUT choices (only if currently unset)
		if not choices and not getattr(qip, "custom_is_numeric", None):
			qip.custom_is_numeric = 1
			set_numeric += 1

		# Save without triggering validate hooks that might require other fields, AND
		# without re-validating pre-existing Link fields (one QIP has a stale custom_specification
		# value like "0227 ORGANIC INNOVALOE ALOE VERA GEL CONCENTRATE" that isn't a Method record —
		# Phase 1C-A doesn't fix this; preserve-by-default per L119; separate hygiene task).
		qip.flags.ignore_validate = True
		qip.flags.ignore_permissions = True
		qip.flags.ignore_links = True
		qip.save()

	frappe.db.commit()

	# Report
	msg = f"""Phase 1C-A QIP data cleanup complete:
  - Source: {DATA_FILE}
  - Entries processed: {len(data)}
  - Assigned parameter_group to: {assigned_group} records
  - Populated Posibles Valores choices on: {populated_choices} records
  - Set custom_is_numeric=1 on: {set_numeric} records (numeric-only params)
  - Not found in QIP master: {len(not_found)} parameter names from FoxPro data
  - Group resolution failures: {len(group_resolution_failures)} (FoxPro group → QIP Group mapping)

Not found examples (first 10): {not_found[:10]}
Group resolution failures (first 5): {group_resolution_failures[:5]}
"""
	print(msg)
	frappe.log_error(msg, "Phase 1C-A Migration")
