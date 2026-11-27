# TASKS-384 B3, DB-free: nobody changes Batch AMB.quality_status by hand, whatever the role. The status, and the
# four fields that say where it came from (status_source, released_by_doctype, released_by, certificate_status),
# are written by the lot's certificate through lot_quality.set_lot_quality_status only. This replaces the role
# guard of TASKS-342 (Quality Manager / Quality User could change it).
# Every test here fails when the guard body is removed or when it is unhooked from hooks.py.
# TASKS-388, decision 329: no move under a hold. A change of parent_batch_amb is refused when the chain above the
# stored parent or above the new parent holds a record on a hand hold ("Hold action"), and so is a merge that would
# move records out from under a hold or under one (`before_rename`).
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


def fake_frappe(roles=(), stored=None):
	"""`stored`: {name: {"parent_batch_amb", "status_source"}}, the lot records the chain walk of decision 329
	reads (`frappe.db.get_value`); a name not in it does not exist."""
	f = mock.MagicMock()
	f.get_roles.return_value = list(roles)
	f.throw.side_effect = Refused
	f.ValidationError = Refused
	stored = stored or {}
	f.reads = []

	def get_value(doctype, name, fields, as_dict=False):
		assert doctype == "Batch AMB" and as_dict, (doctype, fields)
		f.reads.append(name)
		if name not in stored:
			return None
		return {"name": name, **{k: stored[name].get(k) for k in fields if k != "name"}}

	f.db.get_value.side_effect = get_value
	return f


class Case(unittest.TestCase):
	stored = None  # the lot records the chain walk reads

	def guard(self, doc, roles=(), method="before_validate"):
		"""-> True when the guard refused"""
		f = fake_frappe(roles, self.stored)
		self.last = f
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


INHERITED_STATE = {
	"quality_status": "Passed",
	"status_source": "Inherited",
	"released_by_doctype": "COA AMB2",
	"released_by": "CERT-1",
	"certificate_status": "Passed",
}


class TestTheParentPointer(Case):
	"""Review of TASKS-384, finding 3: a record that carries a certificate's state is not moved by hand."""

	def moved(self, state, old="SUB-1", new="SUB-2", **now):
		before = dict(state, parent_batch_amb=old)
		return Doc(old=before, name="CONT-1", **dict(before, parent_batch_amb=new, **now))

	def test_a_re_parented_inherited_container_is_refused_for_every_role_on_both_lines(self):
		for roles in EVERY_ROLE_SET:
			for method in ("before_validate", "on_update"):
				self.assertTrue(self.guard(self.moved(INHERITED_STATE), roles, method), (roles, method))
		self.assertTrue(self.guard(self.moved(INHERITED_STATE, new=None)))  # taken out of the tree
		self.assertTrue(self.guard(self.moved(INHERITED_STATE, old=None, new="SUB-2")))

	def test_a_record_with_any_state_from_a_certificate_is_refused(self):
		own = dict(INHERITED_STATE, status_source="Own certificate")
		held = dict(INHERITED_STATE, quality_status="Hold", status_source="Hold action")
		for state in (own, held):
			self.assertTrue(self.guard(self.moved(state), ["System Manager"]), state["status_source"])
		# "Inherited" alone refuses, whatever else the row says
		self.assertTrue(self.guard(self.moved({"quality_status": "Passed", "status_source": "Inherited"})))

	def test_a_record_no_certificate_speaks_for_moves_freely(self):
		for state in (
			{},
			{"quality_status": "Pending"},
			{"quality_status": "Hold", "status_source": "Hold action"},  # a hand hold, nothing stored
			{"quality_status": "Passed"},  # a status from before this rule
		):
			self.assertFalse(self.guard(self.moved(state), ["Manufacturing User"]), state)

	def test_a_save_that_does_not_move_the_record_is_free(self):
		self.assertFalse(self.guard(self.moved(INHERITED_STATE, new="SUB-1")))
		self.assertFalse(self.guard(self.moved(INHERITED_STATE, old=None, new="")))
		self.assertFalse(self.guard(self.moved(INHERITED_STATE, new="SUB-1", batch_status="Completed")))

	def test_a_new_record_is_placed_not_moved_and_the_writers_own_save_passes(self):
		self.assertFalse(self.guard(Doc(name=None, parent_batch_amb="SUB-1")))
		doc = self.moved(INHERITED_STATE)
		doc.flags = {lq.WRITER_FLAG: lq._WRITER}
		self.assertFalse(self.guard(doc))

	def test_the_message_says_which_record_which_certificate_and_what_to_do(self):
		f = fake_frappe()
		with mock.patch.object(lq, "frappe", f), mock.patch.object(lq, "_", lambda s: s):
			with self.assertRaises(Refused):
				lq.refuse_hand_change(self.moved(INHERITED_STATE), "before_validate")
		msg = f.throw.call_args.args[0]
		for needle in (
			"CONT-1",
			"SUB-1",
			"SUB-2",
			"COA AMB2 CERT-1",
			"Inherited",
			"The certificate must be rejected first",
			"Pending",
		):
			self.assertIn(needle, msg)

	def test_the_certificate_links_are_not_guarded(self):
		for fieldname in ("coa_reference", "coa_amb2"):
			before = dict(INHERITED_STATE, **{fieldname: "CERT-1"})
			for value in ("CERT-2", None):
				doc = Doc(old=before, **dict(before, **{fieldname: value}))
				self.assertFalse(self.guard(doc, ["Quality User"]), (fieldname, value))


