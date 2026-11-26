# TASKS-384 B4 (decision 319), DB-free: an approval is written down the hierarchy of the lot record.
#
#   * lot approved -> the lot (Own certificate), its sub-lots and their containers (Inherited)
#   * a sub-lot with a certificate of its own is left alone with its containers, in both orders of approval
#   * a withdrawal resets only the records the certificate wrote; a sub-lot that loses its own certificate takes
#     the status of its nearest certified ancestor
#   * a record on a hand hold keeps Hold and stores the verdict; the records below it are written as usual
#   * a new sub-lot or container under a released record is born released (Inherited)
#   * how it is written: one full save and ONE history row for the lot and for each sub-lot; the containers by
#     one column write per sub-lot, named in that sub-lot's row; one read per level of the tree
#
# The tree rules run against the in-memory table of test_lot_quality (`Table`); the real seam
# (`lot_quality.LotTable`) runs against the fake frappe whose documents call the REAL guard when saved.
#
# Run: python -m unittest amb_w_spc.tests.test_lot_quality_hierarchy   (no site needed)

import unittest
from unittest import mock

from amb_w_spc.sfc_manufacturing import lot_quality as lq
from amb_w_spc.sfc_manufacturing.doctype.batch_amb import batch_amb as bam
from amb_w_spc.tests.test_lot_quality import (
	CUSTOMER,
	INTERNAL,
	USER,
	Db,
	Refused,
	Table,
	fake_frappe,
	rec,
	site,
)

PENDING = ("Pending", "", None, None)


def tree(*changed, sublots=3, containers=2):
	"""L (lot) > S1..Sn (sub-lots) > Cij (containers), all Pending; `changed` records replace their namesakes."""
	records = {"L": rec("L")}
	for i in range(1, sublots + 1):
		records[f"S{i}"] = rec(f"S{i}", "2", "L")
		for j in range(1, containers + 1):
			records[f"C{i}{j}"] = rec(f"C{i}{j}", "3", f"S{i}")
	for r in changed:
		records[r["name"]] = r
	return Table(*records.values())


def inherited(cert, status):
	return (status, "Inherited", cert, status)


def own(cert, status):
	return (status, "Own certificate", cert, status)


def held(cert=None, says=None):
	return ("Hold", "Hold action", cert, says)


class TestApprovalGoesDown(unittest.TestCase):
	def test_a_lot_approved_is_written_to_all_three_levels(self):
		for cert_type in (INTERNAL, CUSTOMER):
			for result, status in (("Pass", "Passed"), ("Fail", "Failed"), ("Partial", "Hold")):
				t = tree()
				with site(t):
					lq.certificate_approved(cert_type, "CERT-L", "L", result)
				self.assertEqual(t.state("L"), own("CERT-L", status))
				for name in ("S1", "S2", "S3", "C11", "C12", "C21", "C22", "C31", "C32"):
					self.assertEqual(t.state(name), inherited("CERT-L", status), (name, result))
					self.assertEqual(t.rows[name]["released_by_doctype"], cert_type, name)

	def test_a_sub_lot_approved_is_written_to_its_containers_and_to_nothing_else(self):
		t = tree()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-S2", "S2", "Pass")
		self.assertEqual(t.state("S2"), own("CERT-S2", "Passed"))
		for name in ("C21", "C22"):
			self.assertEqual(t.state(name), inherited("CERT-S2", "Passed"))
		for name in ("L", "S1", "S3", "C11", "C12", "C31", "C32"):
			self.assertEqual(t.state(name), PENDING, name)

	def test_a_container_directly_under_the_lot_follows_the_lot(self):
		t = tree(rec("CX", "3", "L"))
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		self.assertEqual(t.state("CX"), inherited("CERT-L", "Passed"))
		self.assertIn("CX", t.rows_of("L")[0].note)  # the lot's row speaks for it

	def test_a_record_of_another_level_is_not_written(self):
		t = tree(rec("P1", "4", "C11"), rec("P2", "4", "S1"))
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		self.assertEqual((t.state("P1"), t.state("P2")), (PENDING, PENDING))
		self.assertEqual(t.state("C11"), inherited("CERT-L", "Passed"))

	def test_a_loop_in_the_parent_pointers_ends(self):
		t = tree()
		t.rows["L"]["parent_batch_amb"] = "S1"  # L > S1 > L
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		self.assertEqual(t.state("L"), own("CERT-L", "Passed"))
		self.assertEqual(len(t.rows_of("L")), 1)


