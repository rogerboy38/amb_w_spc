"""T3-v1 unit tests — the five outcomes of assign_golden_number_to_batch.

Site-free by construction: the LIVE function def (last module-level def — the
shadowing lesson) is extracted by AST from batch_amb.py and exec'd against a
stubbed `frappe`, so these tests run under plain `python -m unittest` with no
site bound and no DB. File-level invariant tests (I1/I2/RD) read the source of
both halves directly, ratchet-style.
"""

import ast
import pathlib
import re
import sys
import types
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve()
DOCTYPE_DIR = HERE.parents[1] / "sfc_manufacturing" / "doctype" / "batch_amb"
PY_PATH = DOCTYPE_DIR / "batch_amb.py"
JS_PATH = DOCTYPE_DIR / "batch_amb.js"

GOLDEN_RE = re.compile(r"^\d{10}$")

_golden_mod = types.ModuleType("amb_w_spc.sfc_manufacturing.golden_number")
_golden_mod.GOLDEN_RE = GOLDEN_RE
_pkg = types.ModuleType("amb_w_spc")
_sub = types.ModuleType("amb_w_spc.sfc_manufacturing")
_pkg.sfc_manufacturing = _sub
_sub.golden_number = _golden_mod
_STUB_MODULES = {
    "amb_w_spc": _pkg,
    "amb_w_spc.sfc_manufacturing": _sub,
    "amb_w_spc.sfc_manufacturing.golden_number": _golden_mod,
}


def _load_function():
    """Compile the LIVE assign_golden_number_to_batch against a stub frappe."""
    tree = ast.parse(PY_PATH.read_text(encoding="utf-8"))
    defs = [n for n in tree.body
            if isinstance(n, ast.FunctionDef)
            and n.name == "assign_golden_number_to_batch"]
    assert defs, "function not found"
    fn = defs[-1]                     # Python binds the LAST def
    fn.decorator_list = []            # drop @frappe.whitelist for exec
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)

    stub_frappe = mock.MagicMock(name="frappe")
    ns = {"frappe": stub_frappe}
    with mock.patch.dict(sys.modules, _STUB_MODULES):
        exec(compile(module, str(PY_PATH), "exec"), ns)
        # Card 2: the copier now calls the fence; this loader tests the copier's
        # OWN outcomes, so the fence is a no-op here (it has its own suite).
        ns["_enforce_l1_golden_fence"] = lambda *a, **k: None
        func = ns["assign_golden_number_to_batch"]
        return func, stub_frappe


def _batch(golden="", derived="", item="0334"):
    b = types.SimpleNamespace(
        name="LOTE-TEST-0001",
        custom_golden_number=golden,
        custom_generated_batch_name=derived,
        item_to_manufacture=item,
        save=mock.MagicMock(name="save"),
    )
    return b


def _run(golden="", derived="", item="0334"):
    func, frappe_stub = _load_function()
    batch = _batch(golden, derived, item)
    frappe_stub.get_doc.return_value = batch
    # the in-function GOLDEN_RE import executes at CALL time, so the module
    # stubs must be live around the call, not only around the exec
    with mock.patch.dict(sys.modules, _STUB_MODULES):
        result = func("LOTE-TEST-0001")
    return result, batch


class TestExtractor(unittest.TestCase):
    """Positive control: the extractor finds the live def and it is executable."""

    def test_function_extracts_and_runs(self):
        result, _ = _run(golden="1111111111", derived="1111111111")
        self.assertIn("outcome", result)


class TestFiveOutcomes(unittest.TestCase):

    def test_assigned_from_derived(self):
        r, b = _run(golden="", derived="1234567890")
        self.assertEqual(r["outcome"], "assigned")
        self.assertEqual(r["indicator"], "green")
        self.assertIn("ASSIGNED from computed value: 1234567890", r["message"])
        b.save.assert_called_once()                      # the ONLY writing branch
        self.assertEqual(b.custom_golden_number, "1234567890")

    def test_already_assigned_writes_nothing(self):
        r, b = _run(golden="1111111111", derived="1111111111")
        self.assertEqual(r["outcome"], "already_assigned")
        self.assertEqual(r["indicator"], "blue")
        self.assertIn("ALREADY ASSIGNED: 1111111111", r["message"])
        b.save.assert_not_called()                       # I8

    def test_mismatch_is_a_finding_and_writes_nothing(self):
        r, b = _run(golden="1111111111", derived="2222222222")
        self.assertEqual(r["outcome"], "already_assigned_mismatch")
        self.assertEqual(r["indicator"], "orange")
        self.assertIn("1111111111", r["message"])
        self.assertIn("2222222222", r["message"])
        self.assertIn("FINDING", r["message"])
        self.assertIn("nothing changed", r["message"])
        b.save.assert_not_called()                       # I8 — the warning never writes

    def test_refused_no_derived(self):
        r, b = _run(golden="", derived="", item="0334")
        self.assertEqual(r["outcome"], "refused_no_derived")
        self.assertEqual(r["indicator"], "orange")
        self.assertIn("no computed value present", r["message"])
        b.save.assert_not_called()

    def test_refused_missing_input_names_it(self):
        r, b = _run(golden="", derived="", item="")
        self.assertEqual(r["outcome"], "refused_missing_input")
        self.assertIn("item_to_manufacture", r["message"])   # I5
        b.save.assert_not_called()

    def test_malformed_derived_refused_nothing_written(self):
        r, b = _run(golden="", derived="NOT10DIGIT")
        self.assertEqual(r["outcome"], "refused_malformed_derived")
        self.assertIn("malformed", r["message"])
        b.save.assert_not_called()                       # I7


