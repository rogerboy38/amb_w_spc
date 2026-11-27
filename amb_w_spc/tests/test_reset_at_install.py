# TASKS-390 item 7 (decision 339), DB-free: the install patch `amb_w_spc.patches.v15_9_0.reset_lots_without_certificate`.
#
#   * every Batch AMB not Pending (empty is Pending) with `released_by` empty -> Pending through lot_quality's one
#     writer, with ONE history row "reset at install: no certificate"
#   * a record that cannot carry a row (no plant, or neither item field) is reset all the same by the writer's
#     column write, LISTED in the output and given an Info Comment; never skipped silently
#   * a record on a hand hold is kept by the writer (decision 315) and listed as kept
#   * a record a certificate speaks for, and a Pending one, is not touched
#   * counts before and after are printed; a second run writes nothing
#   * a site without the fields: nothing done, printed; `execute` reloads the two DocTypes first (patches.txt has
#     no sections, so the patch runs before the DocType sync)
#   * the real table: its saves are the writer's (guard pass) and quiet like a release's
#   * a save the lot controller refuses (a ValidationError, e.g. a broken link) is rolled back to its savepoint and
#     the record reset by the column write, LISTED with the refusal and commented; any other error fails the patch,
#     named (review finding 3)
#   * a lot reset although a legacy certificate still names it is counted and listed apart, with the certificate;
#     a site without the certificate DocTypes or fields: not read, said (review finding 5)
#
# Run: python -m unittest amb_w_spc.tests.test_reset_at_install   (no site needed)

import contextlib
import copy
import importlib
import pathlib
import unittest
from unittest import mock

import frappe as real_frappe

from amb_w_spc.patches.v15_9_0 import reset_lots_without_certificate as patch
from amb_w_spc.sfc_manufacturing import lot_quality as lq
from amb_w_spc.tests.test_lot_quality import Db, Table, fake_frappe, rec, site

PATCH = "amb_w_spc.patches.v15_9_0.reset_lots_without_certificate"
PATCHES_TXT = pathlib.Path(lq.__file__).resolve().parents[1] / "patches.txt"


def lot(name, level="1", parent=None, plant="1 (Mix)", item="0227", item_to_manufacture=None, **kw):
	return dict(
		rec(name, level, parent, **kw),
		current_plant2=plant,
		current_item_code=item,
		item_to_manufacture=item_to_manufacture,
	)


class PatchTable(Table):
	"""The in-memory table with what the patch asks beside the writer's seam."""

	def __init__(self, *records, missing=(), refuse=None, standing=None, unread=()):
		super().__init__(*records)
		self.missing, self.comments = list(missing), []
		# {name: exception}: the save of that record writes, then raises it (a validation of the lot controller)
		self.refuse = dict(refuse or {})
		# what `standing_certificates` answers: {lot: [(doctype, certificate, state)]}, [what was not read]
		self.standing, self.unread = dict(standing or {}), list(unread)
		self.savepoints, self._saved_state = [], None

	def missing_fields(self):
		return list(self.missing)

	def records(self):
		return [dict(r) for _n, r in sorted(self.rows.items())]

	def comment(self, name, text):
		self.comments.append((name, text))

	def standing_certificates(self):
		return dict(self.standing), list(self.unread)

	# a savepoint in memory: what the table holds, restored by the rollback
	def savepoint(self):
		self.savepoints.append("savepoint")
		self._saved_state = copy.deepcopy((self.rows, self.history, self.column_writes, self.written_rows))

	def rollback_to_savepoint(self):
		self.savepoints.append("rollback")
		self.rows, self.history, self.column_writes, self.written_rows = copy.deepcopy(self._saved_state)

	def release_savepoint(self):
		self.savepoints.append("release")

	def save(self, name, values, reason=None, note=None, always=False):
		changed = super().save(name, values, reason=reason, note=note, always=always)
		if changed and name in self.refuse:
			raise self.refuse[name]  # after the record and its row were written: the rollback must undo them
		return changed


