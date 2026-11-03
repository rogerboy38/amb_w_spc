"""DB-free: Stock Entry `custom_sap_movement_type` stores "<code> (<label>)"; amb_w_spc's CustomStockEntry used to
compare it to bare "261"/"311", so every real value was "Invalid SAP Movement Type" (and the 311/261 signature checks
never fired). frappe/erpnext are stubbed; the real stock_entry.py is loaded."""

import importlib.util
import json
import os
import sys
import types
import unittest
from unittest import mock

PKG = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WM = os.path.join(PKG, "sfc_manufacturing", "warehouse_management")


class Thrown(Exception):
	pass


def _load():
	frappe = mock.MagicMock()
	frappe._ = lambda s: s
	frappe.throw = mock.Mock(side_effect=Thrown)
	stubs = {
		"frappe": frappe,
		"frappe.utils": mock.MagicMock(),
		"erpnext": mock.MagicMock(),
		"erpnext.stock": mock.MagicMock(),
		"erpnext.stock.doctype": mock.MagicMock(),
		"erpnext.stock.doctype.stock_entry": mock.MagicMock(),
		"erpnext.stock.doctype.stock_entry.stock_entry": types.SimpleNamespace(StockEntry=object),
	}
	for name, path in (("amb_w_spc", PKG), ("amb_w_spc.sfc_manufacturing", os.path.join(PKG, "sfc_manufacturing")),
	                   ("amb_w_spc.sfc_manufacturing.warehouse_management", WM)):
		m = types.ModuleType(name)
		m.__path__ = [path]
		stubs[name] = m
	with mock.patch.dict(sys.modules, stubs):
		spec = importlib.util.spec_from_file_location("_amb_stock_entry_under_test", os.path.join(WM, "stock_entry.py"))
		mod = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(mod)
		codes = importlib.import_module("amb_w_spc.sfc_manufacturing.warehouse_management.sap_movement_codes")
	return mod, frappe, codes


def _entry(value, **kw):
	ns = types.SimpleNamespace(custom_sap_movement_type=value, purpose=None, items=[],
	                           custom_warehouse_supervisor_signature=None, custom_kitting_supervisor_signature=None, **kw)
	ns.validate_warehouse_types = lambda mapping: None
	return ns


class TestSapCode(unittest.TestCase):
	def test_sap_code(self):
		_, _, codes = _load()
		self.assertEqual(codes.sap_code("311 (BackFlush - Transfer for Kitting)"), "311")
		self.assertEqual(codes.sap_code("311"), "311")
		self.assertEqual(codes.sap_code(None), "")
		self.assertEqual(codes.sap_code(""), "")

	def test_known_codes_are_the_fixture_options(self):
		_, _, codes = _load()
		with open(os.path.join(PKG, "fixtures", "custom_field.json"), encoding="utf-8") as f:
			(cf,) = [c for c in json.load(f) if c["name"] == "Stock Entry-custom_sap_movement_type"]
		fixture_codes = {codes.sap_code(o) for o in cf["options"].split("\n") if o}
		self.assertEqual(set(codes.KNOWN_CODES), fixture_codes)
		self.assertEqual(len(fixture_codes), 16)


class TestValidate(unittest.TestCase):
	def setUp(self):
		self.mod, self.frappe, _ = _load()
		self.cls = self.mod.CustomStockEntry

	def test_labelled_261_and_311_are_valid_and_get_their_purpose(self):
		for value, purpose in (("261 (FrontFlush - Goods Issue for Production)", "Material Issue"),
		                       ("311 (BackFlush - Transfer for Kitting)", "Material Transfer")):
			se = _entry(value)
			self.cls.validate_sap_movement_type(se)
			self.assertEqual(se.purpose, purpose)
		self.frappe.throw.assert_not_called()

	def test_every_other_option_is_valid_and_untouched(self):
		for value in ("561 (Initial Entry - Stock Balance)", "101 (Plant/General Material Receipt)",
		              "281 (Goods Issue for Sampling)", "545 (Receive from Subcontractor / Material Receipt)"):
			se = _entry(value)
			self.cls.validate_sap_movement_type(se)
			self.assertIsNone(se.purpose, value)
		self.frappe.throw.assert_not_called()

	def test_bare_codes_still_work(self):
		self.cls.validate_sap_movement_type(_entry("311"))
		self.cls.validate_sap_movement_type(_entry("561"))
		self.frappe.throw.assert_not_called()

	def test_unknown_value_is_still_rejected(self):
		for value in ("999 (Nope)", "601 (Goods Issue to Customer)", "abc"):
			with self.assertRaises(Thrown, msg=value):
				self.cls.validate_sap_movement_type(_entry(value))

	def test_empty_is_a_no_op(self):
		self.cls.validate_sap_movement_type(_entry(None))
		self.frappe.throw.assert_not_called()


class TestSignatures(unittest.TestCase):
	def setUp(self):
		self.mod, self.frappe, _ = _load()
		self.cls = self.mod.CustomStockEntry

	def test_labelled_311_requires_both_signatures(self):
		se = _entry("311 (BackFlush - Transfer for Kitting)")
		with self.assertRaises(Thrown):
			self.cls.validate_required_signatures(se)
		se.custom_warehouse_supervisor_signature = "x"
		with self.assertRaises(Thrown):
			self.cls.validate_required_signatures(se)
		se.custom_kitting_supervisor_signature = "y"
		self.cls.validate_required_signatures(se)

	def test_labelled_261_requires_warehouse_signature(self):
		se = _entry("261 (FrontFlush - Goods Issue for Production)")
		with self.assertRaises(Thrown):
			self.cls.validate_required_signatures(se)
		se.custom_warehouse_supervisor_signature = "x"
		self.cls.validate_required_signatures(se)

	def test_other_codes_need_no_signature(self):
		self.cls.validate_required_signatures(_entry("561 (Initial Entry - Stock Balance)"))


if __name__ == "__main__":
	unittest.main()