class TestOwnCertificateBelow(unittest.TestCase):
	def test_a_sub_lots_own_failed_under_a_passed_lot_stays_failed_sub_lot_first(self):
		t = tree()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-S1", "S1", "Fail")
			lq.certificate_approved(CUSTOMER, "CERT-L", "L", "Pass")
		self.check(t)

	def test_a_sub_lots_own_failed_under_a_passed_lot_stays_failed_lot_first(self):
		t = tree()
		with site(t):
			lq.certificate_approved(CUSTOMER, "CERT-L", "L", "Pass")
			self.assertEqual(t.state("S1"), inherited("CERT-L", "Passed"))
			lq.certificate_approved(INTERNAL, "CERT-S1", "S1", "Fail")
		self.check(t)

	def check(self, t):
		self.assertEqual(t.state("L"), own("CERT-L", "Passed"))
		self.assertEqual(t.state("S1"), own("CERT-S1", "Failed"))
		for name in ("C11", "C12"):  # the containers of the failed sub-lot follow the sub-lot, not the lot
			self.assertEqual(t.state(name), inherited("CERT-S1", "Failed"), name)
		for name in ("S2", "S3", "C21", "C22", "C31", "C32"):
			self.assertEqual(t.state(name), inherited("CERT-L", "Passed"), name)

	def test_a_second_approval_of_the_lot_still_leaves_the_sub_lot_with_its_own_certificate(self):
		t = tree()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-S1", "S1", "Fail")
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
			lq.certificate_approved(CUSTOMER, "CERT-L2", "L", "Partial")
		self.assertEqual(t.state("L"), own("CERT-L2", "Hold"))
		self.assertEqual(t.state("S1"), own("CERT-S1", "Failed"))
		self.assertEqual(t.state("C11"), inherited("CERT-S1", "Failed"))
		self.assertEqual(t.state("S2"), inherited("CERT-L2", "Hold"))
		self.assertEqual(t.state("C21"), inherited("CERT-L2", "Hold"))


class TestHandHoldBelow(unittest.TestCase):
	def test_a_held_sub_lot_keeps_hold_and_stores_the_verdict_and_the_rest_is_written(self):
		t = tree(rec("S1", "2", "L", status="Hold", source="Hold action"))
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
			self.assertEqual(t.state("S1"), held("CERT-L", "Passed"))
			# the hold is on the one record: what is below it follows the certificate
			self.assertEqual(t.state("C11"), inherited("CERT-L", "Passed"))
			self.assertEqual(t.state("S2"), inherited("CERT-L", "Passed"))
			lq.lift_hand_hold("S1", "checked")
		self.assertEqual(t.state("S1"), inherited("CERT-L", "Passed"))

	def test_a_held_container_keeps_hold_and_the_row_above_says_so(self):
		t = tree(rec("C11", "3", "S1", status="Hold", source="Hold action"))
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Fail")
		self.assertEqual(t.state("C11"), held("CERT-L", "Failed"))
		self.assertEqual(t.state("C12"), inherited("CERT-L", "Failed"))
		(row,) = t.rows_of("S1")
		self.assertIn("1 from Hold to Hold (on hand hold: the verdict is stored): C11", row.note)
		self.assertIn("1 from Pending to Failed: C12", row.note)

	def test_a_held_lot_is_not_released_by_its_approval_and_takes_the_verdict_when_lifted(self):
		t = tree(rec("L", status="Hold", source="Hold action"))
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
			self.assertEqual(t.state("L"), held("CERT-L", "Passed"))
			lq.lift_hand_hold("L", "deviation closed")
		self.assertEqual(t.state("L"), own("CERT-L", "Passed"))

	def test_a_held_sub_lot_with_a_certificate_of_its_own_is_left_alone_with_its_containers(self):
		t = tree(
			rec("S1", "2", "L", status="Hold", source="Hold action", cert="CERT-S1", says="Failed"),
			rec("C11", "3", "S1", status="Failed", source="Inherited", cert="CERT-S1"),
		)
		with site(t):
			lq.certificate_approved(CUSTOMER, "CERT-L", "L", "Pass")
		self.assertEqual(t.state("S1"), held("CERT-S1", "Failed"))
		self.assertEqual(t.state("C11"), inherited("CERT-S1", "Failed"))
		self.assertEqual(t.state("C12"), PENDING)  # below the sub-lot with its own certificate: not walked
		self.assertEqual(t.state("S2"), inherited("CERT-L", "Passed"))

	def test_a_held_sub_lot_that_followed_the_lots_earlier_certificate_follows_the_new_one(self):
		t = tree(
			rec("L", status="Passed", source="Own certificate", cert="CERT-OLD"),
			rec("S1", "2", "L", status="Hold", source="Hold action", cert="CERT-OLD", says="Passed"),
		)
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-NEW", "L", "Fail")
		self.assertEqual(t.state("S1"), held("CERT-NEW", "Failed"))