def legacy():
	return PatchTable(
		lot("P1", status="Passed"),  # set by hand under the old guard
		lot("F1", status="Failed"),
		lot("H1", status="Hold"),
		lot("NOPLANT", status="Passed", plant=None),  # cannot carry a row
		lot("NOITEM", status="Failed", item=None, item_to_manufacture=None),
		lot(
			"ITEM2", status="Passed", item=None, item_to_manufacture="0227"
		),  # the second item field is enough
		lot("OK", status="Passed", source="Own certificate", cert="CERT-1"),  # a certificate speaks for it
		lot("INH", "2", "OK", status="Passed", source="Inherited", cert="CERT-1"),
		lot("PEND"),
		lot("EMPTY", status=""),
		lot("HELD", status="Hold", source="Hold action"),  # a hand hold with no certificate
	)


def run(table):
	lines = []
	with site():
		result = patch.run(table, out=lines.append)
	return result, lines


class TestTheReset(unittest.TestCase):
	def test_every_lot_not_pending_without_a_certificate_is_pending_after(self):
		t = legacy()
		result, _lines = run(t)
		for name in ("P1", "F1", "H1", "ITEM2", "NOPLANT", "NOITEM"):
			self.assertEqual(t.state(name), ("Pending", "", None, None), name)
		self.assertEqual(result["saved"], ["F1", "H1", "ITEM2", "P1"])
		self.assertEqual(result["column"], ["NOITEM", "NOPLANT"])
		self.assertEqual(result["kept"], ["HELD"])

	def test_each_reset_through_the_writer_has_one_history_row_saying_why(self):
		t = legacy()
		run(t)
		for name in ("P1", "F1", "H1", "ITEM2"):
			(row,) = t.rows_of(name)
			self.assertEqual(row.reason, "reset at install: no certificate")
			self.assertEqual(row.after["quality_status"], "Pending")
		self.assertEqual(t.rows_of("P1")[0].before["quality_status"], "Passed")

	def test_a_record_that_cannot_carry_a_row_is_reset_by_the_column_write_listed_and_commented(self):
		t = legacy()
		_result, lines = run(t)
		self.assertEqual((t.rows_of("NOPLANT"), t.rows_of("NOITEM")), ([], []))
		writes = {tuple(names): values for names, values in t.column_writes}
		for name in ("NOPLANT", "NOITEM"):
			self.assertEqual(
				writes[(name,)],
				{
					"quality_status": "Pending",
					"status_source": "",
					"released_by_doctype": None,
					"released_by": None,
					"certificate_status": None,
				},
			)
		comments = dict(t.comments)
		self.assertEqual(set(comments), {"NOPLANT", "NOITEM"})
		self.assertIn(
			"reset at install (TASKS-390, decision 339) from Passed to Pending", comments["NOPLANT"]
		)
		self.assertIn("Current Plant", comments["NOPLANT"])
		self.assertIn("Current Item Code / Item to Manufacture", comments["NOITEM"])
		(listed,) = [line for line in lines if line.startswith("reset WITHOUT a history row")]
		self.assertTrue(listed.endswith(": 2: NOITEM, NOPLANT"), listed)

	def test_certified_pending_and_empty_records_are_not_touched(self):
		t = legacy()
		run(t)
		touched = {h.lot for h in t.history} | {n for names, _v in t.column_writes for n in names}
		self.assertFalse(touched & {"OK", "INH", "PEND", "EMPTY", "HELD"})
		self.assertEqual(t.state("OK"), ("Passed", "Own certificate", "CERT-1", "Passed"))

	def test_a_hand_hold_is_kept_by_the_writer_and_listed(self):
		t = PatchTable(
			lot("HELD", status="Hold", source="Hold action"),
			lot("HELD-NOPLANT", status="Hold", source="Hold action", plant=None),
		)
		result, lines = run(t)
		self.assertEqual(result["kept"], ["HELD", "HELD-NOPLANT"])
		self.assertEqual((t.history, t.column_writes, t.comments), ([], [], []))
		self.assertIn(
			"kept: on a hand hold, which the writer keeps (decision 315): 2: HELD, HELD-NOPLANT", lines
		)

	def test_counts_before_and_after_are_printed(self):
		_result, lines = run(legacy())
		self.assertIn(
			"before: 11 Batch AMB; Pending 2, Passed 5, Failed 2, Hold 2; not Pending with no certificate: 7",
			lines,
		)
		self.assertIn(
			"after: 11 Batch AMB; Pending 8, Passed 2, Failed 0, Hold 1; not Pending with no certificate: 1",
			lines,
		)
		self.assertIn("reset with a history row ('reset at install: no certificate'): 4", lines)

	def test_a_second_run_writes_nothing(self):
		t = legacy()
		run(t)
		history, writes, comments = len(t.history), len(t.column_writes), len(t.comments)
		result, _lines = run(t)
		self.assertEqual((len(t.history), len(t.column_writes), len(t.comments)), (history, writes, comments))
		self.assertEqual((result["saved"], result["column"]), ([], []))
		self.assertEqual(result["before"], result["after"])

	def test_a_site_without_the_fields_nothing_is_done_and_it_says_why(self):
		t = PatchTable(lot("P1", status="Passed"), missing=["status_source", "released_by"])
		result, lines = run(t)
		self.assertEqual(t.state("P1")[0], "Passed")
		self.assertEqual((t.history, t.column_writes, t.comments), ([], [], []))
		self.assertEqual(result["missing"], ["status_source", "released_by"])
		self.assertTrue(
			any("no field status_source, released_by" in line and "nothing done" in line for line in lines)
		)


