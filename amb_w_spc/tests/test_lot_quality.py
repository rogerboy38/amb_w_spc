# TASKS-384 B3, DB-free: a lot record's quality status is what its certificate says, written by one function.
#
#   * the vocabulary of lot_quality.py equals the option lists of the DocType JSON (and of amb_w_tds when importable)
#   * each certificate result sets the mapped status; a result without mapping is refused
#   * a withdrawn certificate returns the lot to Pending, or to the status of a certificate that still stands
#   * a lot on a hand hold is not released by an approval: it shows the verdict and takes it when the hold is lifted
#   * one history row per change, appended before the save, with who / when / from / to / certificate / reason
#   * the hand writers of the lot are gone
#   * the approval writes the lot's certificate link (coa_reference / coa_amb2) and the withdrawal takes it back
#
# The rules are run against an in-memory table (`Table`) through the module's data-access seam; the real seam
# (`lot_quality.LotTable`) is run against a fake frappe whose documents call the REAL guard when saved.
#
# Run: python -m unittest amb_w_spc.tests.test_lot_quality   (no site needed)

import ast
import contextlib
import importlib
import json
import pathlib
import types
import unittest
from unittest import mock

from amb_w_spc.sfc_manufacturing import lot_quality as lq
from amb_w_spc.sfc_manufacturing.doctype.batch_amb import batch_amb as bam

SFC = pathlib.Path(lq.__file__).resolve().parent
LOT_JSON = SFC / "doctype" / "batch_amb" / "batch_amb.json"
HISTORY_JSON = SFC / "doctype" / "batch_processing_history" / "batch_processing_history.json"
USER = "quality-approver"
INTERNAL, CUSTOMER = "COA AMB2", "COA AMB"


class Refused(Exception):
	pass


class NoOutgoingAccount(Exception):
	"""Stands in for `frappe.OutgoingEmailError` (which is not a ValidationError in Frappe 16.17.5)."""


def rec(
	name, level="1", parent=None, status="Pending", source=None, cert=None, says=None, cert_type=INTERNAL
):
	"""One lot record. `cert` = the certificate its status comes from; `says` = what that certificate says
	(default: the status)."""
	return {
		"name": name,
		"custom_batch_level": level,
		"parent_batch_amb": parent,
		"quality_status": status,
		"status_source": source,
		"released_by_doctype": cert_type if cert else None,
		"released_by": cert,
		"certificate_status": (says or status) if cert else None,
	}


class Table:
	"""The lot table in memory: the five things the module asks of it (get, children, released_by, save,
	write_columns), and a record of what was read and written."""

	acting_on = None

	def __init__(self, *records):
		self.rows = {r["name"]: dict(r) for r in records}
		self.history = []  # one entry per saved change: (lot, before, after, reason, note)
		self.column_writes = []  # direct column writes: (names, values)
		self.reads = []  # every read: ("get", name) or ("children", [names])
		# as LotTable: {record: name of the history row its first save wrote}; `_add_to_row` writes into it
		self.written_rows = {}

	def get(self, name):
		self.reads.append(("get", name))
		row = self.rows.get(name)
		return dict(row) if row else None

	def children(self, names):
		names = list(names)
		self.reads.append(("children", names))
		return [dict(r) for _n, r in sorted(self.rows.items()) if r["parent_batch_amb"] in names]

	def released_by(self, certificate_doctype, certificate):
		self.reads.append(("released_by", (certificate_doctype, certificate)))
		return [
			dict(r)
			for _n, r in sorted(self.rows.items())
			if (r.get("released_by_doctype"), r.get("released_by")) == (certificate_doctype, certificate)
		]

	def write_columns(self, names, values):
		assert set(values) <= set(lq.GUARDED_FIELDS), values
		self.column_writes.append((list(names), dict(values)))
		for name in names:
			self.rows[name].update(values)

	def save(self, name, values, reason=None, note=None, always=False):
		assert set(values) <= {*lq.GUARDED_FIELDS, *lq.LINK_FIELDS}, values
		before = {f: self.rows[name].get(f) for f in (*lq.GUARDED_FIELDS, *values)}
		after = lq._after(before, values)
		if after is None:
			if not always:
				return False
			after = dict(before)
		self.rows[name].update(values)
		row = f"ROW-{len(self.history) + 1}"
		self.history.append(
			types.SimpleNamespace(
				lot=name, before=before, after=after, reason=reason, note=note, row=row, added=[]
			)
		)
		self.written_rows.setdefault(name, row)
		return True

	def _add_to_row(self, row_name, text):
		(entry,) = [h for h in self.history if h.row == row_name]
		entry.added.append(text)

	# what a test reads
	def state(self, name):
		r = self.rows[name]
		return (
			r["quality_status"] or "Pending",
			r["status_source"] or "",
			r["released_by"],
			r["certificate_status"],
		)

	def rows_of(self, name):
		return [h for h in self.history if h.lot == name]


def fake_frappe():
	f = mock.MagicMock(name="frappe")
	f.throw.side_effect = Refused
	f.ValidationError = Refused
	f.session.user = USER
	f.utils.nowdate.return_value = "2026-11-26"
	f.utils.now.return_value = "2026-11-26 10:00:00.000000"
	f.OutgoingEmailError = NoOutgoingAccount
	f.utils.validate_email_address.side_effect = lambda email, throw=False: email  # test tokens are valid
	f.local.message_log = []
	return f


