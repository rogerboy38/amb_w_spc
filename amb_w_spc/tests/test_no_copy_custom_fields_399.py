# Copyright (c) 2026, AMB and contributors
"""TASKS-399, decision 355: patch v15_10_0 sets "no copy" on the site Custom Fields of Batch AMB, on an in-memory
Custom Field table. DB-free."""

import copy
import unittest
from unittest import mock

from amb_w_spc.patches.v15_10_0 import no_copy_on_batch_amb_custom_fields as patch


class CustomFieldTable:
	"""The Custom Field rows of a site, in memory; records every write."""

	def __init__(self, *rows):
		self.rows = [dict(r) for r in rows]
		self.writes = []
		self.cleared = []

	def frappe(self):
		f = mock.MagicMock()
		f.get_all.side_effect = self.get_all
		f.db.set_value.side_effect = self.set_value
		f.clear_cache.side_effect = lambda doctype=None: self.cleared.append(doctype)
		return f

	def get_all(self, doctype, filters, fields):
		assert doctype == "Custom Field"
		return [
			{k: r.get(k) for k in fields} for r in self.rows if all(r.get(k) == v for k, v in filters.items())
		]

	def set_value(self, doctype, name, fieldname, value, update_modified=True):
		self.writes.append((doctype, name, fieldname, value, update_modified))
		(row,) = [r for r in self.rows if r["name"] == name]
		row[fieldname] = value


def cf(fieldname, no_copy=0, dt="Batch AMB", **more):
	return dict(
		name=f"{dt}-{fieldname}",
		dt=dt,
		fieldname=fieldname,
		no_copy=no_copy,
		label="L",
		insert_after="x",
		**more,
	)


def run(table):
	with mock.patch.object(patch, "frappe", table.frappe()):
		return dict(patch.set_no_copy())


class TestThePatch(unittest.TestCase):
	def test_the_three_cases_absent_already_and_set(self):
		t = CustomFieldTable(cf("output_products"), cf("batch_output_products", no_copy=1))
		out = run(t)
		self.assertEqual(out["output_products"], "set")
		self.assertEqual(out["batch_output_products"], "already 1")
		self.assertEqual(out["custom_historic_sales_lots"], "absent")
		self.assertEqual(out["custom_produced_qty"], "absent")
		self.assertEqual(out["total_net_weight"], "absent")
		self.assertEqual(t.writes, [("Custom Field", "Batch AMB-output_products", "no_copy", 1, False)])
		self.assertEqual(t.cleared, ["Batch AMB"])

	def test_the_three_record_tables_and_every_cleared_header_figure_are_covered(self):
		from amb_w_spc.sfc_manufacturing import lot_quality as lq

		self.assertEqual(
			set(patch.FIELDS),
			{
				"output_products",
				"batch_output_products",
				"custom_historic_sales_lots",
				*lq.COPY_CLEARED_HEADER_FIGURES,
			},
		)
		self.assertEqual(len(patch.FIELDS), 16)
		self.assertEqual(len(set(patch.FIELDS)), len(patch.FIELDS))

	def test_a_second_run_changes_nothing(self):
		t = CustomFieldTable(*(cf(n) for n in patch.FIELDS))
		self.assertEqual(set(run(t).values()), {"set"})
		before, t.writes, t.cleared = copy.deepcopy(t.rows), [], []
		self.assertEqual(set(run(t).values()), {"already 1"})
		self.assertEqual((t.writes, t.cleared, t.rows), ([], [], before))

	def test_no_other_property_and_no_other_row_is_touched(self):
		others = (cf("output_products", dt="Batch AMB2"), cf("planned_qty"), cf("custom_historic_lot_real"))
		t = CustomFieldTable(cf("output_products", reqd=0, hidden=0, read_only=0), *others)
		before = copy.deepcopy(t.rows)
		run(t)
		self.assertEqual({w[2] for w in t.writes}, {"no_copy"})
		for old, new in zip(before, t.rows, strict=True):
			changed = {k for k in old if old[k] != new[k]}
			self.assertEqual(
				changed, {"no_copy"} if old["name"] == "Batch AMB-output_products" else set(), old
			)

	def test_safe_on_a_site_with_none_of_them(self):
		t = CustomFieldTable()
		self.assertEqual(set(run(t).values()), {"absent"})
		self.assertEqual((t.writes, t.cleared), ([], []))

	def test_it_is_registered_once_in_patches_txt(self):
		import pathlib

		lines = (
			(pathlib.Path(patch.__file__).parents[2] / "patches.txt").read_text(encoding="utf-8").splitlines()
		)
		self.assertEqual(lines.count("amb_w_spc.patches.v15_10_0.no_copy_on_batch_amb_custom_fields"), 1)
		self.assertFalse(
			[line for line in lines if line.strip().startswith("[")]
		)  # no sections: pre_model_sync


if __name__ == "__main__":
	unittest.main()
