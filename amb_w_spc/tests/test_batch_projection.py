# T1 unit tests — Batch AMB → native Batch projection core (Phase 1)
# Batch-projection plan 2026-07-05 §3 T1: generator (golden format, counter
# seed, collision), projection idempotency (double-fire = 1 batch), level
# guard, controller-only guard, expiry calc, backfill dry-run.
#
# House pattern (test_phase_1a_invariants.py): plain unittest, mutating
# tests clean up explicitly via tracked-doc LIFO delete in tearDown.
#
# Run: bench --site v2.sysmayal.cloud run-tests --app amb_w_spc \
#          --module amb_w_spc.tests.test_batch_projection

import unittest

import frappe
from frappe.utils import add_days, getdate

from amb_w_spc.sfc_manufacturing import batch_projection as bp
from amb_w_spc.sfc_manufacturing import golden_number as gn

# prod-shaped test codes (family 03 = aloe, high subfamilies to avoid
# clashing with real 0301-0334 subproducts; plan §3 test-data rule)
ITEM_JUICE_FAMILY = "0397"
ITEM_OUTPUT_A = "0398"
SHELF_LIFE_DAYS = 100
PLANT_NAME_JUICE = "3 (Juice)"  # production_plant_name fallback → plant 3
YY = "26"


def _ensure_item(code, shelf_life=SHELF_LIFE_DAYS):
	if frappe.db.exists("Item", code):
		return False
	# Mexico-compliance apps make these mandatory on this bench — borrow
	# valid values from any existing item rather than hardcoding SAT keys.
	sat = frappe.db.get_value(
		"Item", {"product_key": ["is", "set"], "mx_product_service_key": ["is", "set"]},
		["product_key", "mx_product_service_key"], as_dict=True) or frappe._dict()
	frappe.get_doc({
		"doctype": "Item",
		"item_code": code,
		"item_name": f"PH1 TEST FAMILY {code}",
		"item_group": "All Item Groups",
		"stock_uom": "Kg",
		"is_stock_item": 1,
		"has_batch_no": 1,
		"shelf_life_in_days": shelf_life,
		"product_key": sat.product_key,
		"mx_product_service_key": sat.mx_product_service_key,
	}).insert(ignore_permissions=True)
	return True