class TestWithdrawalGoesDown(unittest.TestCase):
	def released(self):
		t = tree()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-S1", "S1", "Fail")
			lq.certificate_approved(CUSTOMER, "CERT-L", "L", "Pass")
		t.history.clear()
		t.column_writes.clear()
		t.reads.clear()
		return t

	def test_rejecting_the_lots_certificate_resets_only_what_it_wrote(self):
		t = self.released()
		with site(t):
			lq.certificate_withdrawn(CUSTOMER, "CERT-L", "L")
		for name in ("L", "S2", "S3", "C21", "C22", "C31", "C32"):
			self.assertEqual(t.state(name), PENDING, name)
			self.assertIsNone(t.rows[name]["released_by_doctype"], name)
		self.assertEqual(t.state("S1"), own("CERT-S1", "Failed"))  # its own certificate still stands
		self.assertEqual(t.state("C11"), inherited("CERT-S1", "Failed"))
		self.assertEqual(sorted(h.lot for h in t.history), ["L", "S2", "S3"])

	def test_a_sub_lot_that_loses_its_own_certificate_takes_its_nearest_certified_ancestors_status(self):
		t = self.released()
		with site(t):
			lq.certificate_withdrawn(INTERNAL, "CERT-S1", "S1")
		self.assertEqual(t.state("S1"), inherited("CERT-L", "Passed"))
		self.assertEqual(t.rows["S1"]["released_by_doctype"], CUSTOMER)
		for name in ("C11", "C12"):  # its own descendants follow it
			self.assertEqual(t.state(name), inherited("CERT-L", "Passed"), name)
		self.assertEqual(t.state("L"), own("CERT-L", "Passed"))
		self.assertEqual([h.lot for h in t.history], ["S1"])
		self.assertIn("follows L", t.history[0].reason)

	def test_with_no_certified_ancestor_it_returns_to_pending(self):
		t = tree()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-S1", "S1", "Pass")
			lq.certificate_withdrawn(INTERNAL, "CERT-S1", "S1")
		for name in ("S1", "C11", "C12"):
			self.assertEqual(t.state(name), PENDING, name)

	def test_a_lot_above_that_is_passed_with_no_certificate_named_is_not_a_certified_ancestor(self):
		# a status from before this rule (no source, no certificate): nothing to inherit from
		t = tree(rec("L", status="Passed"))
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-S1", "S1", "Fail")
			lq.certificate_withdrawn(INTERNAL, "CERT-S1", "S1")
		self.assertEqual(t.state("S1"), PENDING)
		self.assertEqual(t.state("L"), ("Passed", "", None, None))

	def test_an_ancestor_on_hand_hold_gives_what_its_certificate_says(self):
		t = self.released()
		t.rows["L"].update(quality_status="Hold", status_source="Hold action")
		with site(t):
			lq.certificate_withdrawn(INTERNAL, "CERT-S1", "S1")
		self.assertEqual(t.state("S1"), inherited("CERT-L", "Passed"))

	def test_with_a_certificate_that_still_stands_everything_it_wrote_takes_that_one(self):
		t = tree()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
			lq.certificate_approved(CUSTOMER, "CERT-2", "L", "Fail")
			lq.certificate_withdrawn(
				CUSTOMER, "CERT-2", "L", standing={"doctype": INTERNAL, "name": "CERT-1", "result": "Pass"}
			)
		self.assertEqual(t.state("L"), own("CERT-1", "Passed"))
		for name in ("S1", "S2", "S3", "C11", "C32"):
			self.assertEqual(t.state(name), inherited("CERT-1", "Passed"), name)
			self.assertEqual(t.rows[name]["released_by_doctype"], INTERNAL)

	def test_a_certificate_that_did_not_write_the_lot_changes_nothing_below_either(self):
		t = self.released()
		with site(t):
			self.assertEqual(lq.certificate_withdrawn(INTERNAL, "CERT-OTHER", "L"), 0)
		self.assertEqual((t.history, t.column_writes), ([], []))
		self.assertEqual(t.state("S2"), inherited("CERT-L", "Passed"))

	def test_a_held_record_it_wrote_keeps_hold_and_forgets_the_verdict(self):
		t = self.released()
		t.rows["S2"].update(quality_status="Hold", status_source="Hold action")
		t.rows["C31"].update(quality_status="Hold", status_source="Hold action")
		with site(t):
			lq.certificate_withdrawn(CUSTOMER, "CERT-L", "L")
		self.assertEqual(t.state("S2"), held())
		self.assertEqual(t.state("C31"), held())
		self.assertEqual(t.state("C21"), PENDING)


