# TASKS-390, decision 338 (amb_w_spc's half), DB-free: when more than one certificate stands for a record, the
# record takes the worst verdict, Failed over Hold over Passed.
#
#   * approval: `certificate_approved(..., others=[{"doctype", "name", "result"}, ...])` = the OTHER certificates
#     still standing for the same record (amb_w_tds computes them); a worse one holds the status: `released_by*`
#     name it, the history row says it holds it, the records below inherit from it; on a tie the approved one
#   * withdrawal: `certificate_withdrawn(..., standing=[...])` (a list; a single dict as before) -> the worst of the
#     certificates still standing, from the one that has it
#   * the hand hold rule and a record's own certificate below are unchanged; descendants follow as now
#   * `others=None` / `[]` and a single-dict `standing` behave exactly as before TASKS-390
#
# Run: python -m unittest amb_w_spc.tests.test_worst_result_wins   (no site needed)

import unittest

from amb_w_spc.sfc_manufacturing import lot_quality as lq
from amb_w_spc.tests.test_lot_quality import CUSTOMER, INTERNAL, Refused, Table, rec, site


def tree(*changed):
	"""L (lot) > S1 (sub-lot) > C1 (container), plus S2 with a certificate of its own (CERT-S2, Passed)."""
	records = {
		r["name"]: r
		for r in (
			rec("L"),
			rec("S1", "2", "L"),
			rec("C1", "3", "S1"),
			rec("S2", "2", "L", status="Passed", source="Own certificate", cert="CERT-S2"),
			rec("C2", "3", "S2", status="Passed", source="Inherited", cert="CERT-S2"),
		)
	}
	for r in changed:
		records[r["name"]] = r
	return Table(*records.values())


def cert(name, result, doctype=INTERNAL):
	return {"doctype": doctype, "name": name, "result": result}


def approve(t, name, result, others=None, lot="L", doctype=INTERNAL):
	with site(t):
		if others is None:
			return lq.certificate_approved(doctype, name, lot, result)
		return lq.certificate_approved(doctype, name, lot, result, others=others)


def withdraw(t, name, standing=None, lot="L", doctype=INTERNAL):
	with site(t):
		return lq.certificate_withdrawn(doctype, name, lot, standing)


