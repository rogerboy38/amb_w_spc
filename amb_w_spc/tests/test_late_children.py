# TASKS-391 and TASKS-392, DB-free: what a new child of a released record is born with, and what a copy carries.
#
#   * decision 344 (TASKS-392, amends 342): the same as below for a container created directly under a LOT
#   * decision 345 (TASKS-392): a copy of a lot record carries no certificate link
#   * decision 346 (TASKS-397): a duplicate of a lot record copies none of the source's history rows and gets ONE
#     row "copied from <source>" through the module's own insert; it keeps its parent pointer, no certificate link
#     and Pending; a duplicated container under a certified lot or sub-lot inherits as in 344, else Pending (336);
#     the form's own Duplicate copies no history row ("no copy" on `processing_history`)
#
#   * decision 342 (amends 336): a CONTAINER (level 3) created under a SUB-LOT (level 2) whose status comes from a
#     certificate takes that sub-lot's certificate verdict as "Inherited" from the same certificate, with ONE
#     history row "created after approval of <certificate>: inherits from <sub-lot>"; a sub-lot on a hand hold:
#     the container takes what the sub-lot's certificate says (`certificate_status`), not Hold, as the
#     write-down of an approval does (reading 1)
#   * a SUB-LOT (level 2) created after an approval is still born Pending (336), and so is every other child
#     (a container under a container; a parent whose certificate says no status)
#   * decision 343: `create_child_batch` gives a new child no certificate link (`coa_reference`, `coa_amb`,
#     `coa_amb2` empty), whatever the parent carries
#
# `create_child_batch` runs for real with a parent and a child that behave like documents; the child's insert
# runs the REAL guard (test_lot_quality_hierarchy.Child).
#
# Run: python -m unittest amb_w_spc.tests.test_late_children   (no site needed)

import unittest
from unittest import mock

from amb_w_spc.sfc_manufacturing import lot_quality as lq
from amb_w_spc.sfc_manufacturing.doctype.batch_amb import batch_amb as bam
from amb_w_spc.tests.test_lot_quality import INTERNAL, USER, Table, fake_frappe, rec, site
from amb_w_spc.tests.test_lot_quality_hierarchy import PENDING_NO_CERTIFICATE, Child, Fields

LINKS = ("coa_reference", "coa_amb", "coa_amb2")


def create(child_level, **parent_fields):
	"""-> (result, child, frappe) of `create_child_batch("SUB-1", child_level)` under a parent with these fields."""
	fields = {
		"name": "SUB-1",
		"is_group": 1,
		"custom_batch_level": "2",
		"current_plant2": "1 (Mix)",
		"current_item_code": "0227",
		"item_to_manufacture": "0227",
	}
	parent = Fields(**dict(fields, **parent_fields))
	parent.db_set = mock.Mock()
	child = Child()
	f = fake_frappe()
	f.get_doc.return_value = parent
	f.new_doc.return_value = child
	with mock.patch.object(bam, "frappe", f), site(frappe=f):
		out = bam.create_child_batch("SUB-1", child_level)
	return out, child, f


def released(status="Passed", source="Inherited", cert="CERT-L", says=None, **kw):
	"""A parent whose status comes from a certificate; `says` = what that certificate says (default: status)."""
	return dict(
		{
			"quality_status": status,
			"status_source": source,
			"released_by_doctype": INTERNAL,
			"released_by": cert,
			"certificate_status": says or status,
		},
		**kw,
	)


def inherited(cert, status):
	return {
		"quality_status": status,
		"status_source": "Inherited",
		"released_by_doctype": INTERNAL,
		"released_by": cert,
		"certificate_status": status,
	}