def lot(parent=None, source=None):
	return {"parent_batch_amb": parent, "status_source": source}


# H is on a hand hold; HS is under it, HSS under HS. P and Q are free lots, PS is under P.
STORED = {
	"H": lot(None, "Hold action"),
	"HS": lot("H", "Inherited"),
	"HSS": lot("HS"),
	"P": lot(),
	"PS": lot("P"),
	"Q": lot(None, "Own certificate"),
	"R": lot("P"),  # the record being moved in most tests, as stored
}


class TestNoMoveUnderAHold(Case):
	"""TASKS-388, decision 329: `parent_batch_amb` cannot change while the chain above the stored parent or above
	the new parent holds a record whose status_source is "Hold action"."""

	stored = STORED

	def moved(self, old, new, name="R", **state):
		before = dict(state, parent_batch_amb=old)
		return Doc(old=before, name=name, **dict(before, parent_batch_amb=new))

	def test_a_move_off_a_held_lot_is_refused_for_every_role_on_both_lines(self):
		for old in ("H", "HS", "HSS"):  # the held lot itself, or anywhere above the stored parent
			for roles in EVERY_ROLE_SET:
				for method in ("before_validate", "on_update"):
					self.assertTrue(self.guard(self.moved(old, "P"), roles, method), (old, roles, method))
		self.assertTrue(self.guard(self.moved("HS", None)))  # taken out of the tree
		self.assertTrue(self.guard(self.moved("HS", "Q")))

	def test_a_move_under_a_held_lot_is_refused_for_every_role_on_both_lines(self):
		for new in ("H", "HS", "HSS"):
			for roles in EVERY_ROLE_SET:
				for method in ("before_validate", "on_update"):
					self.assertTrue(self.guard(self.moved("P", new), roles, method), (new, roles, method))
		self.assertTrue(self.guard(self.moved(None, "HSS")))  # a root put under a hold

	def test_the_message_names_the_held_record_and_the_way(self):
		for old, new, needles in (
			("HS", "P", ("R", "HS", "P", "leave the hold on lot record H")),
			("P", "HSS", ("R", "P", "HSS", "come under the hold on lot record H")),
		):
			self.assertTrue(self.guard(self.moved(old, new)))
			msg = self.last.throw.call_args.args[0]
			for needle in (*needles, "until the hold is lifted"):
				self.assertIn(needle, msg)

	def test_a_free_move_passes(self):
		for old, new in (("P", "Q"), ("PS", "Q"), (None, "PS"), ("P", None), ("Q", "P")):
			self.assertFalse(self.guard(self.moved(old, new), ["Manufacturing User"]), (old, new))
		# and the chain walk read both chains to their top
		self.guard(self.moved("PS", "Q"))
		self.assertEqual(self.last.reads, ["PS", "P", "Q"])

	def test_the_record_being_moved_is_not_judged_its_hold_moves_with_it(self):
		self.assertFalse(self.guard(self.moved("P", "Q", quality_status="Hold", status_source="Hold action")))

	def test_a_save_that_does_not_move_the_record_reads_nothing(self):
		self.assertFalse(self.guard(self.moved("HS", "HS")))
		self.assertEqual(self.last.reads, [])

	def test_a_new_record_is_placed_under_a_held_lot_not_moved(self):
		self.assertFalse(self.guard(Doc(name=None, parent_batch_amb="HS")))  # narrowest reading: inserts pass
		self.assertEqual(self.last.reads, [])

	def test_the_loop_guard_ends_the_walk_without_refusing(self):
		loop = dict(STORED, A=lot("B"), B=lot("A"))
		f = fake_frappe(stored=loop)
		with mock.patch.object(lq, "frappe", f), mock.patch.object(lq, "_", lambda s: s):
			self.assertIsNone(lq._hold_on_chain("A"))
			self.assertEqual(f.reads, ["A", "B"])
		self.stored = loop
		self.assertFalse(self.guard(self.moved("A", "P")))
		# a new parent whose chain runs through the record being moved: the walk stops at the record itself
		self.stored = dict(STORED, R=lot("P"), K=lot("R"))
		self.assertFalse(self.guard(self.moved("P", "K")))
		self.assertEqual(self.last.reads, ["P", "K"])
		# a parent that does not exist ends the walk
		self.stored = STORED
		self.assertFalse(self.guard(self.moved("GONE", "P")))

	def test_a_loop_through_a_held_record_refuses(self):
		self.stored = dict(STORED, A=lot("B", "Hold action"), B=lot("A"))
		self.assertTrue(self.guard(self.moved("B", "P")))

	def test_the_refusal_for_a_record_that_carries_a_certificate_stays_first(self):
		self.assertTrue(
			self.guard(self.moved("P", "Q", **INHERITED_STATE))
		)  # no hold anywhere: still refused
		self.assertIn("The certificate must be rejected first", self.last.throw.call_args.args[0])
		self.assertTrue(self.guard(self.moved("HS", "Q", **INHERITED_STATE)))
		self.assertIn("The certificate must be rejected first", self.last.throw.call_args.args[0])

	def test_the_writers_own_save_is_not_judged(self):
		doc = self.moved("HS", "P")
		doc.flags = {lq.WRITER_FLAG: lq._WRITER}
		self.assertFalse(self.guard(doc))