@contextlib.contextmanager
def site(table=None, frappe=None):
	"""The module with a fake frappe and, when given, the in-memory table behind its public functions."""
	f = frappe or fake_frappe()
	with contextlib.ExitStack() as stack:
		stack.enter_context(mock.patch.object(lq, "frappe", f))
		stack.enter_context(mock.patch.object(lq, "_", lambda s: s))
		if table is not None:
			stack.enter_context(mock.patch.object(lq, "LotTable", lambda: table))
		yield f


def options(path, fieldname):
	(f,) = [f for f in json.loads(path.read_text(encoding="utf-8"))["fields"] if f["fieldname"] == fieldname]
	return f


# ----------------------------------------------------------------------------------------------------------------
class TestVocabulary(unittest.TestCase):
	def test_the_lot_statuses_are_the_options_of_quality_status_in_this_order(self):
		self.assertEqual(options(LOT_JSON, "quality_status")["options"].split("\n"), list(lq.LOT_STATUSES))
		self.assertEqual(list(lq.LOT_STATUSES), ["Pending", "Passed", "Failed", "Hold"])

	def test_certificate_status_offers_empty_and_the_lot_statuses(self):
		self.assertEqual(
			options(LOT_JSON, "certificate_status")["options"].split("\n"), ["", *lq.LOT_STATUSES]
		)

	def test_the_status_sources_are_the_options_of_status_source(self):
		self.assertEqual(options(LOT_JSON, "status_source")["options"].split("\n"), list(lq.STATUS_SOURCES))
		self.assertEqual(list(lq.STATUS_SOURCES), ["", "Own certificate", "Inherited", "Hold action"])
		self.assertEqual(
			(lq.OWN_CERTIFICATE, lq.INHERITED, lq.HOLD_ACTION),
			("Own certificate", "Inherited", "Hold action"),
		)

	def test_the_map_is_decision_303_and_stays_inside_the_two_lists(self):
		self.assertEqual(lq.RESULT_TO_LOT_STATUS, {"Pass": "Passed", "Fail": "Failed", "Partial": "Hold"})
		self.assertEqual(list(lq.CERTIFICATE_RESULTS), ["Pending", "Pass", "Fail", "Partial", "No Tests"])
		self.assertLessEqual(set(lq.RESULT_TO_LOT_STATUS), set(lq.CERTIFICATE_RESULTS))
		self.assertLessEqual(set(lq.RESULT_TO_LOT_STATUS.values()), set(lq.LOT_STATUSES))
		self.assertNotIn("No Tests", lq.RESULT_TO_LOT_STATUS)
		self.assertNotIn("Pending", lq.RESULT_TO_LOT_STATUS)

	def test_the_same_vocabulary_as_the_certificates_app(self):
		try:
			tds = importlib.import_module("amb_w_tds.quality_vocabulary")
		except ImportError:
			self.skipTest("amb_w_tds.quality_vocabulary is not importable here")
		for name in ("LOT_STATUSES", "CERTIFICATE_RESULTS", "STATUS_SOURCES"):
			self.assertEqual(list(getattr(tds, name)), list(getattr(lq, name)), name)
		self.assertEqual(dict(tds.RESULT_TO_LOT_STATUS), dict(lq.RESULT_TO_LOT_STATUS))

	def test_the_history_action_is_an_option_of_the_history_table(self):
		self.assertIn(lq.HISTORY_ACTION, options(HISTORY_JSON, "processing_action")["options"].split("\n"))
		self.assertEqual(options(LOT_JSON, lq.HISTORY_TABLE)["options"], "Batch Processing History")


class TestFields(unittest.TestCase):
	def test_the_status_is_read_only_on_the_form_and_not_copied(self):
		f = options(LOT_JSON, "quality_status")
		self.assertEqual((f["read_only"], f["no_copy"]), (1, 1))

	def test_the_four_fields_that_say_where_the_status_came_from(self):
		want = {
			"certificate_status": ("Select", None),
			"status_source": ("Select", None),
			"released_by_doctype": ("Link", "DocType"),
			"released_by": ("Dynamic Link", "released_by_doctype"),
		}
		for fieldname, (fieldtype, opts) in want.items():
			f = options(LOT_JSON, fieldname)
			self.assertEqual(f["fieldtype"], fieldtype, fieldname)
			if opts:
				self.assertEqual(f["options"], opts, fieldname)
			self.assertEqual((f["read_only"], f["no_copy"], f["reqd"]), (1, 1, 0), fieldname)
		self.assertEqual(set(lq.GUARDED_FIELDS), {"quality_status", *want})

	def test_every_field_has_a_position_of_its_own(self):
		fields = json.loads(LOT_JSON.read_text(encoding="utf-8"))["fields"]
		idx = [f["idx"] for f in fields if f.get("idx")]
		self.assertEqual(len(idx), len(set(idx)))
		names = [f["fieldname"] for f in fields]
		self.assertEqual(len(names), len(set(names)))