class TestTheRealTable(unittest.TestCase):
	def test_execute_reloads_the_two_doctypes_then_runs(self):
		f = fake_frappe()
		order = []
		f.reload_doc.side_effect = lambda *a: order.append(("reload", a))
		with (
			mock.patch.object(patch, "frappe", f),
			mock.patch.object(patch, "run", lambda table: order.append(("run", type(table)))),
		):
			patch.execute()
		self.assertEqual(
			order,
			[
				("reload", ("sfc_manufacturing", "doctype", "batch_amb")),
				("reload", ("sfc_manufacturing", "doctype", "batch_processing_history")),
				("run", patch.InstallTable),
			],
		)

	def test_the_reads_of_the_real_table(self):
		f = fake_frappe()
		f.db.has_column.side_effect = lambda dt, field: field != "released_by"
		with mock.patch.object(patch, "frappe", f):
			self.assertEqual(patch.InstallTable().missing_fields(), ["released_by"])
			patch.InstallTable().records()
		f.get_all.assert_called_once_with(
			"Batch AMB", fields=patch.READ_FIELDS, order_by="name asc", limit_page_length=0
		)
		self.assertTrue(
			{"current_plant2", "current_item_code", "item_to_manufacture", *lq.GUARDED_FIELDS}
			<= set(patch.READ_FIELDS)
		)

	def test_the_saves_are_the_writers_and_quiet_like_a_releases(self):
		db = Db(rec("P1", status="Passed"))
		f = db.frappe()
		seen = []
		original = lq.LotTable.save

		def save(self, name, values, **kwargs):
			seen.append((type(self), self.release))
			return original(self, name, values, **kwargs)

		table = patch.InstallTable()
		table.records = lambda: [dict(r) for r in db.rows.values()]
		table.missing_fields = lambda: []
		table.standing_certificates = lambda: ({}, [])
		table.savepoint = table.release_savepoint = table.rollback_to_savepoint = lambda: None
		with site(frappe=f), mock.patch.object(lq.LotTable, "save", save):
			patch.run(table, out=lambda line: None)
		self.assertEqual(db.rows["P1"]["quality_status"], "Pending")
		((_save, name, kwargs, flag, appended),) = db.saves()
		self.assertIs(flag, lq._WRITER)  # the guard's pass: the writer's own save, no hand path
		self.assertEqual(len(appended), 1)
		self.assertIn("reason: reset at install: no certificate", appended[0][1]["comments"])
		self.assertTrue(
			seen and seen[0][1]
		)  # the table carries `release`: is_release_save is true for its saves

	def test_the_comment_is_an_info_comment_on_the_record(self):
		f = fake_frappe()
		with site(frappe=f):
			patch.InstallTable().comment("P1", "text")
		(doc,) = f.get_doc.call_args.args
		self.assertEqual(
			{
				k: doc[k]
				for k in ("doctype", "comment_type", "reference_doctype", "reference_name", "content")
			},
			{
				"doctype": "Comment",
				"comment_type": "Info",
				"reference_doctype": "Batch AMB",
				"reference_name": "P1",
				"content": "text",
			},
		)

	def test_patches_txt_names_it_once_and_after_every_older_patch(self):
		lines = [
			line.strip()
			for line in PATCHES_TXT.read_text(encoding="utf-8").splitlines()
			if line.strip() and not line.strip().startswith("#")
		]
		self.assertEqual(lines.count(PATCH), 1)
		# TASKS-399: newer patches may follow it; every patch before it is older (v15_9_0 and below)
		older = lines[: lines.index(PATCH)]
		self.assertTrue(older)
		minor = lambda line: int(line.split(".")[2].split("_")[1])  # noqa: E731  amb_w_spc.patches.v15_<minor>_<n>
		self.assertTrue(all(minor(line) <= 9 for line in older if line.startswith("amb_w_spc.patches.v15_")))
		self.assertFalse(
			[line for line in lines if line.startswith("[")]
		)  # still the old format: no sections


