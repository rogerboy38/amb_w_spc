# LOOP-4 — `create_child_batch`'s handler, as executable record.
#
# ⭐ WHAT THIS SUITE IS ABOUT. The endpoint wrapped 94 lines in one bare
# `except Exception` and returned {"success": False} for anything that threw.
# That single handler produced TWO different defects at TWO different lines:
#
#   throw inside child.insert()  → frappe consumed the naming series in
#                                  set_new_name (document.py:442) BEFORE
#                                  _validate (:448), so the NAME IS GONE and no
#                                  row lands. A front-gap in the series that
#                                  nothing reports. (the ZERO-MINT)
#   throw inside child.save()    → the row was ALREADY inserted, and on a POST
#                                  the request commits at the end regardless, so
#                                  a COMMITTED ROW survived behind a reported
#                                  failure. The operator re-presses. (the
#                                  DOUBLE-MINT's enabler)
#
# ⛔ THE SECOND THROW POINT IS GONE, NOT CAUGHT HARDER. `set_batch_naming()`
# returns immediately for any level != "1" and a child is always level 2 or 3,
# so that call was a no-op and the save behind it persisted nothing. Removing
# the pair removes the throw point — which is why the "no committed row behind a
# failure" property is STRUCTURAL here rather than a promise about catching.
#
# ⚠ WHAT THIS SUITE DOES NOT PROVE, stated so a green is not over-read:
#   · not validate-before-consume — it is RECORD-THE-NAME. The series is
#     consumed inside the framework, below anything this app may touch. The gap
#     still happens; it is now attributable.
#   · not the double-mint — no FOR UPDATE, no unique index, and a second
#     "Create Sublot" button exists as a DB Client Script. That class is OPEN.
#   · not the title-length class — the composer is auto_set_title(), out of
#     this cargo's scope. Carried separately.
#
# Run: bench --site v2.sysmayal.cloud run-tests --app amb_w_spc \
#          --module amb_w_spc.tests.test_loop4_child_batch_handler

import frappe

from amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb import create_child_batch
from amb_w_spc.tests.test_batch_projection import ITEM_JUICE_FAMILY, ProjectionTestBase

GOLDEN = "0397888301"


