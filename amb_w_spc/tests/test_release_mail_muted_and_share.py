# TASKS-390, DB-free: decisions 333 (muted mail is noted, not queued) and 334's amb_w_spc half (the share is summed
# up like a release, `lot_quality.certificate_shared`).
#
#   * 333: `frappe.are_emails_muted()` (Frappe's own function, fed through what it reads: `frappe.flags.mute_emails`,
#     `frappe.conf.mute_emails`) is asked before `frappe.sendmail`; muted -> no sendmail, the release's row says
#     "summary not sent: mail is muted", the user is told, the release stands; not muted -> sent as before
#   * 334: ONE summary per share to the certificate's filler, the user who shared and the lot's Work Order owner
#     (enabled users only, never Administrator / Guest, each once), queued with no `now`; it writes no lot status
#     and no row of its own; muted, no outgoing account, nothing queued or no valid address -> "summary not sent:
#     <reason>" appended to the LATEST history row of the lot by a column write, or an Info Comment on the lot when
#     it has no row; no Error Log; `lot` empty -> nothing
#
# Run: python -m unittest amb_w_spc.tests.test_release_mail_muted_and_share   (no site needed)

import ast
import inspect
import unittest

import frappe as real_frappe

from amb_w_spc.sfc_manufacturing import lot_quality as lq
from amb_w_spc.tests.test_lot_quality import INTERNAL, USER, Refused, Table, site
from amb_w_spc.tests.test_release_summary import (
	EMAIL,
	FILLER,
	WO_OWNER,
	SummaryCase,
	controller_db,
	controller_site,
	every_recipient_unsubscribed,
	no_outgoing_account,
	people,
	summary_frappe,
	tree,
)

MUTED_BY_FLAG = {"flags": {"mute_emails": True}}
MUTED_BY_CONF = {"conf": {"mute_emails": 1}}
MUTED = "summary not sent: mail is muted"


class MutedCase(SummaryCase):
	def approve(self, table, f, mail=None, lot="L", certificate="CERT-L", result="Pass"):
		with site(table, frappe=f, mail=mail):
			self.assertIs(lq.frappe.are_emails_muted, real_frappe.are_emails_muted)  # the real function
			return lq.certificate_approved(INTERNAL, certificate, lot, result)

	def withdraw(self, table, f, mail=None, lot="L", certificate="CERT-L"):
		with site(table, frappe=f, mail=mail):
			return lq.certificate_withdrawn(INTERNAL, certificate, lot)

	def notes(self, table):
		return {h.lot: h.added for h in table.history if h.added}


# ----------------------------------------------------------------------------------------------------------------
# decision 333
# ----------------------------------------------------------------------------------------------------------------
class TestMutedMailIsNotedNotQueued(MutedCase):
	def test_muted_by_the_flag_or_by_the_site_config_no_sendmail_and_the_row_says_so(self):
		for mail in (
			MUTED_BY_FLAG,
			MUTED_BY_CONF,
			{"conf": {"mute_emails": "1"}},  # a config value read as text: Frappe's cint
			{"flags": {"mute_emails": False}, "conf": {"mute_emails": 1}},
		):
			with self.subTest(mail=mail):
				t, f = Table(*tree()), summary_frappe()
				written = self.approve(t, f, mail=mail)
				self.assertEqual(written, 6)  # the release stands
				self.assertEqual(t.state("L"), ("Passed", "Own certificate", "CERT-L", "Passed"))
				f.sendmail.assert_not_called()  # nothing queued, so nothing leaves at unmute
				self.assertEqual(self.notes(t), {"L": [MUTED]})
				for address in EMAIL.values():
					self.assertNotIn(address, MUTED)
				f.log_error.assert_not_called()
				# the user is told, as for decision 328
				self.assertIn("summary was not sent (mail is muted)", f.msgprint.call_args.args[0])
				self.assertIn("history of lot record L", f.msgprint.call_args.args[0])
				self.assertEqual(f.msgprint.call_args.kwargs.get("indicator"), "orange")

	def test_a_withdrawal_and_a_cancel_under_muted_mail_are_noted_too(self):
		for docstatus in (0, 2):
			with self.subTest(docstatus=docstatus):
				t = Table(*tree())
				self.approve(t, summary_frappe())
				f = summary_frappe(docstatus=docstatus)
				self.assertEqual(self.withdraw(t, f, mail=MUTED_BY_CONF), 6)
				f.sendmail.assert_not_called()
				self.assertEqual(self.notes(t), {"L": [MUTED]})

	def test_not_muted_still_sends_as_before(self):
		for mail in (None, {"flags": {"mute_emails": False}, "conf": {"mute_emails": 0}}, {"conf": {"x": 1}}):
			with self.subTest(mail=mail):
				t, f = Table(*tree()), summary_frappe()
				self.approve(t, f, mail=mail)
				(call,) = f.sendmail.call_args_list
				self.assertEqual(call.kwargs["recipients"], [EMAIL[FILLER], EMAIL[USER], EMAIL[WO_OWNER]])
				self.assertEqual(self.notes(t), {})
				f.msgprint.assert_not_called()

	def test_nobody_to_tell_under_muted_mail_writes_nothing_as_before(self):
		t, f = Table(*tree()), summary_frappe(users={})
		self.assertEqual(self.approve(t, f, mail=MUTED_BY_FLAG), 6)
		self.assertEqual(self.notes(t), {})

	def test_the_check_comes_before_the_one_sendmail_and_outside_the_try(self):
		fn = ast.parse(inspect.getsource(lq._send_summary)).body[0]
		order = [
			ast.unparse(n.func)
			for n in ast.walk(fn)
			if isinstance(n, ast.Call)
			and ast.unparse(n.func) in ("frappe.are_emails_muted", "frappe.sendmail")
		]
		self.assertEqual(order, ["frappe.are_emails_muted", "frappe.sendmail"])
		muted_at = next(
			n.lineno
			for n in ast.walk(fn)
			if isinstance(n, ast.Call) and ast.unparse(n.func) == "frappe.are_emails_muted"
		)
		(trying,) = [n for n in ast.walk(fn) if isinstance(n, ast.Try)]
		self.assertLess(muted_at, trying.lineno)


