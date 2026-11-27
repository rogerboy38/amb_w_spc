# TASKS-387 item 4 (decisions 324 and 325), DB-free: a release is quiet record by record and summed up once.
#
#   * a save made by the writer for a certificate's approval or withdrawal is a "release save"
#     (`lot_quality.is_release_save`); the lot controller then runs no `notify_stakeholders` (no mail to the quality
#     roles, no "Notifications Sent" row) and no `sync_with_lote_amb` (no orphan Lote AMB); ordinary saves still do
#   * `on_update` no longer calls `log_batch_history` (a row appended after the write was never stored)
#   * ONE summary per approval / withdrawal that wrote any record, to the certificate's filler, the session user
#     and the owner of the lot's Work Order: enabled users only, each once, never Administrator / Guest; it lists
#     the certificate, its result and every record written (containers included); nothing written: no message
#   * the summary is a queued mail: inserted in the release's transaction, sent after commit, gone on rollback;
#     a summary that cannot be queued fails the release
#
# Run: python -m unittest amb_w_spc.tests.test_release_summary   (no site needed)

import ast
import contextlib
import inspect
import pathlib
import types
import unittest
from unittest import mock

from amb_w_spc.sfc_manufacturing import lot_quality as lq
from amb_w_spc.sfc_manufacturing.doctype.batch_amb import batch_amb as bam
from amb_w_spc.tests.test_lot_quality import INTERNAL, USER, Db, Refused, Table, fake_frappe, rec, site

FILLER, WO_OWNER = "quality-filler", "planner"
EMAIL = {
	USER: "mail-approver",
	FILLER: "mail-filler",
	WO_OWNER: "mail-planner",
}
QUALITY_ROLE_USERS = ("quality-1", "quality-2", "quality-3")


def tree():
	"""L (lot) > S1, S2 (sub-lots) > C11, C12 under S1, C21 under S2 (containers), all Pending."""
	return (
		rec("L"),
		rec("S1", "2", "L"),
		rec("S2", "2", "L"),
		rec("C11", "3", "S1"),
		rec("C12", "3", "S1"),
		rec("C21", "3", "S2"),
	)


def people(**overrides):
	"""{user: {"enabled", "email"}} for the three recipients; `overrides`: user -> dict or None (no such user)."""
	out = {user: {"enabled": 1, "email": email} for user, email in EMAIL.items()}
	for user, value in overrides.items():
		if value is None:
			out.pop(user, None)
		else:
			out[user] = value
	return out


class Transaction:
	"""What Frappe 16.17.5 does with a queued mail (`frappe.sendmail` with no `now`): an Email Queue row inserted
	in the current transaction (`QueueBuilder.process(send_now=False)` -> `EmailQueue.new` -> `insert`). The
	scheduler's flush sends only committed rows; `rollback` takes the row away. `after_commit` callbacks are kept
	here only to show that none is registered."""

	def __init__(self):
		self.pending, self.sent, self.after_commit = [], [], []

	def sendmail(self, **kwargs):
		if kwargs.get("now") or kwargs.get("delayed") is False:
			self.after_commit.append(kwargs)  # what `now=True` would do: send after commit, outside the row
		row = types.SimpleNamespace(**kwargs)
		self.pending.append(row)
		return row

	def commit(self):
		self.sent.extend(self.pending)
		self.pending = []

	def rollback(self):
		self.pending, self.after_commit = [], []


def summary_frappe(
	users=None, filled_by=FILLER, work_order="WO-1", wo_owner=WO_OWNER, session=USER, docstatus=0
):
	"""A fake frappe for the in-memory table: the reads of the summary (the certificate, the lot's Work Order, its
	owner, the users) and a transaction that holds the queued mail."""
	f = fake_frappe()
	f.session.user = session
	users = people() if users is None else users
	tx = Transaction()
	f.tx = tx

	def get_value(dt, name, fields, as_dict=False):
		if dt == "Batch AMB":
			assert fields == "work_order_ref", fields  # the table is not read through frappe here
			return work_order
		if dt == "Work Order":
			assert name == work_order and fields == "owner"
			return wo_owner
		if dt == "User":
			u = users.get(name)
			return None if u is None else {k: u.get(k) for k in fields}
		assert dt == INTERNAL and as_dict, (dt, fields)
		return {"filled_by": filled_by, "docstatus": docstatus, "overall_result": "Pass"}

	f.db.get_value.side_effect = get_value
	f.sendmail.side_effect = tx.sendmail
	f.db.commit.side_effect = (
		tx.commit
	)  # a commit inside the release would send the summary before a rollback
	return f


