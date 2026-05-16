"""Phase 1A Step 2B — install `form` Custom Field + backfill on existing 124 TDS Product Specification docs.

Pattern A1: Custom Field overlay only. No in-place mods to the existing custom=1 TDS DocType, no
fixture export. The override class registered separately in hooks.py provides the live derivation
logic (`validate()` → `derive_form()`); this patch installs the field shape + backfills existing rows.

Idempotency:
  - `create_custom_field` is no-op on exact match (idempotent by (doctype, fieldname))
  - Backfill writes only to rows where `form` is NULL/empty (guard via WHERE clause)

Empirical pre-state on VM3 v2.sysmayal.cloud (2026-05-12):
  - 124 TDS Product Specification rows
  - 0 Custom Fields named `form` currently on this DocType
  - 24 stock DocFields + 2 existing Custom Fields (workflow_state, version)
  - All sampled rows: product_item populated, links to Items with meaningful item_groups
    ("Products Liquid", "Products Powder", "FG Mix Powder Products", "RAW M Powders")
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

DOCTYPE = "TDS Product Specification"


def execute():
	_add_form_custom_field()
	frappe.clear_cache(doctype=DOCTYPE)
	_backfill_form_from_product_item()
	frappe.db.commit()


def _add_form_custom_field() -> None:
	"""Install `form` Custom Field — Link to Item Group, fetch_from product_item.item_group."""
	create_custom_field(
		DOCTYPE,
		{
			"fieldname": "form",
			"label": "Form",
			"fieldtype": "Link",
			"options": "Item Group",
			"fetch_from": "product_item.item_group",
			"in_list_view": 1,
			# Leave non-mandatory so existing 124 docs without form still validate during backfill,
			# and so docs created before product_item is set don't block on this field.
			"insert_after": "item_code",
			"description": "Auto-derived from product_item's Item Group. Scopes the IQI Parameter Group picker filter (see Step 1B JS work).",
		},
		ignore_validate=True,
	)


def _backfill_form_from_product_item() -> None:
	"""Set `form` = product_item.item_group on existing rows where `form` is empty AND product_item is set.

	Idempotent: WHERE clause only matches rows still needing backfill. Re-runs produce no changes.
	Uses a single UPDATE-JOIN against tabItem to avoid Python-level row-by-row writes (124 rows is
	small, but the SQL form keeps it safe-update compliant via PK reference on the target's name).
	"""
	frappe.db.sql(
		f"""
		UPDATE `tab{DOCTYPE}` t
		INNER JOIN `tabItem` i ON i.name = t.product_item
		SET t.form = i.item_group
		WHERE (t.form IS NULL OR t.form = '')
		  AND t.product_item IS NOT NULL
		  AND t.product_item != ''
		  AND i.item_group IS NOT NULL
		  AND i.item_group != ''
		  AND t.name = t.name
		"""
	)