class TestFileInvariants(unittest.TestCase):
    """Ratchet-style reads of the two halves (I1, I2-in-control, RD, I4)."""

    def setUp(self):
        self.py = PY_PATH.read_text(encoding="utf-8")
        self.js = JS_PATH.read_text(encoding="utf-8")

    def test_I1_random_mint_deleted(self):
        self.assertEqual(self.py.count("random.choices(string.digits, k=10)"), 0)

    def test_I2_control_carries_no_successfully(self):
        # the control's function body, by extraction
        tree = ast.parse(self.py)
        fn = [n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "assign_golden_number_to_batch"][-1]
        body_src = ast.get_source_segment(self.py, fn)
        self.assertNotIn("successfully", body_src)
        # and the JS handler block
        start = self.js.index("Assign Golden Number Button")
        end = self.js.index("Update Planned Qty Button")
        self.assertNotIn("successfully", self.js[start:end])
        self.assertNotIn("Failed to assign", self.js[start:end])

    def test_I4_client_renders_server_sentence_and_indicator(self):
        start = self.js.index("Assign Golden Number Button")
        end = self.js.index("Update Planned Qty Button")
        block = self.js[start:end]
        self.assertIn("message: m.message", block)
        self.assertIn("indicator: m.indicator", block)
        self.assertNotIn("r.message.success", block)

    def test_RD_reload_only_on_assigned(self):
        start = self.js.index("Assign Golden Number Button")
        end = self.js.index("Update Planned Qty Button")
        block = self.js[start:end]
        self.assertEqual(block.count("reload_doc"), 1)
        self.assertIn("m.outcome === 'assigned'", block)


def _load_copier_with_fence():
    """Card 2: extract BOTH defs (copier + fence, each the LAST module-level
    def) into one namespace so the copier's fence call hits the real fence."""
    tree = ast.parse(PY_PATH.read_text(encoding="utf-8"))
    wanted = {}
    for name in ("assign_golden_number_to_batch", "_enforce_l1_golden_fence"):
        defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
        assert defs, name
        fn = defs[-1]
        fn.decorator_list = []
        wanted[name] = fn
    module = ast.Module(body=list(wanted.values()), type_ignores=[])
    ast.fix_missing_locations(module)
    class _FenceRefusal(Exception):
        pass
    stub = mock.MagicMock(name="frappe")
    stub.ValidationError = _FenceRefusal
    def throw(msg, title=None):
        raise _FenceRefusal(str(msg))
    stub.throw.side_effect = throw
    ns = {"frappe": stub, "_": lambda x: x}
    with mock.patch.dict(sys.modules, _STUB_MODULES):
        exec(compile(module, str(PY_PATH), "exec"), ns)
    return ns["assign_golden_number_to_batch"], stub


class TestCard2CopierFence(unittest.TestCase):
    """Card 2 (+2, as carded): the copier refuses a colliding derived value."""

    def _press(self, holder_rows):
        func, stub = _load_copier_with_fence()
        batch = _batch(golden="", derived="1234567890")
        stub.get_doc.return_value = batch
        stub.db.sql.return_value = holder_rows      # the fence's census
        with mock.patch.dict(sys.modules, _STUB_MODULES):
            return func("LOTE-NEW-0001"), batch

    def test_copier_clean_still_assigns(self):
        r, b = self._press([])
        self.assertEqual(r["outcome"], "assigned")
        b.save.assert_called_once()

    def test_copier_collision_refuses_names_both_writes_nothing(self):
        r, b = self._press([("LOTE-26-24-0003",)])
        self.assertEqual(r["outcome"], "refused_collision")     # the RULED sixth outcome
        self.assertEqual(r["indicator"], "orange")
        self.assertIn("1234567890", r["message"])               # the value
        self.assertIn("LOTE-26-24-0003", r["message"])          # the holder
        self.assertIn("Nothing has been written", r["message"]) # K4, the fence's own sentence
        b.save.assert_not_called()                              # nothing written
        self.assertEqual(b.custom_golden_number, "")            # golden untouched


if __name__ == "__main__":
    unittest.main()
