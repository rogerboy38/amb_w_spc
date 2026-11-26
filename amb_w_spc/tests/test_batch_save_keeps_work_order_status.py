# TASKS-383, DB-free: a Batch AMB save never changes the status of a Work Order that is not a draft.
# `BatchAMB.on_update` used to write the linked Work Order's `status` twice (from `batch_status`, then from
# `processing_status`) with db_set + commit, whatever the order's docstatus: a Completed order read "Draft" after
# only the lot's quality status was edited. Every refusal test here fails when the guard is removed from either
# writer; the draft tests fail if the kept behaviour is dropped.
#
# Run: python -m unittest amb_w_spc.tests.test_batch_save_keeps_work_order_status   (no site needed)

import ast
import pathlib
import types
import unittest
from unittest import mock

from amb_w_spc.sfc_manufacturing.doctype.batch_amb import batch_amb as bam

PY_PATH = pathlib.Path(bam.__file__)
WRITERS = ("update_work_order_status", "update_work_order_processing_status")


class WorkOrder:
	"""Stands for the Work Order frappe.get_doc returns; db_set is the only way its status can change here."""

	def __init__(self, docstatus, status, workflow_state):
		self.name = "WO-1"
		self.docstatus = docstatus
		self.status = status
		self.workflow_state = workflow_state
		self.writes = []

	def db_set(self, field, value=None, **kw):
		self.writes.append((field, value))
		setattr(self, field, value)


def lot(**fields):
	"""A stand-in lot carrying the REAL on_update and the two REAL writers; the other on_update steps are inert."""
	doc = types.SimpleNamespace(
		name="LOTE-1",
		work_order_ref="WO-1",
		batch_status=None,
		processing_status=None,
		quality_status="Pending",
	)
	doc.__dict__.update(fields)
	doc.sync_with_lote_amb = lambda: None
	doc.log_batch_history = lambda *a, **k: None
	for name in WRITERS:
		setattr(doc, name, types.MethodType(getattr(bam.BatchAMB, name), doc))
	return doc


def save(doc, wo):
	"""Run the lot's real on_update against `wo`; -> the fake frappe, to read commits and error logs."""
	f = mock.MagicMock(name="frappe")
	f.get_doc.return_value = wo
	with mock.patch.object(bam, "frappe", f):
		bam.BatchAMB.on_update(doc)
	return f


class SubmittedWorkOrderIsLeftAlone(unittest.TestCase):
	def assert_untouched(self, wo, f, status, workflow_state):
		self.assertEqual(wo.writes, [])
		self.assertEqual((wo.status, wo.workflow_state), (status, workflow_state))
		f.db.commit.assert_not_called()
		f.db.set_value.assert_not_called()
		f.log_error.assert_not_called()

	def test_completed_work_order_keeps_status_and_workflow_state(self):
		# the incident: lot statuses say "Draft", the order is Completed
		wo = WorkOrder(1, "Completed", "Scheduled")
		f = save(lot(batch_status="Draft", processing_status="Draft"), wo)
		self.assert_untouched(wo, f, "Completed", "Scheduled")

	def test_in_process_work_order_keeps_status_and_workflow_state(self):
		for fields in (
			{"batch_status": "Completed", "processing_status": "Completed"},
			{"batch_status": "Draft", "processing_status": "Scheduled"},
			{"batch_status": "Cancelled", "processing_status": "On Hold"},
		):
			with self.subTest(fields=fields):
				wo = WorkOrder(1, "In Process", "Scheduled")
				f = save(lot(**fields), wo)
				self.assert_untouched(wo, f, "In Process", "Scheduled")

	def test_only_the_quality_status_changes(self):
		for wo_status in ("Completed", "In Process", "Not Started", "Stopped", "Closed"):
			for lot_status in (None, "", "Draft"):
				with self.subTest(wo_status=wo_status, lot_status=lot_status):
					wo = WorkOrder(1, wo_status, "Scheduled")
					doc = lot(batch_status=lot_status, processing_status=lot_status, quality_status="Passed")
					f = save(doc, wo)
					self.assert_untouched(wo, f, wo_status, "Scheduled")

	def test_cancelled_work_order_is_left_alone_too(self):
		wo = WorkOrder(2, "Cancelled", "Cancelled")
		f = save(lot(batch_status="In Progress", processing_status="In Progress"), wo)
		self.assert_untouched(wo, f, "Cancelled", "Cancelled")

	def test_a_docstatus_that_is_not_plainly_draft_is_refused(self):
		for docstatus in (None, "", "x", "1", 1.0, True):
			with self.subTest(docstatus=docstatus):
				wo = WorkOrder(docstatus, "Completed", "Scheduled")
				f = save(lot(batch_status="Draft", processing_status="Draft"), wo)
				self.assertEqual(wo.writes, [])
				f.db.commit.assert_not_called()


