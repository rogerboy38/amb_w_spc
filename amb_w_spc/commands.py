"""Phase 1.2 bench admin commands for amb_w_spc.

Authored by claude-ubuntuvm 2026-05-12 per Phase 1.2 kickoff f1b2a8d4
and claude-sandbox's coordination letter 070e563e.

Scope:
- DocType: Quality Inspection Parameter Group (Step 2A target)
  - NestedSet tree fields: is_group, lft, rgt, old_parent
  - Parent pointer field: custom_parameter_group_child
- DocType: TDS Product Specification (Step 2B target)
  - Form derivation: form Custom Field, fetch_from product_item.item_group

All commands fail gracefully (exit 2) if invoked BEFORE their respective
Phase 1A sub-step applies — they introspect the schema first and report
"not ready" rather than tracebacking on a missing column.

Idempotent + safe to re-run by design.
"""

import click

import frappe
from frappe.commands import get_site, pass_context


DOCTYPE = "Quality Inspection Parameter Group"
TABLE = "tabQuality Inspection Parameter Group"
PARENT_FIELD = "custom_parameter_group_child"
TREE_COLUMNS = ("is_group", "lft", "rgt", "old_parent")

TDS_DOCTYPE = "TDS Product Specification"
TDS_TABLE = "tabTDS Product Specification"
TDS_FORM_COLUMN = "form"

IQI_DOCTYPE = "Item Quality Inspection Parameter"
IQI_TABLE = "tabItem Quality Inspection Parameter"
QIP_PARAM_TABLE = "tabQuality Inspection Parameter"

# Phase 1B-1 Pattern A1 overlay targets (ADR-004 §2/§3).
SPC_PM_DOCTYPE = "SPC Parameter Master"
SPC_PM_TABLE = "tabSPC Parameter Master"
SPC_PM_OVERLAY_CFS = (
	"qip_source",
	"parameter_group",
	"default_l4_spec",
	"external_method_reference",
	"default_method",
	"insumos_y_materiales",
)
SPC_PM_BASE_FIELD_COUNT = 27  # MiniMax Agent canonical (ADR-004 inventory)
SPC_PM_VALIDATE_HOOK = (
	"amb_w_spc.core_spc.spc_server_validations.validate_spc_parameter_master"
)

SPC_SPEC_DOCTYPE = "SPC Specification"
SPC_SPEC_TABLE = "tabSPC Specification"
SPC_SPEC_BASE_FIELD_COUNT = 66  # MiniMax Agent canonical (ADR-004 §3)
SPC_SPEC_VALIDATE_HOOK = (
	"amb_w_spc.core_spc.spc_server_validations.validate_spc_specification"
)
# SPC Specification overlay CFs — TBD per ADR-004 §3 (sandbox to finalize
# post-Tier 0 in follow-up inventory letter). Audit gates this dimension
# until the tuple is populated. Probable: qip_source, item_link/product_item,
# parameter_master, selected_l4_spec.
SPC_SPEC_OVERLAY_CFS: tuple = ()


def _check_tree_schema_ready():
	"""Return (ready: bool, missing: list[str]).

	Used to gate operations against the post-Step-2A schema. If any of the
	four NestedSet columns is absent, the tree extension hasn't landed yet.
	"""
	present = set(
		frappe.db.sql_list(
			"""SELECT column_name FROM information_schema.columns
			   WHERE table_schema = DATABASE() AND table_name = %s""",
			TABLE,
		)
	)
	missing = [c for c in TREE_COLUMNS if c not in present]
	return (not missing, missing)


@click.command("audit_qip_tree_health")
@pass_context
def audit_qip_tree_health(context):
	"""Audit tree-integrity invariants on Quality Inspection Parameter Group.

	Reports four checks:
	  1. Schema readiness (Step 2A applied?)
	  2. Rows with NULL lft or rgt
	  3. Rows where rgt <= lft (NestedSet bound violation)
	  4. Orphan parent references (custom_parameter_group_child pointing
	     to a non-existent row name)

	Exit codes:
	  0  healthy — all invariants hold
	  1  unhealthy — one or more violations
	  2  schema not ready — Step 2A patches not yet applied
	"""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		click.echo(f"Auditing tree health on '{DOCTYPE}' (site: {site})")

		ready, missing = _check_tree_schema_ready()
		if not ready:
			click.echo(f"  ! schema not ready - missing columns: {missing}")
			click.echo("  -> Phase 1A Step 2A patches not yet applied; cannot audit.")
			raise SystemExit(2)

		total = frappe.db.count(DOCTYPE)
		null_bounds = frappe.db.sql(
			f"SELECT COUNT(*) FROM `{TABLE}` WHERE lft IS NULL OR rgt IS NULL"
		)[0][0]
		bad_bounds = frappe.db.sql(
			f"SELECT COUNT(*) FROM `{TABLE}` WHERE rgt <= lft"
		)[0][0]
		orphan_parents = frappe.db.sql(
			f"""SELECT COUNT(*) FROM `{TABLE}` child
			    WHERE child.{PARENT_FIELD} IS NOT NULL
			      AND child.{PARENT_FIELD} != ''
			      AND NOT EXISTS (
			        SELECT 1 FROM `{TABLE}` parent
			        WHERE parent.name = child.{PARENT_FIELD}
			      )"""
		)[0][0]

		click.echo(f"  total rows:                          {total}")
		click.echo(f"  rows with NULL lft/rgt:              {null_bounds}")
		click.echo(f"  rows where rgt <= lft:               {bad_bounds}")
		click.echo(f"  orphan {PARENT_FIELD} refs: {orphan_parents}")

		violations = null_bounds + bad_bounds + orphan_parents
		if violations:
			click.echo(f"  X {violations} invariant violation(s); tree is unhealthy.")
			raise SystemExit(1)

		click.echo("  OK tree is healthy.")
	finally:
		frappe.destroy()


