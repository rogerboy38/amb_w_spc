"""Phase 1A Step 2C — populate `parameter_group` on non-flag IQI Parameter rows with empty parameter_group.

**Empirical-driven deviation from kickoff `e9a47c2b` §Step 2C** (documented in detail in the close-out letter for that step):

- Kickoff specified title-row-propagation: walk child rows in idx order, propagate parameter_group from `custom_is_title_row=1` rows to following non-flag rows. Cowork's `b3cfca10` sign-off re-affirmed this approach.

- Empirical baseline on VM3 v2.sysmayal.cloud reveals the kickoff strategy hits 0 rows:
  - 445 non-flag rows with empty `parameter_group` (across 113 parent docs)
  - Only 5 title rows TOTAL, in 2 of 113 affected parent docs (022700001 + 0308 Barentz)
  - For those 2 docs, non-flag rows already have parameter_group populated (via Frappe's own auto-fill on save)
  - The other 111 docs containing empty-pg rows have NO title rows → title-based propagation can't reach them

- Empirical source-of-truth identified: `tabQuality Inspection Parameter` (linked via `specification` field) carries its own `parameter_group` mapping. 430 of 445 empty rows resolve via this lookup. Sample mapping:
  - specification="Pathogens" → parameter_group="Microbiological LQD Pathogens"
  - specification="Color Gardner" → "Physicochemical LQD Color Gardner"
  - specification="Arsenic" → "Physicochemical LQD Arsenic"

- Frappe's auto-fill behavior (observed in Step 2B smoke test) uses the same lookup. This migration explicitly applies the same source-of-truth as a one-shot UPDATE.

Strategy: raw SQL with PK-based UPDATE (not Document API) — bypasses Frappe's auto-fill flow safely, and is PK-based for MariaDB safe-update-mode compliance (Step 2A/2B lesson `feedback_mariadb_safe_delete`).

Idempotent: WHERE clause only matches rows still needing backfill. Re-run = 0 updates.

Out of scope: 15 of 445 rows whose `specification` links to a Quality Inspection Parameter that itself has no parameter_group (e.g., uppercase-variant entries like "ACEMANNAN BY O-ACETIL METHOD", "ALOE EMODIN (BY DRY WEIGHT)"). These need separate data hygiene at the QIP level — sysmayal can spot-check during Step 4 deploy.
"""

import frappe


def execute():
	pre_empty = _count_empty_non_flag()
	print(f"  pre-migration empty parameter_group rows (non-flag): {pre_empty}")

	mappings = _select_target_mappings()
	print(f"  rows resolvable via specification → QIP parameter_group lookup: {len(mappings)}")

	updated = _apply_pk_based_updates(mappings)
	print(f"  rows updated: {updated}")

	post_empty = _count_empty_non_flag()
	print(f"  post-migration empty parameter_group rows (non-flag): {post_empty}")

	delta = pre_empty - post_empty
	print(f"  net population: {delta}")

	frappe.db.commit()


def _count_empty_non_flag() -> int:
	row = frappe.db.sql(
		"""
		SELECT COUNT(*) FROM `tabItem Quality Inspection Parameter`
		WHERE (custom_is_title_row = 0 OR custom_is_title_row IS NULL)
		  AND (parameter_group IS NULL OR parameter_group = '')
		"""
	)
	return row[0][0] if row else 0


def _select_target_mappings():
	"""Return [(iqi_name, qip_parameter_group), ...] for rows that should be updated.

	JOIN against `tabQuality Inspection Parameter` (the source-of-truth doctype) using
	`specification` Link. Filter to empty-pg non-flag rows where the QIP target HAS pg set.
	"""
	return frappe.db.sql(
		"""
		SELECT iqi.name, qip.parameter_group
		FROM `tabItem Quality Inspection Parameter` iqi
		INNER JOIN `tabQuality Inspection Parameter` qip ON qip.name = iqi.specification
		WHERE (iqi.custom_is_title_row = 0 OR iqi.custom_is_title_row IS NULL)
		  AND (iqi.parameter_group IS NULL OR iqi.parameter_group = '')
		  AND qip.parameter_group IS NOT NULL AND qip.parameter_group != ''
		"""
	)


def _apply_pk_based_updates(mappings) -> int:
	"""Apply each mapping as a PK-based UPDATE. Safe-update compliant by name=...

	Returns count of UPDATEs executed (NOT rows-affected; that may differ if Frappe's
	auto-fill somehow re-mutates between the SELECT and UPDATE — post-write SELECT in
	`execute()` catches that).
	"""
	count = 0
	for name, pg in mappings:
		frappe.db.sql(
			"""
			UPDATE `tabItem Quality Inspection Parameter`
			SET parameter_group = %s
			WHERE name = %s
			""",
			(pg, name),
		)
		count += 1
	return count
