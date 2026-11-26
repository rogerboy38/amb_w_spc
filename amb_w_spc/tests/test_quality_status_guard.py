# TASKS-384 B3, DB-free: nobody changes Batch AMB.quality_status by hand, whatever the role. The status, and the
# four fields that say where it came from (status_source, released_by_doctype, released_by, certificate_status),
# are written by the lot's certificate through lot_quality.set_lot_quality_status only. This replaces the role
# guard of TASKS-342 (Quality Manager / Quality User could change it).
# Every test here fails when the guard body is removed or when it is unhooked from hooks.py.
#
# Run: python -m unittest amb_w_spc.tests.test_quality_status_guard   (no site needed)

import importlib
import json
import types
import unittest
from unittest import mock

from amb_w_spc.sfc_manufacturing import lot_quality as lq
from amb_w_spc.sfc_manufacturing.doctype.batch_amb import batch_amb as bam

GUARD_PATH = "amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.batch_amb_quality_status_guard"
EVERY_ROLE_SET = (
	[],
	["Quality Manager"],
	["Quality User"],
	["Quality Manager", "Quality User"],
	["System Manager"],
	["Administrator", "System Manager", "Quality Manager", "Quality User", "RND Manager"],
	["RND Manager"],
	["Manufacturing Manager"],
	["Manufacturing User"],
	["Quality Inspector"],
)


class Refused(Exception):
	pass


class Doc:
	"""A lot record as the guard reads it: its values now, its values before the save, its flags."""

	def __init__(self, new=None, old="<new>", name="BATCH-1", flags=None, **fields):
		self.name = name
		self._now = dict(fields)
		if new is not None:
			self._now["quality_status"] = new
		if old == "<new>":
			self._before = None
		else:
			before = old if isinstance(old, dict) else {"quality_status": old}
			self._before = types.SimpleNamespace(get=lambda k, d=None, _b=before: _b.get(k, d))
		self.flags = {} if flags is None else flags

	def get(self, key, default=None):
		return self._now.get(key, default)

	def get_doc_before_save(self):
		return self._before


def fake_frappe(roles=()):
	f = mock.MagicMock()
	f.get_roles.return_value = list(roles)
	f.throw.side_effect = Refused
	f.ValidationError = Refused
	return f


class Case(unittest.TestCase):
	def guard(self, doc, roles=(), method="before_validate"):
		"""-> True when the guard refused"""
		f = fake_frappe(roles)
		with (
			mock.patch.object(lq, "frappe", f),
			mock.patch.object(bam, "frappe", f),
			mock.patch.object(lq, "_", lambda s: s),
		):
			try:
				bam.batch_amb_quality_status_guard(doc, method)
				return False
			except Refused:
				return True


class TestNobodyByHand(Case):
	def test_a_hand_edit_is_refused_for_every_role(self):
		# the roles the old guard let through (Quality Manager, Quality User, and Administrator who holds them
		# all) are refused like everyone else
		for roles in EVERY_ROLE_SET:
			self.assertTrue(self.guard(Doc("Passed", "Pending"), roles), roles)

	def test_every_transition_is_refused(self):
		for old in lq.LOT_STATUSES:
			for new in lq.LOT_STATUSES:
				if old != new:
					self.assertTrue(self.guard(Doc(new, old), ["Quality Manager"]), (old, new))

	def test_the_fields_that_say_where_the_status_came_from_are_refused_too(self):
		before = {
			"quality_status": "Passed",
			"status_source": "Own certificate",
			"released_by_doctype": "COA AMB2",
			"released_by": "CERT-1",
			"certificate_status": "Passed",
		}
		self.assertFalse(self.guard(Doc(old=before, **before), ["System Manager"]))  # untouched: free
		for fieldname, value in (
			("status_source", "Inherited"),
			("status_source", "Hold action"),
			("status_source", None),
			("released_by_doctype", "COA AMB"),
			("released_by", "CERT-2"),
			("released_by", None),
			("certificate_status", "Failed"),
			("certificate_status", None),
		):
			for roles in (["System Manager"], ["Quality Manager"]):
				now = dict(before, **{fieldname: value})
				self.assertTrue(self.guard(Doc(old=before, **now), roles), (fieldname, value))

	def test_both_lines_refuse_the_one_before_the_save_and_the_one_after_the_write(self):
		for method in ("before_validate", "on_update"):
			self.assertTrue(self.guard(Doc("Passed", "Pending"), ["Quality Manager"], method), method)
			self.assertFalse(self.guard(Doc("Passed", "Passed"), ["Quality Manager"], method), method)


class TestUnchanged(Case):
	def test_saving_the_lot_without_touching_the_status_is_free_for_everyone(self):
		for st in lq.LOT_STATUSES:
			for roles in EVERY_ROLE_SET:
				self.assertFalse(self.guard(Doc(st, st), roles), (st, roles))
		# the contrast: the same user changing it is refused
		self.assertTrue(self.guard(Doc("Passed", "Pending"), ["Manufacturing User"]))

	def test_an_empty_status_is_pending(self):
		self.assertFalse(self.guard(Doc(None, "Pending")))
		self.assertFalse(self.guard(Doc("Pending", None)))
		self.assertTrue(self.guard(Doc("Passed", None)))
		self.assertTrue(self.guard(Doc(None, "Passed")))  # blanking a Passed lot is a change to Pending

	def test_an_empty_source_or_certificate_is_the_same_empty_as_none(self):
		before = {"quality_status": "Pending", "status_source": None, "released_by": None}
		self.assertFalse(
			self.guard(Doc(old=before, quality_status="Pending", status_source="", released_by=""))
		)