def broken_link():
	return real_frappe.LinkValidationError("Could not find Work Order: WO-GONE")


class TestARefusedSave(unittest.TestCase):
	"""Review finding 3: one legacy record the lot controller refuses does not stop the migrate."""

	def table(self, error):
		return PatchTable(
			lot("A1", status="Passed"),
			lot("B1", status="Failed"),  # its save is refused
			lot("C1", status="Hold"),
			refuse={"B1": error},
		)

	def test_a_refused_save_is_rolled_back_and_the_record_reset_by_the_column_write(self):
		t = self.table(broken_link())
		result, _lines = run(t)
		for name in ("A1", "B1", "C1"):
			self.assertEqual(t.state(name), ("Pending", "", None, None), name)
		self.assertEqual((result["saved"], result["refused"], result["column"]), (["A1", "C1"], ["B1"], []))
		self.assertEqual(t.rows_of("B1"), [])  # the row of the refused save is undone with it
		self.assertEqual([names for names, _v in t.column_writes], [["B1"]])
		self.assertEqual([len(t.rows_of(n)) for n in ("A1", "C1")], [1, 1])
		self.assertEqual(
			t.savepoints, ["savepoint", "release", "savepoint", "rollback", "savepoint", "release"]
		)

	def test_the_refused_record_is_listed_with_the_refusal_and_commented(self):
		t = self.table(broken_link())
		_result, lines = run(t)
		(listed,) = [line for line in lines if "the writer's save refused" in line]
		self.assertTrue(
			listed.endswith(": 1: B1 (LinkValidationError: Could not find Work Order: WO-GONE)"), listed
		)
		((name, text),) = t.comments
		self.assertEqual(name, "B1")
		self.assertIn("reset at install (TASKS-390, decision 339) from Failed to Pending", text)
		self.assertIn("refused (LinkValidationError: Could not find Work Order: WO-GONE)", text)
		self.assertIn("after: 3 Batch AMB; Pending 3, Passed 0, Failed 0, Hold 0", lines[-1])

	def test_every_validation_error_is_a_refusal_of_the_record(self):
		for error in (
			real_frappe.ValidationError("refused"),
			real_frappe.MandatoryError("missing"),
			real_frappe.DoesNotExistError("gone"),
		):
			with self.subTest(type(error).__name__):
				t = self.table(error)
				result, _lines = run(t)
				self.assertEqual(result["refused"], ["B1"])
				self.assertEqual(t.state("B1")[0], "Pending")

	def test_any_other_error_fails_the_patch_naming_the_record(self):
		for error in (
			real_frappe.DuplicateEntryError("dup"),  # a NameError, not a ValidationError
			real_frappe.QueryDeadlockError("deadlock"),
			real_frappe.ImplicitCommitError("ddl"),  # a ValidationError about the code, not the record
			real_frappe.InReadOnlyMode("read only"),  # a ValidationError about the site
			TypeError("a hook's bug"),
		):
			with self.subTest(type(error).__name__):
				t, lines = self.table(error), []
				with site(), self.assertRaises(type(error)) as raised:
					patch.run(t, out=lines.append)
				self.assertIn("Batch AMB B1", "".join(raised.exception.__notes__))
				self.assertIn("failed on B1: ", lines[-1])
				self.assertNotIn("rollback", t.savepoints)  # not caught: Frappe rolls the whole patch back
				self.assertEqual(t.column_writes, [])

	def test_a_refused_save_on_a_hand_hold_is_kept(self):
		# the writer writes nothing on a hand hold: no document save runs, so there is nothing to refuse
		t = PatchTable(lot("HELD", status="Hold", source="Hold action"), refuse={"HELD": broken_link()})
		result, _lines = run(t)
		self.assertEqual((result["kept"], result["refused"]), (["HELD"], []))

	def test_a_second_run_after_a_refusal_writes_nothing(self):
		t = self.table(broken_link())
		run(t)
		writes, comments = len(t.column_writes), len(t.comments)
		result, _lines = run(t)
		self.assertEqual((len(t.column_writes), len(t.comments)), (writes, comments))
		self.assertEqual((result["saved"], result["refused"], result["column"]), ([], [], []))