class SummaryCase(unittest.TestCase):
	def approve(self, table, f, lot="L", certificate="CERT-L", result="Pass"):
		with site(table, frappe=f):
			return lq.certificate_approved(INTERNAL, certificate, lot, result)

	def withdraw(self, table, f, lot="L", certificate="CERT-L"):
		with site(table, frappe=f):
			return lq.certificate_withdrawn(INTERNAL, certificate, lot)

	def mails(self, f):
		return [c.kwargs for c in f.sendmail.call_args_list]


class TestOneSummary(SummaryCase):
	def test_an_approval_of_a_lot_with_sub_lots_and_containers_sends_exactly_one_message_to_the_three(self):
		t, f = Table(*tree()), summary_frappe()
		written = self.approve(t, f)
		self.assertEqual(written, 6)  # L, S1, S2 saved; C11, C12, C21 by column write
		(mail,) = self.mails(f)
		self.assertEqual(mail["recipients"], [EMAIL[FILLER], EMAIL[USER], EMAIL[WO_OWNER]])
		self.assertEqual((mail["reference_doctype"], mail["reference_name"]), (INTERNAL, "CERT-L"))
		body = mail["message"]
		self.assertIn(f"{INTERNAL} CERT-L was approved with result Pass", body)
		self.assertIn(f"By {USER}. 6 lot record(s) written", body)
		self.assertEqual(body.count("<li>"), written)  # every record counted is listed, containers included
		self.assertIn("<li>L (level 1): Pending &rarr; Passed, source Own certificate, saved</li>", body)
		for sub in ("S1", "S2"):
			self.assertIn(f"<li>{sub} (level 2): Pending &rarr; Passed, source Inherited, saved</li>", body)
		for container in ("C11", "C12", "C21"):
			self.assertIn(
				f"<li>{container} (level 3): Pending &rarr; Passed, source Inherited, column write</li>", body
			)
		self.assertIn("approved (Pass): 6 lot record(s) written", mail["subject"])

	def test_no_role_wide_mail_and_no_role_is_read(self):
		t, f = Table(*tree()), summary_frappe()
		self.approve(t, f)
		f.get_all.assert_not_called()  # Has Role is never read
		self.assertEqual(f.sendmail.call_count, 1)

	def test_a_withdrawal_sends_one_saying_withdrawn_and_the_status_taken(self):
		t, f = Table(*tree()), summary_frappe()
		self.approve(t, f)
		f.sendmail.reset_mock()
		written = self.withdraw(t, f)
		(mail,) = self.mails(f)
		self.assertEqual(written, 6)
		self.assertIn(
			f"{INTERNAL} CERT-L was withdrawn (rejected back from Approved); lot record L now Pending (source none)",
			mail["message"],
		)
		self.assertIn(
			"<li>C21 (level 3): Passed &rarr; Pending, source none, column write</li>", mail["message"]
		)
		self.assertIn("withdrawn: 6 lot record(s) written", mail["subject"])
		self.assertIn("Its result was Pass.", mail["message"])  # review finding 7: the result is given
		self.assertEqual(mail["recipients"], [EMAIL[FILLER], EMAIL[USER], EMAIL[WO_OWNER]])

	def test_a_cancelled_certificate_says_cancelled(self):
		t = Table(*tree())
		self.approve(t, summary_frappe())
		f = summary_frappe(docstatus=2)
		self.withdraw(t, f)
		(mail,) = self.mails(f)
		self.assertIn("was withdrawn (cancelled)", mail["message"])

	def test_a_disabled_or_deleted_user_or_one_without_an_address_is_skipped(self):
		for users, expected in (
			(people(**{FILLER: {"enabled": 0, "email": EMAIL[FILLER]}}), [EMAIL[USER], EMAIL[WO_OWNER]]),
			(people(**{WO_OWNER: None}), [EMAIL[FILLER], EMAIL[USER]]),
			(people(**{FILLER: {"enabled": 1, "email": None}}), [EMAIL[USER], EMAIL[WO_OWNER]]),
			(people(**{FILLER: {"enabled": "0", "email": EMAIL[FILLER]}}), [EMAIL[USER], EMAIL[WO_OWNER]]),
		):
			with self.subTest(users=users):
				t, f = Table(*tree()), summary_frappe(users=users)
				self.approve(t, f)
				(mail,) = self.mails(f)
				self.assertEqual(mail["recipients"], expected)

	def test_duplicates_collapse(self):
		# the filler owns the Work Order: one address once
		t, f = Table(*tree()), summary_frappe(wo_owner=FILLER)
		self.approve(t, f)
		self.assertEqual(self.mails(f)[0]["recipients"], [EMAIL[FILLER], EMAIL[USER]])
		# two users with the same address: once
		users = people(**{WO_OWNER: {"enabled": 1, "email": EMAIL[USER]}})
		t, f = Table(*tree()), summary_frappe(users=users)
		self.approve(t, f)
		self.assertEqual(self.mails(f)[0]["recipients"], [EMAIL[FILLER], EMAIL[USER]])

	def test_administrator_and_guest_are_never_recipients(self):
		users = people(Administrator={"enabled": 1, "email": "mail-admin"})
		t, f = Table(*tree()), summary_frappe(users=users, session="Administrator", wo_owner="Guest")
		self.approve(t, f)
		self.assertEqual(self.mails(f)[0]["recipients"], [EMAIL[FILLER]])

	def test_the_work_order_is_the_one_of_the_lot_named_in_the_call(self):
		t, f = Table(*tree()), summary_frappe(work_order=None)
		self.approve(t, f)
		self.assertEqual(self.mails(f)[0]["recipients"], [EMAIL[FILLER], EMAIL[USER]])
		self.assertNotIn("Work Order", [c.args[0] for c in f.db.get_value.call_args_list])

	def test_nothing_written_nothing_sent(self):
		t = Table(*tree())
		self.approve(t, summary_frappe())
		f = summary_frappe()
		self.assertEqual(self.approve(t, f), 0)  # the same approval again writes nothing
		f.sendmail.assert_not_called()
		f = summary_frappe()
		self.assertEqual(self.withdraw(t, f, certificate="CERT-OTHER"), 0)  # a certificate that wrote nothing
		f.sendmail.assert_not_called()

	def test_nobody_to_tell_sends_nothing_and_the_release_stands(self):
		t, f = Table(*tree()), summary_frappe(users={})
		self.assertEqual(self.approve(t, f), 6)
		f.sendmail.assert_not_called()