class ProjectionTestBase(unittest.TestCase):
	"""Flag management + tracked-doc cleanup shared by all T1 classes."""

	@classmethod
	def setUpClass(cls):
		cls._orig_flag = frappe.conf.get("batch_amb_projection_enabled")
		frappe.conf["batch_amb_projection_enabled"] = 1
		cls._created_items = []
		for code in (ITEM_JUICE_FAMILY, ITEM_OUTPUT_A):
			if _ensure_item(code):
				cls._created_items.append(code)
		# work_order_ref is a required Link — borrow a real WO. Prefer a
		# plant-neutral one so plant resolution deterministically falls
		# through to production_plant_name ("3 (Juice)" → P=3). Batch AMB's
		# on_update can db_set the WO status, so capture + restore it.
		wo_meta_fields = {f.fieldname for f in frappe.get_meta("Work Order").fields}
		plant_fields = [f for f in ("production_plant_amb", "custom_plant_code")
						if f in wo_meta_fields]
		rows = frappe.get_all("Work Order",
							  fields=["name", "status"] + plant_fields, limit=100)
		neutral = [r for r in rows if not any(r.get(f) for f in plant_fields)]
		chosen = (neutral or rows)[0]
		cls.test_wo = chosen.name
		cls._wo_original_status = chosen.status
		cls.expected_plant = "3" if neutral else None
		# item_to_manufacture has fetch_from work_order_ref.production_item
		# with fetch_if_empty=0 → always overwritten from the WO; the L1
		# golden's CCCC therefore derives from the WO's production item.
		cls.wo_production_item = frappe.db.get_value(
			"Work Order", cls.test_wo, "production_item") or ""

	@classmethod
	def tearDownClass(cls):
		for code in cls._created_items:
			frappe.delete_doc("Item", code, force=1, ignore_permissions=True,
							  ignore_missing=True)
		frappe.db.set_value("Work Order", cls.test_wo, "status",
							cls._wo_original_status, update_modified=False)
		if cls._orig_flag is None:
			frappe.conf.pop("batch_amb_projection_enabled", None)
		else:
			frappe.conf["batch_amb_projection_enabled"] = cls._orig_flag
		frappe.db.commit()

	def setUp(self):
		self.tracked = []  # (doctype, name), deleted LIFO in tearDown

	def tearDown(self):
		frappe.flags.pop(bp.CONTROLLER_FLAG, None)
		for doctype, name in reversed(self.tracked):
			# force=1 skips the link check; Batch AMB on_trash tombstones
			# its projected batches first, then we delete those directly
			frappe.delete_doc(doctype, name, force=1, ignore_permissions=True,
							  ignore_missing=True)
		frappe.db.commit()

	def track(self, doc):
		self.tracked.append((doc.doctype, doc.name))
		return doc

	def make_amb(self, level, parent=None, item=ITEM_JUICE_FAMILY, **kw):
		fields = {
			"doctype": "Batch AMB",
			"custom_batch_level": str(level),
			"item_to_manufacture": item,
			"work_order_ref": self.test_wo,
			"production_plant_name": PLANT_NAME_JUICE,
			"parent_batch_amb": parent.name if parent else None,
			"is_group": 1 if str(level) in ("1", "2") else 0,
		}
		if parent:
			# mirror add_child_batch: children inherit the parent golden
			fields["custom_golden_number"] = parent.custom_golden_number
		fields.update(kw)
		doc = frappe.get_doc(fields)
		doc.insert(ignore_permissions=True)
		self.track(doc)
		if doc.get("lote_amb_reference"):
			self.tracked.append(("Lote AMB", doc.lote_amb_reference))
		return doc

	def make_sublot_with_output(self, output_rows, item=ITEM_JUICE_FAMILY):
		"""L1 parent + L2 sub-lot carrying the given output rows."""
		l1 = self.make_amb(1, item=item)
		l2 = self.make_amb(2, parent=l1, item=item)
		for row in output_rows:
			l2.append("output_products", row)
		l2.save(ignore_permissions=True)
		for batch_name in frappe.get_all(
			"Batch", filters={"custom_batch_amb": l2.name}, pluck="name"
		):
			self.tracked.append(("Batch", batch_name))
		return l1, l2

	def controller_batch(self, **kw):
		batch = frappe.new_doc("Batch")
		batch.update(kw)
		batch.flags[bp.CONTROLLER_FLAG] = True
		batch.insert(ignore_permissions=True)
		return self.track(batch)


class TestGoldenGenerator(ProjectionTestBase):
	"""1.3 — D1a generator: format, counter seed, collision advance."""

	def test_golden_format_and_decomposition(self):
		l1 = self.make_amb(1)
		golden = l1.custom_golden_number
		self.assertRegex(golden, r"^\d{10}$")
		self.assertEqual(golden[0:4], self.wo_production_item[:4].zfill(4))  # CCCC
		self.assertEqual(golden[7:9], YY)                    # YY
		if self.expected_plant:                              # P = Juice
			self.assertEqual(golden[9], self.expected_plant)
		else:
			self.assertIn(golden[9], "12345")
		self.assertEqual(l1.custom_product_family, golden[0:2])
		self.assertEqual(l1.custom_subfamily, golden[2:4])
		self.assertEqual(l1.custom_consecutive, golden[4:7])

	def test_counter_seeds_from_all_registers(self):
		"""FFF = historical max across Item / Batch / Batch AMB + 1."""
		self.controller_batch(batch_id=f"{ITEM_OUTPUT_A}900{YY}2",
							  item=ITEM_OUTPUT_A)
		self.assertEqual(gn.next_consecutive(ITEM_OUTPUT_A, YY), 901)
		golden = gn.generate_golden_number(ITEM_OUTPUT_A, "2", YY)
		self.assertEqual(golden, f"{ITEM_OUTPUT_A}901{YY}2")

	def test_generator_is_stable_on_resave(self):
		"""Counter-based FFF must never renumber an existing golden."""
		l1 = self.make_amb(1)
		golden = l1.custom_golden_number
		l1.save(ignore_permissions=True)
		l1.save(ignore_permissions=True)
		self.assertEqual(l1.custom_golden_number, golden)

	def test_collision_advances_candidate(self):
		"""If the seeded candidate is taken, the generator skips past it."""
		self.controller_batch(batch_id=f"{ITEM_OUTPUT_A}001{YY}1",
							  item=ITEM_OUTPUT_A)
		orig = gn._max_fff
		gn._max_fff = lambda cccc, yy: 0  # force candidate 001 → collides
		try:
			golden = gn.generate_golden_number(ITEM_OUTPUT_A, "1", YY)
		finally:
			gn._max_fff = orig
		self.assertEqual(golden, f"{ITEM_OUTPUT_A}002{YY}1")

	def test_sublot_batch_ids_reserve_the_golden(self):
		self.controller_batch(batch_id=f"{ITEM_OUTPUT_A}555{YY}3-1",
							  item=ITEM_OUTPUT_A)
		self.assertTrue(gn.has_collision(f"{ITEM_OUTPUT_A}555{YY}3"))