# finding 5: what `standing_certificates` answers in these tests
STANDING = {
	"P1": [("COA AMB", "COA-1", "Certificate Shared")],
	"NOPLANT": [("COA AMB2", "COA2-1", "Approved"), ("COA AMB", "COA-2", "Certificate Shared")],
	"OK": [("COA AMB", "CERT-1", "Certificate Shared")],  # not reset: released_by is set
	"HELD": [("COA AMB2", "COA2-9", "Approved")],  # not reset: kept by the writer
}


class TestLotsACertificateStillNames(unittest.TestCase):
	"""Review finding 5: what is reset does not change; these lots are counted and listed apart."""

	def test_they_are_reset_all_the_same(self):
		t, plain = legacy(), legacy()
		t.standing = dict(STANDING)
		result, _lines = run(t)
		plain_result, _ = run(plain)
		self.assertEqual(t.rows, plain.rows)
		for key in ("saved", "column", "refused", "kept"):
			self.assertEqual(result[key], plain_result[key], key)

	def test_they_are_counted_and_listed_with_their_certificates(self):
		t = legacy()
		t.standing = dict(STANDING)
		result, lines = run(t)
		self.assertEqual(result["certified"], ["NOPLANT", "P1"])
		self.assertIn(
			"reset although a certificate names it (the ruling resets by released_by alone): 2: "
			"NOPLANT, certificate COA AMB2 COA2-1 (Approved), certificate COA AMB COA-2 (Certificate Shared); "
			"P1, certificate COA AMB COA-1 (Certificate Shared)",
			lines,
		)

	def test_none_is_said_as_none(self):
		result, lines = run(legacy())
		self.assertEqual(result["certified"], [])
		self.assertIn(
			"reset although a certificate names it (the ruling resets by released_by alone): 0", lines
		)

	def test_what_could_not_be_read_is_said(self):
		t = legacy()
		t.unread = ["COA AMB2 (no such DocType on this site)"]
		_result, lines = run(t)
		self.assertIn("certificates not read: COA AMB2 (no such DocType on this site)", lines)


