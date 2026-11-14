# TASKS-342 ruling 75, DB-free: only Quality Manager and Quality User may change Batch AMB.quality_status.
# Every test here fails when the guard body is removed or when it is unhooked from hooks.py.
#
# Run: python -m unittest amb_w_spc.tests.test_quality_status_guard   (no site needed)

import importlib
import types
import unittest
from unittest import mock

from amb_w_spc.sfc_manufacturing.doctype.batch_amb import batch_amb as bam


class Doc:
	def __init__(self, new_status, old_status="<new>", name="BATCH-1"):
		self.name = name
		self._new = new_status
		self._before = None if old_status == "<new>" else types.SimpleNamespace(get=lambda k, d=None, _o=old_status: _o if k == "quality_status" else d)

	def get(self, key, default=None):
		return self._new if key == "quality_status" else default

	def get_doc_before_save(self):
		return self._before


def fake_frappe(roles):
	f = mock.MagicMock()
	f.get_roles.return_value = list(roles)
	f.throw.side_effect = PermissionError
	f.PermissionError = PermissionError
	return f


class Case(unittest.TestCase):
	def guard(self, doc, roles):
		"""-> True when the guard refused"""
		with mock.patch.object(bam, "frappe", fake_frappe(roles)), mock.patch.object(bam, "_", lambda s: s):
			try:
				bam.batch_amb_quality_status_guard(doc, "before_validate")
				return False
			except PermissionError:
				return True


class TestWho(Case):
	def test_quality_manager_and_quality_user_may_change_it(self):
		for role in ("Quality Manager", "Quality User"):
			self.assertFalse(self.guard(Doc("Passed", "Pending"), [role]), role)
		# ... and the same change by everyone else is refused (a stub that never refuses fails here)
		for roles in ([], ["System Manager"], ["RND Manager"], ["System RND"], ["Manufacturing Manager"], ["Manufacturing User"],
				["Quality Inspector"], ["System Manager", "Manufacturing Manager", "Manufacturing User"]):
			self.assertTrue(self.guard(Doc("Passed", "Pending"), roles), roles)

	def test_every_transition_out_of_a_status_is_covered(self):
		for old, new in (("Pending", "Passed"), ("Failed", "Passed"), ("Passed", "Failed"), ("Hold", "Passed"), ("Passed", "Hold"), ("Passed", "Pending")):
			self.assertTrue(self.guard(Doc(new, old), ["Manufacturing User"]), (old, new))
			self.assertFalse(self.guard(Doc(new, old), ["Quality User"]), (old, new))


class TestUnchanged(Case):
	def test_saving_the_batch_without_touching_the_status_is_free_for_everyone(self):
		for st in ("Pending", "Passed", "Failed", "Hold"):
			self.assertFalse(self.guard(Doc(st, st), ["Manufacturing User"]), st)
		# the contrast: the same user changing it is refused
		self.assertTrue(self.guard(Doc("Passed", "Pending"), ["Manufacturing User"]))

	def test_an_empty_status_is_pending(self):
		self.assertFalse(self.guard(Doc(None, "Pending"), ["Manufacturing User"]))
		self.assertFalse(self.guard(Doc("Pending", None), ["Manufacturing User"]))
		self.assertTrue(self.guard(Doc("Passed", None), ["Manufacturing User"]))


class TestNewDocument(Case):
	def test_nobody_else_can_create_a_batch_already_passed(self):
		self.assertTrue(self.guard(Doc("Passed"), ["Manufacturing User"]))
		self.assertTrue(self.guard(Doc("Failed"), ["System Manager"]))
		self.assertFalse(self.guard(Doc(None), ["Manufacturing User"]))        # default
		self.assertFalse(self.guard(Doc("Pending"), ["Manufacturing User"]))   # default, explicit
		self.assertFalse(self.guard(Doc("Passed"), ["Quality Manager"]))


class TestRefusal(Case):
	def test_the_message_says_who_may_and_what_changed(self):
		f = fake_frappe(["Manufacturing User"])
		with mock.patch.object(bam, "frappe", f), mock.patch.object(bam, "_", lambda s: s):
			with self.assertRaises(PermissionError):
				bam.batch_amb_quality_status_guard(Doc("Passed", "Pending", name="B-9"))
		msg = f.throw.call_args.args[0]
		for needle in ("Quality Manager", "Quality User", "B-9", "Pending", "Passed"):
			self.assertIn(needle, msg)


class TestWiring(Case):
	"""Through the real hooks.py: unhook it and these fail."""

	def test_the_guard_is_hooked_at_before_validate_and_refuses_through_the_hook_path(self):
		hooks = importlib.import_module("amb_w_spc.hooks")
		paths = hooks.doc_events["Batch AMB"]["before_validate"]
		self.assertEqual(len(paths), 1)
		mod, _, fn = paths[0].rpartition(".")
		hooked = getattr(importlib.import_module(mod), fn)
		with mock.patch.object(bam, "frappe", fake_frappe(["Manufacturing User"])), mock.patch.object(bam, "_", lambda s: s):
			with self.assertRaises(PermissionError):
				hooked(Doc("Passed", "Pending"), "before_validate")
		with mock.patch.object(bam, "frappe", fake_frappe(["Quality Manager"])), mock.patch.object(bam, "_", lambda s: s):
			hooked(Doc("Passed", "Pending"), "before_validate")

	def test_before_validate_not_validate_so_the_ignore_validate_flag_and_the_controller_do_not_matter(self):
		hooks = importlib.import_module("amb_w_spc.hooks")
		self.assertNotIn("batch_amb_quality_status_guard", " ".join(hooks.doc_events["Batch AMB"]["validate"]))
		self.assertIn("before_validate", hooks.doc_events["Batch AMB"])


if __name__ == "__main__":
	unittest.main()