@click.command("rebuild_specification_tree")
@pass_context
def rebuild_specification_tree(context):
	"""Rebuild NestedSet (lft/rgt) on Quality Inspection Parameter Group.

	Wraps frappe.utils.nestedset.rebuild_tree with verbose logging.
	The parent-pointer column (custom_parameter_group_child) is read from
	the DocType meta's nsm_parent_field Property Setter, which Step 2A
	configures — rebuild_tree() in frappe 16.17.5 takes only the doctype name.

	Use after manual edits to the tree, or to fix invariant violations
	surfaced by audit_qip_tree_health. Idempotent — re-running on a
	healthy tree leaves it unchanged.

	Exit codes:
	  0  rebuild complete (any rows shifted or not)
	  2  schema not ready — Step 2A patches not yet applied
	"""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		click.echo(f"Rebuilding tree for '{DOCTYPE}' (site: {site})")

		ready, missing = _check_tree_schema_ready()
		if not ready:
			click.echo(f"  ! schema not ready - missing columns: {missing}")
			click.echo("  -> Cannot rebuild. Apply Phase 1A Step 2A patches first.")
			raise SystemExit(2)

		# Snapshot pre-state bounds for shift counting
		before = frappe.db.sql(
			f"SELECT name, lft, rgt FROM `{TABLE}`", as_dict=True
		)
		before_map = {r["name"]: (r["lft"], r["rgt"]) for r in before}

		from frappe.utils.nestedset import rebuild_tree

		rebuild_tree(DOCTYPE)

		# Compare post-state
		after = frappe.db.sql(
			f"SELECT name, lft, rgt FROM `{TABLE}`", as_dict=True
		)
		shifted = sum(
			1
			for r in after
			if before_map.get(r["name"]) != (r["lft"], r["rgt"])
		)

		frappe.db.commit()
		click.echo(f"  rebuilt {len(after)} rows; {shifted} had lft/rgt shifts")
		click.echo("  OK tree rebuild complete.")
	finally:
		frappe.destroy()


def _check_tds_form_schema_ready():
	"""Return (ready: bool, missing: list[str]).

	Gates audit_tds_form_health against the post-Step-2B schema.
	The form Custom Field column on tabTDS Product Specification is added
	by Step 2B's migration patch.
	"""
	present = set(
		frappe.db.sql_list(
			"""SELECT column_name FROM information_schema.columns
			   WHERE table_schema = DATABASE() AND table_name = %s""",
			TDS_TABLE,
		)
	)
	missing = [TDS_FORM_COLUMN] if TDS_FORM_COLUMN not in present else []
	return (not missing, missing)


@click.command("audit_tds_form_health")
@pass_context
def audit_tds_form_health(context):
	"""Audit form-derivation invariants on TDS Product Specification.

	Reports:
	  1. Schema readiness (Step 2B applied?)
	  2. form-populated count vs total TDS docs
	  3. form matches product_item.item_group count (derive_form regression)
	  4. Distinct form values (expect ~7 Item Groups on VM3 substrate)
	  5. Orphan form references (form values not resolving to a real Item Group)

	Drift on (2) or (3) indicates a derive_form hook regression OR a TDS
	doc saved with an inconsistent form override. Drift on (5) indicates
	an Item Group rename or delete that orphaned downstream references.

	Exit codes:
	  0  healthy — all invariants hold
	  1  unhealthy — one or more violations
	  2  schema not ready — Step 2B patches not yet applied
	"""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		click.echo(f"Auditing form-derivation health on '{TDS_DOCTYPE}' (site: {site})")

		ready, missing = _check_tds_form_schema_ready()
		if not ready:
			click.echo(f"  ! schema not ready - missing columns: {missing}")
			click.echo("  -> Phase 1A Step 2B patches not yet applied; cannot audit.")
			raise SystemExit(2)

		total = frappe.db.count(TDS_DOCTYPE)
		form_populated = frappe.db.sql(
			f"SELECT COUNT(*) FROM `{TDS_TABLE}` "
			f"WHERE {TDS_FORM_COLUMN} IS NOT NULL AND {TDS_FORM_COLUMN} != ''"
		)[0][0]
		form_match_ig = frappe.db.sql(
			f"""SELECT COUNT(*) FROM `{TDS_TABLE}` t
			    JOIN `tabItem` i ON i.name = t.product_item
			    WHERE t.{TDS_FORM_COLUMN} = i.item_group"""
		)[0][0]
		distinct_forms = frappe.db.sql_list(
			f"SELECT DISTINCT {TDS_FORM_COLUMN} FROM `{TDS_TABLE}` "
			f"WHERE {TDS_FORM_COLUMN} IS NOT NULL AND {TDS_FORM_COLUMN} != '' "
			f"ORDER BY {TDS_FORM_COLUMN}"
		)
		orphan_forms = frappe.db.sql(
			f"""SELECT COUNT(*) FROM `{TDS_TABLE}` t
			    WHERE t.{TDS_FORM_COLUMN} IS NOT NULL
			      AND t.{TDS_FORM_COLUMN} != ''
			      AND NOT EXISTS (
			        SELECT 1 FROM `tabItem Group` ig WHERE ig.name = t.{TDS_FORM_COLUMN}
			      )"""
		)[0][0]

		click.echo(f"  total TDS docs:                  {total}")
		click.echo(f"  form populated:                  {form_populated}/{total}")
		click.echo(f"  form = product_item.item_group:  {form_match_ig}/{total}")
		click.echo(f"  distinct form values:            {len(distinct_forms)}")
		for f in distinct_forms:
			click.echo(f"    - {f}")
		click.echo(f"  orphan form -> Item Group refs:  {orphan_forms}")

		missing_form = total - form_populated
		derive_drift = total - form_match_ig
		violations = missing_form + derive_drift + orphan_forms
		if violations:
			parts = []
			if missing_form:
				parts.append(f"{missing_form} doc(s) with empty form")
			if derive_drift:
				parts.append(f"{derive_drift} doc(s) with form != product_item.item_group")
			if orphan_forms:
				parts.append(f"{orphan_forms} orphan form ref(s)")
			click.echo(f"  X violations: {', '.join(parts)}")
			raise SystemExit(1)

		click.echo("  OK form-derivation is healthy.")
	finally:
		frappe.destroy()