class TestApproval(unittest.TestCase):
	def test_fail_then_pass_stays_failed(self):
		t = tree()
		approve(t, "CERT-F", "Fail")
		approve(t, "CERT-P", "Pass", others=[cert("CERT-F", "Fail")])
		self.assertEqual(t.state("L"), ("Failed", "Own certificate", "CERT-F", "Failed"))
		self.assertEqual(t.rows["L"]["released_by_doctype"], INTERNAL)
		# the records below follow the record above, as now
		for name in ("S1", "C1"):
			self.assertEqual(t.state(name), ("Failed", "Inherited", "CERT-F", "Failed"), name)
		# the history row of this approval says which certificate holds the status
		row = t.rows_of("L")[-1]
		self.assertIn("certificate COA AMB2 CERT-P approved with result Pass", row.reason)
		self.assertIn(
			"COA AMB2 CERT-F (result Fail) still stands for this record and holds the status Failed",
			row.reason,
		)
		self.assertIn("worst result wins", row.reason)
		# the link field names the certificate approved for the record (unchanged rule)
		self.assertEqual(t.rows["L"]["coa_amb2"], "CERT-P")

	def test_pass_then_fail_is_failed(self):
		t = tree()
		approve(t, "CERT-P", "Pass")
		approve(t, "CERT-F", "Fail", others=[cert("CERT-P", "Pass")])
		self.assertEqual(t.state("L"), ("Failed", "Own certificate", "CERT-F", "Failed"))
		for name in ("S1", "C1"):
			self.assertEqual(t.state(name), ("Failed", "Inherited", "CERT-F", "Failed"), name)
		self.assertNotIn("still stands", t.rows_of("L")[-1].reason)  # it holds the status itself

	def test_the_order_failed_hold_passed(self):
		for result, others, holder, status in (
			("Pass", [cert("CERT-H", "Partial")], "CERT-H", "Hold"),
			("Partial", [cert("CERT-P", "Pass")], "CERT-X", "Hold"),
			("Partial", [cert("CERT-F", "Fail")], "CERT-F", "Failed"),
			(
				"Pass",
				[cert("CERT-P", "Pass"), cert("CERT-H", "Partial"), cert("CERT-F", "Fail")],
				"CERT-F",
				"Failed",
			),
			("Pass", [cert("CERT-H", "Partial"), cert("CERT-H2", "Partial")], "CERT-H", "Hold"),
		):
			with self.subTest(result=result, others=others):
				t = tree()
				approve(t, "CERT-X", result, others=others)
				self.assertEqual(t.state("L"), (status, "Own certificate", holder, status))

	def test_a_tie_goes_to_the_certificate_approved(self):
		t = tree()
		approve(t, "CERT-F1", "Fail")
		approve(t, "CERT-F2", "Fail", others=[cert("CERT-F1", "Fail")])
		self.assertEqual(t.state("L"), ("Failed", "Own certificate", "CERT-F2", "Failed"))

	def test_a_worse_certificate_of_the_other_type_holds_it_with_its_type(self):
		t = tree()
		approve(t, "CERT-P", "Pass", others=[cert("CUST-F", "Fail", CUSTOMER)])
		self.assertEqual(t.state("L"), ("Failed", "Own certificate", "CUST-F", "Failed"))
		self.assertEqual(t.rows["L"]["released_by_doctype"], CUSTOMER)
		self.assertEqual(t.rows["C1"]["released_by_doctype"], CUSTOMER)

	def test_a_sub_lot_with_its_own_certificate_is_left_alone_as_now(self):
		t = tree()
		approve(t, "CERT-P", "Pass", others=[cert("CERT-F", "Fail")])
		self.assertEqual(t.state("S2"), ("Passed", "Own certificate", "CERT-S2", "Passed"))
		self.assertEqual(t.state("C2"), ("Passed", "Inherited", "CERT-S2", "Passed"))

	def test_a_hand_hold_keeps_hold_and_stores_the_worst_verdict(self):
		t = tree(rec("L", status="Hold", source="Hold action"))
		approve(t, "CERT-P", "Pass", others=[cert("CERT-F", "Fail")])
		self.assertEqual(t.state("L"), ("Hold", "Hold action", "CERT-F", "Failed"))
		self.assertEqual(t.state("S1"), ("Failed", "Inherited", "CERT-F", "Failed"))

	def test_no_others_or_an_empty_list_is_the_behaviour_before(self):
		results = []
		for others in (None, []):
			t = tree()
			approve(t, "CERT-F", "Fail")
			approve(t, "CERT-P", "Pass", others=others)
			results.append(({n: t.state(n) for n in t.rows}, [h.reason for h in t.history]))
		self.assertEqual(results[0], results[1])
		states, reasons = results[0]
		self.assertEqual(
			states["L"], ("Passed", "Own certificate", "CERT-P", "Passed")
		)  # the last approval wins
		self.assertIn("certificate COA AMB2 CERT-P approved with result Pass", reasons)
		self.assertFalse([r for r in reasons if "still stands" in r])

	def test_others_naming_the_certificate_approved_or_without_a_mapping_or_a_name_are_refused(self):
		for others in (
			[cert("CERT-P", "Fail")],
			[cert("CERT-F", "No Tests")],
			[cert("CERT-F", None)],
			[{"doctype": INTERNAL, "name": "", "result": "Fail"}],
			[{"doctype": None, "name": "CERT-F", "result": "Fail"}],
		):
			with self.subTest(others=others):
				t = tree()
				with self.assertRaises(Refused):
					approve(t, "CERT-P", "Pass", others=others)
				self.assertEqual((t.history, t.column_writes), ([], []))  # nothing written

	def test_the_summary_says_what_the_record_took(self):
		t = tree()
		approve(t, "CERT-F", "Fail")
		with site(t) as f:
			lq.certificate_approved(INTERNAL, "CERT-P", "L", "Pass", others=[cert("CERT-F", "Fail")])
		(call,) = f.sendmail.call_args_list
		self.assertIn(
			"<li>L (level 1): Failed &rarr; Failed, source Own certificate, saved</li>",
			call.kwargs["message"],
		)