class TestAfterCommitOnly(SummaryCase):
	def test_the_summary_is_queued_in_the_transaction_with_no_after_commit_send(self):
		t, f = Table(*tree()), summary_frappe()
		self.approve(t, f)
		kwargs = self.mails(f)[0]
		self.assertNotIn("now", kwargs)
		self.assertNotIn("delayed", kwargs)
		self.assertEqual(f.tx.after_commit, [])
		f.db.after_commit.add.assert_not_called()
		f.db.commit.assert_not_called()  # the caller's transaction, whole
		self.assertEqual((len(f.tx.pending), f.tx.sent), (1, []))
		f.tx.commit()
		self.assertEqual(len(f.tx.sent), 1)

	def test_a_rolled_back_approval_sends_nothing(self):
		# the approval wrote and queued its summary; something later in the certificate's save fails, and the
		# request is rolled back: the queued row goes with it
		t, f = Table(*tree()), summary_frappe()
		self.approve(t, f)
		f.tx.rollback()
		f.tx.commit()
		self.assertEqual(f.tx.sent, [])

	def test_an_approval_that_fails_midway_builds_no_summary(self):
		t, f = Table(*tree()), summary_frappe()
		original = t.save

		def save(name, *args, **kwargs):
			if name == "S2":
				raise RuntimeError("S2 cannot be saved")
			return original(name, *args, **kwargs)

		t.save = save
		with self.assertRaises(RuntimeError):
			self.approve(t, f)
		f.sendmail.assert_not_called()

	def test_a_summary_that_cannot_be_queued_fails_the_release_visibly(self):
		t, f = Table(*tree()), summary_frappe()
		f.sendmail.side_effect = (
			lambda **k: None
		)  # Frappe queued nothing (an invalid address, all unsubscribed)
		with self.assertRaises(Refused):
			self.approve(t, f)
		self.assertIn("could not be queued", f.throw.call_args.args[0])
		t, f = Table(*tree()), summary_frappe()
		f.sendmail.side_effect = OSError("queue unavailable")
		with self.assertRaises(OSError):  # not caught
			self.approve(t, f)

	def test_the_source_queues_without_now_and_without_a_try(self):
		fn = ast.parse(inspect.getsource(lq.send_release_summary)).body[0]
		calls = [
			n for n in ast.walk(fn) if isinstance(n, ast.Call) and ast.unparse(n.func) == "frappe.sendmail"
		]
		self.assertEqual(len(calls), 1)
		self.assertFalse({k.arg for k in calls[0].keywords} & {"now", "delayed"})
		self.assertFalse([n for n in ast.walk(fn) if isinstance(n, ast.Try)])
		code = "\n".join(ast.unparse(n) for n in fn.body[1:])  # without the docstring
		self.assertNotIn("after_commit", code)
		self.assertNotIn("commit(", code)