class TestMutedThroughTheController(unittest.TestCase):
	"""Decision 333 through the real LotTable.save, the real guard and BatchAMB.validate / on_update."""

	def test_the_stored_row_of_the_lot_says_muted_and_nothing_is_queued(self):
		db = controller_db()
		with controller_site(db, mail=MUTED_BY_CONF) as f:
			written = lq.certificate_approved(INTERNAL, "CERT-L", "L", "Pass")
		self.assertEqual(written, 6)
		self.assertEqual(db.rows["L"]["quality_status"], "Passed")
		f.sendmail.assert_not_called()  # neither the summary nor any per-record mail
		(row,) = db.history["L"]
		self.assertTrue(row["comments"].endswith(" | " + MUTED), row["comments"])
		self.assertEqual([e[1] for e in db.saves()], ["L", "S1", "S2"])  # no second save for the note
		f.log_error.assert_not_called()


# ----------------------------------------------------------------------------------------------------------------
# decision 334, amb_w_spc's half: certificate_shared
# ----------------------------------------------------------------------------------------------------------------
def share_frappe(latest_row="ROW-9", stored="Quality status: from Pending to Passed", **kwargs):
	"""summary_frappe, with the lot's history rows: `latest_row` = the name of its last row (None: it has none)."""
	f = summary_frappe(**kwargs)
	summary_get_value = f.db.get_value.side_effect
	f.history_reads, f.rows = [], {latest_row: stored} if latest_row else {}

	def get_value(dt, name, fields, as_dict=False, order_by=None):
		if dt == lq.HISTORY_DOCTYPE:
			f.history_reads.append((name, fields, order_by))
			if isinstance(name, dict):
				return latest_row
			return f.rows.get(name)
		return summary_get_value(dt, name, fields, as_dict=as_dict)

	def set_value(dt, name, fieldname, value, update_modified=True):
		assert dt == lq.HISTORY_DOCTYPE and fieldname == "comments" and update_modified is False
		f.rows[name] = value

	f.db.get_value.side_effect = get_value
	f.db.set_value.side_effect = set_value
	return f


class ShareCase(unittest.TestCase):
	def share(self, f, lot="L", mail=None, certificate="CERT-L"):
		with site(Table(*tree()), frappe=f, mail=mail):
			return lq.certificate_shared(INTERNAL, certificate, lot)

	def comments(self, f):
		return [c for c in f.get_doc.call_args_list if c.args and c.args[0].get("doctype") == "Comment"]


