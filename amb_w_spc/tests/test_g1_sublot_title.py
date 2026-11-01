# G1 (TASKS-266, 2026-11-01) — a sub-lot's title is minted once and survives plain saves.
#
# Before: Batch AMB.auto_set_title recounted the parent's other children on EVERY save, so
# re-saving sub-lot "-1" after "-2" existed renumbered it to "-2" (two siblings, one title).
# House pattern: ProjectionTestBase (tracked-doc LIFO cleanup, borrowed WO, test items 0397/0398).
#
# Run: bench --site <site> run-tests --app amb_w_spc --module amb_w_spc.tests.test_g1_sublot_title
import frappe

from amb_w_spc.tests.test_batch_projection import ProjectionTestBase


class TestSublotTitleIsStable(ProjectionTestBase):
	def _reload_and_save(self, doc):
		doc = frappe.get_doc("Batch AMB", doc.name)
		doc.save(ignore_permissions=True)
		return frappe.db.get_value("Batch AMB", doc.name, "title")

	def test_two_sublots_keep_minus_1_and_minus_2_across_saves(self):
		l1 = self.make_amb(1)
		g = l1.custom_golden_number
		a = self.make_amb(2, parent=l1)
		b = self.make_amb(2, parent=l1)
		self.assertEqual((a.title, b.title), (f"{g}-1", f"{g}-2"))

		# the defect: a plain save of "-1" used to recount the siblings and become "-2"
		self.assertEqual(self._reload_and_save(a), f"{g}-1")
		self.assertEqual(self._reload_and_save(b), f"{g}-2")
		self.assertEqual(self._reload_and_save(a), f"{g}-1")
		titles = frappe.get_all("Batch AMB", filters={"parent_batch_amb": l1.name, "custom_batch_level": "2"}, pluck="title")
		self.assertEqual(sorted(titles), [f"{g}-1", f"{g}-2"])

	def test_level_3_under_minus_1_gets_its_container_index_and_keeps_it(self):
		l1 = self.make_amb(1)
		g = l1.custom_golden_number
		a = self.make_amb(2, parent=l1)
		self.make_amb(2, parent=l1)
		c = self.make_amb(3, parent=a)
		# the live format on the sandbox/prod for level 3 is <level-2 title>-C<index, 3 digits>
		self.assertEqual(c.title, f"{g}-1-C001")
		self.assertEqual(self._reload_and_save(a), f"{g}-1")      # the parent is still "-1"
		self.assertEqual(self._reload_and_save(c), f"{g}-1-C001")  # and the container keeps its index

	def test_an_existing_record_keeps_whatever_title_it_has(self):
		l1 = self.make_amb(1)
		a = self.make_amb(2, parent=l1)
		self.make_amb(2, parent=l1)
		# emulate an older record carrying a title the current rule would not produce
		frappe.db.set_value("Batch AMB", a.name, "title", "LEGACY-TITLE-7", update_modified=False)
		self.assertEqual(self._reload_and_save(a), "LEGACY-TITLE-7")

	def test_a_sublot_without_a_title_is_still_titled_on_save(self):
		l1 = self.make_amb(1)
		g = l1.custom_golden_number
		a = self.make_amb(2, parent=l1)
		frappe.db.set_value("Batch AMB", a.name, "title", "", update_modified=False)
		self.assertEqual(self._reload_and_save(a), f"{g}-1")

	def test_moving_a_sublot_to_another_parent_re_mints_the_title(self):
		l1 = self.make_amb(1)
		l1b = self.make_amb(1)
		a = self.make_amb(2, parent=l1)
		a = frappe.get_doc("Batch AMB", a.name)
		a.parent_batch_amb = l1b.name
		a.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Batch AMB", a.name, "title"), f"{l1b.custom_golden_number}-1")