# ----------------------------------------------------------------------------------------------------------------
# the real controller under a release: the real LotTable.save, the real guard, BatchAMB.validate and on_update
# ----------------------------------------------------------------------------------------------------------------
class Flags(dict):
	def __getattr__(self, key):
		return self.get(key)


# the steps of BatchAMB.validate that read or write outside this test; each is a no-op here
VALIDATE_STEPS = (
	"set_batch_naming",
	"validate_production_dates",
	"update_planned_qty_from_work_order",
	"validate_quantities",
	"validate_work_order",
	"validate_containers",
	"validate_batch_level_hierarchy",
	"validate_barrel_weights",
	"set_item_details",
	"validate_processing_dates",
	"calculate_yield_percentage",
)


class ControllerDoc:
	"""A Batch AMB document whose save runs, in Frappe's order: the guard (before_validate), the REAL
	`BatchAMB.validate`, the write of the record and its rows (what is on the document then is what is stored),
	the REAL `BatchAMB.on_update`, the guard (on_update). `notify_stakeholders`, `log_batch_history` and
	`sync_with_lote_amb` are the controller's own."""

	def __init__(self, db, name):
		fields = dict(db.rows[name])
		fields.setdefault("processing_history", [])
		fields.setdefault("lote_amb_reference", None)
		fields.update(batch_status="Draft", work_order_ref="WO-1", owner=FILLER, title=name)
		fields.update(item_to_manufacture="0227", wo_item_name="")
		object.__setattr__(self, "fields", fields)
		object.__setattr__(self, "db", db)
		object.__setattr__(self, "name", name)
		object.__setattr__(self, "flags", Flags())
		for step in VALIDATE_STEPS:
			object.__setattr__(self, step, lambda *a, **k: None)
		for method in ("notify_stakeholders", "log_batch_history", "sync_with_lote_amb"):
			object.__setattr__(self, method, types.MethodType(getattr(bam.BatchAMB, method), self))

	def __getattr__(self, key):
		if key in self.fields:
			return self.fields[key]
		raise AttributeError(key)

	def __setattr__(self, key, value):
		self.fields[key] = value

	def get(self, key, default=None):
		return self.fields.get(key, default)

	def set(self, key, value):
		self.fields[key] = value

	def append(self, table, row):
		self.fields.setdefault(table, []).append(row)

	def get_doc_before_save(self):
		stored = dict(self.db.rows[self.name], batch_status="Draft")
		before = types.SimpleNamespace(**stored)
		before.get = lambda k, d=None: stored.get(k, d)
		return before

	def save(self, **kwargs):
		self.db.log.append(("save", self.name, lq.is_release_save(self)))
		lq.refuse_hand_change(self, "before_validate")
		bam.BatchAMB.validate(self)
		stored_rows = list(self.fields["processing_history"])  # update_children: what is on the doc now
		self.db.rows[self.name] = {k: v for k, v in self.fields.items() if k != "processing_history"}
		self.db.history.setdefault(self.name, []).extend(stored_rows)
		bam.BatchAMB.on_update(self)
		lq.refuse_hand_change(self, "on_update")
		self.after_on_update = list(self.fields["processing_history"])