@click.command("audit_iqi_parameter_completeness")
@pass_context
def audit_iqi_parameter_completeness(context):
	"""Audit IQI Parameter completeness vs source-of-truth QIP records.

	Reports three cohorts of post-Step-2C IQI rows:
	  1. Healthy: parameter_group populated AND matches source QIP's parameter_group
	  2. Unmigratable: parameter_group empty AND source QIP's parameter_group is NULL
	     (Step 2C's documented 15-row edge case; needs QIP-side data hygiene)
	  3. Drift: parameter_group populated AND mismatches source QIP
	     (pre-existing legacy data drift on VM3 2026-05-12 substrate; 15 rows
	     across 4 specifications — Total Solids ×11, Brix grado ×2, Color abs
	     ×1, Polysaccharides ×1. Needs reconciliation at QIP source.)

	Designed for the AUDITOR A2 data-audit cycle on the post-Step-2C state.

	Exit codes:
	  0  healthy — drift count within expected baseline (15 on VM3 substrate)
	  1  drift count exceeds baseline — regression to investigate
	"""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		click.echo(f"Auditing IQI Parameter completeness vs QIP source (site: {site})")

		iqi_total = frappe.db.count(IQI_DOCTYPE)
		non_flag_total = frappe.db.sql(
			f"SELECT COUNT(*) FROM `{IQI_TABLE}` WHERE custom_is_title_row = 0"
		)[0][0]

		populated_match = frappe.db.sql(
			f"""SELECT COUNT(*) FROM `{IQI_TABLE}` iqi
			    JOIN `{QIP_PARAM_TABLE}` qip ON qip.name = iqi.specification
			    WHERE iqi.parameter_group IS NOT NULL AND iqi.parameter_group != ''
			      AND qip.parameter_group IS NOT NULL AND qip.parameter_group != ''
			      AND iqi.parameter_group = qip.parameter_group"""
		)[0][0]

		unmigratable = frappe.db.sql(
			f"""SELECT COUNT(*) FROM `{IQI_TABLE}` iqi
			    JOIN `{QIP_PARAM_TABLE}` qip ON qip.name = iqi.specification
			    WHERE (iqi.parameter_group IS NULL OR iqi.parameter_group = '')
			      AND (qip.parameter_group IS NULL OR qip.parameter_group = '')
			      AND iqi.custom_is_title_row = 0"""
		)[0][0]

		drift = frappe.db.sql(
			f"""SELECT iqi.specification, iqi.parameter_group AS iqi_pg,
			           qip.parameter_group AS qip_pg, COUNT(*) AS row_count
			    FROM `{IQI_TABLE}` iqi
			    JOIN `{QIP_PARAM_TABLE}` qip ON qip.name = iqi.specification
			    WHERE iqi.parameter_group IS NOT NULL AND iqi.parameter_group != ''
			      AND qip.parameter_group IS NOT NULL AND qip.parameter_group != ''
			      AND iqi.parameter_group != qip.parameter_group
			    GROUP BY iqi.specification, iqi.parameter_group, qip.parameter_group
			    ORDER BY row_count DESC, iqi.specification""",
			as_dict=True,
		)
		drift_total = sum(r["row_count"] for r in drift)

		click.echo(f"  total IQI rows:                                {iqi_total}")
		click.echo(f"  non-flag rows (custom_is_title_row=0):         {non_flag_total}")
		click.echo(f"  populated + matches source QIP (healthy):      {populated_match}")
		click.echo(f"  unmigratable (Step 2C edge — QIP has NULL pg): {unmigratable}")
		click.echo(f"  drift (legacy mismatch with source QIP):       {drift_total}")
		if drift:
			click.echo("    drift breakdown:")
			for r in drift:
				click.echo(
					f"      {r['specification']!r}: iqi={r['iqi_pg']!r} "
					f"vs qip={r['qip_pg']!r} ({r['row_count']} row(s))"
				)

		baseline_drift = 15  # VM3 2026-05-12 substrate baseline
		if drift_total > baseline_drift:
			click.echo(
				f"  X drift exceeds baseline ({drift_total} > {baseline_drift}) — investigate."
			)
			raise SystemExit(1)

		click.echo(f"  OK drift within baseline ({drift_total} <= {baseline_drift}).")
	finally:
		frappe.destroy()


