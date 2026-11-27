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
#
# Run: python -m unittest amb_w_spc.tests.test_reset_at_install   (no site needed)

import contextlib
import pathlib
import unittest
from unittest import mock

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

	def __init__(self, *records, missing=()):
		super().__init__(*records)
		self.missing, self.comments = list(missing), []

	def missing_fields(self):
		return list(self.missing)

	def records(self):
		return [dict(r) for _n, r in sorted(self.rows.items())]

	def comment(self, name, text):
		self.comments.append((name, text))


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

	def test_patches_txt_names_it_once_and_last(self):
		lines = [
			line.strip()
			for line in PATCHES_TXT.read_text(encoding="utf-8").splitlines()
			if line.strip() and not line.strip().startswith("#")
		]
		self.assertEqual(lines.count(PATCH), 1)
		self.assertEqual(lines[-1], PATCH)
		self.assertFalse(
			[line for line in lines if line.startswith("[")]
		)  # still the old format: no sections


if __name__ == "__main__":
	unittest.main()