class TestAContainerUnderACertifiedSubLotInherits(unittest.TestCase):
	def test_it_takes_the_sub_lots_verdict_from_the_same_certificate(self):
		for status in ("Passed", "Failed", "Hold"):
			for source in ("Own certificate", "Inherited"):
				with self.subTest(status=status, source=source):
					out, child, _f = create("3", **released(status, source, cert="CERT-S"))
					self.assertTrue(out["success"], out)
					self.assertEqual(child.inserted, inherited("CERT-S", status))
					self.assertIs(child.flag_at_insert, lq._WRITER)  # the module's own insert
					self.assertEqual(child.flags, {})  # ... and the flag is down after it

	def test_its_birth_leaves_one_history_row_saying_it_inherits(self):
		_out, child, _f = create("3", **released("Failed", "Own certificate", cert="CERT-S"))
		(row,) = child.rows
		self.assertEqual(
			(row["processing_action"], row["quality_status"], row["changed_by"], row["batch_reference"]),
			("Quality Status Changed", "Failed", USER, "LOTE-NEW"),
		)
		for needle in (
			"created after approval of COA AMB2 CERT-S: inherits from SUB-1",
			"from Pending to Failed",
			"source: from none to Inherited",
			"certificate: from none to COA AMB2 CERT-S (says Failed)",
		):
			self.assertIn(needle, row["comments"])
		self.assertNotIn("Pending until certified", row["comments"])
		self.assertNotIn("hand hold", row["comments"])

	def test_under_a_sub_lot_on_a_hand_hold_it_takes_what_the_certificate_says_not_the_hold(self):
		for says in ("Passed", "Failed"):
			with self.subTest(says=says):
				_out, child, _f = create("3", **released("Hold", "Hold action", cert="CERT-S", says=says))
				self.assertEqual(child.inserted, inherited("CERT-S", says))
				(row,) = child.rows
				self.assertIn(
					"created after approval of COA AMB2 CERT-S: inherits from SUB-1", row["comments"]
				)
				self.assertIn(
					f"SUB-1 is on a hand hold: the container takes what COA AMB2 CERT-S says ({says}), not the hold",
					row["comments"],
				)
		# a hold with no certificate behind it: no certificate was approved, Pending with no row (as in 336)
		_out, child, _f = create("3", quality_status="Hold", status_source="Hold action")
		self.assertEqual(child.inserted, PENDING_NO_CERTIFICATE)
		self.assertEqual(child.rows, [])

	def test_its_birth_is_what_the_write_down_of_the_same_approval_gives_a_container(self):
		# the same tree approved with the container already there: the container born later ends the same
		for result in ("Pass", "Fail", "Partial"):
			for held in (False, True):
				with self.subTest(result=result, held=held):
					t = Table(rec("L"), rec("S", "2", "L"), rec("C-OLD", "3", "S"))
					with site(t):
						lq.certificate_approved(INTERNAL, "CERT-L", "L", result)
						if held:
							lq.set_lot_quality_status(
								"S", "Hold", reason="looked wrong", source="Hold action"
							)
							lq.certificate_approved(INTERNAL, "CERT-S", "S", result)
					sub_lot = dict(t.rows["S"], name="SUB-1")
					sub_lot.pop("custom_batch_level")
					_out, child, _f = create("3", **sub_lot)
					old = {f: t.rows["C-OLD"][f] or None for f in lq.GUARDED_FIELDS}
					self.assertEqual(child.inserted, old)

	def test_no_certificate_link_is_written_on_it(self):
		_out, child, _f = create("3", **released(cert="CERT-S", coa_amb2="CERT-S"))
		for fieldname in LINKS:
			self.assertIsNone(child.get(fieldname), fieldname)