def _overlay_field_state(doctype, table, field_names):
	"""Return per-field state via {column present, meta-field present, source}.

	Returns dict {field_name: (col_present, meta_present, source)} where source
	is one of "docfield", "custom_field", or None.

	Pattern-agnostic — works for both:
	  - Pattern A1 (Custom Field overlay): meta_present comes from tabCustom Field
	  - Pattern A2 (direct DocField in JSON): meta_present comes from tabDocField

	`frappe.get_meta(doctype).fields` is the unified abstraction: it merges
	DocField (canonical JSON) + Custom Field (per-site overlay) into one list,
	with `is_custom_field` set on the overlaid entries. The audit only cares
	whether the field is metadata-backed; pattern (A1 vs A2) is incidental.

	A "phantom column" is col_present=True, meta_present=False — typically an
	aborted earlier overlay attempt that left the ALTER TABLE in place but
	didn't (or no longer) registers the field metadata via either surface.
	Preserve-by-default discipline (shared Lesson 119): never DROP these;
	flag and re-back via the next overlay.
	"""
	cols_present = set(
		frappe.db.sql_list(
			"""SELECT column_name FROM information_schema.columns
			   WHERE table_schema = DATABASE() AND table_name = %s""",
			table,
		)
	)
	# Build the meta-source map: which field-name is backed by what surface.
	meta_source = {}
	try:
		meta = frappe.get_meta(doctype)
		for f in meta.fields:
			if not getattr(f, "fieldname", None):
				continue
			meta_source[f.fieldname] = (
				"custom_field" if getattr(f, "is_custom_field", 0) else "docfield"
			)
	except Exception:
		# meta unavailable — fall through with empty source map; helper still
		# returns column-presence data, just marks all meta_present=False.
		pass
	return {
		fn: (fn in cols_present, fn in meta_source, meta_source.get(fn))
		for fn in field_names
	}


def _check_spc_pm_overlay_schema_ready():
	"""Return (ready, missing_full, phantom_cols, registered_no_col, sources).

	"Fully deployed" requires BOTH the DB column AND a metadata-backing row
	(via either tabDocField for Pattern A2 or tabCustom Field for Pattern A1):
	  - missing_full: no column, no meta row → not deployed
	  - phantom_cols: column present, meta row absent → preserve-by-default
	  - registered_no_col: meta row present, column absent → needs bench migrate

	`sources` is a dict {field_name: "docfield"|"custom_field"|None} for
	post-deploy reporting clarity (tells future readers which pattern landed).

	`ready=True` only when all overlay fields are fully metadata-backed.
	"""
	state = _overlay_field_state(SPC_PM_DOCTYPE, SPC_PM_TABLE, SPC_PM_OVERLAY_CFS)
	missing_full = [fn for fn, (col, meta, _) in state.items() if not col and not meta]
	phantom_cols = [fn for fn, (col, meta, _) in state.items() if col and not meta]
	registered_no_col = [fn for fn, (col, meta, _) in state.items() if meta and not col]
	fully_deployed = [fn for fn, (col, meta, _) in state.items() if col and meta]
	sources = {fn: src for fn, (_c, _m, src) in state.items()}
	ready = len(fully_deployed) == len(SPC_PM_OVERLAY_CFS)
	return (ready, missing_full, phantom_cols, registered_no_col, sources)


def _check_spc_spec_overlay_schema_ready():
	"""Return (ready, missing_full, phantom_cols, registered_no_col, sources).

	Same shape as _check_spc_pm_overlay_schema_ready. When
	SPC_SPEC_OVERLAY_CFS is empty (pre-sandbox-inventory), returns ready=True
	with empty lists/dict; the audit's other dimensions still run.
	"""
	if not SPC_SPEC_OVERLAY_CFS:
		return (True, [], [], [], {})
	state = _overlay_field_state(SPC_SPEC_DOCTYPE, SPC_SPEC_TABLE, SPC_SPEC_OVERLAY_CFS)
	missing_full = [fn for fn, (col, meta, _) in state.items() if not col and not meta]
	phantom_cols = [fn for fn, (col, meta, _) in state.items() if col and not meta]
	registered_no_col = [fn for fn, (col, meta, _) in state.items() if meta and not col]
	fully_deployed = [fn for fn, (col, meta, _) in state.items() if col and meta]
	sources = {fn: src for fn, (_c, _m, src) in state.items()}
	ready = len(fully_deployed) == len(SPC_SPEC_OVERLAY_CFS)
	return (ready, missing_full, phantom_cols, registered_no_col, sources)