# ----------------------------------------------------------------------------------------------------------------
class TestApproved(unittest.TestCase):
	def test_each_result_of_each_certificate_type_sets_the_mapped_status(self):
		for cert_type in (INTERNAL, CUSTOMER):
			for result, status in (("Pass", "Passed"), ("Fail", "Failed"), ("Partial", "Hold")):
				for level in ("1", "2"):
					t = Table(rec("L", level))
					with site(t):
						lq.certificate_approved(cert_type, "CERT-1", "L", result)
					self.assertEqual(
						t.state("L"), (status, "Own certificate", "CERT-1", status), (cert_type, result)
					)
					self.assertEqual(t.rows["L"]["released_by_doctype"], cert_type)

	def test_a_result_without_mapping_is_refused_and_nothing_is_written(self):
		for result in ("No Tests", "Pending", None, "", "Passed", "pass"):
			t = Table(rec("L"))
			with site(t), self.assertRaises(Refused):
				lq.certificate_approved(INTERNAL, "CERT-1", "L", result)
			self.assertEqual((t.state("L"), t.history), (("Pending", "", None, None), []), result)

	def test_the_refusal_names_the_result(self):
		with site(Table(rec("L"))) as f, self.assertRaises(Refused):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "No Tests")
		self.assertIn("No Tests", f.throw.call_args.args[0])

	def test_a_lot_that_does_not_exist_is_refused(self):
		for lot in ("NOPE", None, ""):
			with site(Table(rec("L"))), self.assertRaises(Refused):
				lq.certificate_approved(INTERNAL, "CERT-1", lot, "Pass")

	def test_a_certificate_must_be_named_with_its_type(self):
		for cert_type, cert in ((None, "CERT-1"), (INTERNAL, None), ("", "")):
			t = Table(rec("L"))
			with site(t), self.assertRaises(Refused):
				lq.certificate_approved(cert_type, cert, "L", "Pass")
			self.assertEqual(t.history, [])

	def test_a_container_is_not_released_by_a_certificate_of_its_own(self):
		for level in ("3", "4"):
			t = Table(rec("S", "2"), rec("C", level, "S"))
			with site(t), self.assertRaises(Refused):
				lq.certificate_approved(INTERNAL, "CERT-1", "C", "Pass")
			self.assertEqual(t.state("C"), ("Pending", "", None, None))

	def test_a_later_certificate_of_the_same_lot_replaces_the_earlier_one(self):
		t = Table(rec("L"))
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Fail")
			lq.certificate_approved(CUSTOMER, "CERT-2", "L", "Pass")
		self.assertEqual(t.state("L"), ("Passed", "Own certificate", "CERT-2", "Passed"))
		self.assertEqual(t.rows["L"]["released_by_doctype"], CUSTOMER)


class TestWithdrawn(unittest.TestCase):
	def test_reject_returns_the_lot_to_pending_with_no_certificate(self):
		for status in ("Passed", "Failed", "Hold"):
			t = Table(rec("L", status=status, source="Own certificate", cert="CERT-1"))
			with site(t):
				lq.certificate_withdrawn(INTERNAL, "CERT-1", "L")
			self.assertEqual(t.state("L"), ("Pending", "", None, None), status)
			self.assertIsNone(t.rows["L"]["released_by_doctype"])

	def test_with_a_certificate_that_still_stands_the_lot_takes_that_ones_status(self):
		for result, status in (("Pass", "Passed"), ("Fail", "Failed"), ("Partial", "Hold")):
			t = Table(rec("L", status="Passed", source="Own certificate", cert="CERT-1", cert_type=CUSTOMER))
			with site(t):
				lq.certificate_withdrawn(
					CUSTOMER,
					"CERT-1",
					"L",
					standing={"doctype": INTERNAL, "name": "CERT-0", "result": result},
				)
			self.assertEqual(t.state("L"), (status, "Own certificate", "CERT-0", status), result)
			self.assertEqual(t.rows["L"]["released_by_doctype"], INTERNAL)

	def test_a_standing_certificate_without_a_mapped_result_is_refused(self):
		t = Table(rec("L", status="Passed", source="Own certificate", cert="CERT-1"))
		with site(t), self.assertRaises(Refused):
			lq.certificate_withdrawn(
				INTERNAL,
				"CERT-1",
				"L",
				standing={"doctype": CUSTOMER, "name": "CERT-0", "result": "No Tests"},
			)
		self.assertEqual(t.state("L"), ("Passed", "Own certificate", "CERT-1", "Passed"))

	def test_the_standing_certificate_cannot_be_the_withdrawn_one(self):
		t = Table(rec("L", status="Passed", source="Own certificate", cert="CERT-1"))
		with site(t), self.assertRaises(Refused):
			lq.certificate_withdrawn(
				INTERNAL, "CERT-1", "L", standing={"doctype": INTERNAL, "name": "CERT-1", "result": "Pass"}
			)

	def test_a_certificate_that_did_not_write_the_lot_takes_nothing_back(self):
		# the lot is released by CERT-2; CERT-1 (replaced earlier, or never applied) is rejected
		t = Table(rec("L", status="Passed", source="Own certificate", cert="CERT-2"))
		with site(t):
			lq.certificate_withdrawn(INTERNAL, "CERT-1", "L")
			lq.certificate_withdrawn(CUSTOMER, "CERT-2", "L")  # same name, the other certificate type
		self.assertEqual(t.state("L"), ("Passed", "Own certificate", "CERT-2", "Passed"))
		self.assertEqual(t.history, [])
		# a record nobody's certificate wrote (status from before this rule) is left as it is too
		t = Table(rec("L", status="Passed"))
		with site(t):
			lq.certificate_withdrawn(INTERNAL, "CERT-1", "L")
		self.assertEqual((t.state("L"), t.history), (("Passed", "", None, None), []))


