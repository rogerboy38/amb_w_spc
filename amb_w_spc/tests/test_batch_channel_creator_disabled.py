"""TASKS-276a (2026-11-03), DB-free: the Server Script "Batch Raven Channel Creator" ships DISABLED (one shared
channel for lot notices replaces the per-lot channels), with its script text untouched."""

import hashlib
import json
import os
import unittest

PKG = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT_SHA256 = "f59dbaaa19545cf3f9c7cbd4b6b9b784d5ba824499fc7a37cc0cb630be46f142"


class TestBatchChannelCreatorDisabled(unittest.TestCase):
	def setUp(self):
		with open(os.path.join(PKG, "fixtures", "server_script.json"), encoding="utf-8") as f:
			(self.row,) = [r for r in json.load(f) if r["name"] == "Batch Raven Channel Creator"]

	def test_it_is_the_after_insert_batch_script(self):
		self.assertEqual((self.row["script_type"], self.row["reference_doctype"], self.row["doctype_event"]),
		                 ("DocType Event", "Batch", "After Insert"))

	def test_it_ships_disabled(self):
		self.assertEqual(self.row["disabled"], 1)

	def test_its_script_text_is_unchanged(self):
		self.assertEqual(hashlib.sha256(self.row["script"].encode("utf-8")).hexdigest(), SCRIPT_SHA256)


if __name__ == "__main__":
	unittest.main()