class TestEveryOtherChildIsStillBornPending(unittest.TestCase):
	def test_a_sub_lot_created_after_an_approval_is_born_pending(self):
		# under a lot (level 1) and under a sub-lot (create_child_batch does not check the parent's level)
		for parent_level in ("1", "2"):
			for source in ("Own certificate", "Inherited"):
				with self.subTest(parent_level=parent_level, source=source):
					out, child, _f = create(
						"2", custom_batch_level=parent_level, **released("Passed", source)
					)
					self.assertTrue(out["success"], out)
					self.assertEqual(child.inserted, PENDING_NO_CERTIFICATE)
					(row,) = child.rows
					self.assertIn(
						"created after approval of COA AMB2 CERT-L: Pending until certified", row["comments"]
					)

	def test_a_container_under_another_container_is_born_pending(self):
		_out, child, _f = create("3", custom_batch_level="3", **released())
		self.assertEqual(child.inserted, PENDING_NO_CERTIFICATE)
		(row,) = child.rows
		self.assertIn("Pending until certified", row["comments"])

	def test_a_container_under_a_sub_lot_whose_certificate_says_no_status_is_born_pending(self):
		for parent in (
			dict(released(), certificate_status=None),
			dict(released(), certificate_status="Pending"),
			dict(released(), released_by_doctype=None),
		):
			with self.subTest(parent=parent):
				_out, child, _f = create("3", **parent)
				self.assertEqual(child.inserted, PENDING_NO_CERTIFICATE)
				self.assertIn("Pending until certified", child.rows[0]["comments"])

	def test_a_level_4_child_is_not_created(self):
		out, child, _f = create("4", **released())
		self.assertFalse(out["success"])
		self.assertIsNone(child.inserted)


class TestAContainerUnderACertifiedLotInherits(unittest.TestCase):
	"""Decision 344 (TASKS-392, amends 342): the record directly above, lot or sub-lot."""

	def test_under_an_approved_lot_it_inherits_and_under_an_approved_sub_lot_too(self):
		for parent_level in ("1", None, "2"):
			for source in ("Own certificate", "Inherited"):
				with self.subTest(parent_level=parent_level, source=source):
					out, child, _f = create(
						"3", custom_batch_level=parent_level, **released("Passed", source)
					)
					self.assertTrue(out["success"], out)
					self.assertEqual(child.inserted, inherited("CERT-L", "Passed"))
					(row,) = child.rows
					self.assertIn("created after approval of COA AMB2 CERT-L: inherits from", row["comments"])

	def test_a_sub_lot_under_an_approved_lot_is_still_born_pending(self):
		_out, child, _f = create("2", custom_batch_level="1", **released("Passed", "Own certificate"))
		self.assertEqual(child.inserted, PENDING_NO_CERTIFICATE)


class TestADuplicateCarriesNoCertificateLink(unittest.TestCase):
	"""Decision 345 (TASKS-392, extends 343)."""

	def test_a_duplicate_of_a_certified_lot_carries_no_link_and_starts_pending(self):
		copy = Fields(
			quality_status="Passed",
			status_source="Own certificate",
			released_by_doctype=INTERNAL,
			released_by="CERT-L",
			certificate_status="Passed",
			coa_reference="COA-CUST-1",
			coa_amb="COA-CUST-1",
			coa_amb2="CERT-L",
		)
		lq.reset_for_copy(copy)
		for fieldname in LINKS:
			self.assertIsNone(copy.get(fieldname), fieldname)
		self.assertEqual(copy.get("quality_status"), lq.PENDING)
		for fieldname in lq.GUARDED_FIELDS[1:]:
			self.assertIsNone(copy.get(fieldname), fieldname)

	def test_the_forms_own_duplicate_does_not_copy_the_three_links(self):
		"""The form's Duplicate menu item copies every field not marked "no copy" (Frappe's client copy_doc); the
		three certificate links are marked, as are the quality fields."""
		import json
		import pathlib

		meta = json.loads((pathlib.Path(bam.__file__).parent / "batch_amb.json").read_text(encoding="utf-8"))
		no_copy = {f["fieldname"]: f.get("no_copy") for f in meta["fields"]}
		for fieldname in (*LINKS, *lq.GUARDED_FIELDS):
			self.assertEqual(no_copy.get(fieldname), 1, fieldname)


