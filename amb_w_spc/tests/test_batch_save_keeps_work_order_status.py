# TASKS-383 / TASKS-384 (decision 311), DB-free: a Batch AMB save writes no Work Order status, in any docstatus.
# The Work Order is the truth and the lot record follows it. `BatchAMB.on_update` used to write the linked Work
# Order's `status` twice (from `batch_status`, then from `processing_status`) with db_set + commit, whatever the
# order's docstatus: a Completed order read "Draft" after only the lot's quality status was edited. Both writers
# are gone. These tests fail if either comes back, or if any save-time method starts writing a Work Order.
#
# Run: python -m unittest amb_w_spc.tests.test_batch_save_keeps_work_order_status   (no site needed)

import ast
import pathlib
import types
import unittest
from unittest import mock

from amb_w_spc.sfc_manufacturing.doctype.batch_amb import batch_amb as bam

PY_PATH = pathlib.Path(bam.__file__)
GONE = ("update_work_order_status", "update_work_order_processing_status")
# functions that write a Work Order and are NOT on the save path: the on_submit chain (Batch AMB is not
# submittable) and the "Create Work Order" button. Anything else writing `wo` fails the ratchet below.
KNOWN_WORK_ORDER_WRITERS = {"update_work_order_on_completion", "create_work_order_from_batch"}


class WorkOrder:
	"""Stands for the Work Order frappe.get_doc would return; db_set/save are the ways its status could change."""

	def __init__(self, docstatus, status, workflow_state):
		self.name = "WO-1"
		self.docstatus = docstatus
		self.status = status
		self.workflow_state = workflow_state
		self.writes = []

	def db_set(self, field, value=None, **kw):
		self.writes.append((field, value))
		setattr(self, field, value)

	def save(self, *a, **k):
		self.writes.append(("save", None))


def lot(**fields):
	"""A stand-in lot for the REAL on_update; its other steps are inert."""
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
	return doc


def save(doc, wo):
	"""Run the lot's real on_update against `wo`; -> the fake frappe, to read commits and writes."""
	f = mock.MagicMock(name="frappe")
	f.get_doc.return_value = wo
	with mock.patch.object(bam, "frappe", f):
		bam.BatchAMB.on_update(doc)
	return f


class NoWorkOrderStatusWrite(unittest.TestCase):
	def assert_untouched(self, wo, f, status, workflow_state):
		self.assertEqual(wo.writes, [])
		self.assertEqual((wo.status, wo.workflow_state), (status, workflow_state))
		f.db.commit.assert_not_called()
		f.db.set_value.assert_not_called()
		f.db.sql.assert_not_called()
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

	def test_cancelled_work_order_is_left_alone(self):
		wo = WorkOrder(2, "Cancelled", "Cancelled")
		f = save(lot(batch_status="In Progress", processing_status="In Progress"), wo)
		self.assert_untouched(wo, f, "Cancelled", "Cancelled")

	def test_draft_work_order_is_left_alone_too(self):
		# decision 311: the write that TASKS-383 kept for a draft order is removed as well
		for fields in (
			{"batch_status": "In Progress"},
			{"processing_status": "Scheduled"},
			{"batch_status": "In Progress", "processing_status": "On Hold"},
			{"batch_status": "Completed", "processing_status": "Completed"},
		):
			with self.subTest(fields=fields):
				wo = WorkOrder(0, "Draft", "Draft")
				f = save(lot(**fields), wo)
				self.assert_untouched(wo, f, "Draft", "Draft")

	def test_any_docstatus_value_is_left_alone(self):
		for docstatus in (None, "", "x", "0", "1", 0, 1, 2, 1.0, True, False):
			with self.subTest(docstatus=docstatus):
				wo = WorkOrder(docstatus, "Not Started", "Scheduled")
				f = save(lot(batch_status="Completed", processing_status="Completed"), wo)
				self.assert_untouched(wo, f, "Not Started", "Scheduled")

	def test_the_save_does_not_even_load_the_work_order(self):
		f = save(
			lot(batch_status="In Progress", processing_status="Completed"),
			WorkOrder(1, "Completed", "Scheduled"),
		)
		f.get_doc.assert_not_called()


class SourceRatchet(unittest.TestCase):
	"""The file itself: Python binds the LAST def of a name, so the absence is checked on every def."""

	def setUp(self):
		self.tree = ast.parse(PY_PATH.read_text(encoding="utf-8"))
		self.cls = [n for n in self.tree.body if isinstance(n, ast.ClassDef) and n.name == "BatchAMB"][-1]

	def test_the_two_writers_are_gone_and_nothing_calls_them(self):
		names = {n.name for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)}
		called = {
			n.func.attr
			for n in ast.walk(self.tree)
			if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
		}
		for name in GONE:
			with self.subTest(name=name):
				self.assertNotIn(name, names)
				self.assertNotIn(name, called)

	def test_on_update_calls_only_its_two_remaining_steps(self):
		defs = [n for n in self.cls.body if isinstance(n, ast.FunctionDef) and n.name == "on_update"]
		self.assertEqual(len(defs), 1)
		called = {
			n.func.attr
			for n in ast.walk(defs[0])
			if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
		}
		self.assertEqual(called, {"sync_with_lote_amb", "log_batch_history"})

	def test_only_the_known_off_save_functions_write_a_work_order(self):
		writers = set()
		for fn in ast.walk(self.tree):
			if not isinstance(fn, ast.FunctionDef):
				continue
			for n in ast.walk(fn):
				if (
					isinstance(n, ast.Call)
					and isinstance(n.func, ast.Attribute)
					and n.func.attr in ("db_set", "save", "submit", "insert", "cancel")
					and isinstance(n.func.value, ast.Name)
					and n.func.value.id in ("wo", "wo_doc", "work_order")
				):
					writers.add(fn.name)
		self.assertEqual(writers, KNOWN_WORK_ORDER_WRITERS)

	def test_no_direct_column_write_to_work_order(self):
		src = PY_PATH.read_text(encoding="utf-8")
		for needle in (
			'set_value("Work Order"',
			"set_value('Work Order'",
			"`tabWork Order` SET",
			"UPDATE `tabWork Order`",
		):
			with self.subTest(needle=needle):
				self.assertNotIn(needle, src)