class TestHandHold(unittest.TestCase):
	def held(self, **kw):
		return rec("L", status="Hold", source="Hold action", **kw)

	def test_an_approval_does_not_release_a_lot_on_hand_hold_and_the_verdict_is_shown(self):
		for result, verdict in (("Pass", "Passed"), ("Fail", "Failed"), ("Partial", "Hold")):
			t = Table(self.held())
			with site(t):
				lq.certificate_approved(INTERNAL, "CERT-1", "L", result)
			self.assertEqual(t.state("L"), ("Hold", "Hold action", "CERT-1", verdict), result)
			self.assertEqual(len(t.history), 1)  # the stored verdict leaves a row too

	def test_the_lot_takes_the_verdict_when_the_hold_is_lifted(self):
		t = Table(self.held())
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
			lq.lift_hand_hold("L", "deviation closed")
		self.assertEqual(t.state("L"), ("Passed", "Own certificate", "CERT-1", "Passed"))
		self.assertIn("deviation closed", t.history[-1].reason)

	def test_a_hold_lifted_with_no_certificate_returns_pending(self):
		t = Table(self.held())
		with site(t):
			lq.lift_hand_hold("L", "checked")
		self.assertEqual(t.state("L"), ("Pending", "", None, None))

	def test_a_withdrawal_under_a_hold_keeps_the_hold_and_forgets_the_verdict(self):
		t = Table(self.held(cert="CERT-1", says="Passed"))
		with site(t):
			lq.certificate_withdrawn(INTERNAL, "CERT-1", "L")
			self.assertEqual(t.state("L"), ("Hold", "Hold action", None, None))
			lq.lift_hand_hold("L", "checked")
		self.assertEqual(t.state("L"), ("Pending", "", None, None))

	def test_a_held_record_that_follows_the_lot_above_it_is_inherited_again_when_lifted(self):
		t = Table(
			rec("L", status="Failed", source="Own certificate", cert="CERT-1"),
			rec("S", "2", "L", status="Hold", source="Hold action", cert="CERT-1", says="Failed"),
		)
		with site(t):
			lq.lift_hand_hold("S", "checked")
		self.assertEqual(t.state("S"), ("Failed", "Inherited", "CERT-1", "Failed"))

	def test_a_held_record_with_a_certificate_of_its_own_is_own_certificate_again_when_lifted(self):
		t = Table(
			rec("L", status="Passed", source="Own certificate", cert="CERT-1"),
			rec("S", "2", "L", status="Hold", source="Hold action", cert="CERT-9", says="Failed"),
		)
		with site(t):
			lq.lift_hand_hold("S", "checked")
		self.assertEqual(t.state("S"), ("Failed", "Own certificate", "CERT-9", "Failed"))

	def test_lifting_needs_a_hold_and_a_reason(self):
		t = Table(
			rec("L", status="Hold", source="Own certificate", cert="CERT-1"), self.held() | {"name": "H"}
		)
		with site(t):
			with self.assertRaises(Refused):
				lq.lift_hand_hold("L", "a Hold that a Partial certificate set is not a hand hold")
			for reason in (None, ""):
				with self.assertRaises(Refused):
					lq.lift_hand_hold("H", reason)
			with self.assertRaises(Refused):
				lq.lift_hand_hold("NOPE", "x")
		self.assertEqual(t.history, [])

	def test_the_writer_places_a_hold_and_keeps_what_the_certificate_says(self):
		t = Table(rec("L", status="Passed", source="Own certificate", cert="CERT-1"))
		with site(t):
			lq.set_lot_quality_status("L", "Hold", reason="foreign matter found", source="Hold action")
			self.assertEqual(t.state("L"), ("Hold", "Hold action", "CERT-1", "Passed"))
			for bad in (
				dict(status="Passed", reason="x", source="Hold action"),  # a hold is Hold
				dict(status="Hold", source="Hold action"),  # a hold has a reason
				dict(
					status="Hold",
					reason="x",
					source="Hold action",
					certificate="C",
					certificate_doctype=INTERNAL,
				),
			):
				with self.assertRaises(Refused):
					lq.set_lot_quality_status("L", **bad)
		self.assertEqual(len(t.history), 1)


