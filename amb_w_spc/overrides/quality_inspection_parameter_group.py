"""Phase 1A Step 2A — Override class giving Quality Inspection Parameter Group NestedSet tree semantics.

Pattern A1: extends ERPNext's vanilla `QualityInspectionParameterGroup` (which is a no-op `class ... (Document): pass`) by adding NestedSet as a mixin base. The Custom Field `custom_parameter_group_child` (existing on prod) is the parent pointer.

MRO note: `(NestedSet, _ErpQualityInspectionParameterGroup)` — NestedSet's lifecycle methods (`on_update`, `on_trash`) take precedence on name conflicts. The vanilla ERPNext class is a pure stub (verified 2026-05-12: `pass` body, no locally-defined lifecycle methods), so nothing is shadowed. Frappe's `override_doctype_class` hook validates that the override is a subclass of the vanilla — inheritance from `_ErpQualityInspectionParameterGroup` satisfies that check.

Registered via `override_doctype_class` in amb_w_spc.hooks. Required Custom Fields (`is_group`, `lft`, `rgt`, `old_parent`) and Property Setters (`is_tree=1`, `nsm_parent_field=custom_parameter_group_child`) are installed by the migration patch `amb_w_spc.patches.v15.setup_qip_group_tree_extension`.
"""

from erpnext.stock.doctype.quality_inspection_parameter_group.quality_inspection_parameter_group import (
	QualityInspectionParameterGroup as _ErpQualityInspectionParameterGroup,
)
from frappe.utils.nestedset import NestedSet


class QualityInspectionParameterGroup(NestedSet, _ErpQualityInspectionParameterGroup):
	nsm_parent_field = "custom_parameter_group_child"