class TestProjection(ProjectionTestBase):
	"""1.2 — projection: creation, batch_id resolution, expiry, idempotency,
	level guard."""

	def test_projects_output_row_with_golden_batch_id(self):
		output_golden = f"{ITEM_OUTPUT_A}777{YY}3"
		l1, l2 = self.make_sublot_with_output([{
			"item_code": ITEM_OUTPUT_A,
			"quantity_kg": 120,
			"output_golden_number": output_golden,
		}])
		row = l2.output_products[0]
		self.assertTrue(row.batch_no)
		batch = frappe.get_doc("Batch", row.batch_no)
		self.assertEqual(batch.batch_id, output_golden)
		self.assertEqual(batch.item, ITEM_OUTPUT_A)
		self.assertEqual(batch.custom_batch_amb, l2.name)
		self.assertEqual(batch.custom_batch_output_row, row.name)
		# expiry = mfg + family shelf life (mfg = WO start, else creation)
		expected_mfg = getdate(l2.wo_start_date or l2.creation)
		self.assertEqual(getdate(batch.manufacturing_date), expected_mfg)
		self.assertEqual(getdate(batch.expiry_date),
						 getdate(add_days(expected_mfg, SHELF_LIFE_DAYS)))
		# summary counter maintained on the controller (1.1)
		self.assertEqual(frappe.db.get_value("Batch AMB", l2.name, "erpnext_batches"), 1)

	def test_single_output_falls_back_to_golden_dash_n(self):
		l1, l2 = self.make_sublot_with_output([{
			"item_code": ITEM_OUTPUT_A,
			"quantity_kg": 80,
		}])
		row = l2.output_products[0]
		self.assertTrue(row.batch_no)
		self.assertEqual(
			frappe.db.get_value("Batch", row.batch_no, "batch_id"),
			f"{l2.custom_golden_number}-1",
		)

	def test_multi_output_without_goldens_is_skipped_not_invented(self):
		l1, l2 = self.make_sublot_with_output([
			{"item_code": ITEM_OUTPUT_A, "quantity_kg": 10},
			{"item_code": ITEM_JUICE_FAMILY, "quantity_kg": 20},
		])
		self.assertEqual(
			frappe.db.count("Batch", {"custom_batch_amb": l2.name}), 0)

	def test_double_fire_is_idempotent(self):
		l1, l2 = self.make_sublot_with_output([{
			"item_code": ITEM_OUTPUT_A,
			"quantity_kg": 50,
			"output_golden_number": f"{ITEM_OUTPUT_A}778{YY}3",
		}])
		first = frappe.get_all("Batch", filters={"custom_batch_amb": l2.name}, pluck="name")
		l2.save(ignore_permissions=True)   # second fire
		l2.save(ignore_permissions=True)   # third fire
		after = frappe.get_all("Batch", filters={"custom_batch_amb": l2.name}, pluck="name")
		self.assertEqual(sorted(first), sorted(after))
		self.assertEqual(len(after), 1)

	def test_level_guard_only_sublots_emit(self):
		l1 = self.make_amb(1)
		l1.append("output_products", {
			"item_code": ITEM_OUTPUT_A,
			"quantity_kg": 30,
			"output_golden_number": f"{ITEM_OUTPUT_A}779{YY}3",
		})
		l1.save(ignore_permissions=True)
		self.assertEqual(frappe.db.count("Batch", {"custom_batch_amb": l1.name}), 0)

	def test_rejected_rows_do_not_project(self):
		l1, l2 = self.make_sublot_with_output([{
			"item_code": ITEM_OUTPUT_A,
			"quantity_kg": 40,
			"quality_status": "Rejected",
			"output_golden_number": f"{ITEM_OUTPUT_A}780{YY}3",
		}])
		self.assertEqual(frappe.db.count("Batch", {"custom_batch_amb": l2.name}), 0)

	def test_projection_inert_when_flag_off(self):
		frappe.conf["batch_amb_projection_enabled"] = 0
		try:
			l1, l2 = self.make_sublot_with_output([{
				"item_code": ITEM_OUTPUT_A,
				"quantity_kg": 60,
				"output_golden_number": f"{ITEM_OUTPUT_A}781{YY}3",
			}])
			self.assertEqual(frappe.db.count("Batch", {"custom_batch_amb": l2.name}), 0)
		finally:
			frappe.conf["batch_amb_projection_enabled"] = 1