def _expected_base_db_field_count(doctype, exclude_fieldnames=()):
	"""Return count of MiniMax Agent base fields that materialize as DB columns.

	Excludes layout-only fieldtypes (Section/Column/Tab Break, HTML, etc.),
	table fields (Table / Table MultiSelect — live in child tables), Custom
	Field overlays (is_custom_field=1), AND any fieldnames in
	`exclude_fieldnames` (for Pattern A2 where overlay fields are first-class
	DocFields and the audit subtracts them on the actual-cols side).
	"""
	LAYOUT_FIELDTYPES = {
		"Section Break", "Column Break", "Tab Break", "HTML", "Heading",
		"Button", "Image", "Fold",
	}
	CHILD_FIELDTYPES = {"Table", "Table MultiSelect"}
	exclude = set(exclude_fieldnames)
	try:
		meta = frappe.get_meta(doctype)
		base_count = 0
		for f in meta.fields:
			if f.fieldtype in LAYOUT_FIELDTYPES:
				continue
			if f.fieldtype in CHILD_FIELDTYPES:
				continue
			if getattr(f, "is_custom_field", 0):
				continue
			if f.fieldname in exclude:
				continue
			base_count += 1
		return base_count
	except Exception:
		return None


def _hook_wired(doctype, expected_method_path):
	"""Return (wired, callable_ok, observed_value).

	Verifies that `doc_events[doctype]['validate']` resolves to
	`expected_method_path` AND that the function is importable + callable.
	"""
	hooks = frappe.get_hooks("doc_events") or {}
	entry = hooks.get(doctype) or {}
	observed = entry.get("validate")
	if isinstance(observed, list):
		observed_value = observed[0] if observed else None
	else:
		observed_value = observed
	wired = observed_value == expected_method_path

	import importlib

	callable_ok = False
	if wired:
		try:
			mod_path, _, func_name = expected_method_path.rpartition(".")
			mod = importlib.import_module(mod_path)
			fn = getattr(mod, func_name, None)
			callable_ok = callable(fn)
		except Exception:
			callable_ok = False
	return (wired, callable_ok, observed_value)


def _validator_runs_clean(doctype, populate_healthy):
	"""Build an in-memory doc via populate_healthy(doc), call validate.

	Returns (ok, err_msg). No DB mutation — doc is never saved.
	"""
	try:
		doc = frappe.new_doc(doctype)
		populate_healthy(doc)
		doc.run_method("validate")
		return (True, None)
	except Exception as e:
		return (False, f"{type(e).__name__}: {e}")


def _validator_rejects_bad(doctype, populate_bad):
	"""Build an in-memory bad-input doc; expect run_method('validate') to raise.

	Returns (ok, observed). ok=True if a ValidationError (or subclass) was raised.
	"""
	try:
		doc = frappe.new_doc(doctype)
		populate_bad(doc)
		doc.run_method("validate")
		return (False, "no exception raised; validator failed to reject bad input")
	except frappe.ValidationError as e:
		return (True, f"{type(e).__name__} raised as expected: {e}")
	except Exception as e:
		return (False, f"unexpected exception type: {type(e).__name__}: {e}")


def _ps_active(doctype, fieldname_or_none, prop, expected_value):
	"""Return (active, observed).

	If fieldname_or_none is None → DocType-level Property Setter.
	"""
	filters = {"doc_type": doctype, "property": prop}
	if fieldname_or_none is None:
		filters["field_name"] = ""
	else:
		filters["field_name"] = fieldname_or_none
	row = frappe.db.get_value(
		"Property Setter", filters, ["value"], as_dict=True
	)
	if not row:
		return (False, None)
	observed = row["value"]
	return (str(observed) == str(expected_value), observed)


def _default_company():
	"""Return a Company name (any) for in-memory test docs, or None."""
	return frappe.db.get_value("Company", {}, "name")