class TestHowItIsWritten(unittest.TestCase):
	def test_one_row_on_the_lot_and_on_each_sub_lot_and_none_on_the_containers(self):
		t = tree()
		with site(t):
			written = lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		self.assertEqual([h.lot for h in t.history], ["L", "S1", "S2", "S3"])  # top first, 1 + S rows
		self.assertEqual(written, 10)
		# the containers: one column write per sub-lot, all of GUARDED_FIELDS, nothing else
		self.assertEqual(
			[names for names, _v in t.column_writes], [["C11", "C12"], ["C21", "C22"], ["C31", "C32"]]
		)
		for _names, values in t.column_writes:
			self.assertEqual(
				values,
				{
					"quality_status": "Passed",
					"status_source": "Inherited",
					"released_by_doctype": INTERNAL,
					"released_by": "CERT-L",
					"certificate_status": "Passed",
				},
			)

	def test_the_sub_lots_row_names_every_container_written_with_it(self):
		t = tree()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		self.assertIsNone(t.rows_of("L")[0].note)  # no container directly under the lot
		for sublot, containers in (("S1", "C11, C12"), ("S2", "C21, C22"), ("S3", "C31, C32")):
			(row,) = t.rows_of(sublot)
			self.assertIn(f"2 from Pending to Passed: {containers}", row.note)
			self.assertIn("follows L", row.reason)
			self.assertIn("CERT-L", row.reason)

	def test_a_sub_lot_that_does_not_change_still_gets_a_row_for_the_containers_written_with_it(self):
		# a container that was not following (written before this rule, or by a column write of someone else)
		t = tree()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
			t.history.clear()
			t.column_writes.clear()
			t.rows["C21"].update(rec("C21", "3", "S2"))  # back to Pending behind the module's back
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		self.assertEqual(t.state("C21"), inherited("CERT-L", "Passed"))
		self.assertEqual([h.lot for h in t.history], ["S2"])
		self.assertIn("1 from Pending to Passed: C21", t.history[0].note)
		self.assertEqual(t.column_writes[0][0], ["C21"])

	def test_one_read_per_level_however_many_containers(self):
		for containers in (2, 200):
			t = tree(containers=containers)
			with site(t):
				lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
			self.assertEqual(
				[kind for kind, _what in t.reads], ["get", "children", "children", "children"], containers
			)
			self.assertEqual(t.reads[0], ("get", "L"))
			self.assertEqual(t.reads[1], ("children", ["L"]))
			self.assertEqual(t.reads[2], ("children", ["S1", "S2", "S3"]))
			self.assertEqual(len(t.reads[3][1]), 3 * containers)  # the containers' own children: none
			self.assertEqual((len(t.history), len(t.column_writes)), (4, 3), containers)

	def test_nothing_is_written_before_the_whole_tree_is_read(self):
		order = []
		t = tree()
		for method in ("get", "children", "save", "write_columns"):
			original = getattr(t, method)
			setattr(t, method, lambda *a, _m=method, _o=original, **k: (order.append(_m), _o(*a, **k))[1])
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		first_write = min(order.index("save"), order.index("write_columns"))
		self.assertNotIn("children", order[first_write:])
		self.assertNotIn("get", order[first_write:])

	def test_a_record_that_cannot_be_written_stops_the_approval_and_nothing_after_it_is_written(self):
		t = tree()
		original = t.save
		boom = RuntimeError("S2 cannot be saved")

		def save(name, *args, **kwargs):
			if name == "S2":
				raise boom
			return original(name, *args, **kwargs)

		t.save = save
		with site(t), self.assertRaises(RuntimeError) as caught:
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		self.assertIs(caught.exception, boom)  # not caught: the caller's transaction is what undoes L and S1
		self.assertEqual(t.state("S2"), PENDING)
		self.assertEqual(t.state("C21"), PENDING)  # its containers are written after its own save
		self.assertEqual(t.state("S3"), PENDING)