class TestControllerGuard(ProjectionTestBase):
	"""1.4 — controller-only guard on native Batch."""

	def test_manual_create_rejected(self):
		batch = frappe.new_doc("Batch")
		batch.update({"batch_id": f"{ITEM_OUTPUT_A}888{YY}1", "item": ITEM_OUTPUT_A})
		with self.assertRaises(bp.BatchControllerGuardError):
			batch.insert(ignore_permissions=True)

	def test_manual_edit_rejected(self):
		batch = self.controller_batch(batch_id=f"{ITEM_OUTPUT_A}889{YY}1",
									  item=ITEM_OUTPUT_A)
		victim = frappe.get_doc("Batch", batch.name)
		victim.description = "tampered"
		with self.assertRaises(bp.BatchControllerGuardError):
			victim.save(ignore_permissions=True)

	def test_controller_flag_allows_write(self):
		batch = self.controller_batch(batch_id=f"{ITEM_OUTPUT_A}890{YY}1",
									  item=ITEM_OUTPUT_A)
		self.assertTrue(frappe.db.exists("Batch", batch.name))

	def test_guard_inert_when_flag_off(self):
		frappe.conf["batch_amb_projection_enabled"] = 0
		try:
			batch = frappe.new_doc("Batch")
			batch.update({"batch_id": f"{ITEM_OUTPUT_A}891{YY}1", "item": ITEM_OUTPUT_A})
			batch.insert(ignore_permissions=True)  # legacy behavior preserved
			self.track(batch)
		finally:
			frappe.conf["batch_amb_projection_enabled"] = 1

	def test_trash_tombstones_projected_batches(self):
		l1, l2 = self.make_sublot_with_output([{
			"item_code": ITEM_OUTPUT_A,
			"quantity_kg": 25,
			"output_golden_number": f"{ITEM_OUTPUT_A}892{YY}3",
		}])
		batch_name = l2.output_products[0].batch_no
		frappe.delete_doc("Batch AMB", l2.name, force=1, ignore_permissions=True)
		self.tracked = [t for t in self.tracked if t != ("Batch AMB", l2.name)]
		state = frappe.db.get_value(
			"Batch", batch_name,
			["disabled", "custom_batch_amb", "description"], as_dict=True)
		self.assertEqual(state.disabled, 1)
		self.assertFalse(state.custom_batch_amb)
		self.assertIn("projection tombstone", state.description or "")


class TestBackfillAndReconcile(ProjectionTestBase):
	"""1.5 backfill dry-run + 1.6 reconcile healthcheck."""

	def test_backfill_dry_run_writes_nothing(self):
		before = frappe.db.count("Batch")
		report = bp.backfill_projection(dry_run=1)
		self.assertTrue(report["dry_run"])
		self.assertEqual(frappe.db.count("Batch"), before)

	def test_reconcile_detects_drift_and_orphans(self):
		l1, l2 = self.make_sublot_with_output([{
			"item_code": ITEM_OUTPUT_A,
			"quantity_kg": 15,
			"output_golden_number": f"{ITEM_OUTPUT_A}893{YY}3",
		}])
		batch_name = l2.output_products[0].batch_no
		report = bp.reconcile()
		self.assertNotIn(
			batch_name,
			[d["batch"] for d in report["drift"]],
			"freshly projected batch must not drift",
		)
		# introduce drift out-of-band (db_set skips the guard by design)
		frappe.db.set_value("Batch", batch_name, "expiry_date", "2030-01-01",
							update_modified=False)
		report = bp.reconcile()
		self.assertIn(batch_name, [d["batch"] for d in report["drift"]])
		self.assertFalse(report["clean"])
