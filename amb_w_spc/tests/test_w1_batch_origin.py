# W1 (Task #36, ruling R-ID-1) — Batch AMB origin regime + legacy-golden mechanics.
#
# Migrated lots keep their legacy FoxPro golden VERBATIM (validated, never
# WO-derived); Native lots mint from the WO as before. Also proves F-B: the
# batch_amb_validate doc_events hook no longer clobbers an already-valid golden
# by re-deriving from the Work Order.
#
# House pattern: reuse ProjectionTestBase (projection flag on, borrowed WO,
# tracked-doc LIFO cleanup).
#
# Run: bench --site v2.sysmayal.cloud run-tests --app amb_w_spc \
#          --module amb_w_spc.tests.test_w1_batch_origin

import frappe

from amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb import (
	MIGRATION_PROVENANCE_ACTION,
	_validate_migrated_golden,
)
from amb_w_spc.tests.test_batch_projection import ProjectionTestBase

# synthetic migrated golden — family 03, high subfamily/consecutive to avoid
# colliding with real 03xx data; shape CCCC FFF YY P = 0397 888 26 1
MIGRATED_GOLDEN = "0397888261"


class TestBatchOriginUnit(ProjectionTestBase):
	"""Pure validation-helper behaviour (no insert)."""

	def test_valid_10_digit_golden_passes(self):
		# does not raise
		_validate_migrated_golden("0402252251", "TEST")

	def test_empty_migrated_golden_throws(self):
		with self.assertRaises(frappe.ValidationError):
			_validate_migrated_golden("", "TEST")

	def test_malformed_migrated_golden_throws(self):
		for bad in ("12345", "0402-25", "04022522510", "abcd252251"):
			with self.assertRaises(frappe.ValidationError):
				_validate_migrated_golden(bad, "TEST")


class TestBatchOriginMigrated(ProjectionTestBase):
	"""Migrated regime: legacy golden preserved verbatim, no WO required."""

	def _make_migrated(self, golden=MIGRATED_GOLDEN, **kw):
		fields = {
			"doctype": "Batch AMB",
			"custom_batch_level": "1",
			"custom_batch_origin": "Migrated",
			"custom_golden_number": golden,
			"work_order_ref": None,      # O-1: migrated lots may have no WO
			"item_to_manufacture": None,
			"is_group": 1,
		}
		fields.update(kw)
		doc = frappe.get_doc(fields)
		doc.insert(ignore_permissions=True)
		self.track(doc)
		return doc

	def test_migrated_golden_survives_insert_and_resave(self):
		doc = self._make_migrated()
		self.assertEqual(doc.custom_golden_number, MIGRATED_GOLDEN)
		# re-derivation must never touch it (both layers, twice)
		doc.save(ignore_permissions=True)
		doc.save(ignore_permissions=True)
		fresh = frappe.get_doc("Batch AMB", doc.name)
		self.assertEqual(fresh.custom_golden_number, MIGRATED_GOLDEN)
		# decomposition follows golden_number.py slicing (O-3)
		self.assertEqual(fresh.custom_product_family, MIGRATED_GOLDEN[0:2])
		self.assertEqual(fresh.custom_subfamily, MIGRATED_GOLDEN[2:4])
		self.assertEqual(fresh.custom_consecutive, MIGRATED_GOLDEN[4:7])

	def test_migrated_batch_inserts_without_work_order(self):
		doc = self._make_migrated()
		self.assertFalse(doc.get("work_order_ref"))

	def test_provenance_helper_records_folios_and_is_idempotent(self):
		# usage path: the migration-fixer (PR-2) / pilot records provenance
		# explicitly after creating the batch — the FoxPro folios live in the
		# migration context, not the controller.
		from amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb import (
			add_migration_provenance_row,
		)
		doc = self._make_migrated()
		add_migration_provenance_row(
			doc, folios=["F-2835-25", "F-2836-25"], coa_folio="6048")
		doc.save(ignore_permissions=True)
		fresh = frappe.get_doc("Batch AMB", doc.name)
		markers = [r for r in (fresh.get("processing_history") or [])
				   if (r.processing_action or "") == MIGRATION_PROVENANCE_ACTION]
		self.assertEqual(len(markers), 1)
		self.assertIn(MIGRATED_GOLDEN, markers[0].comments or "")
		self.assertIn("6048", markers[0].comments or "")
		# idempotent: a second record adds no duplicate marker
		add_migration_provenance_row(fresh)
		fresh.save(ignore_permissions=True)
		again = frappe.get_doc("Batch AMB", doc.name)
		markers = [r for r in (again.get("processing_history") or [])
				   if (r.processing_action or "") == MIGRATION_PROVENANCE_ACTION]
		self.assertEqual(len(markers), 1)

	def test_migrated_empty_golden_refused_on_insert(self):
		with self.assertRaises(frappe.ValidationError):
			self._make_migrated(golden=None)

	def test_migrated_malformed_golden_refused_on_insert(self):
		with self.assertRaises(frappe.ValidationError):
			self._make_migrated(golden="12345")


class TestNativeGoldenNotClobbered(ProjectionTestBase):
	"""F-B: an already-valid native golden is immutable across re-saves — the
	doc_events hook no longer re-derives it from the Work Order."""

	def test_native_golden_stable_and_valid(self):
		# make_amb builds a Native L1 (default origin) with the borrowed WO
		l1 = self.make_amb(1)
		golden = l1.custom_golden_number
		self.assertRegex(golden, r"^\d{10}$")
		l1.save(ignore_permissions=True)
		l1.save(ignore_permissions=True)
		fresh = frappe.get_doc("Batch AMB", l1.name)
		self.assertEqual(fresh.custom_golden_number, golden)


class TestPreW1RowBackfill(ProjectionTestBase):
	"""REV-W1-3: custom_batch_origin is reqd:1 but field defaults apply to NEW
	docs only — every pre-W1 row has NULL origin and would throw 'mandatory' on
	its next resave. The patch backfills them to Native (true by definition)."""

	def test_null_origin_throws_then_backfill_fixes_resave(self):
		l1 = self.make_amb(1)  # native; origin defaults to Native on create
		# simulate a pre-W1 row: NULL origin in the DB
		frappe.db.set_value("Batch AMB", l1.name, "custom_batch_origin", None,
							update_modified=False)
		stale = frappe.get_doc("Batch AMB", l1.name)
		with self.assertRaises(frappe.ValidationError):
			stale.save(ignore_permissions=True)   # "Batch Origin is mandatory"
		# the patch's idempotent backfill predicate, scoped to this row
		frappe.db.sql(
			"UPDATE `tabBatch AMB` SET custom_batch_origin='Native' "
			"WHERE (custom_batch_origin IS NULL OR custom_batch_origin='') "
			"AND name=%s", l1.name)
		fixed = frappe.get_doc("Batch AMB", l1.name)
		self.assertEqual(fixed.custom_batch_origin, "Native")
		fixed.save(ignore_permissions=True)        # must NOT throw