@contextlib.contextmanager
def controller_site(db):
	f = db.frappe()
	docs = []

	def get_doc(doctype, name):
		if doctype == "Work Order":
			return types.SimpleNamespace(name=name, owner=WO_OWNER)
		assert doctype == "Batch AMB"
		docs.append(ControllerDoc(db, name))
		return docs[-1]

	lot_get_all = f.get_all.side_effect

	def get_all(doctype, filters=None, fields=None, **kwargs):
		if doctype == "Has Role":  # notify_stakeholders: every holder of the quality roles
			return [types.SimpleNamespace(parent=u) for u in QUALITY_ROLE_USERS]
		return lot_get_all(doctype, filters=filters, fields=fields, **kwargs)

	f.get_doc.side_effect = get_doc
	f.get_all.side_effect = get_all
	f.docs = docs
	with contextlib.ExitStack() as stack:
		stack.enter_context(site(frappe=f))
		stack.enter_context(mock.patch.object(bam, "frappe", f))
		stack.enter_context(mock.patch.object(bam, "_", lambda s: s))
		stack.enter_context(mock.patch.object(bam, "_sync_from_work_order", lambda doc: None))
		stack.enter_context(mock.patch.object(bam, "get_url", lambda: ""))
		stack.enter_context(mock.patch.object(bam, "now_datetime", lambda: "2026-11-26 10:00:00"))
		yield f


def lote_amb_inserts(f):
	return [c for c in f.new_doc.call_args_list if c.args and c.args[0] == "Lote AMB"]


def controller_db():
	db = Db(*tree())
	db.certificates[(INTERNAL, "CERT-L")] = {"filled_by": FILLER, "docstatus": 0, "overall_result": "Pass"}
	db.work_orders["WO-1"] = {"owner": WO_OWNER}
	db.users.update(people())
	for user in QUALITY_ROLE_USERS:
		db.users[user] = {"enabled": 1, "email": f"mail-{user}"}
	return db


class TestTheControllerUnderARelease(unittest.TestCase):
	def test_an_approval_sends_one_message_creates_no_lote_amb_and_notifies_nobody_per_record(self):
		db = controller_db()
		with controller_site(db) as f:
			written = lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		self.assertEqual(written, 6)
		self.assertEqual([e[1:] for e in db.saves()], [("L", True), ("S1", True), ("S2", True)])
		self.assertEqual(lote_amb_inserts(f), [])  # no orphan Lote AMB
		# ONE mail: the summary, to the three; notify_stakeholders would have mailed the quality roles per record
		(mail,) = [c.kwargs for c in f.sendmail.call_args_list]
		self.assertEqual(mail["recipients"], [EMAIL[FILLER], EMAIL[USER], EMAIL[WO_OWNER]])
		self.assertEqual(mail["reference_name"], "CERT-L")
		self.assertNotIn("Has Role", [c.args[0] for c in f.get_all.call_args_list])
		# one history row per saved record, the writer's: no "Notifications Sent" row
		for name in ("L", "S1", "S2"):
			actions = [r["processing_action"] for r in db.history[name]]
			self.assertEqual(actions, [lq.HISTORY_ACTION], name)
		# the documents are back to ordinary after the save: both flags are down
		self.assertFalse(any(lq.is_release_save(d) for d in f.docs))

	def test_a_withdrawal_is_quiet_per_record_too(self):
		db = controller_db()
		with controller_site(db) as f:
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
			f.sendmail.reset_mock()
			f.new_doc.reset_mock()
			lq.certificate_withdrawn(INTERNAL, "CERT-L", "L")
		self.assertEqual(f.sendmail.call_count, 1)
		self.assertEqual(lote_amb_inserts(f), [])

	def test_an_ordinary_save_still_syncs_with_lote_amb_as_before(self):
		db = controller_db()
		with controller_site(db) as f:
			doc = ControllerDoc(db, "L")
			doc.fields["batch_status"] = "Completed"
			doc.save()
		self.assertEqual(len(lote_amb_inserts(f)), 1)  # sync_with_lote_amb ran: not changed by this task

	def test_validate_skips_notify_only_under_the_release_flag(self):
		for release, calls in ((True, 0), (False, 1)):
			with self.subTest(release=release):
				db = controller_db()
				with controller_site(db):
					doc = ControllerDoc(db, "L")
					doc.fields["quality_status"] = "Passed"
					doc.flags[lq.WRITER_FLAG] = lq._WRITER
					if release:
						doc.flags[lq.RELEASE_FLAG] = lq._RELEASE
					notify = mock.Mock()
					object.__setattr__(doc, "notify_stakeholders", notify)
					bam.BatchAMB.validate(doc)
				self.assertEqual(notify.call_count, calls)

	def test_on_update_appends_no_history_row_for_any_save(self):
		for release in (True, False):
			with self.subTest(release=release):
				db = controller_db()
				with controller_site(db):
					doc = ControllerDoc(db, "L")
					if release:
						doc.flags[lq.WRITER_FLAG] = lq._WRITER
						doc.flags[lq.RELEASE_FLAG] = lq._RELEASE
					before = list(doc.fields["processing_history"])
					bam.BatchAMB.on_update(doc)
				self.assertEqual(doc.fields["processing_history"], before)