class TestANewChildCarriesNoCertificateLink(unittest.TestCase):
	def test_a_child_under_a_certified_parent_has_none_of_the_three_links(self):
		parent = released(
			"Passed", "Own certificate", coa_reference="COA-CUST-1", coa_amb="COA-CUST-1", coa_amb2="CERT-L"
		)
		for level in ("2", "3"):
			for parent_level in ("1", "2"):
				with self.subTest(level=level, parent_level=parent_level):
					out, child, _f = create(level, custom_batch_level=parent_level, **parent)
					self.assertTrue(out["success"], out)
					for fieldname in LINKS:
						self.assertIsNone(child.get(fieldname), fieldname)

	def test_a_link_already_on_the_new_document_does_not_survive(self):
		# a default or a hook could fill a field of a new document; create_child_batch empties all three
		parent = Fields(
			name="SUB-1", is_group=1, current_plant2="1", current_item_code="0227", coa_reference="COA-CUST-1"
		)
		parent.db_set = mock.Mock()
		child = Child()
		child.coa_reference, child.coa_amb, child.coa_amb2 = "COA-X", "COA-X", "CERT-X"
		f = fake_frappe()
		f.get_doc.return_value = parent
		f.new_doc.return_value = child
		with mock.patch.object(bam, "frappe", f), site(frappe=f):
			out = bam.create_child_batch("SUB-1", "2")
		self.assertTrue(out["success"], out)
		for fieldname in LINKS:
			self.assertIsNone(child.get(fieldname), fieldname)


SOURCE_ROWS = (
	{
		"processing_action": "Quality Status Changed",
		"comments": "source row: approved",
		"batch_reference": "SRC",
	},
	{"processing_action": "Notifications Sent", "comments": "source row: mailed", "batch_reference": "SRC"},
)


def duplicate(*stored, **copy_fields):
	"""-> (result, copy) of `duplicate_batch("SRC")`: `frappe.copy_doc` gives a copy with these fields, the source's
	certificate fields and links, and the source's history rows (it copies child tables whatever "no copy" says);
	the lot table holds the `stored` records the copy's parent pointer may name."""
	copy = Child()
	fields = dict(
		{
			"current_plant2": "1 (Mix)",
			"current_item_code": "0227",
			"coa_reference": "COA-CUST-1",
			"coa_amb": "COA-CUST-1",
			"coa_amb2": "CERT-SRC",
		},
		**released("Passed", "Own certificate", cert="CERT-SRC"),
	)
	for key, value in dict(fields, **copy_fields).items():
		copy.set(key, value)
	copy.processing_history = [dict(row) for row in SOURCE_ROWS]
	f = fake_frappe()
	f.get_doc.return_value = Fields(name="SRC")
	f.copy_doc.return_value = copy
	with mock.patch.object(bam, "frappe", f), site(Table(*stored), frappe=f):
		out = bam.duplicate_batch("SRC")
	return out, copy


