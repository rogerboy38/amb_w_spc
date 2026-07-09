# W4a (Task #36) — Expiry derivation: E.D. = M.D. + Item.shelf_life_in_days.
#
# Guards: derive only when empty (or forced recompute); never overwrite an
# explicit expiry; missing M.D. or shelf_life -> EMPTY + message, never 730.
# Works for custom_batch_origin=Migrated (M.D. from production_start_date, no WO).
#
# House pattern: reuse ProjectionTestBase (flag on, borrowed WO, LIFO cleanup).
# Run: bench --site v2.sysmayal.cloud run-tests --app amb_w_spc \
#          --module amb_w_spc.tests.test_w4a_expiry

import frappe
from frappe.utils import add_days, getdate

from amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb import (
	compute_batch_expiry,
	recompute_batch_expiry,
)
from amb_w_spc.tests.test_batch_projection import (
	ProjectionTestBase, ITEM_JUICE_FAMILY, _ensure_item, YY,
)

MFD = "2025-12-12"          # M.D. — 0402252251's legacy FECHA_MFD
PILOT_ITEM = "0402"         # real dev item, shelf_life_in_days = 730
PILOT_GOLDEN = "0402252251"
PILOT_EXPIRY = "2027-12-12"  # 2025-12-12 + 730  (LEAP-NEUTRAL: days == months)
ITEM_NOSHELF = "0396"       # test item with shelf_life = 0

# Leap-crossing ground truth — signed customer COA, Barentz France, lot 0466050262:
# M.D. 2026-05-28, shelf 730d, PRINTED E.D. 2028-05-27. The window crosses
# 29-Feb-2028, so the two methods DISAGREE by one day:
#   add_days(2026-05-28, 730)  = 2028-05-27  <- correct, matches the signed COA
#   add_months(2026-05-28, 24) = 2028-05-28  <- WRONG by one day
# The printed (days-based) date is what the customer holds — days must win.
BARENTZ_MFD = "2026-05-28"
BARENTZ_EXPIRY = "2028-05-27"        # add_days(730)
BARENTZ_MONTHS_WRONG = "2028-05-28"  # add_months(24) — off by one


class W4aBase(ProjectionTestBase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if _ensure_item(ITEM_NOSHELF, shelf_life=0):
			cls._created_items.append(ITEM_NOSHELF)

	def _migrated(self, golden=PILOT_GOLDEN, item=PILOT_ITEM, mfg=MFD, expiry=None):
		fields = {
			"doctype": "Batch AMB", "custom_batch_level": "1",
			"custom_batch_origin": "Migrated", "custom_golden_number": golden,
			"item_code": item, "work_order_ref": None, "is_group": 1,
		}
		if mfg:
			fields["production_start_date"] = mfg      # legacy M.D. (no WO)
		if expiry:
			fields["expiry_date"] = expiry
		doc = frappe.get_doc(fields)
		doc.insert(ignore_permissions=True)
		return self.track(doc)


class TestExpiryComputeUnit(W4aBase):
	"""compute_batch_expiry() — field precedence + guards (no insert)."""

	def test_native_wo_start_date_computes(self):
		exp, msg = compute_batch_expiry(frappe._dict(
			wo_start_date=MFD, item_code=PILOT_ITEM))
		self.assertEqual(getdate(exp), getdate(PILOT_EXPIRY))
		self.assertIsNone(msg)

	def test_migrated_production_start_date_computes(self):
		exp, msg = compute_batch_expiry(frappe._dict(
			production_start_date=MFD, item_code=PILOT_ITEM))
		self.assertEqual(getdate(exp), getdate(PILOT_EXPIRY))

	def test_leap_crossing_uses_add_days_not_add_months(self):
		# Barentz ground truth (lot 0466050262): the ONLY case in this suite that
		# crosses 29-Feb-2028, so it distinguishes add_days(730) from
		# add_months(24). item 0402 supplies the 730d shelf.
		exp, msg = compute_batch_expiry(frappe._dict(
			production_start_date=BARENTZ_MFD, item_code=PILOT_ITEM))
		self.assertEqual(str(exp), BARENTZ_EXPIRY)            # 2028-05-27, matches signed COA
		self.assertNotEqual(str(exp), BARENTZ_MONTHS_WRONG)  # not 2028-05-28 (add_months bug)
		self.assertIsNone(msg)

	def test_no_manufacturing_date_returns_message_not_date(self):
		exp, msg = compute_batch_expiry(frappe._dict(item_code=PILOT_ITEM))
		self.assertIsNone(exp)
		self.assertIn("manufacturing date", (msg or "").lower())

	def test_no_shelf_life_leaves_empty_never_730(self):
		exp, msg = compute_batch_expiry(frappe._dict(
			production_start_date=MFD, item_code=ITEM_NOSHELF))
		self.assertIsNone(exp)                 # NOT a date, NOT +730
		self.assertIn("shelf life", (msg or "").lower())

	def test_explicit_expiry_preserved_unless_forced(self):
		human = frappe._dict(expiry_date="2030-01-01",
							 production_start_date=MFD, item_code=PILOT_ITEM)
		exp, msg = compute_batch_expiry(human, force=False)
		self.assertEqual(str(exp), "2030-01-01")      # untouched
		exp2, _m = compute_batch_expiry(human, force=True)
		self.assertEqual(getdate(exp2), getdate(PILOT_EXPIRY))  # recompute overrides


class TestExpiryIntegration(W4aBase):
	"""Full insert / recompute on the Batch AMB (Migrated, no WO)."""

	def test_migrated_0402_computes_on_insert(self):
		doc = self._migrated()
		self.assertEqual(getdate(doc.expiry_date), getdate(PILOT_EXPIRY))

	def test_leap_crossing_computes_on_insert(self):
		# Barentz 0466050262 shape (item 0402 = 730d shelf); crosses 29-Feb-2028.
		doc = self._migrated(golden="0466050262", item=PILOT_ITEM, mfg=BARENTZ_MFD)
		self.assertEqual(str(doc.expiry_date), BARENTZ_EXPIRY)  # 2028-05-27, days-based

	def test_explicit_expiry_survives_insert(self):
		doc = self._migrated(expiry="2030-06-01")
		self.assertEqual(str(doc.expiry_date), "2030-06-01")

	def test_empty_shelf_leaves_expiry_empty_on_insert(self):
		doc = self._migrated(item=ITEM_NOSHELF, golden="0396888261")
		self.assertFalse(doc.expiry_date)

	def test_recompute_forces_recomputation(self):
		# explicit expiry survives insert, then operator recompute overrides it
		doc = self._migrated(expiry="2030-06-01")
		self.assertEqual(str(doc.expiry_date), "2030-06-01")
		recompute_batch_expiry(doc.name)
		fresh = frappe.get_doc("Batch AMB", doc.name)
		self.assertEqual(getdate(fresh.expiry_date), getdate(PILOT_EXPIRY))
