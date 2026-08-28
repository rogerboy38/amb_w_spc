# LOOP-5 — the LOT GRAPH, against VMG-P.
#
# ⭐ WHAT THIS SUITE HAS TO PROVE THAT IS NOT OBVIOUS. Two of the four identifier
# classes are STRUCTURALLY EMPTY on any bench: `custom_historic_lot_real` and the
# customer-lot child table are the carriers LOOP-1 built and deliberately left
# unfilled pending A-3. So a coverage test written against live data would pass
# vacuously on two classes and prove nothing about them.
#
# The split VMG-P ruled, and the reason each half exists:
#   · a SYNTHETIC fixture carries all four identifiers on one lot and asserts
#     they resolve to the SAME node — this proves the RESOLVER, on any substrate,
#     and is rolled back;
#   · a SCOPED live assertion covers only the two populated classes, and records
#     the other two as UNEXERCISED-PENDING-A-3 rather than counting them green.
# Neither half alone is honest.
#
# ⚠ AND THE NEAR-MISS TEST IS ANCHORED TO A POPULATED CLASS ON PURPOSE. A
# near-miss against an empty class is indistinguishable from "not found", so it
# would pass no matter what the code did.
#
# Run: bench --site v2.sysmayal.cloud run-tests --app amb_w_spc \
#          --module amb_w_spc.tests.test_loop5_lot_graph

import ast
import inspect

import frappe

from amb_w_spc.sfc_manufacturing import lot_graph
from amb_w_spc.tests.test_batch_projection import ITEM_JUICE_FAMILY, ProjectionTestBase

GOLDEN = "0397888410"
HISTORIC = "0291004777"
SALES_LOT = "LV-LOOP5-7"


class TestLotGraphStructure(ProjectionTestBase):
	"""The properties that hold regardless of what data exists."""

	def test_the_module_performs_no_writes(self):
		"""⛔⛔ VMG-P P-4/P-5, by AST — a docstring saying 'read-only' is not a control.

		`frappe.log_error` is counted as a WRITE here deliberately: it INSERTs an
		Error Log row, so a read-only tool that logs its own failures writes on
		every failure. This module must not call it.
		"""
		tree = ast.parse(inspect.getsource(lot_graph))
		called = set()
		for n in ast.walk(tree):
			if isinstance(n, ast.Call):
				f, parts = n.func, []
				while isinstance(f, ast.Attribute):
					parts.append(f.attr)
					f = f.value
				if isinstance(f, ast.Name):
					parts.append(f.id)
				called.add(".".join(reversed(parts)))

		banned = {
			"frappe.db.set_value", "frappe.db.commit", "frappe.new_doc",
			"frappe.delete_doc", "frappe.rename_doc", "frappe.log_error",
		}
		self.assertEqual(called & banned, set(), f"write call in a read-only module: {called & banned}")
		for suffix in (".save", ".insert", ".db_set", ".delete", ".submit"):
			offenders = {c for c in called if c.endswith(suffix)}
			self.assertEqual(offenders, set(), f"write-shaped call {offenders}")

	def test_no_write_sql_and_no_fuzzy_matching(self):
		"""⛔ VMG-P P-4 and P-9 — read every SQL string literal in the module.

		A prefix match on this data collides a lot with its own family code, so
		`LIKE` is banned outright rather than reviewed case by case.
		"""
		src = inspect.getsource(lot_graph)
		tree = ast.parse(src)
		literals = [n.value for n in ast.walk(tree)
					if isinstance(n, ast.Constant) and isinstance(n.value, str)]
		sql = [s for s in literals if "select" in s.lower() or "from `tab" in s.lower()]
		self.assertTrue(sql, "no SQL literals found — the detector is looking in the wrong place")
		for s in sql:
			low = s.lower()
			for verb in ("update ", "insert ", "delete ", "replace "):
				self.assertNotIn(verb, low, f"write verb {verb!r} in SQL: {s[:80]}")
			self.assertNotIn(" like ", low, f"fuzzy match in SQL: {s[:80]}")
			self.assertNotIn("%'", s, f"prefix match in SQL: {s[:80]}")

	def test_the_tree_walk_never_reads_lft_or_rgt(self):
		"""⛔ VMG-P P-10. lft/rgt are 0 on every row — NestedSet is not maintained
		— so a query against them returns nothing and READS AS A CLEAN TREE."""
		src = inspect.getsource(lot_graph)
		tree = ast.parse(src)
		# ⚠ DOCSTRINGS ARE EXCLUDED. The module's own docstring EXPLAINS why it
		# never reads lft/rgt, so a scan over every string constant matches the
		# explanation and reports the opposite of the truth. That mistake has now
		# been made four times in this program; the fix is to scan CODE only.
		docstrings = set()
		for n in ast.walk(tree):
			if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
				d = ast.get_docstring(n, clean=False)
				if d:
					docstrings.add(d)
		checked = 0
		for n in ast.walk(tree):
			if isinstance(n, ast.Constant) and isinstance(n.value, str):
				if n.value in docstrings:
					continue
				checked += 1
				low = n.value.lower()
				self.assertNotIn("lft", low, "the module references lft — a false-clean tree query")
				self.assertNotIn("rgt", low, "the module references rgt — a false-clean tree query")
		self.assertGreater(checked, 0, "no non-docstring literals scanned — the detector is dead")
		self.assertIn("parent_batch_amb", src, "the tree walk must use parent_batch_amb")

	def test_it_reads_custom_batch_level_not_batch_level(self):
		"""⛔ VMG-P P-11 — `batch_level` is 100% NULL; a control on it reads clean."""
		src = inspect.getsource(lot_graph)
		self.assertIn("custom_batch_level", src)
		tree = ast.parse(src)
		for n in ast.walk(tree):
			if isinstance(n, ast.Constant) and isinstance(n.value, str):
				self.assertNotEqual(n.value, "batch_level",
									"reads the always-NULL batch_level column")

	def test_it_reuses_both_modules_rather_than_reimplementing(self):
		"""⛔ VMG-P P-2/P-3 — the lookup and the identity matrix each have exactly
		one owner. A second implementation is a second source of truth."""
		src = inspect.getsource(lot_graph)
		self.assertIn("resolve_historic_number", src, "the lookup is not reused")
		self.assertIn("amb_lot_identity", src, "the identity renderer is not reused")
		# and it must not re-query the carriers itself
		for carrier in ("custom_historic_lot_real", "sales_lot ="):
			self.assertNotIn(f"where {carrier}", src.lower(),
							 f"re-queries {carrier} instead of using historic_lookup")