class TestWhatIsAReleaseSave(unittest.TestCase):
	def test_only_the_writers_saves_of_an_approval_or_withdrawal(self):
		db = controller_db()
		with controller_site(db) as f:
			lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
			lq.certificate_withdrawn(INTERNAL, "CERT-L", "L")
			self.assertTrue(all(e[2] for e in db.saves()))
			db.log.clear()
			f.sendmail.reset_mock()
			f.new_doc.reset_mock()
			# the writer's other saves are not a release, and keep the controller's steps: a hand hold placed and
			# lifted mails as before (notify_stakeholders, the status changes) and syncs with Lote AMB
			lq.set_lot_quality_status("S1", "Hold", reason="checked", source=lq.HOLD_ACTION)
			lq.lift_hand_hold("S1", "done")
			self.assertEqual([e[1:] for e in db.saves()], [("S1", False), ("S1", False)])
		self.assertEqual(f.sendmail.call_count, 2)
		for call in f.sendmail.call_args_list:
			self.assertIn("mail-quality-1", call.kwargs["recipients"])
		self.assertEqual(len(lote_amb_inserts(f)), 2)

	def test_a_flag_that_arrives_as_data_is_not_a_release(self):
		doc = types.SimpleNamespace(flags=Flags({lq.WRITER_FLAG: lq._WRITER, lq.RELEASE_FLAG: True}))
		self.assertFalse(lq.is_release_save(doc))
		doc = types.SimpleNamespace(flags=Flags({lq.RELEASE_FLAG: lq._RELEASE}))
		self.assertFalse(lq.is_release_save(doc))  # the writer's own pass is needed too
		self.assertFalse(lq.is_release_save(types.SimpleNamespace()))

	def test_insert_child_is_not_a_release(self):
		seen = []
		child = types.SimpleNamespace(name="S9", current_plant2="1", current_item_code="0227")
		child.flags = Flags()
		child.set = lambda k, v: setattr(child, k, v)
		child.get = lambda k, d=None: getattr(child, k, d)
		child.append = lambda table, row: None
		child.insert = lambda: seen.append(lq.is_release_save(child))
		parent = rec("L", status="Passed", source=lq.OWN_CERTIFICATE, cert="CERT-L")
		with site():
			lq.insert_child(child, parent)
		self.assertEqual(seen, [False])


class TestTheControllerSource(unittest.TestCase):
	def setUp(self):
		tree_ = ast.parse(pathlib.Path(bam.__file__).read_text(encoding="utf-8"))
		(self.cls,) = [n for n in tree_.body if isinstance(n, ast.ClassDef) and n.name == "BatchAMB"]

	def method(self, name):
		(fn,) = [n for n in self.cls.body if isinstance(n, ast.FunctionDef) and n.name == name]
		return fn

	def test_the_controller_asks_lot_quality_and_tests_no_flag_name_itself(self):
		for name in ("validate", "on_update"):
			src = ast.unparse(self.method(name))
			self.assertIn("lot_quality.is_release_save(self)", src, name)
			self.assertNotIn("lot_quality_release", src)
			self.assertNotIn("RELEASE_FLAG", src)

	def test_on_update_no_longer_calls_log_batch_history(self):
		calls = [ast.unparse(n.func) for n in ast.walk(self.method("on_update")) if isinstance(n, ast.Call)]
		self.assertNotIn("self.log_batch_history", calls)


if __name__ == "__main__":
	unittest.main()