class TestADuplicateIsACleanNewRecord(unittest.TestCase):
	"""Decision 346 (TASKS-397): `duplicate_batch`."""

	def test_a_source_without_a_plant_or_an_item_is_refused_naming_the_source(self):
		"""Review finding 1: the copy's one row needs them; the refusal names the source and what it lacks."""
		for missing in ({"current_plant2": None}, {"current_item_code": None, "item_to_manufacture": None}):
			with self.subTest(missing=missing):
				copy = Child()
				for key, value in dict(
					{"current_plant2": "1 (Mix)", "current_item_code": "0227", "custom_batch_level": "1"},
					**missing,
				).items():
					copy.set(key, value)
				with site(Table()) as f:
					with self.assertRaises(Exception):
						lq.insert_copy(copy, "SRC")
				text = str(f.throw.call_args_list[0])
				self.assertIn("Lot record SRC cannot be duplicated: it has no", text)
				self.assertIn('("copied from SRC") needs it', text)
				self.assertIsNone(copy.inserted)  # nothing was written

	def test_the_copy_names_no_work_order(self):
		"""Review finding 5: the older Work Order field too, or the planned-quantity sync adds a second row."""
		_out, copy = duplicate(rec("L"), parent_batch_amb="L", custom_batch_level="2", work_order="WO-1")
		self.assertIsNone(copy.get("work_order"))
		self.assertIsNone(copy.get("work_order_ref"))

	def test_none_of_the_sources_history_rows_is_copied_and_it_gets_one_copied_from_row(self):
		for parent in (None, "L"):
			with self.subTest(parent=parent):
				out, copy = duplicate(
					rec("L"), parent_batch_amb=parent, custom_batch_level="2" if parent else "1"
				)
				self.assertEqual(out, "LOTE-NEW")
				(row,) = copy.rows
				self.assertNotIn("source row", row["comments"])
				self.assertEqual(
					(
						row["processing_action"],
						row["quality_status"],
						row["changed_by"],
						row["batch_reference"],
					),
					("Quality Status Changed", "Pending", USER, "LOTE-NEW"),
				)
				self.assertIn("reason: copied from SRC", row["comments"])
				self.assertIn("certificate: from none to none", row["comments"])
				self.assertIs(copy.flag_at_insert, lq._WRITER)  # the module's own insert
				self.assertEqual(copy.flags, {})  # ... and the flag is down after it

	def test_it_keeps_its_parent_pointer_no_certificate_link_and_pending(self):
		_out, copy = duplicate(rec("L"), parent_batch_amb="L", custom_batch_level="2")
		self.assertEqual(copy.get("parent_batch_amb"), "L")
		self.assertEqual(copy.inserted, PENDING_NO_CERTIFICATE)
		for fieldname in LINKS:
			self.assertIsNone(copy.get(fieldname), fieldname)

	def test_a_container_duplicate_under_a_certified_lot_or_sub_lot_inherits(self):
		for level in ("1", "2"):
			for source in ("Own certificate", "Inherited"):
				with self.subTest(level=level, source=source):
					parent = rec("P", level, None if level == "1" else "L", "Failed", source, cert="CERT-P")
					_out, copy = duplicate(parent, parent_batch_amb="P", custom_batch_level="3")
					self.assertEqual(copy.inserted, inherited("CERT-P", "Failed"))
					(row,) = copy.rows
					for needle in (
						"created after approval of COA AMB2 CERT-P: inherits from P",
						"from Pending to Failed",
						"certificate: from none to COA AMB2 CERT-P (says Failed)",
						"copied from SRC",
					):
						self.assertIn(needle, row["comments"])
					self.assertNotIn("source row", row["comments"])
					for fieldname in LINKS:
						self.assertIsNone(copy.get(fieldname), fieldname)

	def test_it_is_the_same_birth_as_a_new_container_under_the_same_parent(self):
		# insert_copy goes through insert_child: same values, same row text plus "copied from"
		for parent in (
			rec("P", "2", "L", "Passed", "Own certificate", cert="CERT-P"),
			rec("P", "2", "L", "Hold", "Hold action", cert="CERT-P", says="Passed"),
			rec("P", "2", "L", "Passed", "Inherited", cert="CERT-L"),
		):
			with self.subTest(parent=parent):
				_out, copy = duplicate(parent, parent_batch_amb="P", custom_batch_level="3")
				fields = dict(parent, name="SUB-1", current_plant2="1 (Mix)", current_item_code="0227")
				_r, child, _f = create("3", **fields)
				self.assertEqual(copy.inserted, child.inserted)
				expected = child.rows[0]["comments"].replace("SUB-1", "P")
				self.assertEqual(
					copy.rows[0]["comments"].split(" | by ")[0],
					expected.split(" | by ")[0] + " | copied from SRC",
				)

	def test_under_an_uncertified_parent_a_container_duplicate_is_pending(self):
		for parent in (rec("P", "2", "L"), rec("P", "2", "L", "Hold", "Hold action")):
			with self.subTest(parent=parent):
				_out, copy = duplicate(parent, parent_batch_amb="P", custom_batch_level="3")
				self.assertEqual(copy.inserted, PENDING_NO_CERTIFICATE)
				(row,) = copy.rows
				self.assertIn("reason: copied from SRC", row["comments"])
				self.assertNotIn("approval", row["comments"])

	def test_a_duplicate_other_than_such_a_container_is_pending_with_the_336_row(self):
		# a sub-lot under a certified lot; a container under a certified container
		for parent, level in (
			(rec("P", "1", None, "Passed", "Own certificate", cert="CERT-P"), "2"),
			(rec("P", "3", "S", "Passed", "Inherited", cert="CERT-P"), "3"),
		):
			with self.subTest(parent_level=parent["custom_batch_level"], level=level):
				_out, copy = duplicate(parent, parent_batch_amb="P", custom_batch_level=level)
				self.assertEqual(copy.inserted, PENDING_NO_CERTIFICATE)
				(row,) = copy.rows
				self.assertIn(
					"created after approval of COA AMB2 CERT-P: Pending until certified", row["comments"]
				)
				self.assertIn("copied from SRC", row["comments"])

	def test_a_parent_pointer_to_a_record_that_no_longer_exists_is_kept_and_the_copy_is_pending(self):
		_out, copy = duplicate(parent_batch_amb="GONE", custom_batch_level="3")
		self.assertEqual(copy.get("parent_batch_amb"), "GONE")
		self.assertEqual(copy.inserted, PENDING_NO_CERTIFICATE)
		(row,) = copy.rows
		self.assertIn("reason: copied from SRC", row["comments"])

	def test_the_forms_own_duplicate_copies_no_history_row(self):
		"""The form's Duplicate (Frappe's client `frappe.model.copy_doc`, create_new.js) skips a Table field marked
		"no copy" with all its rows; it sends no name of the source, so the server writes no "copied from" row for
		it (see the report of TASKS-397)."""
		import json
		import pathlib

		meta = json.loads((pathlib.Path(bam.__file__).parent / "batch_amb.json").read_text(encoding="utf-8"))
		(field,) = [f for f in meta["fields"] if f["fieldname"] == lq.HISTORY_TABLE]
		self.assertEqual((field["fieldtype"], field.get("no_copy")), ("Table", 1))
		# ... and the parent pointer is copied by it (kept)
		(parent,) = [f for f in meta["fields"] if f["fieldname"] == lq.PARENT_FIELD]
		self.assertFalse(parent.get("no_copy"))