class TestNoMergeUnderAHold(unittest.TestCase):
	"""TASKS-388, decision 329: Frappe's merge rewrites the children's parent_batch_amb by a direct column write and
	deletes the old record, so the merge is refused at `before_rename` when it would move records out from under
	a hold or under one. A plain rename moves nothing."""

	def rename(self, old, new, merge, stored=STORED):
		"""-> True when refused; the call is what Frappe's `Document.hook` makes: f(doc, method, old, new, merge)"""
		f = fake_frappe(stored=stored)
		self.last = f
		doc = Doc(name=old)
		with mock.patch.object(lq, "frappe", f), mock.patch.object(lq, "_", lambda s: s):
			try:
				bam.batch_amb_before_rename(doc, "before_rename", old, new, merge)
				return False
			except Refused:
				return True

	def test_a_merge_of_a_held_lot_is_refused(self):
		self.assertTrue(self.rename("H", "P", True))
		msg = self.last.throw.call_args.args[0]
		for needle in ("H cannot be merged into P", "lot record H is on a hand hold", "Lift the hold first"):
			self.assertIn(needle, msg)

	def test_a_merge_of_a_record_under_a_hold_or_into_one_is_refused(self):
		for old, new in (("HS", "P"), ("HSS", "PS"), ("PS", "H"), ("P", "HSS"), ("R", "HS")):
			self.assertTrue(self.rename(old, new, True), (old, new))

	def test_a_free_merge_and_any_plain_rename_pass(self):
		self.assertFalse(self.rename("PS", "Q", True))
		for old, new in (("H", "H-NEW"), ("HS", "HS-NEW"), ("P", "P-NEW")):
			self.assertFalse(self.rename(old, new, False), (old, new))
			self.assertEqual(self.last.reads, [])

	def test_the_merge_walk_has_the_loop_guard(self):
		self.assertFalse(self.rename("A", "Q", True, stored=dict(STORED, A=lot("B"), B=lot("A"))))

	def test_hooked_at_before_rename(self):
		events = importlib.import_module("amb_w_spc.hooks").doc_events["Batch AMB"]
		self.assertEqual(
			events["before_rename"],
			["amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.batch_amb_before_rename"],
		)
		mod, _, fn = events["before_rename"][0].rpartition(".")
		self.assertIs(getattr(importlib.import_module(mod), fn), bam.batch_amb_before_rename)


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
