# G1 (TASKS-266) — DB-free: the once-minted title guard in Batch AMB.auto_set_title.
# Drives the method on a bare controller object with frappe.get_doc / frappe.db.count stubbed.
import unittest
from unittest import mock

import frappe

from amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb import BatchAMB


def bare(**fields):
	doc = BatchAMB.__new__(BatchAMB)
	doc.__dict__.update({"title": None, "custom_batch_level": "2", "parent_batch_amb": "L1", "name": "L2-X",
	                     "custom_golden_number": None, "_doc_before_save": None, "_new": False})
	doc.__dict__.update(fields)
	return doc


class TestTitleGuard(unittest.TestCase):
	def run_title(self, doc, siblings):
		parent = frappe._dict(custom_golden_number="0397000126", title="0397000126", name="L1")
		# frappe.db is a site-bound local proxy; outside a site it is replaced wholesale
		with mock.patch.object(frappe, "get_doc", return_value=parent), \
		     mock.patch.object(frappe, "db", mock.Mock(count=mock.Mock(return_value=siblings))), \
		     mock.patch.object(BatchAMB, "is_new", lambda self: self._new), \
		     mock.patch.object(BatchAMB, "get_doc_before_save", lambda self: self._doc_before_save):
			doc.auto_set_title()
		return doc.title

	def test_new_sublot_is_numbered_from_the_sibling_count(self):
		self.assertEqual(self.run_title(bare(_new=True), siblings=0), "0397000126-1")
		self.assertEqual(self.run_title(bare(_new=True), siblings=1), "0397000126-2")

	def test_plain_save_keeps_the_title_even_when_siblings_grew(self):
		before = frappe._dict(parent_batch_amb="L1", custom_batch_level="2")
		doc = bare(title="0397000126-1", _doc_before_save=before)
		self.assertEqual(self.run_title(doc, siblings=1), "0397000126-1")   # used to become "-2"

	def test_legacy_title_is_kept_on_save(self):
		before = frappe._dict(parent_batch_amb="L1", custom_batch_level="2")
		self.assertEqual(self.run_title(bare(title="LEGACY-7", _doc_before_save=before), siblings=5), "LEGACY-7")

	def test_missing_title_is_minted_on_save(self):
		before = frappe._dict(parent_batch_amb="L1", custom_batch_level="2")
		self.assertEqual(self.run_title(bare(title="", _doc_before_save=before), siblings=0), "0397000126-1")

	def test_parent_change_re_mints(self):
		before = frappe._dict(parent_batch_amb="OTHER-L1", custom_batch_level="2")
		self.assertEqual(self.run_title(bare(title="OLD-1", _doc_before_save=before), siblings=2), "0397000126-3")

	def test_level_change_re_mints(self):
		before = frappe._dict(parent_batch_amb="L1", custom_batch_level="3")
		self.assertEqual(self.run_title(bare(title="OLD-C001", _doc_before_save=before), siblings=0), "0397000126-1")

	def test_level_3_container_index_is_kept_on_save(self):
		before = frappe._dict(parent_batch_amb="L2-A", custom_batch_level="3")
		doc = bare(custom_batch_level="3", parent_batch_amb="L2-A", title="0397000126-1-C001", _doc_before_save=before)
		self.assertEqual(self.run_title(doc, siblings=1), "0397000126-1-C001")

	def test_level_1_unchanged(self):
		doc = bare(custom_batch_level="1", custom_golden_number="0397000126", title="whatever", _doc_before_save=frappe._dict())
		self.assertEqual(self.run_title(doc, siblings=9), "0397000126")


if __name__ == "__main__":
	unittest.main()