class TestNewRecord(Case):
	def test_a_new_lot_record_starts_pending_for_every_role(self):
		for roles in EVERY_ROLE_SET:
			self.assertFalse(self.guard(Doc(None), roles), roles)  # default
			self.assertFalse(self.guard(Doc("Pending"), roles), roles)  # default, explicit
			for st in ("Passed", "Failed", "Hold"):
				self.assertTrue(self.guard(Doc(st), roles), (st, roles))

	def test_a_new_lot_record_cannot_arrive_naming_a_certificate_or_a_source(self):
		for fields in (
			{"released_by": "CERT-1"},
			{"released_by_doctype": "COA AMB2"},
			{"status_source": "Inherited"},
			{"status_source": "Hold action"},
			{"certificate_status": "Passed"},
		):
			self.assertTrue(self.guard(Doc("Pending", **fields), ["Quality Manager"]), fields)
			self.assertTrue(self.guard(Doc("Pending", **fields), ["Quality Manager"], "on_update"), fields)


class TestTheWritersPass(Case):
	def test_the_writers_own_flag_passes_an_update_and_an_insert(self):
		flags = {lq.WRITER_FLAG: lq._WRITER}
		self.assertFalse(self.guard(Doc("Passed", "Pending", flags=dict(flags))))
		self.assertFalse(
			self.guard(Doc("Passed", flags=dict(flags), status_source="Inherited", released_by="C"))
		)
		self.assertFalse(self.guard(Doc("Passed", "Pending", flags=dict(flags)), method="on_update"))

	def test_a_flag_that_is_not_the_writers_object_does_not_pass(self):
		# what a caller can send or set as data: truthy values, the flag's name under another key, a look-alike
		for forged in (
			{lq.WRITER_FLAG: True},
			{lq.WRITER_FLAG: 1},
			{lq.WRITER_FLAG: "1"},
			{lq.WRITER_FLAG: lq.WRITER_FLAG},
			{lq.WRITER_FLAG: object()},
			{lq.WRITER_FLAG: {}},
			json.loads(
				json.dumps({lq.WRITER_FLAG: True, "ignore_validate": True, "ignore_permissions": True})
			),
			{"ignore_validate": True, "ignore_permissions": True, "ignore_mandatory": True},
			{"lot_quality": lq._WRITER},
		):
			self.assertTrue(self.guard(Doc("Passed", "Pending", flags=forged), ["System Manager"]), forged)
			self.assertTrue(self.guard(Doc("Passed", flags=forged), ["System Manager"]), forged)

	def test_a_document_whose_flags_were_replaced_by_something_else_does_not_pass(self):
		for flags in (None, "lot_quality_writer", [lq.WRITER_FLAG], 1):
			doc = Doc("Passed", "Pending")
			doc.flags = flags
			self.assertTrue(self.guard(doc, ["System Manager"]), flags)
		doc = Doc("Passed", "Pending")
		del doc.flags
		self.assertTrue(self.guard(doc, ["System Manager"]))


class TestRefusal(Case):
	def run_guard(self, doc):
		f = fake_frappe(["Quality Manager"])
		with (
			mock.patch.object(lq, "frappe", f),
			mock.patch.object(bam, "frappe", f),
			mock.patch.object(lq, "_", lambda s: s),
		):
			with self.assertRaises(Refused):
				bam.batch_amb_quality_status_guard(doc)
		return f

	def test_the_message_says_what_changed_and_what_to_do_instead(self):
		f = self.run_guard(Doc("Passed", "Pending", name="B-9"))
		msg = f.throw.call_args.args[0]
		for needle in ("B-9", "Pending", "Passed", "certificate", "any role"):
			self.assertIn(needle, msg)
		f.get_roles.assert_not_called()  # the rule does not look at who asks

	def test_a_new_record_gets_the_message_for_a_new_record(self):
		msg = self.run_guard(Doc("Passed", name=None)).throw.call_args.args[0]
		self.assertIn("starts with the quality status Pending", msg)


class TestWiring(Case):
	"""Through the real hooks.py: unhook it and these fail."""

	def setUp(self):
		self.events = importlib.import_module("amb_w_spc.hooks").doc_events["Batch AMB"]

	def hooked(self, path):
		mod, _, fn = path.rpartition(".")
		return getattr(importlib.import_module(mod), fn)

	def test_first_line_before_validate_and_it_refuses_through_the_hook_path(self):
		self.assertEqual(self.events["before_validate"], [GUARD_PATH])
		f = fake_frappe(["Quality Manager"])
		with mock.patch.object(lq, "frappe", f), mock.patch.object(lq, "_", lambda s: s):
			with self.assertRaises(Refused):
				self.hooked(self.events["before_validate"][0])(Doc("Passed", "Pending"), "before_validate")
			self.hooked(self.events["before_validate"][0])(Doc("Passed", "Passed"), "before_validate")

	def test_second_line_first_in_on_update_and_it_refuses_through_the_hook_path(self):
		self.assertEqual(self.events["on_update"][0], GUARD_PATH)
		f = fake_frappe(["Quality Manager"])
		with mock.patch.object(lq, "frappe", f), mock.patch.object(lq, "_", lambda s: s):
			with self.assertRaises(Refused):
				self.hooked(self.events["on_update"][0])(Doc("Failed", "Passed"), "on_update")

	def test_before_validate_not_validate_so_the_ignore_validate_flag_and_the_controller_do_not_matter(self):
		self.assertNotIn("batch_amb_quality_status_guard", " ".join(self.events["validate"]))
		self.assertNotIn("batch_amb_quality_status_guard", " ".join(self.events["before_save"]))

	def test_the_role_list_of_the_old_guard_is_gone(self):
		self.assertFalse(hasattr(bam, "QUALITY_STATUS_ROLES"))


if __name__ == "__main__":
	unittest.main()
