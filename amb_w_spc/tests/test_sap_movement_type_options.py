"""TASKS-272b (2026-11-03), DB-free: amb_w_spc ships the same Stock Entry `custom_sap_movement_type` Custom Field as
rnd_warehouse_management and syncs AFTER it at every migrate, so its options must be the same 16, byte for byte."""

import json
import os
import unittest

PKG = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

OPTIONS = "\n".join([
	"",
	"101 (Plant/General Material Receipt)",
	"102 (Raw Material / Material Receipt)",
	"103 (Finished Goods Delivery / Material Issue)",
	"104 (Semi-Finished Goods Transfer / Material Transfer)",
	"105 (In Transit Transfer / Material Transfer)",
	"106 (Quality Control Transfer / Material Transfer)",
	"107 (MRB Movement / Material Transfer)",
	"108 (Send to Subcontractor / Material Transfer)",
	"109 (Stores Movement / Material Transfer)",
	"261 (FrontFlush - Goods Issue for Production)",
	"281 (Goods Issue for Sampling)",
	"311 (BackFlush - Transfer for Kitting)",
	"313 (Kitting to WIP / Material Transfer for Manufacture)",
	"501 (Receipt without Purchase Order)",
	"545 (Receive from Subcontractor / Material Receipt)",
	"561 (Initial Entry - Stock Balance)",   # the string the 42 submitted Stock Entries on prod store
])


class TestSapMovementTypeOptions(unittest.TestCase):
	def setUp(self):
		with open(os.path.join(PKG, "fixtures", "custom_field.json"), encoding="utf-8") as f:
			(self.cf,) = [c for c in json.load(f) if c["name"] == "Stock Entry-custom_sap_movement_type"]

	def test_select_with_the_sixteen_options(self):
		self.assertEqual(self.cf["fieldtype"], "Select")
		self.assertEqual(self.cf["options"], OPTIONS)
		self.assertEqual(len([o for o in OPTIONS.split("\n") if o]), 16)

	def test_same_options_as_rnd_warehouse_management_if_reachable(self):
		other = os.environ.get("RND_WAREHOUSE_FIXTURES")
		if not other:
			self.skipTest("RND_WAREHOUSE_FIXTURES not set")
		with open(os.path.join(other, "custom_field.json"), encoding="utf-8") as f:
			(theirs,) = [c for c in json.load(f) if c["name"] == "Stock Entry-custom_sap_movement_type"]
		self.assertEqual(theirs["options"], self.cf["options"])
		self.assertEqual(theirs["modified"], self.cf["modified"])


if __name__ == "__main__":
	unittest.main()