class TestWithdrawal(unittest.TestCase):
	def test_withdrawing_the_fail_with_the_pass_standing_is_passed_from_the_pass(self):
		t = tree()
		approve(t, "CERT-P", "Pass")
		approve(t, "CERT-F", "Fail", others=[cert("CERT-P", "Pass")])
		withdraw(t, "CERT-F", standing=[cert("CERT-P", "Pass")])
		self.assertEqual(t.state("L"), ("Passed", "Own certificate", "CERT-P", "Passed"))
		for name in ("S1", "C1"):
			self.assertEqual(t.state(name), ("Passed", "Inherited", "CERT-P", "Passed"), name)
		self.assertEqual(t.rows["L"]["coa_amb2"], "CERT-P")  # the link follows the certificate that stands

	def test_a_single_dict_standing_still_works_as_before(self):
		states = []
		for standing in (cert("CERT-P", "Pass"), [cert("CERT-P", "Pass")]):
			t = tree()
			approve(t, "CERT-F", "Fail")
			withdraw(t, "CERT-F", standing=standing)
			states.append(({n: t.state(n) for n in t.rows}, t.rows_of("L")[-1].reason))
		self.assertEqual(states[0], states[1])
		self.assertEqual(states[0][0]["L"], ("Passed", "Own certificate", "CERT-P", "Passed"))
		self.assertEqual(
			states[0][1],
			"certificate COA AMB2 CERT-F withdrawn; COA AMB2 CERT-P still stands with result Pass",
		)

	def test_the_worst_of_those_still_standing_wins_and_the_row_says_so(self):
		t = tree()
		approve(t, "CERT-X", "Fail")
		withdraw(
			t, "CERT-X", standing=[cert("CERT-P", "Pass"), cert("CERT-H", "Partial"), cert("CERT-P2", "Pass")]
		)
		self.assertEqual(t.state("L"), ("Hold", "Own certificate", "CERT-H", "Hold"))
		self.assertEqual(t.state("C1"), ("Hold", "Inherited", "CERT-H", "Hold"))
		reason = t.rows_of("L")[-1].reason
		self.assertIn("COA AMB2 CERT-H still stands with result Partial", reason)
		self.assertIn("the worst of the 3 certificates still standing", reason)
		self.assertEqual(t.rows["L"]["coa_amb2"], "CERT-H")

	def test_the_link_takes_a_standing_certificate_of_its_own_type(self):
		t = tree()
		approve(t, "CERT-X", "Pass")
		withdraw(t, "CERT-X", standing=[cert("CERT-P", "Pass"), cert("CUST-F", "Fail", CUSTOMER)])
		self.assertEqual(t.state("L"), ("Failed", "Own certificate", "CUST-F", "Failed"))
		self.assertEqual(t.rows["L"]["coa_amb2"], "CERT-P")  # coa_amb2 links COA AMB2 only

	def test_an_empty_list_is_no_standing_certificate(self):
		t = tree()
		approve(t, "CERT-X", "Pass")
		withdraw(t, "CERT-X", standing=[])
		self.assertEqual(t.state("L"), ("Pending", "", None, None))

	def test_a_standing_list_naming_the_withdrawn_certificate_or_unmapped_is_refused(self):
		for standing in ([cert("CERT-P", "Pass"), cert("CERT-X", "Pass")], [cert("CERT-P", "No Tests")]):
			with self.subTest(standing=standing):
				t = tree()
				approve(t, "CERT-X", "Pass")
				before = len(t.history)
				with self.assertRaises(Refused):
					withdraw(t, "CERT-X", standing=standing)
				self.assertEqual(len(t.history), before)

	def test_a_hand_hold_keeps_hold_on_withdrawal_too(self):
		t = tree(rec("L", status="Hold", source="Hold action"))
		approve(t, "CERT-X", "Fail")
		withdraw(t, "CERT-X", standing=[cert("CERT-P", "Pass"), cert("CERT-H", "Partial")])
		self.assertEqual(t.state("L"), ("Hold", "Hold action", "CERT-H", "Hold"))
		self.assertEqual(t.state("S1"), ("Hold", "Inherited", "CERT-H", "Hold"))


if __name__ == "__main__":
	unittest.main()