class TestTheWriter(unittest.TestCase):
	def test_one_history_row_per_change_and_none_when_nothing_changes(self):
		t = Table(rec("L"))
		with site(t):
			self.assertTrue(lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass"))
			self.assertEqual(len(t.history), 1)
			self.assertFalse(lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass"))  # the same again
			self.assertEqual(len(t.history), 1)
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Fail")  # the same certificate, another verdict
			self.assertEqual(len(t.history), 2)
			lq.certificate_withdrawn(INTERNAL, "CERT-1", "L")
			self.assertEqual(len(t.history), 3)
		self.assertEqual(
			[(h.before["quality_status"], h.after["quality_status"]) for h in t.history],
			[("Pending", "Passed"), ("Passed", "Failed"), ("Failed", "Pending")],
		)
		self.assertIn("CERT-1", t.history[0].reason)

	def test_what_the_writer_refuses(self):
		t = Table(rec("L"))
		with site(t):
			for bad in (
				dict(status="Approved"),  # not a lot status
				dict(status="Passed"),  # no certificate: only Pending
				dict(status="Failed", source=""),
				dict(status="Passed", certificate="CERT-1"),  # a certificate without its type
				dict(
					status="Passed", certificate_doctype=INTERNAL, source="Inherited"
				),  # ... or a type without it
				dict(status="Pending", certificate="CERT-1", certificate_doctype=INTERNAL, source=""),
				dict(status="Passed", certificate="CERT-1", certificate_doctype=INTERNAL, source="By hand"),
			):
				with self.assertRaises(Refused, msg=bad):
					lq.set_lot_quality_status("L", **bad)
			with self.assertRaises(Refused):
				lq.set_lot_quality_status("NOPE", "Pending")
		self.assertEqual((t.state("L"), t.history), (("Pending", "", None, None), []))

	def test_the_contract_signature(self):
		t = Table(rec("L"))
		with site(t):
			# positional, in the order of the contract: lot, status, certificate, reason, certificate_doctype, source
			lq.set_lot_quality_status("L", "Passed", "CERT-1", "because", INTERNAL, "Inherited")
		self.assertEqual(t.state("L"), ("Passed", "Inherited", "CERT-1", "Passed"))
		self.assertEqual((t.rows["L"]["released_by_doctype"], t.history[0].reason), (INTERNAL, "because"))


# ----------------------------------------------------------------------------------------------------------------
# the real seam against a fake frappe whose documents run the REAL guard, both lines, when saved
# ----------------------------------------------------------------------------------------------------------------
class LotDoc:
	def __init__(self, db, name):
		self.db, self.name = db, name
		self.fields = dict(db.rows[name])
		self.flags = {}
		self.appended = []
		self.fail = None

	def get(self, key, default=None):
		return self.fields.get(key, default)

	def set(self, key, value):
		self.fields[key] = value

	def append(self, table, row):
		self.appended.append((table, row))

	def get_doc_before_save(self):
		return types.SimpleNamespace(get=lambda k, d=None: self.db.rows[self.name].get(k, d))

	def save(self, **kwargs):
		self.db.log.append(("save", self.name, kwargs, self.flags.get(lq.WRITER_FLAG), list(self.appended)))
		lq.refuse_hand_change(self, "before_validate")
		if self.fail:
			raise self.fail
		lq.refuse_hand_change(self, "on_update")
		self.db.rows[self.name] = dict(self.fields)
		self.db.history.setdefault(self.name, []).extend(row for _table, row in self.appended)


class Db:
	def __init__(self, *records, plant="1 (Mix)", item="0227"):
		self.rows = {r["name"]: dict(r, current_plant2=plant, current_item_code=item) for r in records}
		self.history, self.log, self.docs = {}, [], []
		# what the release summary reads (TASKS-387 item 4): {(certificate type, name): {field: value}},
		# {Work Order: {field: value}}, {user: {"enabled", "email"}}; empty: nobody to tell, no mail
		self.certificates, self.work_orders, self.users = {}, {}, {}

	def frappe(self):
		f = fake_frappe()

		def get_value(dt, name, fields, as_dict=False):
			if dt == "Batch AMB":
				source = self.rows.get(name)
			elif dt == "Work Order":
				source = self.work_orders.get(name)
			elif dt == "User":
				source = self.users.get(name)
			else:
				source = self.certificates.get((dt, name))
			if source is None:
				return None
			if isinstance(fields, str):
				return source.get(fields)
			return {k: source.get(k) for k in fields}

		f.db.get_value.side_effect = get_value

		def get_doc(doctype, name):
			assert doctype == "Batch AMB"
			self.docs.append(LotDoc(self, name))
			return self.docs[-1]

		f.get_doc.side_effect = get_doc

		def get_all(doctype, filters=None, fields=None, **kwargs):
			assert doctype == "Batch AMB"
			self.log.append(("get_all", filters, fields, kwargs))
			if "released_by" in filters:  # LotTable.released_by: the records a certificate speaks for
				assert set(filters) == {"released_by_doctype", "released_by"}, filters
				wanted = (filters["released_by_doctype"], filters["released_by"])
				return [
					{k: r.get(k) for k in fields}
					for _n, r in sorted(self.rows.items())
					if (r.get("released_by_doctype"), r.get("released_by")) == wanted
				]
			(op, names) = filters["parent_batch_amb"]
			assert op == "in"
			return [
				{k: r.get(k) for k in fields}
				for _n, r in sorted(self.rows.items())
				if r["parent_batch_amb"] in names
			]

		def set_value(doctype, filters, values):
			assert doctype == "Batch AMB"
			self.log.append(("set_value", filters, dict(values)))
			(op, names) = filters["name"]
			assert op == "in"
			for name in names:
				self.rows[name].update(values)

		f.get_all.side_effect = get_all
		f.db.set_value.side_effect = set_value
		return f

	def saves(self):
		return [entry for entry in self.log if entry[0] == "save"]


class TestTheRealSave(unittest.TestCase):
	def test_the_row_is_appended_before_the_save_and_the_save_passes_the_real_guard(self):
		db = Db(rec("L"))
		with site(frappe=db.frappe()):
			self.assertTrue(lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass"))
		((_save, name, kwargs, flag, appended),) = db.saves()
		self.assertEqual(name, "L")
		self.assertIs(flag, lq._WRITER)  # the flag is up during the save ...
		self.assertEqual(db.docs[-1].flags, {})  # ... and down after it
		self.assertEqual(len(appended), 1)  # ONE row, already on the document when save() starts
		self.assertEqual(kwargs, {"ignore_permissions": True})
		row = db.rows["L"]
		self.assertEqual(
			[row[f] for f in lq.GUARDED_FIELDS], ["Passed", "Own certificate", INTERNAL, "CERT-1", "Passed"]
		)

	def test_the_history_row_says_who_when_from_to_which_certificate_and_why(self):
		db = Db(rec("L"))
		with site(frappe=db.frappe()):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
		((table, row),) = db.docs[-1].appended
		self.assertEqual(table, "processing_history")
		self.assertEqual(
			{k: row[k] for k in ("date", "plant", "item_code", "quality_status", "processing_action")},
			{
				"date": "2026-11-26",
				"plant": "1 (Mix)",
				"item_code": "0227",
				"quality_status": "Passed",
				"processing_action": "Quality Status Changed",
			},
		)
		self.assertEqual((row["changed_by"], row["system_generated"], row["batch_reference"]), (USER, 1, "L"))
		for needle in (
			"from Pending to Passed",
			"source: from none to Own certificate",
			"certificate: from none to COA AMB2 CERT-1 (says Passed)",
			"approved with result Pass",
			f"by {USER} at 2026-11-26 10:00:00",
		):
			self.assertIn(needle, row["comments"])
		# the fields declared too short for a status or that link to the other certificate type stay empty
		for fieldname in ("previous_value", "new_value", "coa_reference"):
			self.assertNotIn(fieldname, row)

	def test_every_mandatory_field_of_the_history_table_is_supplied(self):
		db = Db(rec("L"))
		with site(frappe=db.frappe()):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
		((_table, row),) = db.docs[-1].appended
		mandatory = [
			f["fieldname"]
			for f in json.loads(HISTORY_JSON.read_text(encoding="utf-8"))["fields"]
			if f.get("reqd")
		]
		self.assertEqual(
			sorted(mandatory), ["date", "item_code", "plant", "processing_action", "quality_status"]
		)
		for fieldname in mandatory:
			self.assertTrue(row.get(fieldname), fieldname)

	def test_a_lot_with_no_plant_or_no_item_is_refused_with_a_message_that_names_the_field(self):
		for plant, item, needle in ((None, "0227", "Current Plant"), ("1 (Mix)", None, "Current Item Code")):
			db = Db(rec("L"), plant=plant, item=item)
			with site(frappe=db.frappe()) as f, self.assertRaises(Refused):
				lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
			self.assertIn(needle, f.throw.call_args.args[0])
			self.assertIn("L", f.throw.call_args.args[0])
			self.assertEqual(db.saves(), [])  # no save was attempted: nothing invented, nothing written
			self.assertEqual(db.rows["L"]["quality_status"], "Pending")

	def test_the_item_to_manufacture_stands_in_for_an_empty_current_item(self):
		db = Db(rec("L"), item=None)
		db.rows["L"]["item_to_manufacture"] = "0301"
		with site(frappe=db.frappe()):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
		self.assertEqual(db.docs[-1].appended[0][1]["item_code"], "0301")

	def test_a_save_that_fails_stops_the_caller_and_takes_the_flag_down(self):
		db = Db(rec("L"))
		f = db.frappe()
		boom = RuntimeError("the lot cannot be saved")

		def get_doc(doctype, name):
			doc = LotDoc(db, name)
			doc.fail = boom
			db.docs.append(doc)
			return doc

		f.get_doc.side_effect = get_doc
		with site(frappe=f), self.assertRaises(RuntimeError) as caught:
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
		self.assertIs(caught.exception, boom)  # not swallowed, not wrapped
		self.assertEqual(db.docs[-1].flags, {})
		self.assertEqual(db.rows["L"]["quality_status"], "Pending")

	def test_nothing_to_change_means_no_save_and_no_row(self):
		db = Db(dict(rec("L", status="Passed", source="Own certificate", cert="CERT-1"), coa_amb2="CERT-1"))
		with site(frappe=db.frappe()):
			self.assertFalse(lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass"))
		self.assertEqual((db.saves(), db.docs[-1].appended), ([], []))

	def test_the_same_document_saved_again_by_someone_else_is_judged_by_the_guard(self):
		# the flag does not outlive the writer's save: a later change on the same object is a hand change
		db = Db(rec("L"))
		with site(frappe=db.frappe()):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
			doc = db.docs[-1]
			doc.set("quality_status", "Failed")
			with self.assertRaises(Refused):
				doc.save()

	def test_a_hold_in_force_is_said_in_the_row(self):
		db = Db(rec("L", status="Hold", source="Hold action"))
		with site(frappe=db.frappe()):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
		row = db.docs[-1].appended[0][1]
		self.assertEqual(row["quality_status"], "Hold")
		self.assertIn("hand hold in force", row["comments"])
		self.assertIn("(says Passed)", row["comments"])


# ----------------------------------------------------------------------------------------------------------------
class TestTheHandWritersAreGone(unittest.TestCase):
	def setUp(self):
		self.tree = ast.parse(pathlib.Path(bam.__file__).read_text(encoding="utf-8"))

	def functions(self):
		return {n.name: n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)}

	def test_approve_quality_and_reject_quality_are_removed_from_the_lot(self):
		for name in ("approve_quality", "reject_quality"):
			self.assertFalse(hasattr(bam.BatchAMB, name), name)
			self.assertNotIn(name, self.functions())

	def test_nothing_in_the_lot_controller_assigns_the_status_or_where_it_came_from(self):
		writers = {}
		for name, fn in self.functions().items():
			for node in ast.walk(fn):
				targets = []
				if isinstance(node, ast.Assign):
					targets = node.targets
				elif isinstance(node, ast.AugAssign | ast.AnnAssign):
					targets = [node.target]
				for t in targets:
					if isinstance(t, ast.Attribute) and t.attr in lq.GUARDED_FIELDS:
						writers.setdefault(name, []).append(ast.unparse(node))
		self.assertEqual(writers, {})

	def test_the_controller_no_longer_logs_its_own_row_when_the_status_changes_but_still_notifies(self):
		(cls,) = [n for n in self.tree.body if isinstance(n, ast.ClassDef) and n.name == "BatchAMB"]
		(validate,) = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "validate"]
		calls = [ast.unparse(n.func) for n in ast.walk(validate) if isinstance(n, ast.Call)]
		self.assertNotIn("self.log_batch_history", calls)
		self.assertIn("self.notify_stakeholders", calls)

	def test_a_copy_of_a_lot_starts_pending_with_no_certificate(self):
		source = types.SimpleNamespace()
		copy = types.SimpleNamespace(
			name=None,
			quality_status="Passed",
			status_source="Own certificate",
			released_by_doctype=INTERNAL,
			released_by="CERT-1",
			certificate_status="Passed",
			insert=mock.Mock(),
		)
		copy.set = lambda k, v: setattr(copy, k, v)
		f = mock.MagicMock()
		f.get_doc.return_value = source
		f.copy_doc.return_value = copy

		def insert():
			copy.at_insert = [getattr(copy, k) for k in lq.GUARDED_FIELDS]

		copy.insert.side_effect = insert
		with mock.patch.object(bam, "frappe", f):
			bam.duplicate_batch("LOTE-1")
		self.assertEqual(copy.at_insert, ["Pending", None, None, None, None])


# ----------------------------------------------------------------------------------------------------------------
# the lot's link to its certificate: written by the approval on the certificate's own record, taken back by the
# withdrawal (review of TASKS-384, finding 7)
# ----------------------------------------------------------------------------------------------------------------
LINK_OF = {INTERNAL: "coa_amb2", CUSTOMER: "coa_reference"}


class TestCertificateLink(unittest.TestCase):
	def family(self, **lot_fields):
		return Table(dict(rec("L"), **lot_fields), rec("S1", "2", "L"), rec("C1", "3", "S1"))

	def links(self, t, name):
		return {f: t.rows[name].get(f) for f in ("coa_reference", "coa_amb2")}

	def test_the_link_fields_are_the_two_link_fields_of_the_lot_record_by_certificate_type(self):
		self.assertEqual(lq.CERTIFICATE_LINKS, {"COA AMB": "coa_reference", "COA AMB2": "coa_amb2"})
		fields = {f["fieldname"]: f for f in json.loads(LOT_JSON.read_text(encoding="utf-8"))["fields"]}
		for cert_type, fieldname in lq.CERTIFICATE_LINKS.items():
			self.assertEqual(
				(fields[fieldname]["fieldtype"], fields[fieldname]["options"]), ("Link", cert_type)
			)

	def test_an_approval_writes_the_link_of_the_certificates_type_on_its_own_record(self):
		for cert_type, fieldname in LINK_OF.items():
			t = self.family()
			with site(t):
				lq.certificate_approved(cert_type, "CERT-1", "L", "Pass")
			other = "coa_reference" if fieldname == "coa_amb2" else "coa_amb2"
			self.assertEqual(self.links(t, "L"), {fieldname: "CERT-1", other: None}, cert_type)
			# the same save and the same row as the status
			(row,) = t.rows_of("L")
			self.assertEqual((row.before.get(fieldname), row.after[fieldname]), (None, "CERT-1"))
			self.assertEqual(row.after["quality_status"], "Passed")

	def test_the_link_is_not_written_on_the_records_that_inherit(self):
		for cert_type in LINK_OF:
			t = self.family()
			with site(t):
				lq.certificate_approved(cert_type, "CERT-1", "L", "Pass")
			for name in ("S1", "C1"):
				self.assertEqual(t.rows[name]["status_source"], "Inherited")
				self.assertEqual(self.links(t, name), {"coa_reference": None, "coa_amb2": None}, name)
			for _names, values in t.column_writes:
				self.assertEqual(set(values), set(lq.GUARDED_FIELDS))

	def test_a_sub_lots_own_certificate_is_linked_on_the_sub_lot_and_not_on_the_lot(self):
		t = self.family()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-S", "S1", "Pass")
		self.assertEqual(self.links(t, "S1")["coa_amb2"], "CERT-S")
		self.assertEqual(self.links(t, "L"), {"coa_reference": None, "coa_amb2": None})

	def test_a_withdrawal_clears_the_link(self):
		for cert_type, fieldname in LINK_OF.items():
			t = self.family()
			with site(t):
				lq.certificate_approved(cert_type, "CERT-1", "L", "Pass")
				t.history.clear()
				lq.certificate_withdrawn(cert_type, "CERT-1", "L")
			self.assertEqual(self.links(t, "L"), {"coa_reference": None, "coa_amb2": None}, cert_type)
			(row,) = t.rows_of("L")  # one row: the status and the link together
			self.assertEqual((row.before[fieldname], row.after[fieldname]), ("CERT-1", None))
			self.assertEqual(row.after["quality_status"], "Pending")

	def test_with_a_standing_certificate_of_the_same_type_the_link_points_at_that_one(self):
		t = self.family()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
			lq.certificate_approved(INTERNAL, "CERT-2", "L", "Fail")
			self.assertEqual(self.links(t, "L")["coa_amb2"], "CERT-2")
			lq.certificate_withdrawn(
				INTERNAL, "CERT-2", "L", standing={"doctype": INTERNAL, "name": "CERT-1", "result": "Pass"}
			)
		self.assertEqual(self.links(t, "L"), {"coa_reference": None, "coa_amb2": "CERT-1"})
		self.assertEqual(t.state("L"), ("Passed", "Own certificate", "CERT-1", "Passed"))

	def test_a_standing_certificate_of_the_other_type_does_not_go_in_this_types_field(self):
		t = self.family()
		with site(t):
			lq.certificate_approved(CUSTOMER, "CERT-C", "L", "Pass")
			lq.certificate_approved(INTERNAL, "CERT-I", "L", "Fail")
			self.assertEqual(self.links(t, "L"), {"coa_reference": "CERT-C", "coa_amb2": "CERT-I"})
			lq.certificate_withdrawn(
				INTERNAL, "CERT-I", "L", standing={"doctype": CUSTOMER, "name": "CERT-C", "result": "Pass"}
			)
		self.assertEqual(self.links(t, "L"), {"coa_reference": "CERT-C", "coa_amb2": None})
		self.assertEqual(t.state("L"), ("Passed", "Own certificate", "CERT-C", "Passed"))

	def test_the_withdrawal_of_one_certificate_does_not_clear_the_link_to_another(self):
		# the same type: a later certificate replaced the link; the earlier one is withdrawn
		t = self.family()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
			lq.certificate_approved(INTERNAL, "CERT-2", "L", "Pass")
			t.history.clear()
			self.assertEqual(lq.certificate_withdrawn(INTERNAL, "CERT-1", "L"), 0)
		self.assertEqual(self.links(t, "L")["coa_amb2"], "CERT-2")
		self.assertEqual(t.history, [])
		# the other type, and a link somebody set by hand to another certificate
		t = self.family(coa_reference="CERT-HAND")
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
			lq.certificate_withdrawn(CUSTOMER, "CERT-9", "L")
			self.assertEqual(self.links(t, "L"), {"coa_reference": "CERT-HAND", "coa_amb2": "CERT-1"})
			t.rows["L"]["coa_amb2"] = "CERT-HAND-2"  # edited by hand after the approval: the field is free
			lq.certificate_withdrawn(INTERNAL, "CERT-1", "L")
		self.assertEqual(t.state("L")[0], "Pending")
		self.assertEqual(self.links(t, "L"), {"coa_reference": "CERT-HAND", "coa_amb2": "CERT-HAND-2"})

	def test_the_link_is_taken_back_also_when_the_status_comes_from_another_certificate(self):
		t = self.family()
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-I", "L", "Pass")
			lq.certificate_approved(CUSTOMER, "CERT-C", "L", "Fail")
			t.history.clear()
			written = lq.certificate_withdrawn(
				INTERNAL, "CERT-I", "L", standing={"doctype": CUSTOMER, "name": "CERT-C", "result": "Fail"}
			)
		self.assertEqual(written, 1)
		self.assertEqual(self.links(t, "L"), {"coa_reference": "CERT-C", "coa_amb2": None})
		self.assertEqual(t.state("L"), ("Failed", "Own certificate", "CERT-C", "Failed"))  # untouched
		(row,) = t.history
		self.assertEqual(
			(row.lot, row.before["quality_status"], row.after["quality_status"]), ("L",) + ("Failed",) * 2
		)

	def test_a_lot_released_without_a_link_gets_it_when_the_same_certificate_is_approved_again(self):
		t = self.family(
			quality_status="Passed",
			status_source="Own certificate",
			released_by_doctype=INTERNAL,
			released_by="CERT-1",
			certificate_status="Passed",
		)
		with site(t):
			lq.certificate_approved(INTERNAL, "CERT-1", "L", "Pass")
		self.assertEqual(self.links(t, "L")["coa_amb2"], "CERT-1")

	def test_the_real_save_writes_the_link_in_the_same_save_and_says_so_in_the_same_row(self):
		for cert_type, fieldname in LINK_OF.items():
			db = Db(rec("L"), rec("S1", "2", "L"), rec("C1", "3", "S1"))
			with site(frappe=db.frappe()):
				lq.certificate_approved(cert_type, "CERT-1", "L", "Pass")
				self.assertEqual(db.rows["L"][fieldname], "CERT-1")
				self.assertEqual([e[1] for e in db.saves()], ["L", "S1"])  # no save of its own for the link
				(row,) = db.history["L"]
				self.assertIn(f"certificate link {fieldname}: from none to CERT-1", row["comments"])
				self.assertIn("from Pending to Passed", row["comments"])
				self.assertNotIn("certificate link", db.history["S1"][0]["comments"])
				self.assertIsNone(db.rows["S1"].get(fieldname))
				self.assertIsNone(db.rows["C1"].get(fieldname))
				lq.certificate_withdrawn(cert_type, "CERT-1", "L")
			self.assertIsNone(db.rows["L"][fieldname])
			self.assertEqual([e[1] for e in db.saves()], ["L", "S1", "L", "S1"])
			self.assertIn(
				f"certificate link {fieldname}: from CERT-1 to none", db.history["L"][1]["comments"]
			)

	def test_the_links_stay_free_to_edit_and_the_save_takes_no_other_field(self):
		for fieldname in lq.LINK_FIELDS:
			self.assertNotIn(fieldname, lq.GUARDED_FIELDS)
		db = Db(rec("L"))
		with site(frappe=db.frappe()):
			with self.assertRaises(Refused):
				lq.LotTable().save("L", {"quality_status": "Pending", "batch_status": "Completed"})
		self.assertEqual(db.saves(), [])


if __name__ == "__main__":
	unittest.main()