class TestLotGraphResolution(ProjectionTestBase):
	"""Behaviour, with a synthetic lot that carries all four identifiers."""

	def _lot_with_all_four(self):
		doc = frappe.get_doc({
			"doctype": "Batch AMB",
			"custom_batch_level": "1",
			"custom_batch_origin": "Migrated",
			"custom_golden_number": GOLDEN,
			"custom_historic_lot_real": HISTORIC,
			"work_order_ref": None,
			"item_to_manufacture": None,
			"current_item_code": ITEM_JUICE_FAMILY,
			"is_group": 1,
		})
		doc.append("custom_historic_sales_lots", {"sales_lot": SALES_LOT, "year": "2019"})
		doc.insert(ignore_permissions=True)
		self.track(doc)
		return doc

	def test_all_four_identifier_classes_resolve_to_the_same_node(self):
		"""⭐⭐ VMG-P P-6 — the criterion the whole tool exists for.

		Synthetic by necessity: two of the four carriers are empty on every bench
		until A-3 imports, so live data cannot exercise them. Rolled back after.
		"""
		doc = self._lot_with_all_four()
		caps = lot_graph.capabilities()

		for identifier, cls in (
			(doc.name, lot_graph.CLASS_SYSTEM_NAME),
			(GOLDEN, lot_graph.CLASS_GOLDEN),
			(HISTORIC, lot_graph.CLASS_HISTORIC_REAL),
			(SALES_LOT, lot_graph.CLASS_SALES_LOT),
		):
			if not caps.get(cls):
				self.skipTest(f"this site cannot answer on {cls} — carrier absent")
			hit = lot_graph.resolve_lot(identifier)
			self.assertTrue(hit["found"], f"{cls}: {identifier!r} did not resolve")
			self.assertIn(doc.name, hit["nodes"],
						  f"{cls}: resolved to {hit['nodes']}, not {doc.name}")
			self.assertIn(doc.name, hit["matches"][cls],
						  f"{cls}: matched, but not under its own class")

	def test_every_class_is_list_shaped_even_at_one_match(self):
		"""⛔ VMG-P P-7. 10.4% of lots carry >1 sales lot and 12.3% of sales lots
		draw on >1 real lot; a scalar return would silently drop one of them. The
		prod duplicate-title case cannot be built on a bench — this shape check is
		what protects it."""
		doc = self._lot_with_all_four()
		hit = lot_graph.resolve_lot(GOLDEN)
		for cls, v in hit["matches"].items():
			self.assertIsInstance(v, list, f"{cls} is not list-shaped")
		n = lot_graph.node(doc.name)
		self.assertIsInstance(n["identifiers"][lot_graph.CLASS_SALES_LOT], list)
		self.assertIsInstance(n["tree"]["children"], list)

	def test_a_near_miss_does_not_resolve(self):
		"""⛔⛔ VMG-P P-8 / N-1 — a digit transposition must NOT match.

		⚠ Anchored to the GOLDEN class deliberately: it is populated here, so a
		'not found' is a real negative. A near-miss against an empty carrier
		would pass regardless of what the code did."""
		doc = self._lot_with_all_four()
		# ⚠ transpose the first ADJACENT PAIR THAT DIFFERS. Swapping two equal
		# digits yields the original string and the test would assert nothing —
		# my first version did exactly that and its own guard caught it.
		transposed = None
		for i in range(len(GOLDEN) - 1):
			if GOLDEN[i] != GOLDEN[i + 1]:
				transposed = GOLDEN[:i] + GOLDEN[i + 1] + GOLDEN[i] + GOLDEN[i + 2:]
				break
		self.assertIsNotNone(transposed, "GOLDEN has no adjacent differing digits to transpose")
		self.assertNotEqual(transposed, GOLDEN, "the transposition produced the same string")

		hit = lot_graph.resolve_lot(transposed)
		self.assertFalse(hit["found"], f"a transposed identifier resolved to {hit['nodes']}")
		self.assertNotIn(doc.name, hit["nodes"])

	def test_a_suffixed_identifier_is_not_stem_matched(self):
		"""⛔ VMG-P N-3 — the tool must not strip a suffix and match the stem."""
		doc = self._lot_with_all_four()
		hit = lot_graph.resolve_lot(f"{GOLDEN}-JUICE")
		self.assertFalse(hit["found"], "a plant-suffixed identifier stem-matched")
		self.assertNotIn(doc.name, hit["nodes"])

	def test_empty_and_none_return_not_found_never_the_first_row(self):
		"""⛔ VMG-P N-4."""
		for bad in ("", "   ", None):
			hit = lot_graph.resolve_lot(bad)
			self.assertFalse(hit["found"], f"{bad!r} resolved to {hit['nodes']}")
			self.assertEqual(hit["nodes"], [])

	def test_a_sentinel_token_is_not_a_lot(self):
		"""⛔ VMG-P N-2 — 'recall' appears 3,831 times in det_lote's LOTE column
		as a marker, not an identifier."""
		hit = lot_graph.resolve_lot("recall")
		self.assertFalse(hit["found"], f"a sentinel token resolved to {hit['nodes']}")

	def test_the_family_walk_reports_its_own_truncation(self):
		"""⚠ parent_batch_amb is unconstrained, so the depth guard exists to stop a
		cycle. If it fires the caller must be told, not handed a short ancestry."""
		doc = self._lot_with_all_four()
		fam = lot_graph.family(GOLDEN)
		self.assertTrue(fam["found"])
		self.assertIn("depth_truncated", fam)
		self.assertFalse(fam["depth_truncated"], "a single root reported truncation")
		self.assertEqual(fam["roots"], [doc.name])

	def test_capabilities_reports_the_site_not_the_git_tree(self):
		"""⛔ VMG-P P-13 — the two capture fields are Custom Fields; a git-scoped
		check goes green on a site where they do not exist."""
		caps = lot_graph.capabilities()
		self.assertEqual(set(caps), set(lot_graph.IDENTIFIER_CLASSES))
		self.assertTrue(caps[lot_graph.CLASS_SYSTEM_NAME], "the primary key is always answerable")
		for cls, ok in caps.items():
			self.assertIsInstance(ok, bool, f"{cls} capability is not a bool")


