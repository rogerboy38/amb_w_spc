# TASKS-384 B4 (decision 319), DB-free: an approval is written down the hierarchy of the lot record.
#
#   * lot approved -> the lot (Own certificate), its sub-lots and their containers (Inherited)
#   * a sub-lot with a certificate of its own is left alone with its containers, in both orders of approval
#   * a withdrawal resets only the records the certificate wrote; a sub-lot that loses its own certificate takes
#     the status of its nearest certified ancestor
#   * a record on a hand hold keeps Hold and stores the verdict; the records below it are written as usual
#   * a withdrawal also resets a record that still names the certificate but is no longer reached by the walk
#     down (moved under another parent before the guard refused that)
#   * a new sub-lot or container created under a released record is born Pending with no certificate
#     (decision 336); the next approval of the record above reaches it. A container created under a released
#     SUB-LOT inherits since decision 342 (TASKS-391): tests/test_late_children.py
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
# what a new child is born with (TASKS-390, decision 336)
PENDING_NO_CERTIFICATE = {
	"quality_status": "Pending",
	"status_source": None,
	"released_by_doctype": None,
	"released_by": None,
	"certificate_status": None,
}


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


class TestWithdrawalFindsWhatWasMoved(unittest.TestCase):
	"""Review of TASKS-384, finding 3: the withdrawal resets by `released_by*`, not only by the walk down. The
	moves are made in the table directly: that is a record moved before the guard refused it."""

	def released(self, *more):
		t = tree(rec("M"), rec("MS", "2", "M"), *more)
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-S1", "S1", "Fail")
			lq.certificate_approved(CUSTOMER, "CERT-L", "L", "Pass")
		t.history.clear()
		t.column_writes.clear()
		t.reads.clear()
		return t

	def test_a_container_moved_under_another_lots_sub_lot_is_still_reset(self):
		t = self.released()
		t.rows["C21"]["parent_batch_amb"] = "MS"
		with site(t):
			written = lq.certificate_withdrawn(CUSTOMER, "CERT-L", "L")
		self.assertEqual(t.state("C21"), PENDING)
		self.assertIsNone(t.rows["C21"]["released_by_doctype"])
		self.assertEqual(written, 7)  # L, S2, S3, C22, C31, C32 and the moved C21
		# no saved record speaks for it where it sits now: it gets a row of its own, which says how it was found
		(row,) = t.rows_of("C21")
		self.assertIn("CERT-L withdrawn", row.reason)
		self.assertIn("found by its certificate, outside the walk down from L", row.reason)
		self.assertEqual((t.state("M"), t.state("MS")), (PENDING, PENDING))

	def test_a_sub_lot_moved_under_another_lot_is_reset_with_its_containers(self):
		t = self.released()
		t.rows["S3"]["parent_batch_amb"] = "M"
		with site(t):
			lq.certificate_withdrawn(CUSTOMER, "CERT-L", "L")
		for name in ("S3", "C31", "C32"):
			self.assertEqual(t.state(name), PENDING, name)
		(row,) = t.rows_of("S3")
		self.assertIn("C31, C32", row.note)  # one row on the sub-lot, its containers named in it
		self.assertEqual([h.lot for h in t.history], ["L", "S2", "S3"])
		self.assertIn(
			(
				["C31", "C32"],
				dict.fromkeys(lq.GUARDED_FIELDS) | {"quality_status": "Pending", "status_source": ""},
			),
			t.column_writes,
		)

	def test_a_moved_record_takes_the_nearest_certified_ancestor_where_it_sits_now(self):
		t = self.released()
		t.rows["C21"]["parent_batch_amb"] = "S1"  # under the sub-lot that failed on its own certificate
		t.rows["S3"]["parent_batch_amb"] = "M"
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-M", "M", "Partial")  # S3 stays with CERT-L: own walk only
			t.rows["S3"].update(
				released_by="CERT-L", released_by_doctype=CUSTOMER, certificate_status="Passed"
			)
			t.rows["S3"].update(quality_status="Passed")
			lq.certificate_withdrawn(CUSTOMER, "CERT-L", "L")
		self.assertEqual(t.state("C21"), inherited("CERT-S1", "Failed"))
		self.assertEqual(t.state("S3"), inherited("CERT-M", "Hold"))
		self.assertEqual(t.rows["S3"]["released_by_doctype"], INTERNAL)
		self.assertIn("follows M", t.rows_of("S3")[-1].reason)

	def test_a_moved_record_never_takes_the_standing_certificate_of_the_lot_it_left(self):
		t = self.released()
		t.rows["C21"]["parent_batch_amb"] = "MS"
		with site(t):
			lq.certificate_withdrawn(
				CUSTOMER, "CERT-L", "L", standing={"doctype": INTERNAL, "name": "CERT-L0", "result": "Fail"}
			)
		self.assertEqual(t.state("L"), own("CERT-L0", "Failed"))
		self.assertEqual(t.state("C22"), inherited("CERT-L0", "Failed"))
		self.assertEqual(t.state("C21"), PENDING)

	def test_a_record_the_walk_cannot_reach_below_the_lot_is_reset_and_follows_the_lot(self):
		# a level 4 record that carries the certificate (born under a released container before TASKS-390, decision
		# 336); the walk stops at level 3
		t = self.released(
			dict(rec("P1", "4", "C21", "Passed", "Inherited", "CERT-L"), released_by_doctype=CUSTOMER)
		)
		with site(t):
			lq.certificate_withdrawn(CUSTOMER, "CERT-L", "L")
		self.assertEqual(t.state("P1"), PENDING)
		t = self.released(
			dict(rec("P1", "4", "C21", "Passed", "Inherited", "CERT-L"), released_by_doctype=CUSTOMER)
		)
		with site(t):
			lq.certificate_withdrawn(
				CUSTOMER, "CERT-L", "L", standing={"doctype": INTERNAL, "name": "CERT-L0", "result": "Pass"}
			)
		self.assertEqual(t.state("P1"), inherited("CERT-L0", "Passed"))

	def test_moved_records_are_reset_also_when_the_lots_status_comes_from_another_certificate(self):
		t = self.released()
		t.rows["C21"]["parent_batch_amb"] = "MS"
		with site(t):
			lq.certificate_approved(
				INTERNAL, "CERT-L2", "L", "Fail"
			)  # replaces CERT-L on L and below; not C21
			self.assertEqual(t.state("C21"), inherited("CERT-L", "Passed"))
			# two writes: the moved container, and the lot's link, which still pointed at CERT-L
			self.assertEqual(lq.certificate_withdrawn(CUSTOMER, "CERT-L", "L"), 2)
		self.assertEqual((t.rows["L"]["coa_reference"], t.rows["L"]["coa_amb2"]), (None, "CERT-L2"))
		self.assertEqual(t.state("C21"), PENDING)
		self.assertEqual(t.state("L"), own("CERT-L2", "Failed"))

	def test_a_moved_record_on_hand_hold_keeps_hold_and_forgets_the_verdict(self):
		t = self.released()
		t.rows["C21"].update(parent_batch_amb="MS", quality_status="Hold", status_source="Hold action")
		with site(t):
			lq.certificate_withdrawn(CUSTOMER, "CERT-L", "L")
		self.assertEqual(t.state("C21"), held())

	def test_another_certificates_records_are_not_touched_and_the_query_names_the_certificate(self):
		t = self.released()
		t.rows["C11"]["parent_batch_amb"] = "MS"  # carries CERT-S1, which is not withdrawn
		with site(t):
			lq.certificate_withdrawn(CUSTOMER, "CERT-L", "L")
		self.assertEqual(t.state("C11"), inherited("CERT-S1", "Failed"))
		self.assertEqual([what for kind, what in t.reads if kind == "released_by"], [(CUSTOMER, "CERT-L")])

	def test_the_real_table_asks_for_the_records_by_the_two_released_by_fields(self):
		db = Db(rec("L"), rec("S1", "2", "L"), rec("C11", "3", "S1"), rec("M"), rec("MS", "2", "M"))
		with site(frappe=db.frappe()):
			lq.certificate_approved(CUSTOMER, "CERT-L", "L", "Pass")
			db.rows["C11"]["parent_batch_amb"] = "MS"
			del db.log[:]
			lq.certificate_withdrawn(CUSTOMER, "CERT-L", "L")
		queries = [e for e in db.log if e[0] == "get_all" and "released_by" in e[1]]
		self.assertEqual(
			[e[1] for e in queries], [{"released_by_doctype": CUSTOMER, "released_by": "CERT-L"}]
		)
		self.assertEqual((queries[0][2], queries[0][3].get("limit_page_length")), (list(lq.RECORD_FIELDS), 0))
		self.assertEqual(db.rows["C11"]["quality_status"], "Pending")
		self.assertIsNone(db.rows["C11"]["released_by"])
		self.assertEqual([e[1] for e in db.saves()], ["L", "S1", "C11"])  # the moved container: a full save
		self.assertEqual(len(db.history["C11"]), 1)


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
		record_reads = [
			c
			for c in f.db.get_value.call_args_list
			if c.args[0] == "Batch AMB" and c.args[2] != "work_order_ref"
		]
		self.assertEqual(len(record_reads), 1)  # the certificate's own record; no read per record

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

	def test_a_sub_lot_that_cannot_carry_its_row_is_named_with_the_lot_of_the_certificate(self):
		# review finding 9: the user is on the certificate of L and has never opened S2
		for item in ("approval", "withdrawal"):
			db = self.db()
			f = db.frappe()
			with site(frappe=f):
				if item == "withdrawal":
					lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
				db.rows["S2"]["current_plant2"] = None
				with self.assertRaises(Refused):
					if item == "approval":
						lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
					else:
						lq.certificate_withdrawn(INTERNAL, "CERT-L", "L")
			msg = f.throw.call_args.args[0]
			for needle in (
				"certificate of lot record L",
				"lot record S2",
				"Current Plant",
				"Open lot record S2",
			):
				self.assertIn(needle, msg, item)
			self.assertNotIn(
				"S2", [e[1] for e in db.saves()][-1:], item
			)  # the rule is the same: S2 is not saved

	def test_the_certificates_own_lot_keeps_the_message_for_the_record_in_front_of_the_user(self):
		db = self.db()
		db.rows["L"]["current_plant2"] = None
		f = db.frappe()
		with site(frappe=f), self.assertRaises(Refused):
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		msg = f.throw.call_args.args[0]
		self.assertIn("The quality status of lot record L cannot be changed", msg)
		self.assertNotIn("also writes", msg)

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
		# what Frappe runs around an insert: the document is named (Document.insert: set_new_name comes before
		# run_before_save_methods), then the guard's two lines, for real
		self.name = "LOTE-NEW"
		lq.refuse_hand_change(self, "before_validate")
		self.flag_at_insert = self.flags.get(lq.WRITER_FLAG)
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

	def test_a_sub_lot_or_container_created_after_its_parents_approval_is_born_pending(self):
		# TASKS-390, decision 336 (replaces TASKS-384 B4's birth "Inherited" with the parent's verdict). The parent
		# here is a LOT (no level): a container under a SUB-LOT inherits since decision 342 (test_late_children)
		for level in ("2", "3"):
			for status in ("Passed", "Failed", "Hold"):
				for source in ("Own certificate", "Inherited"):
					with self.subTest(level=level, status=status, source=source):
						out, child, _f = self.create(
							level,
							**self.released(
								quality_status=status, certificate_status=status, status_source=source
							),
						)
						self.assertTrue(out["success"], out)
						self.assertEqual(child.inserted, PENDING_NO_CERTIFICATE)
						self.assertIs(
							child.flag_at_insert, lq._WRITER
						)  # the module's own insert (its row) ...
						self.assertEqual(child.flags, {})  # ... and the flag is down after it

	def test_its_birth_leaves_one_history_row_saying_it_was_created_after_the_approval(self):
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
			("Quality Status Changed", "Pending", "1 (Mix)", "0227", USER),
		)
		for needle in (
			"created after approval of COA AMB2 CERT-1: Pending until certified",
			"from Pending to Pending",
			"source: from none to none",
			"certificate: from none to none",
			"created under LOTE-1",
		):
			self.assertIn(needle, row["comments"])

	def test_a_value_the_caller_set_on_the_child_does_not_survive(self):
		# create_child_batch copies no quality field; whatever is on the new document, the birth is Pending
		parent = Fields(**self.released(name="LOTE-1", current_plant2="1", current_item_code="0227"))
		child = Child()
		child.quality_status, child.released_by, child.status_source = "Passed", "CERT-9", "Inherited"
		child.current_plant2, child.current_item_code = "1", "0227"
		with site():
			lq.insert_child(child, parent)
		self.assertEqual(child.inserted, PENDING_NO_CERTIFICATE)

	def test_after_the_birth_the_next_approval_above_writes_it_down_as_before(self):
		# a child born Pending has no certificate of its own: the next approval of its parent reaches it (319)
		t = Table(
			rec("L", status="Passed", source="Own certificate", cert="CERT-1"),
			rec("S-NEW", "2", "L"),
		)
		with site(t):
			lq.certificate_withdrawn(INTERNAL, "CERT-1", "L")
			self.assertEqual(
				t.state("S-NEW"), ("Pending", "", None, None)
			)  # not written: CERT-1 never wrote it
			lq.certificate_approved(INTERNAL, "CERT-2", "L", "Fail")
		self.assertEqual(t.state("S-NEW"), ("Failed", "Inherited", "CERT-2", "Failed"))

	def test_the_row_of_its_birth_names_the_new_record(self):
		# review finding 11: the row is appended before the insert, when the record has no name; the guard's
		# first line, which Frappe runs after naming the document, writes the name in it. One insert, no save.
		_out, child, _f = self.create(**self.released())
		(row,) = child.rows
		self.assertEqual(row["batch_reference"], "LOTE-NEW")

	def test_only_the_writers_own_rows_without_a_name_are_filled(self):
		doc = Fields(
			name="LOTE-9",
			processing_history=[
				{"processing_action": "Quality Status Changed", "batch_reference": None},
				{"processing_action": "Quality Status Changed", "batch_reference": "LOTE-OLD"},
				{"processing_action": "Started", "batch_reference": None},
				Fields(processing_action="Quality Status Changed"),
			],
		)
		doc.get_doc_before_save = lambda: None
		with site():
			lq.refuse_hand_change(doc, "before_validate")  # a save like any other: nothing is filled
			self.assertIsNone(doc.processing_history[0]["batch_reference"])
			doc.flags[lq.WRITER_FLAG] = lq._WRITER
			lq.refuse_hand_change(doc, "before_validate")
		rows = doc.processing_history
		self.assertEqual(
			[rows[0]["batch_reference"], rows[1]["batch_reference"], rows[2]["batch_reference"]],
			["LOTE-9", "LOTE-OLD", None],
		)
		self.assertEqual(rows[3].batch_reference, "LOTE-9")  # a child document, as on a real insert

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

	def test_under_a_record_on_hand_hold_it_is_born_pending_too(self):
		_out, child, _f = self.create(**self.released(quality_status="Hold", status_source="Hold action"))
		self.assertEqual(child.inserted, PENDING_NO_CERTIFICATE)
		(row,) = child.rows
		self.assertIn("created after approval of COA AMB2 CERT-1", row["comments"])
		# a hold with no certificate behind it: no certificate was approved, no row
		_out, child, _f = self.create(quality_status="Hold", status_source="Hold action")
		self.assertEqual(child.inserted, PENDING_NO_CERTIFICATE)
		self.assertEqual(child.rows, [])

	def test_a_child_that_cannot_carry_its_history_row_is_not_created_and_the_user_is_told_why(self):
		parent = self.released(current_plant2=None)
		out, child, _f = self.create(**parent)
		self.assertFalse(out["success"])
		self.assertIsNone(child.inserted)
		# the fake throw raises with no text; the message is what frappe.throw was given
		self.assertIn("Current Plant", _f.throw.call_args.args[0])


if __name__ == "__main__":
	unittest.main()