class TestTheRealTable(unittest.TestCase):
	def db(self):
		return Db(
			rec("L"),
			rec("S1", "2", "L"),
			rec("S2", "2", "L"),
			rec("C11", "3", "S1"),
			rec("C12", "3", "S1"),
			rec("C21", "3", "S2"),
		)

	def test_an_approval_loads_the_lot_and_the_sub_lots_as_documents_and_no_container(self):
		db = self.db()
		with site(frappe=db.frappe()):
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		self.assertEqual([d.name for d in db.docs], ["L", "S1", "S2"])
		for name in ("S1", "S2", "C11", "C12", "C21"):
			self.assertEqual(
				[db.rows[name][f] for f in lq.GUARDED_FIELDS],
				["Passed", "Inherited", INTERNAL, "CERT-L", "Passed"],
				name,
			)
		# every document save passed the REAL guard (LotDoc.save runs both lines) with one row appended before
		self.assertEqual([(e[1], len(e[4])) for e in db.saves()], [("L", 1), ("S1", 1), ("S2", 1)])
		self.assertEqual({name: len(rows) for name, rows in db.history.items()}, {"L": 1, "S1": 1, "S2": 1})
		self.assertIn("C11, C12", db.history["S1"][0]["comments"])
		self.assertIn(f"by {USER}", db.history["S1"][0]["comments"])

	def test_the_tree_is_read_with_one_query_per_level_and_no_page_limit(self):
		db = self.db()
		with site(frappe=db.frappe()) as f:
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		queries = [e for e in db.log if e[0] == "get_all"]
		self.assertEqual(
			[e[1] for e in queries],
			[
				{"parent_batch_amb": ["in", ["L"]]},
				{"parent_batch_amb": ["in", ["S1", "S2"]]},
				{"parent_batch_amb": ["in", ["C11", "C12", "C21"]]},
			],
		)
		for _kind, _filters, fields, kwargs in queries:
			self.assertEqual(fields, list(lq.RECORD_FIELDS))
			self.assertEqual(kwargs.get("limit_page_length"), 0)
		self.assertEqual(f.db.get_value.call_count, 1)  # the certificate's own record; no read per record

	def test_the_containers_are_written_by_one_column_write_per_sub_lot_after_its_save(self):
		db = self.db()
		with site(frappe=db.frappe()) as f:
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		writes = [e for e in db.log if e[0] == "set_value"]
		self.assertEqual(
			[e[1] for e in writes], [{"name": ["in", ["C11", "C12"]]}, {"name": ["in", ["C21"]]}]
		)
		for _kind, _filters, values in writes:
			self.assertEqual(set(values), set(lq.GUARDED_FIELDS))
		kinds = [(e[0], e[1] if e[0] == "save" else None) for e in db.log if e[0] in ("save", "set_value")]
		self.assertEqual(
			kinds, [("save", "L"), ("save", "S1"), ("set_value", None), ("save", "S2"), ("set_value", None)]
		)
		f.db.commit.assert_not_called()  # the caller's transaction, whole
		f.db.sql.assert_not_called()

	def test_the_column_write_takes_the_quality_fields_only(self):
		with site() as f:
			with self.assertRaises(Refused):
				lq.LotTable().write_columns(
					["C11"], {"quality_status": "Passed", "batch_status": "Completed"}
				)
			f.db.set_value.assert_not_called()
			lq.LotTable().write_columns([], {"quality_status": "Passed"})
			f.db.set_value.assert_not_called()
			self.assertEqual(lq.LotTable().children([]), [])
			f.get_all.assert_not_called()


# ----------------------------------------------------------------------------------------------------------------
# create_child_batch: the real function, with a parent and a child that behave like documents
# ----------------------------------------------------------------------------------------------------------------
class Fields:
	"""A document as create_child_batch uses one: attributes for fields, None for a field never set."""

	def __init__(self, **fields):
		self.__dict__.update(fields)
		self.flags = {}

	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return None

	def get(self, key, default=None):
		value = self.__dict__.get(key)
		return default if value is None else value

	def set(self, key, value):
		self.__dict__[key] = value