class TestADuplicateCopiesSetupTablesOnly(unittest.TestCase):
	"""Decision 353 (TASKS-398): a copy keeps the setup table and none of the record tables."""

	RECORD = ("output_products", "batch_output_products", "container_barrels", "quality_test_results")

	def meta(self):
		import json
		import pathlib

		return json.loads((pathlib.Path(bam.__file__).parent / "batch_amb.json").read_text(encoding="utf-8"))

	def test_a_server_duplicate_keeps_the_setup_table_and_empties_every_record_table(self):
		tables = {
			name: [{"row": name}] for name in (*lq.COPY_EMPTIED_RECORD_TABLES, *lq.COPY_KEPT_SETUP_TABLES)
		}
		_out, copy = duplicate(rec("L"), parent_batch_amb="L", custom_batch_level="2", **tables)
		for name in lq.COPY_EMPTIED_RECORD_TABLES:
			self.assertEqual(copy.get(name), [], name)
		self.assertEqual(copy.get("batch_parameters"), [{"row": "batch_parameters"}])
		self.assertEqual(len(copy.rows), 1)  # and the one history row of 346

	def test_every_table_of_the_doctype_is_classed(self):
		tables = {
			f["fieldname"] for f in self.meta()["fields"] if f["fieldtype"] in ("Table", "Table MultiSelect")
		}
		classed = {*lq.COPY_EMPTIED_RECORD_TABLES, *lq.COPY_KEPT_SETUP_TABLES, lq.HISTORY_TABLE}
		self.assertEqual(tables - classed, set())  # a new table must be classed before it is copied
		self.assertEqual(set(self.RECORD) | {"batch_parameters"}, tables - {lq.HISTORY_TABLE})

	def test_the_json_marks_every_record_table_no_copy_and_not_the_setup_table(self):
		no_copy = {f["fieldname"]: f.get("no_copy") for f in self.meta()["fields"]}
		for name in (*self.RECORD, lq.HISTORY_TABLE):
			self.assertEqual(no_copy[name], 1, name)
		self.assertFalse(no_copy["batch_parameters"])


if __name__ == "__main__":
	unittest.main()