class TestTheRealCertificateRead(unittest.TestCase):
	def frappe(self, doctypes=("COA AMB", "COA AMB2"), fields=None, rows=None):
		f = fake_frappe()
		f.db.exists.side_effect = lambda dt, name: dt == "DocType" and name in doctypes
		fields = fields or {}

		def meta(doctype):
			m = mock.MagicMock()
			default = ("batch_reference", "approved_by", patch.CERTIFICATE_STATE_FIELDS[doctype])
			m.has_field.side_effect = lambda field: field in fields.get(doctype, default)
			return m

		f.get_meta.side_effect = meta
		rows = rows or {}
		f.get_all.side_effect = lambda doctype, filters, **kw: [
			dict(r)
			for r in rows.get(
				(doctype, filters[patch.CERTIFICATE_STATE_FIELDS[doctype]], filters["docstatus"]), []
			)
		]
		return f

	def read(self, f):
		with mock.patch.object(patch, "frappe", f):
			return patch.InstallTable().standing_certificates()

	def test_both_standing_states_of_both_types_approved_by_a_person(self):
		f = self.frappe(
			rows={
				("COA AMB", "Certificate Shared", 1): [
					{"name": "COA-1", "batch_reference": "L1", "approved_by": "quality-approver"},
					{
						"name": "COA-ADM",
						"batch_reference": "L2",
						"approved_by": "Administrator",
					},  # not a person
				],
				("COA AMB", "Approved", 0): [
					{"name": "COA-3", "batch_reference": "L1", "approved_by": "quality-approver"}
				],
				("COA AMB2", "Approved", 0): [
					{"name": "COA2-1", "batch_reference": "L3", "approved_by": " "}
				],  # no one recorded
			}
		)
		found, unread = self.read(f)
		self.assertEqual(
			found,
			{"L1": [("COA AMB", "COA-1", "Certificate Shared"), ("COA AMB", "COA-3", "Approved")]},
		)
		self.assertEqual(unread, [])
		filters = [
			c.kwargs["filters"] if "filters" in c.kwargs else c.args[1] for c in f.get_all.call_args_list
		]
		self.assertIn(
			{
				"workflow_state_1": "Certificate Shared",
				"docstatus": 1,
				"batch_reference": ["is", "set"],
				"approved_by": ["is", "set"],
			},
			filters,
		)
		self.assertIn(
			{
				"workflow_state": "Approved",
				"docstatus": 0,
				"batch_reference": ["is", "set"],
				"approved_by": ["is", "set"],
			},
			filters,
		)
		self.assertEqual(len(filters), 4)

	def test_a_site_without_the_certificates_app_reads_nothing_and_says_so(self):
		f = self.frappe(doctypes=())
		found, unread = self.read(f)
		self.assertEqual(found, {})
		self.assertEqual(
			unread,
			["COA AMB (no such DocType on this site)", "COA AMB2 (no such DocType on this site)"],
		)
		f.get_all.assert_not_called()
		f.get_meta.assert_not_called()

	def test_a_certificate_type_without_a_field_is_not_read(self):
		f = self.frappe(fields={"COA AMB": ("batch_reference", "approved_by")})
		found, unread = self.read(f)
		self.assertEqual(unread, ["COA AMB (no field workflow_state_1)"])
		self.assertEqual({c.args[0] for c in f.get_all.call_args_list}, {"COA AMB2"})

	def test_the_state_fields_are_the_certificates_apps(self):
		try:
			rules = importlib.import_module("amb_w_tds.certificate_rules")
		except ImportError:
			self.skipTest("amb_w_tds.certificate_rules is not importable here")
		self.assertEqual(dict(rules.STATE_FIELD), patch.CERTIFICATE_STATE_FIELDS)
		self.assertIn((rules.APPROVED, 0), patch.STANDING_STATES)
		for state in rules.SHARED_STATE.values():
			self.assertIn((state, 1), patch.STANDING_STATES)

	def test_the_savepoint_is_frappes(self):
		f = fake_frappe()
		with mock.patch.object(patch, "frappe", f):
			table = patch.InstallTable()
			table.savepoint()
			table.rollback_to_savepoint()
			table.release_savepoint()
		f.db.savepoint.assert_called_once_with(patch.SAVEPOINT)
		f.db.rollback.assert_called_once_with(save_point=patch.SAVEPOINT)
		f.db.release_savepoint.assert_called_once_with(patch.SAVEPOINT)
		self.assertTrue(patch.SAVEPOINT.isidentifier())


if __name__ == "__main__":
	unittest.main()