class TestLotGraphLiveScope(ProjectionTestBase):
	"""⭐ The SCOPED live half — and it records what it could not exercise."""

	def test_live_coverage_is_scoped_and_the_gap_is_recorded(self):
		"""Two classes are populated on any real bench; two are empty until A-3.

		This test asserts the populated ones against live rows and RECORDS the
		other two as unexercised. It deliberately does not skip: a skip reads as
		a pass, and the gap is a fact worth asserting rather than hiding.
		"""
		populated = frappe.db.sql(
			"""select name, custom_golden_number from `tabBatch AMB`
			   where ifnull(custom_golden_number,'') <> '' limit 1""", as_dict=True)
		if not populated:
			self.skipTest("no live lot carries a golden number on this site")

		row = populated[0]
		hit = lot_graph.resolve_lot(row.custom_golden_number)
		self.assertTrue(hit["found"], "a live golden number did not resolve")
		self.assertIn(row.name, hit["nodes"])

		hit_name = lot_graph.resolve_lot(row.name)
		self.assertTrue(hit_name["found"], "a live system name did not resolve")
		self.assertIn(row.name, hit_name["matches"][lot_graph.CLASS_SYSTEM_NAME])

		# ⚠ the recorded gap — asserted, not assumed
		live_historic = frappe.db.count("Batch AMB", {"custom_historic_lot_real": ["!=", ""]})
		live_sales = frappe.db.count("Batch Historic Sales Lot")
		self.assertEqual(
			(live_historic, live_sales), (0, 0),
			"historic_lot_real / sales_lot now carry live data — the two classes this "
			"suite records as UNEXERCISED-PENDING-A-3 are populated, so the scoped "
			"assertion must be widened to cover them live")