class TestChildBatchHandler(ProjectionTestBase):
	"""The handler's contract, asserted from the DB rather than the return value."""

	def _parent(self, golden=GOLDEN, level="1"):
		doc = frappe.get_doc({
			"doctype": "Batch AMB",
			"custom_batch_level": level,
			"custom_batch_origin": "Migrated",
			"custom_golden_number": golden,
			"work_order_ref": None,
			"item_to_manufacture": None,
			"current_item_code": ITEM_JUICE_FAMILY,
			"is_group": 1,
		})
		doc.insert(ignore_permissions=True)
		self.track(doc)
		return doc

	# ── the healthy direction ────────────────────────────────────────────────
	def test_healthy_mint_lands_and_is_read_back_from_the_db(self):
		"""⭐ VMG-O O-11(b). Asserted from a FRESH get_doc, never the in-memory
		doc — reading the object we just built is the G-5 failure mode and it
		renders identically to success."""
		parent = self._parent()
		result = create_child_batch(parent.name, "2")

		self.assertTrue(result.get("success"), f"healthy mint failed: {result}")
		name = result.get("name")
		self.assertTrue(name, "success returned without a name")
		# ⚠ the endpoint created this row, not the test — track it so the LIFO
		# teardown removes the CHILD before its parent. Without this the parent
		# delete raises NestedSetChildExistsError and the failure looks like a
		# defect in the code under test rather than in the fixture.
		self.track(frappe.get_doc("Batch AMB", name))

		fresh = frappe.get_doc("Batch AMB", name)          # ⛔ from the DB
		self.assertEqual(fresh.custom_batch_level, "2")
		self.assertEqual(fresh.parent_batch_amb, parent.name)
		self.assertTrue(fresh.title, "title did not persist")

	# ── the failing direction ────────────────────────────────────────────────
	def test_invalid_level_is_refused_without_touching_the_series(self):
		"""The cheap guard still returns rather than throwing, and consumes
		nothing — asserted on the series counter, not inferred."""
		parent = self._parent(golden="0397888302")
		before = frappe.db.sql(
			"select current from tabSeries where name like 'LOTE-%' order by name")
		result = create_child_batch(parent.name, "9")
		after = frappe.db.sql(
			"select current from tabSeries where name like 'LOTE-%' order by name")

		self.assertFalse(result.get("success"))
		self.assertEqual(before, after, "an invalid level moved a naming series")

	def test_a_failure_return_names_the_consumed_series_value(self):
		"""⭐⭐ VMG-O O-3/O-4 — the whole point of the cargo.

		A failure must be ATTRIBUTABLE: the caller is told, and the message
		carries the series value that was burned. Before LOOP-4 the return was
		{"success": False, "message": str(e)} with no name anywhere, so a
		front-gap in the series could not be traced to the request that made it.

		⚠ Driven through the real endpoint, not by calling the handler with a
		synthetic exception — a test that fabricates its own error proves the
		test, not the code.
		"""
		parent = self._parent(golden="0397888303")

		# a child whose validate() will refuse: level 3 needs its own parent
		# chain, and the parent here is level 1, so the hierarchy guard throws
		# inside insert() — AFTER the series has been consumed.
		result = create_child_batch(parent.name, "3")

		if result.get("success"):
			self.skipTest("this bench accepts L3-under-L1; the refusal path was not exercised")

		self.assertIn("consumed_name", result,
					  "a failure return carries no consumed_name key")
		consumed = result.get("consumed_name")
		if consumed:
			self.assertIn(consumed, result.get("message", ""),
						  "the consumed series value is not surfaced in the message "
						  "the desk shows the operator")

	def test_no_row_survives_a_reported_failure(self):
		"""⭐⭐ VMG-O O-5. The second throw point is gone, so this is structural —
		but structure is a claim, and a claim gets a test. Counted from the DB
		before and after."""
		parent = self._parent(golden="0397888304")
		before = frappe.db.count("Batch AMB", {"parent_batch_amb": parent.name})
		result = create_child_batch(parent.name, "3")
		after = frappe.db.count("Batch AMB", {"parent_batch_amb": parent.name})

		if result.get("success"):
			self.assertEqual(after - before, 1, "a success did not land exactly one row")
		else:
			self.assertEqual(after, before,
							 "a row survived a call that reported failure — the "
							 "committed-row-behind-a-failure defect is back")

	# ── the structural claims ────────────────────────────────────────────────
	def test_the_handler_is_not_a_bare_swallow(self):
		"""⛔ VMG-O O-2. Asserted on the AST of the shipped function, not on a
		grep: the removal comment quotes the old code verbatim, so a substring
		check matches the comment and reports the opposite of the truth. That
		mistake was made twice in this program before it was written down."""
		import ast
		import inspect
		from amb_w_spc.sfc_manufacturing.doctype.batch_amb import batch_amb

		tree = ast.parse(inspect.getsource(batch_amb.create_child_batch))
		handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
		self.assertTrue(handlers, "the function has no exception handlers at all")

		for h in handlers:
			names = []
			t = h.type
			if isinstance(t, ast.Attribute):
				names.append(t.attr)
			elif isinstance(t, ast.Name):
				names.append(t.id)
			if names == ["Exception"]:
				# a broad handler is permitted ONLY if it re-raises
				reraises = any(isinstance(n, ast.Raise) for n in ast.walk(h))
				self.assertTrue(
					reraises,
					"a bare `except Exception` that does not re-raise is back — "
					"that is the defect this cargo exists to remove")

	def test_the_no_op_naming_pair_is_gone(self):
		"""⛔ VMG-O O-6, by AST for the same reason as above."""
		import ast
		import inspect
		from amb_w_spc.sfc_manufacturing.doctype.batch_amb import batch_amb

		tree = ast.parse(inspect.getsource(batch_amb.create_child_batch))
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

		self.assertNotIn("child.set_batch_naming", called,
						 "set_batch_naming is a no-op for children and is called again")
		self.assertNotIn("child.save", called,
						 "the post-insert save is back — it is throw point 2, the one "
						 "that leaves a committed row behind a reported failure")

	def test_the_gate_statement_names_what_it_does_not_guard(self):
		"""⭐ VMG-O O-13. A fence that does not say where it ends gets read as a
		fence around the field."""
		import inspect
		from amb_w_spc.sfc_manufacturing.doctype.batch_amb import batch_amb

		doc = inspect.getdoc(batch_amb.create_child_batch) or ""
		for token in ("F-43", "set_value", "DOUBLE-MINT", "auto_set_title"):
			self.assertIn(token, doc,
						  f"the gate statement does not name {token} among the paths "
						  f"it cannot guard")