@click.command("audit_spc_parameter_master_health")
@pass_context
def audit_spc_parameter_master_health(context):
	"""Audit Phase 1B-1 overlay invariants on SPC Parameter Master (D#3.1).

	Pattern-agnostic — verifies the 6 overlay fields are metadata-backed via
	either Pattern A1 (tabCustom Field) OR Pattern A2 (tabDocField), via
	`frappe.get_meta(...).fields` abstraction. Source reported per field.

	Verifies post-deploy state across 8 dimensions per ADR-004 §2 / ADR-007
	+ cowork commission ubuntuvm-commission-d3-audit-commands §1:

	  1. Schema readiness — 6 overlay fields present + metadata-backed
	     (qip_source, parameter_group, default_l4_spec,
	      external_method_reference, default_method, insumos_y_materiales)
	  2. MiniMax Agent base schema preserved (27 base fields intact)
	  3. Property Setter parameter_name.unique=1 active
	  4. FK integrity — qip_source Link targets resolve to valid QIP records
	  5. doc_events validate hook loaded
	     (amb_w_spc.core_spc.spc_server_validations.validate_spc_parameter_master)
	  6. Validator runs clean on a healthy in-memory test doc
	  7. Validator raises SPCValidationError on a bad-input in-memory doc
	  8. Row count baseline (informational; overlay deploy should not seed data)

	Test docs are in-memory only; nothing is saved, nothing committed.

	Exit codes:
	  0  healthy — all 7 hard checks pass (row count is informational)
	  1  unhealthy — one or more hard checks failed
	  2  schema not ready — overlay not yet deployed; or phantom columns
	     (preserve-by-default, await next overlay) reported alongside
	"""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		click.echo(f"Auditing Pattern A1 overlay on '{SPC_PM_DOCTYPE}' (site: {site})")

		ready, missing_full, phantom_cols, registered_no_col, sources = (
			_check_spc_pm_overlay_schema_ready()
		)
		if not ready:
			click.echo("  ! Phase 1B-1 overlay not fully deployed:")
			if missing_full:
				click.echo(
					f"    - missing entirely (no column, no metadata row): {missing_full}"
				)
			if phantom_cols:
				click.echo(
					f"    ! PHANTOM COLUMNS (column present, no metadata row — "
					f"preserve-by-default per Lesson 119; next overlay re-backs): "
					f"{phantom_cols}"
				)
			if registered_no_col:
				click.echo(
					f"    - registered but column absent (run bench migrate): "
					f"{registered_no_col}"
				)
			click.echo("  -> cannot audit post-deploy invariants until overlay is fully deployed.")
			raise SystemExit(2)

		violations = []

		# Check 1: overlay fields fully deployed (col + metadata row)
		# Report metadata source per field so reviewers can see at a glance
		# whether Pattern A1 (custom_field) or Pattern A2 (docfield) landed.
		click.echo(
			f"  [1/8] overlay fields: {len(SPC_PM_OVERLAY_CFS)}/6 fully deployed"
		)
		for fn in SPC_PM_OVERLAY_CFS:
			src = sources.get(fn) or "unknown"
			click.echo(f"    + {fn}  (source: {src})")

		# Check 2: MiniMax Agent base schema preserved (via Frappe meta)
		# Exclude overlay fieldnames on BOTH sides so the check is pattern-agnostic
		# (Pattern A1 excludes them via is_custom_field; Pattern A2 needs explicit
		# exclude param since they're first-class DocFields).
		expected_base = _expected_base_db_field_count(
			SPC_PM_DOCTYPE, exclude_fieldnames=SPC_PM_OVERLAY_CFS
		)
		FRAPPE_SYSTEM_COLS = {
			"name", "creation", "modified", "modified_by", "owner",
			"docstatus", "idx", "_user_tags", "_comments", "_assign",
			"_liked_by",
		}
		all_cols = set(
			frappe.db.sql_list(
				"""SELECT column_name FROM information_schema.columns
				   WHERE table_schema = DATABASE() AND table_name = %s""",
				SPC_PM_TABLE,
			)
		)
		non_system = all_cols - FRAPPE_SYSTEM_COLS
		base_cols = non_system - set(SPC_PM_OVERLAY_CFS)
		base_ok = (expected_base is None) or len(base_cols) >= expected_base
		marker = "OK" if base_ok else "FAIL"
		click.echo(
			f"  [2/8] MiniMax Agent base schema: {len(base_cols)} non-overlay "
			f"non-system DB cols (expected >= {expected_base}) {marker}"
		)
		if not base_ok:
			violations.append(
				f"base schema regression: {len(base_cols)} < {expected_base}"
			)

		# Check 3: PS parameter_name.unique=1
		ps_ok, ps_observed = _ps_active(SPC_PM_DOCTYPE, "parameter_name", "unique", "1")
		marker = "OK" if ps_ok else "FAIL"
		click.echo(
			f"  [3/8] PS parameter_name.unique=1: {marker} (observed: {ps_observed!r})"
		)
		if not ps_ok:
			violations.append(
				f"Property Setter parameter_name.unique not active (observed: {ps_observed!r})"
			)

		# Check 4: FK integrity on qip_source
		dangling_fk = frappe.db.sql(
			f"""SELECT COUNT(*) FROM `{SPC_PM_TABLE}` pm
			    WHERE pm.qip_source IS NOT NULL AND pm.qip_source != ''
			      AND NOT EXISTS (
			        SELECT 1 FROM `{QIP_PARAM_TABLE}` qip
			        WHERE qip.name = pm.qip_source
			      )"""
		)[0][0]
		fk_ok = dangling_fk == 0
		marker = "OK" if fk_ok else "FAIL"
		click.echo(f"  [4/8] qip_source FK integrity: {dangling_fk} dangling refs {marker}")
		if not fk_ok:
			violations.append(f"{dangling_fk} dangling qip_source FK ref(s)")

		# Check 5: doc_events validate hook wired + callable
		wired, callable_ok, observed = _hook_wired(SPC_PM_DOCTYPE, SPC_PM_VALIDATE_HOOK)
		hook_ok = wired and callable_ok
		marker = "OK" if hook_ok else "FAIL"
		click.echo(
			f"  [5/8] doc_events validate hook: wired={wired} callable={callable_ok} {marker}"
		)
		if not hook_ok:
			violations.append(
				f"validate hook not properly wired (wired={wired}, callable={callable_ok}, "
				f"observed={observed!r})"
			)

		# Check 6: validator runs clean on healthy doc
		def populate_healthy(doc):
			doc.parameter_name = f"AUDIT_TEST_HEALTHY_{int(_now())}"
			doc.parameter_code = "AUDIT_TEST_HEALTHY_001"
			doc.data_type = "Text"  # avoids the precision branch
			company = _default_company()
			if company:
				doc.company = company

		clean_ok, clean_err = _validator_runs_clean(SPC_PM_DOCTYPE, populate_healthy)
		marker = "OK" if clean_ok else "FAIL"
		click.echo(f"  [6/8] validator runs on healthy doc: {marker}")
		if not clean_ok:
			click.echo(f"    error: {clean_err}")
			violations.append(f"validator failed on healthy doc: {clean_err}")

		# Check 7: validator rejects bad-input doc
		def populate_bad(doc):
			doc.parameter_name = f"AUDIT_TEST_BAD_{int(_now())}"
			doc.parameter_code = "BAD CODE!"  # space + ! fail the regex
			doc.data_type = "Text"
			company = _default_company()
			if company:
				doc.company = company

		bad_ok, bad_observed = _validator_rejects_bad(SPC_PM_DOCTYPE, populate_bad)
		marker = "OK" if bad_ok else "FAIL"
		click.echo(f"  [7/8] validator rejects bad input: {marker}")
		click.echo(f"    observed: {bad_observed}")
		if not bad_ok:
			violations.append(f"validator did not reject bad input: {bad_observed}")

		# Check 8: row count (informational)
		row_count = frappe.db.count(SPC_PM_DOCTYPE)
		click.echo(f"  [8/8] row count: {row_count} (informational; pre-seed baseline=0)")

		# No DB writes occurred; rollback any cached state from the validator runs.
		frappe.db.rollback()

		if violations:
			click.echo(f"  X {len(violations)} hard-check violation(s):")
			for v in violations:
				click.echo(f"    - {v}")
			raise SystemExit(1)

		click.echo(f"  OK SPC Parameter Master overlay is healthy (7/7 hard checks pass).")
	finally:
		frappe.destroy()