class TestTheShareSummary(ShareCase):
	def test_one_summary_to_the_three_queued_with_no_now(self):
		f = share_frappe()
		self.share(f)
		(call,) = f.sendmail.call_args_list
		mail = call.kwargs
		self.assertEqual(mail["recipients"], [EMAIL[FILLER], EMAIL[USER], EMAIL[WO_OWNER]])
		self.assertEqual((mail["reference_doctype"], mail["reference_name"]), (INTERNAL, "CERT-L"))
		self.assertFalse({"now", "delayed"} & set(mail))
		self.assertIn(f"{INTERNAL} CERT-L was shared with result Pass, for lot record L", mail["message"])
		self.assertIn(f"Shared by {USER}", mail["message"])
		self.assertIn("shared (Pass): lot record L", mail["subject"])
		f.db.after_commit.add.assert_not_called()
		f.db.commit.assert_not_called()
		f.get_all.assert_not_called()  # no role is read: no team mail
		self.assertEqual(f.rows, {"ROW-9": "Quality status: from Pending to Passed"})  # nothing noted
		f.log_error.assert_not_called()

	def test_it_writes_no_lot_status(self):
		t, f = Table(*tree()), share_frappe()
		before = {name: t.state(name) for name in t.rows}
		with site(t, frappe=f):
			lq.certificate_shared(INTERNAL, "CERT-L", "L")
		self.assertEqual({name: t.state(name) for name in t.rows}, before)
		self.assertEqual((t.history, t.column_writes), ([], []))
		f.get_doc.assert_not_called()

	def test_the_recipient_rules_of_a_release(self):
		users = people(**{FILLER: {"enabled": 0, "email": EMAIL[FILLER]}})
		f = share_frappe(users=users, session="Administrator", wo_owner="Guest")
		self.share(f)
		f.sendmail.assert_not_called()  # the filler disabled, Administrator and Guest never: nobody
		f = share_frappe(wo_owner=FILLER)
		self.share(f)
		self.assertEqual(f.sendmail.call_args.kwargs["recipients"], [EMAIL[FILLER], EMAIL[USER]])

	def test_no_lot_nothing(self):
		for lot in (None, ""):
			f = share_frappe()
			self.assertIsNone(self.share(f, lot=lot))
			f.sendmail.assert_not_called()
			f.db.get_value.assert_not_called()

	def test_muted_the_latest_row_of_the_lot_says_so_by_a_column_write(self):
		for mail in (MUTED_BY_FLAG, MUTED_BY_CONF):
			with self.subTest(mail=mail):
				f = share_frappe()
				self.assertIsNone(self.share(f, mail=mail))
				f.sendmail.assert_not_called()
				self.assertEqual(f.rows["ROW-9"], "Quality status: from Pending to Passed | " + MUTED)
				(latest,) = [r for r in f.history_reads if isinstance(r[0], dict)]
				self.assertEqual(
					latest,
					(
						{"parent": "L", "parenttype": "Batch AMB", "parentfield": "processing_history"},
						"name",
						"idx desc",
					),
				)
				self.assertEqual(self.comments(f), [])
				self.assertIn("the share stands", f.msgprint.call_args.args[0])
				self.assertIn("history of lot record L", f.msgprint.call_args.args[0])
				f.log_error.assert_not_called()

	def test_a_lot_with_no_history_row_gets_an_info_comment(self):
		f = share_frappe(latest_row=None)
		self.share(f, mail=MUTED_BY_FLAG)
		((call),) = self.comments(f)
		comment = call.args[0]
		self.assertEqual(
			{k: comment[k] for k in ("comment_type", "reference_doctype", "reference_name", "content")},
			{
				"comment_type": "Info",
				"reference_doctype": "Batch AMB",
				"reference_name": "L",
				"content": MUTED,
			},
		)
		f.get_doc.return_value.insert.assert_called_once_with(ignore_permissions=True)
		self.assertIn("a comment on it", f.msgprint.call_args.args[0])

	def test_no_outgoing_account_nothing_queued_or_no_valid_address_are_noted_and_the_share_stands(self):
		for make, needle in (
			(lambda: no_outgoing_account(share_frappe()), "no outgoing email account (OutgoingEmailError)"),
			(lambda: every_recipient_unsubscribed(share_frappe()), "every recipient unsubscribed"),
		):
			with self.subTest(needle=needle):
				f = make()
				self.assertIsNone(self.share(f))
				self.assertIn("| summary not sent: ", f.rows["ROW-9"])
				self.assertIn(needle, f.rows["ROW-9"])
				self.assertEqual(f.local.message_log, [])  # no red message on a share that stood
				f.log_error.assert_not_called()
		f = share_frappe()
		f.utils.validate_email_address.side_effect = lambda e, throw=False: ""
		self.share(f)
		f.sendmail.assert_not_called()
		self.assertIn("summary not sent: no valid address for its 3 recipient(s)", f.rows["ROW-9"])

	def test_another_exception_still_fails_the_share(self):
		for exc in (OSError("queue unavailable"), Refused("refused"), RuntimeError("bug")):
			with self.subTest(exc=exc):
				f = share_frappe()
				f.sendmail.side_effect = exc
				with self.assertRaises(type(exc)):
					self.share(f)

	def test_the_share_and_the_release_send_through_the_same_one_function(self):
		for fn in (lq.certificate_shared, lq.send_release_summary):
			calls = {
				ast.unparse(n.func)
				for n in ast.walk(ast.parse(inspect.getsource(fn)))
				if isinstance(n, ast.Call)
			}
			self.assertIn("_send_summary", calls, fn.__name__)
			self.assertNotIn("frappe.sendmail", calls, fn.__name__)
		self.assertEqual(
			list(inspect.signature(lq.certificate_shared).parameters),
			["certificate_doctype", "certificate", "lot"],
		)


if __name__ == "__main__":
	unittest.main()
