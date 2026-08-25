# LOOP-1 / B-3b — the child-table persistence invariant, as executable record.
#
# ⭐ WHY THIS TEST EXISTS AT ALL. G-5/M90 measured that a table nested inside a
# CHILD doctype is never loaded, never saved, and NEVER THROWS: Frappe gives
# every child row `_table_fieldnames = MappingProxyType({})`, empty and
# immutable, and both load and save iterate exactly that. The grid renders,
# accepts input, and discards it. Three such grids already exist in this install
# and hold zero rows between them.
#
# ⛔ THE FAILURE IS INDISTINGUISHABLE FROM SUCCESS BY INSPECTION. A working grid
# and a silently-discarding grid look identical on screen and in code review.
# The ONLY thing that separates them is saving a row and RELOADING IT FROM THE
# DATABASE. That is why this invariant needs a test rather than a comment, and
# why the test reloads instead of reading the in-memory document.
#
# ⚠ THE PREDICATE IS THE RE-WORDED ONE (Node A's Gate-2 §4 correction). The seal
# letter originally claimed the first row was "byte-unchanged" after a second
# was appended. Measured, that is FALSE: saving the parent rewrites its
# children, so `modified` bumps. What is true — and what actually matters — is:
#
#     on parent save: the child's BUSINESS FIELDS are unchanged
#                     AND the row was NOT re-created (name + creation stable)
#                     AND `modified` MAY bump — that is Frappe, not a defect
#
# Asserting the stronger claim would make this test fail on correct behaviour,
# which is how a guard gets deleted by the next person who trips it.
#
# Run: bench --site v2.sysmayal.cloud run-tests --app amb_w_spc \
#          --module amb_w_spc.tests.test_loop1_historic_persistence

import frappe
from frappe.tests.utils import FrappeTestCase

PARENT = "Batch AMB"
CHILD = "Batch Historic Sales Lot"
TABLE_FIELD = "custom_historic_sales_lots"
SCALAR_FIELD = "custom_historic_lot_real"


class TestHistoricCapturePersistence(FrappeTestCase):
	"""The G-5 failure mode, asserted POSITIVELY on every run."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.batch = frappe.db.get_value(PARENT, {}, "name")
		if not cls.batch:
			raise cls.skipTest(cls, f"no {PARENT} on this site")
		doc = frappe.get_doc(PARENT, cls.batch)
		cls._scalar_before = doc.get(SCALAR_FIELD)
		cls._rows_before = len(doc.get(TABLE_FIELD) or [])

	@classmethod
	def tearDownClass(cls):
		# restore, LIFO, so a failed assertion cannot leave rows on a real batch
		doc = frappe.get_doc(PARENT, cls.batch)
		doc.set(TABLE_FIELD, [])
		doc.set(SCALAR_FIELD, cls._scalar_before)
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _reload(self):
		"""⛔ Always from the DB. Reading the in-memory doc would pass even if
		nothing was ever persisted — the exact blindness this test exists for."""
		return frappe.get_doc(PARENT, self.batch)

	def test_the_table_is_on_a_PARENT_doctype_not_a_child(self):
		"""The structural precondition. If `Batch AMB` were ever `istable=1`,
		every other assertion here would still pass at save time and the rows
		would vanish — so this is asserted first and separately."""
		self.assertEqual(frappe.get_meta(PARENT).istable, 0)
		field = frappe.get_meta(PARENT).get_field(TABLE_FIELD)
		self.assertIsNotNone(field, f"{TABLE_FIELD} missing from {PARENT}")
		self.assertEqual(field.fieldtype, "Table")
		self.assertEqual(field.options, CHILD)

	def test_the_child_doctype_declares_no_nested_table(self):
		"""⛔ The G-5 trap, guarded at its source: a Table field on THIS child
		would be silently discarded, and nothing in Frappe would say so."""
		nested = frappe.db.sql(
			"""select fieldname from tabDocField
			   where parent = %s and fieldtype in ('Table', 'Table MultiSelect')""",
			(CHILD,),
		)
		self.assertEqual(nested, (), f"{CHILD} declares a nested table: {nested}")

	def test_a_saved_row_survives_a_reload(self):
		doc = self._reload()
		doc.append(TABLE_FIELD, {"sales_lot": "LOOP1-P-1", "folio": "0001",
		                         "customer": "TESTCO", "invoice": "F-1", "year": "2019"})
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		rows = self._reload().get(TABLE_FIELD)
		self.assertEqual(len(rows), 1, "the row did not persist — the G-5 failure")
		self.assertEqual(rows[0].sales_lot, "LOOP1-P-1")
		self.assertEqual(rows[0].folio, "0001")

	def test_appending_a_second_row_preserves_the_first(self):
		"""1:N proven — and with the RE-WORDED predicate, not the stronger one."""
		doc = self._reload()
		doc.set(TABLE_FIELD, [])
		doc.append(TABLE_FIELD, {"sales_lot": "LOOP1-R1", "folio": "0001", "year": "2019"})
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		first = self._reload().get(TABLE_FIELD)[0]
		before = {"name": first.name, "creation": first.creation,
		          "sales_lot": first.sales_lot, "folio": first.folio, "year": first.year}

		doc = self._reload()
		doc.append(TABLE_FIELD, {"sales_lot": "LOOP1-R2", "folio": "0002", "year": "2020"})
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		rows = self._reload().get(TABLE_FIELD)
		self.assertEqual(len(rows), 2, "a scalar-like overwrite destroyed the first row")

		after = rows[0]
		# ⭐ NOT re-created — the claim that actually matters
		self.assertEqual(after.name, before["name"], "row was deleted and re-inserted")
		self.assertEqual(after.creation, before["creation"], "row was re-created")
		# ⭐ business fields unchanged
		for f in ("sales_lot", "folio", "year"):
			self.assertEqual(getattr(after, f), before[f], f"{f} changed on parent save")
		# ⚠ `modified` deliberately NOT asserted stable — see the header. Frappe
		# rewrites children on parent save, so it may bump; asserting otherwise
		# would fail on correct behaviour.

	def test_the_scalar_and_the_table_are_independent_carriers(self):
		"""1:1 beside 1:N — a historic number may be either, and the lookup
		queries both, so neither may clobber the other."""
		doc = self._reload()
		doc.set(SCALAR_FIELD, "LOOP1-SCALAR")
		doc.append(TABLE_FIELD, {"sales_lot": "LOOP1-TABLE", "year": "2019"})
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		fresh = self._reload()
		self.assertEqual(fresh.get(SCALAR_FIELD), "LOOP1-SCALAR")
		self.assertEqual(fresh.get(TABLE_FIELD)[0].sales_lot, "LOOP1-TABLE")

	def test_clearing_the_table_leaves_no_orphan_rows(self):
		"""⚠ Orphans would make the lookup return a batch that no longer claims
		the number — a false positive on a historic identity."""
		doc = self._reload()
		doc.append(TABLE_FIELD, {"sales_lot": "LOOP1-ORPHAN", "year": "2019"})
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		doc = self._reload()
		doc.set(TABLE_FIELD, [])
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		self.assertEqual(len(self._reload().get(TABLE_FIELD)), 0)
		orphans = frappe.db.sql(
			f"""select name from `tab{CHILD}`
			    where parent = %s and sales_lot = 'LOOP1-ORPHAN'""",
			(self.batch,),
		)
		self.assertEqual(orphans, (), f"orphan child rows survived: {orphans}")