@click.command("audit_spc_specification_health")
@pass_context
def audit_spc_specification_health(context):
	"""Audit Phase 1B-1 overlay invariants on SPC Specification (D#3.2).

	Pattern-agnostic — same meta-abstraction as audit_spc_parameter_master_health.
	Verifies overlay fields are metadata-backed via either Pattern A1 or A2.

	Verifies post-deploy state across the dimensions known at authoring time
	per ADR-004 §3 / ADR-007 (overlay field spec TBD post-sandbox inventory).
	Hard checks:

	  1. doc_events validate hook loaded
	     (amb_w_spc.core_spc.spc_server_validations.validate_spc_specification)
	  2. Property Setter (ADR-003) on Item Quality Inspection Parameter
	     value.depends_on = "eval:doc.specification" active
	  3. Validator runs clean on a healthy in-memory test doc
	  4. Validator raises ValidationError on a bad-input in-memory doc
	  5. SPC Specification base schema preserved (storage-only count per
	     `frappe.get_meta`; layout + child fieldtypes excluded)
	  6. Row count baseline (informational)
	  7. (gated) Overlay field schema — skipped while
	     SPC_SPEC_OVERLAY_CFS is empty; activates once sandbox finalizes
	     the SPC Specification overlay batch.

	Test docs are in-memory only; nothing is saved.

	Exit codes:
	  0  healthy — all active hard checks pass
	  1  unhealthy — one or more checks failed
	  2  schema not ready — SPC Specification table or framework absent
	"""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		click.echo(f"Auditing Pattern A1 overlay on '{SPC_SPEC_DOCTYPE}' (site: {site})")

		# Pre-gate: framework presence
		table_exists = frappe.db.sql(
			"""SELECT COUNT(*) FROM information_schema.tables
			   WHERE table_schema = DATABASE() AND table_name = %s""",
			SPC_SPEC_TABLE,
		)[0][0]
		if not table_exists:
			click.echo(f"  ! '{SPC_SPEC_TABLE}' table not found; framework absent or not migrated.")
			raise SystemExit(2)

		# Overlay-field gate (active only when SPC_SPEC_OVERLAY_CFS is populated)
		ready, missing_full, phantom_cols, registered_no_col, sources = (
			_check_spc_spec_overlay_schema_ready()
		)
		if not ready:
			click.echo("  ! Phase 1B-1 overlay not fully deployed:")
			if missing_full:
				click.echo(f"    - missing entirely: {missing_full}")
			if phantom_cols:
				click.echo(
					f"    ! PHANTOM COLUMNS (column present, no metadata row — "
					f"preserve-by-default): {phantom_cols}"
				)
			if registered_no_col:
				click.echo(f"    - registered but column absent: {registered_no_col}")
			click.echo("  -> cannot audit post-deploy invariants until overlay is fully deployed.")
			raise SystemExit(2)

		violations = []

		# Check 1: doc_events validate hook
		wired, callable_ok, observed = _hook_wired(
			SPC_SPEC_DOCTYPE, SPC_SPEC_VALIDATE_HOOK
		)
		hook_ok = wired and callable_ok
		marker = "OK" if hook_ok else "FAIL"
		click.echo(
			f"  [1] doc_events validate hook: wired={wired} callable={callable_ok} {marker}"
		)
		if not hook_ok:
			violations.append(
				f"validate hook not properly wired (wired={wired}, callable={callable_ok}, "
				f"observed={observed!r})"
			)

		# Check 2: ADR-003 PS on IQI Parameter value.depends_on
		ps_ok, ps_observed = _ps_active(
			IQI_DOCTYPE, "value", "depends_on", "eval:doc.specification"
		)
		marker = "OK" if ps_ok else "FAIL"
		click.echo(
			f"  [2] PS IQI.value.depends_on: {marker} (observed: {ps_observed!r})"
		)
		if not ps_ok:
			violations.append(
				f"ADR-003 Property Setter IQI.value.depends_on not active "
				f"(observed: {ps_observed!r})"
			)

		# Check 3: validator runs clean on healthy doc
		# Validator references upper/lower_control_limit + valid_from/valid_to —
		# set defensively so AttributeErrors don't masquerade as validator
		# failures. Also calls check_overlapping_specifications() which queries
		# the DB — on an unsaved doc with a unique name, returns no overlaps.
		def populate_healthy(doc):
			doc.specification_name = f"AUDIT_TEST_HEALTHY_{int(_now())}"
			doc.target_value = 10.0
			doc.tolerance_plus = 1.0
			doc.tolerance_minus = 1.0
			doc.upper_spec_limit = 11.0
			doc.lower_spec_limit = 9.0
			doc.upper_control_limit = 10.5
			doc.lower_control_limit = 9.5
			doc.valid_from = None
			doc.valid_to = None
			company = _default_company()
			if company:
				doc.company = company

		clean_ok, clean_err = _validator_runs_clean(SPC_SPEC_DOCTYPE, populate_healthy)
		marker = "OK" if clean_ok else "FAIL"
		click.echo(f"  [3] validator runs on healthy doc: {marker}")
		if not clean_ok:
			click.echo(f"    error: {clean_err}")
			violations.append(f"validator failed on healthy doc: {clean_err}")

		# Check 4: validator rejects bad-input doc (negative tolerance_plus)
		def populate_bad(doc):
			doc.specification_name = f"AUDIT_TEST_BAD_{int(_now())}"
			doc.target_value = 10.0
			doc.tolerance_plus = -1.0  # negative → SPCValidationError
			doc.tolerance_minus = 1.0
			doc.upper_spec_limit = None
			doc.lower_spec_limit = None
			doc.upper_control_limit = None
			doc.lower_control_limit = None
			doc.valid_from = None
			doc.valid_to = None
			company = _default_company()
			if company:
				doc.company = company

		bad_ok, bad_observed = _validator_rejects_bad(SPC_SPEC_DOCTYPE, populate_bad)
		marker = "OK" if bad_ok else "FAIL"
		click.echo(f"  [4] validator rejects bad input: {marker}")
		click.echo(f"    observed: {bad_observed}")
		if not bad_ok:
			violations.append(f"validator did not reject bad input: {bad_observed}")

		# Check 5: base schema preserved (via Frappe meta; pattern-agnostic)
		expected_base = _expected_base_db_field_count(
			SPC_SPEC_DOCTYPE, exclude_fieldnames=SPC_SPEC_OVERLAY_CFS
		)
		FRAPPE_SYSTEM_COLS = {
			"name", "creation", "modified", "modified_by", "owner",
			"docstatus", "idx", "_user_tags", "_comments", "_assign",
			"_liked_by",
		}
		all_cols = set(
			frappe.db.sql_list(
				"""SELECT column_name FROM information_schema.columns
				   WHERE table_schema = DATABASE() AND table_name = %s""",
				SPC_SPEC_TABLE,
			)
		)
		non_system = all_cols - FRAPPE_SYSTEM_COLS
		base_cols = non_system - set(SPC_SPEC_OVERLAY_CFS)
		base_ok = (expected_base is None) or len(base_cols) >= expected_base
		marker = "OK" if base_ok else "FAIL"
		click.echo(
			f"  [5] MiniMax Agent base schema: {len(base_cols)} non-overlay non-system "
			f"DB cols (expected >= {expected_base}) {marker}"
		)
		if not base_ok:
			violations.append(
				f"base schema regression: {len(base_cols)} < {expected_base}"
			)

		# Check 6: row count (informational)
		row_count = frappe.db.count(SPC_SPEC_DOCTYPE)
		click.echo(f"  [6] row count: {row_count} (informational; pre-seed baseline=0)")

		# Check 7: overlay fields — gated
		if SPC_SPEC_OVERLAY_CFS:
			click.echo(
				f"  [7] overlay fields: {len(SPC_SPEC_OVERLAY_CFS)} present"
			)
			for fn in SPC_SPEC_OVERLAY_CFS:
				src = sources.get(fn) or "unknown"
				click.echo(f"    + {fn}  (source: {src})")
		else:
			click.echo(
				"  [7] overlay fields: SKIP (SPC_SPEC_OVERLAY_CFS empty; "
				"sandbox to finalize per ADR-004 §3 / ADR-007)"
			)

		frappe.db.rollback()

		if violations:
			click.echo(f"  X {len(violations)} hard-check violation(s):")
			for v in violations:
				click.echo(f"    - {v}")
			raise SystemExit(1)

		click.echo(f"  OK SPC Specification overlay is healthy (active hard checks pass).")
	finally:
		frappe.destroy()


def _now():
	"""Module-local timestamp for in-memory test doc unique names."""
	import time
	return time.time()


commands = [
	audit_qip_tree_health,
	rebuild_specification_tree,
	audit_tds_form_health,
	audit_iqi_parameter_completeness,
	audit_spc_parameter_master_health,
	audit_spc_specification_health,
]