class Child(Fields):
	def __init__(self):
		super().__init__()
		self.rows = []
		self.inserted = None

	def append(self, table, row):
		assert table == "processing_history"
		self.processing_history = [*(self.processing_history or []), row]

	def get_doc_before_save(self):
		return None

	def insert(self):
		# what Frappe runs around an insert: the guard's two lines, for real
		lq.refuse_hand_change(self, "before_validate")
		self.flag_at_insert = self.flags.get(lq.WRITER_FLAG)
		self.name = "LOTE-NEW"
		lq.refuse_hand_change(self, "on_update")
		self.inserted = {f: self.get(f) for f in lq.GUARDED_FIELDS}
		self.rows = list(self.processing_history or [])


class TestANewChild(unittest.TestCase):
	def create(self, level="2", **parent_fields):
		fields = {
			"name": "LOTE-1",
			"is_group": 1,
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
			out = bam.create_child_batch("LOTE-1", level)
		return out, child, f

	def released(self, **kw):
		return dict(
			{
				"quality_status": "Passed",
				"status_source": "Own certificate",
				"released_by_doctype": INTERNAL,
				"released_by": "CERT-1",
				"certificate_status": "Passed",
			},
			**kw,
		)

	def test_a_new_sub_lot_or_container_under_a_released_record_is_released_as_inherited(self):
		for level in ("2", "3"):
			for status in ("Passed", "Failed", "Hold"):
				out, child, _f = self.create(
					level, **self.released(quality_status=status, certificate_status=status)
				)
				self.assertTrue(out["success"], out)
				self.assertEqual(
					child.inserted,
					{
						"quality_status": status,
						"status_source": "Inherited",
						"released_by_doctype": INTERNAL,
						"released_by": "CERT-1",
						"certificate_status": status,
					},
				)
				self.assertIs(child.flag_at_insert, lq._WRITER)  # the module's own insert ...
				self.assertEqual(child.flags, {})  # ... and the flag is down after it

	def test_it_follows_a_parent_that_itself_inherits(self):
		_out, child, _f = self.create("3", **self.released(status_source="Inherited"))
		self.assertEqual(
			(child.inserted["status_source"], child.inserted["released_by"]), ("Inherited", "CERT-1")
		)

	def test_its_birth_leaves_one_history_row_written_by_the_insert(self):
		_out, child, _f = self.create(**self.released())
		(row,) = child.rows
		self.assertEqual(
			(
				row["processing_action"],
				row["quality_status"],
				row["plant"],
				row["item_code"],
				row["changed_by"],
			),
			("Quality Status Changed", "Passed", "1 (Mix)", "0227", USER),
		)
		for needle in (
			"from Pending to Passed",
			"source: from none to Inherited",
			"COA AMB2 CERT-1",
			"LOTE-1",
		):
			self.assertIn(needle, row["comments"])

	def test_under_a_record_no_certificate_speaks_for_it_is_born_pending_with_no_row(self):
		for parent in (
			{},
			{"quality_status": "Pending"},
			{"quality_status": "Passed"},
		):  # the last: no certificate
			out, child, _f = self.create(**parent)
			self.assertTrue(out["success"], out)
			self.assertEqual(
				child.inserted,
				{
					"quality_status": "Pending",
					"status_source": None,
					"released_by_doctype": None,
					"released_by": None,
					"certificate_status": None,
				},
			)
			self.assertIsNone(child.flag_at_insert)  # an insert like any other: the guard judged it
			self.assertEqual(child.rows, [])

	def test_under_a_record_on_hand_hold_it_takes_what_the_certificate_says(self):
		_out, child, _f = self.create(**self.released(quality_status="Hold", status_source="Hold action"))
		self.assertEqual(
			(child.inserted["quality_status"], child.inserted["status_source"]), ("Passed", "Inherited")
		)
		# a hold with no certificate behind it: nothing to inherit
		_out, child, _f = self.create(quality_status="Hold", status_source="Hold action")
		self.assertEqual(
			(child.inserted["quality_status"], child.inserted["status_source"]), ("Pending", None)
		)

	def test_a_child_that_cannot_carry_its_history_row_is_not_created_and_the_user_is_told_why(self):
		parent = self.released(current_plant2=None)
		out, child, _f = self.create(**parent)
		self.assertFalse(out["success"])
		self.assertIsNone(child.inserted)
		# the fake throw raises with no text; the message is what frappe.throw was given
		self.assertIn("Current Plant", _f.throw.call_args.args[0])


if __name__ == "__main__":
	unittest.main()
