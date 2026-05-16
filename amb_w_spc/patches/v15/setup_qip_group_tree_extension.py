"""Phase 1A Step 2A — install Custom Fields + Property Setters + seed is_group + rebuild_tree.

Pattern A1: all schema changes are Custom Fields (lft, rgt, is_group, old_parent) and Property Setters (is_tree=1, nsm_parent_field=custom_parameter_group_child) — no in-place mods to ERPNext core. Override class registered separately in hooks.py.

Idempotent: `create_custom_field` and `make_property_setter` are both no-op on exact match. `rebuild_tree` is safe to re-run. Seed step uses guard against existing non-NULL values.

Empirical pre-state on VM3 v2.sysmayal.cloud (2026-05-12):
  - 54 rows total
  - 44 rows with parent linkage via custom_parameter_group_child
  - 7 distinct parent rows (groups)
  - 1 self-referencing row was cleared forensically before this patch runs
    (forensic capture: /tmp/qip_group_self_ref_20260512T172450Z.json on sandbox bench)
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils.nestedset import rebuild_tree

DOCTYPE = "Quality Inspection Parameter Group"
PARENT_FIELD = "custom_parameter_group_child"


def execute():
	_add_custom_fields()
	_add_property_setters()
	frappe.clear_cache(doctype=DOCTYPE)
	_seed_is_group()
	_rebuild_tree()
	frappe.db.commit()


def _add_custom_fields() -> None:
	"""Insert the 4 NestedSet Custom Fields. `create_custom_field` is idempotent by (doctype, fieldname)."""
	fields = [
		{
			"fieldname": "is_group",
			"label": "Is Group",
			"fieldtype": "Check",
			"default": "0",
			"in_list_view": 1,
			"insert_after": PARENT_FIELD,
		},
		{
			"fieldname": "lft",
			"label": "Left",
			"fieldtype": "Int",
			"hidden": 1,
			"no_copy": 1,
			"allow_on_submit": 1,
			"read_only": 1,
			"insert_after": "is_group",
		},
		{
			"fieldname": "rgt",
			"label": "Right",
			"fieldtype": "Int",
			"hidden": 1,
			"no_copy": 1,
			"allow_on_submit": 1,
			"read_only": 1,
			"insert_after": "lft",
		},
		{
			"fieldname": "old_parent",
			"label": "Old Parent",
			"fieldtype": "Link",
			"options": DOCTYPE,
			"hidden": 1,
			"no_copy": 1,
			"ignore_user_permissions": 1,
			"insert_after": "rgt",
		},
	]
	for df in fields:
		create_custom_field(DOCTYPE, df, ignore_validate=True)


def _add_property_setters() -> None:
	"""Two DocType-level Property Setters. `make_property_setter` is idempotent: it updates an
	existing Property Setter with the same (doc_type, field_name, property) tuple instead of duplicating."""
	make_property_setter(DOCTYPE, None, "is_tree", "1", "Check", for_doctype=True)
	make_property_setter(DOCTYPE, None, "nsm_parent_field", PARENT_FIELD, "Data", for_doctype=True)


def _seed_is_group() -> None:
	"""Mark rows referenced by `custom_parameter_group_child` as groups (is_group=1); all others leaves (is_group=0).

	Idempotent: the WHERE conditions correctly classify regardless of prior state. Uses the primary
	key (`name`) on the inner SELECT for safe-update compliance.
	"""
	# Mark parents
	frappe.db.sql(f"""
		UPDATE `tab{DOCTYPE}`
		SET is_group = 1
		WHERE name IN (
			SELECT * FROM (
				SELECT DISTINCT `{PARENT_FIELD}`
				FROM `tab{DOCTYPE}`
				WHERE `{PARENT_FIELD}` IS NOT NULL AND `{PARENT_FIELD}` != ''
			) AS parents
		)
	""")
	# Mark leaves
	frappe.db.sql(f"""
		UPDATE `tab{DOCTYPE}`
		SET is_group = 0
		WHERE name NOT IN (
			SELECT * FROM (
				SELECT DISTINCT `{PARENT_FIELD}`
				FROM `tab{DOCTYPE}`
				WHERE `{PARENT_FIELD}` IS NOT NULL AND `{PARENT_FIELD}` != ''
			) AS parents
		)
	""")


def _rebuild_tree() -> None:
	"""Compute lft/rgt for all rows via Frappe's NestedSet rebuild. Safe to re-run.

	`rebuild_tree(doctype)` (Frappe 16.x signature) reads the parent_field from
	`meta.nsm_parent_field`, which the Property Setter `_add_property_setters()` just set.
	`frappe.clear_cache(doctype=DOCTYPE)` upstream ensures the meta refresh picks it up.
	"""
	rebuild_tree(DOCTYPE)