class DraftWorkOrderBehaviourIsKept(unittest.TestCase):
	"""What the code did before for a draft Work Order (docstatus 0), unchanged."""

	def test_batch_status_still_maps_onto_a_draft_work_order(self):
		wo = WorkOrder(0, "Draft", "Draft")
		save(lot(batch_status="In Progress"), wo)
		self.assertEqual(wo.writes, [("status", "In Process")])

	def test_processing_status_still_maps_onto_a_draft_work_order(self):
		wo = WorkOrder(0, "Draft", "Draft")
		save(lot(processing_status="Scheduled"), wo)
		self.assertEqual(wo.writes, [("status", "Not Started")])

	def test_both_writers_still_run_in_order_and_commit(self):
		wo = WorkOrder(0, "Draft", "Draft")
		f = save(lot(batch_status="In Progress", processing_status="On Hold"), wo)
		self.assertEqual(wo.writes, [("status", "In Process"), ("status", "On Hold")])
		self.assertEqual(f.db.commit.call_count, 2)
		self.assertEqual(wo.workflow_state, "Draft")

	def test_no_write_when_the_draft_status_already_agrees(self):
		wo = WorkOrder(0, "Draft", "Draft")
		f = save(lot(batch_status="Draft", processing_status="Draft"), wo)
		self.assertEqual(wo.writes, [])
		f.db.commit.assert_not_called()

	def test_a_string_zero_docstatus_counts_as_draft(self):
		wo = WorkOrder("0", "Draft", "Draft")
		save(lot(batch_status="In Progress"), wo)
		self.assertEqual(wo.writes, [("status", "In Process")])


class NoLinkedWorkOrder(unittest.TestCase):
	def test_a_lot_without_a_work_order_reads_nothing(self):
		f = mock.MagicMock(name="frappe")
		with mock.patch.object(bam, "frappe", f):
			bam.BatchAMB.on_update(
				lot(work_order_ref=None, batch_status="In Progress", processing_status="Completed")
			)
		f.get_doc.assert_not_called()


class SourceRatchet(unittest.TestCase):
	"""The file itself: Python binds the LAST def of a name, and on_update must still be the only caller."""

	def setUp(self):
		self.tree = ast.parse(PY_PATH.read_text(encoding="utf-8"))
		self.cls = [n for n in self.tree.body if isinstance(n, ast.ClassDef) and n.name == "BatchAMB"][-1]

	def last_method(self, name):
		defs = [n for n in self.cls.body if isinstance(n, ast.FunctionDef) and n.name == name]
		self.assertEqual(len(defs), 1, f"{name} must be defined exactly once")
		return defs[0]

	def test_each_writer_asks_the_guard_before_any_db_set(self):
		for name in WRITERS:
			with self.subTest(writer=name):
				calls = [
					(n.lineno, getattr(n.func, "id", None) or getattr(n.func, "attr", None))
					for n in ast.walk(self.last_method(name))
					if isinstance(n, ast.Call)
				]
				guard = [ln for ln, fn in calls if fn == "_work_order_status_is_ours_to_write"]
				writes = [ln for ln, fn in calls if fn in ("db_set", "set_value", "save", "submit")]
				self.assertEqual(len(guard), 1)
				self.assertTrue(writes and min(writes) > guard[0])

	def test_the_guard_is_defined_once_at_module_level(self):
		defs = [
			n
			for n in self.tree.body
			if isinstance(n, ast.FunctionDef) and n.name == "_work_order_status_is_ours_to_write"
		]
		self.assertEqual(len(defs), 1)

	def test_on_update_still_calls_both_writers(self):
		called = {
			n.func.attr
			for n in ast.walk(self.last_method("on_update"))
			if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
		}
		self.assertTrue(set(WRITERS) <= called)
