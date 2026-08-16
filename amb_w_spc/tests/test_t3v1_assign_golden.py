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

GOLDEN_PY_PATH = HERE.parents[1] / "sfc_manufacturing" / "golden_number.py"


def _load_golden_defs():
    """AST-load the frappe-free Rung 4 helpers from the REAL module.

    Returns whatever exists — at pre-Rung-4 bases the dict is empty, so the
    stub wiring below stays conditional (a missing def must fail as a RED
    test, never as a collection artifact)."""
    tree = ast.parse(GOLDEN_PY_PATH.read_text(encoding="utf-8"))
    wanted = [n for n in tree.body
              if (isinstance(n, ast.FunctionDef)
                  and n.name in ("mint_year_yy", "yy_in_window",
                                 "wo_tail_consecutive"))
              or (isinstance(n, ast.Assign)
                  and any(getattr(t, "id", "") == "GOLDEN_YY_FLOOR"
                          for t in n.targets))]
    module = ast.Module(body=wanted, type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, str(GOLDEN_PY_PATH), "exec"), ns)
    # __builtins__ stays in ns — the compiled defs keep ns as __globals__ and
    # their in-function imports need it at call time. Callers filter by name.
    return ns


_real_golden = _load_golden_defs()

_golden_mod = types.ModuleType("amb_w_spc.sfc_manufacturing.golden_number")
_golden_mod.GOLDEN_RE = GOLDEN_RE
for _k in ("mint_year_yy", "yy_in_window", "wo_tail_consecutive",
           "GOLDEN_YY_FLOOR"):
    if _k in _real_golden:
        setattr(_golden_mod, _k, _real_golden[_k])
_projection_mod = types.ModuleType("amb_w_spc.sfc_manufacturing.batch_projection")
_projection_mod.is_projection_enabled = lambda: False
_pkg = types.ModuleType("amb_w_spc")
_sub = types.ModuleType("amb_w_spc.sfc_manufacturing")
_pkg.sfc_manufacturing = _sub
_sub.golden_number = _golden_mod
_sub.batch_projection = _projection_mod
_STUB_MODULES = {
    "amb_w_spc": _pkg,
    "amb_w_spc.sfc_manufacturing": _sub,
    "amb_w_spc.sfc_manufacturing.golden_number": _golden_mod,
    "amb_w_spc.sfc_manufacturing.batch_projection": _projection_mod,
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
    # AF-1: real frappe.throw APPENDS a red message_log entry BEFORE raising
    # (messages.py:117-118); mirror that so the leak class is visible under test.
    stub.message_log = []
    def throw(msg, title=None):
        stub.message_log.append({"message": str(msg), "indicator": "red"})
        raise _FenceRefusal(str(msg))
    stub.throw.side_effect = throw
    def clear_last_message():
        if stub.message_log:
            stub.message_log.pop()
    stub.clear_last_message.side_effect = clear_last_message
    ns = {"frappe": stub, "_": lambda x: x}
    with mock.patch.dict(sys.modules, _STUB_MODULES):
        exec(compile(module, str(PY_PATH), "exec"), ns)
    return ns["assign_golden_number_to_batch"], stub


class TestCard2CopierFence(unittest.TestCase):
    """Card 2 (+2, as carded): the copier refuses a colliding derived value."""

    def _press(self, holder_rows):
        func, stub = _load_copier_with_fence()
        self.stub = stub
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
        # AF-1: the throw's red entry must NOT survive the translation — an
        # entry left here ships as _server_messages and repaints the orange red.
        self.assertEqual(self.stub.message_log, [])


def _load_mint_site(name):
    """Compile a LIVE mint-site def (method or module-level) against stub frappe.

    Rung 3 (Q-G b): both loaders bind the LAST def of the name found anywhere
    in the AST (the shadowing lesson, applied to methods too) and neuter the
    fence — the mint clock is what these tests measure, nothing else.
    """
    import datetime as _dt
    tree = ast.parse(PY_PATH.read_text(encoding="utf-8"))
    defs = [n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == name]
    assert defs, f"{name} not found"
    fn = defs[-1]
    fn.decorator_list = []
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    stub = mock.MagicMock(name="frappe")
    ns = {
        "frappe": stub,
        "re": re,
        "datetime": _dt.datetime,
        "_": lambda x: x,
    }
    with mock.patch.dict(sys.modules, _STUB_MODULES):
        exec(compile(module, str(PY_PATH), "exec"), ns)
    if name != "_enforce_l1_golden_fence":
        ns["_enforce_l1_golden_fence"] = lambda *a, **k: None
    ns["_validate_migrated_golden"] = lambda *a, **k: None
    ns["_apply_golden_decomposition"] = lambda *a, **k: None
    return ns[name], stub


class TestRung3MintClock(unittest.TestCase):
    """Rung 3 (+4, as carded): YY comes from the MINT clock at both live sites.

    Q-G ruled (b): YY = the year the lot identity comes into existence.
    A Work Order date is not a mint-time input. Legacy YY never reinterpreted
    (K3) — these tests only mint NEW identities.
    """

    def _this_yy(self):
        import datetime as _dt
        return _dt.datetime.now().strftime("%y")

    def _last_year_date(self):
        import datetime as _dt
        now = _dt.datetime.now()
        return now.replace(year=now.year - 1)

    def _mint_site1(self, wo_start_date):
        func, stub = _load_mint_site("set_batch_naming")
        batch = mock.MagicMock(name="batch")
        batch.custom_batch_level = "1"
        batch.custom_batch_origin = "Native"
        batch.item_to_manufacture = "0433TEST"
        batch.custom_golden_number = ""
        batch.work_order_ref = None
        batch.wo_start_date = wo_start_date
        batch.production_plant = None
        batch.production_plant_name = None
        batch.get_plant_code_for_batch = mock.MagicMock(return_value="1")
        batch.name = "LOTE-RUNG3-0001"
        with mock.patch.dict(sys.modules, _STUB_MODULES):
            func(batch)
        return batch.custom_generated_batch_name

    def _mint_site2(self, planned_start_date):
        func, stub = _load_mint_site("_run_golden_number_logic")
        doc = mock.MagicMock(name="doc")
        doc.custom_batch_level = "1"
        doc.item_to_manufacture = "0433TEST"
        doc.custom_golden_number = ""
        doc.work_order_ref = "MFG-WO-00042.03.25" if planned_start_date else ""
        doc.production_plant_id = None
        doc.production_plant_name = None
        doc.name = "LOTE-RUNG3-0002"
        # dual-field fallbacks: a MagicMock auto-attribute is truthy — pin the
        # alias spellings the function getattr's, or mock reprs leak into YY
        doc.custombatchlevel = None
        doc.itemtomanufacture = None
        doc.workorderref = None
        doc.productionplantname = None
        wo = mock.MagicMock(name="wo")
        wo.planned_start_date = planned_start_date
        stub.get_doc.return_value = wo
        with mock.patch.dict(sys.modules, _STUB_MODULES):
            func(doc)
        return doc.custom_golden_number

    def test_site1_stale_wo_date_mints_this_year(self):
        golden = self._mint_site1(self._last_year_date())
        self.assertEqual(golden[7:9], self._this_yy())   # RED at base: base prefers the WO year

    def test_site1_no_wo_date_mints_this_year(self):
        golden = self._mint_site1(None)
        self.assertEqual(golden[7:9], self._this_yy())   # control: GREEN at base too

    def test_site2_stale_wo_date_mints_this_year(self):
        golden = self._mint_site2(self._last_year_date())
        self.assertEqual(golden[7:9], self._this_yy())   # RED at base: WO planned year overrides

    def test_site2_no_wo_mints_this_year(self):
        golden = self._mint_site2(None)
        self.assertEqual(golden[7:9], self._this_yy())   # control: GREEN at base too


class TestRung4OneMinter(unittest.TestCase):
    """Rung 4: one minter module with teeth — fuse, ASCII, routing, verb."""

    def _real(self, name):
        self.assertIn(name, _real_golden,
                      f"{name} missing from golden_number.py — Rung 4 not applied")
        return _real_golden[name]

    def test_golden_re_rejects_nonascii_digits(self):
        # RED at base: \d without re.ASCII matches fullwidth digits
        src = GOLDEN_PY_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        ns = {"re": re}
        assigns = [n for n in tree.body if isinstance(n, ast.Assign)
                   and any(getattr(t, "id", "") in ("GOLDEN_RE", "SUBLOT_ID_RE")
                           for t in n.targets)]
        module = ast.Module(body=assigns, type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, str(GOLDEN_PY_PATH), "exec"), ns)
        fullwidth = "０１２３４５６７８９"
        self.assertIsNone(ns["GOLDEN_RE"].match(fullwidth))
        self.assertIsNotNone(ns["GOLDEN_RE"].match("0123456789"))
        self.assertIsNone(ns["SUBLOT_ID_RE"].match(fullwidth + "-1"))
        self.assertIsNotNone(ns["SUBLOT_ID_RE"].match("0123456789-1"))

    def test_fuse_window_floor_and_derived_ceiling(self):
        import datetime as _dt
        fuse = self._real("yy_in_window")
        floor = self._real("GOLDEN_YY_FLOOR")
        self.assertEqual(floor, 20)          # measured corpus min, all 4 registers
        self.assertFalse(fuse(floor - 1))
        self.assertTrue(fuse(floor))
        nxt = (_dt.datetime.now().year + 1) % 100
        self.assertTrue(fuse(nxt))           # ceiling derives from the clock
        self.assertFalse(fuse(nxt + 1))
        self.assertFalse(fuse("garbage"))

    def test_sites_route_through_the_one_minter(self):
        # Structural ratchet — RED at base (count 4: dead block's comment +
        # code, site 1, site 2); after Rung 4 only the DEAD :205-shadowed
        # block keeps its comment + code pair.
        src = PY_PATH.read_text(encoding="utf-8")
        self.assertEqual(src.count("[:3]"), 2)
        # Behavioural: both live sites agree with the module's own helpers.
        tail = self._real("wo_tail_consecutive")
        self.assertEqual(tail("MFG-WO-00042.03.25"), "000")
        self.assertEqual(tail(""), "001")
        self.assertEqual(tail(None), "001")

    def test_verb_matches_press(self):
        # Copier press → ASSIGN (RED at base: fence says CREATE everywhere).
        func, stub = _load_copier_with_fence()
        batch = _batch(golden="", derived="1234567890")
        stub.get_doc.return_value = batch
        stub.db.sql.return_value = [("LOTE-26-24-0003",)]
        with mock.patch.dict(sys.modules, _STUB_MODULES):
            r = func("LOTE-NEW-0001")
        self.assertTrue(r["message"].startswith("CANNOT ASSIGN"), r["message"][:40])
        # Fence direct, default verb → CREATE (control: GREEN at base too).
        fence, fstub = _load_mint_site("_enforce_l1_golden_fence")
        captured = {}
        def _throw(msg, title=None):
            captured["msg"] = str(msg)
            raise RuntimeError("refused")
        fstub.throw.side_effect = _throw
        fstub.db.sql.return_value = [("LOTE-26-24-0003",)]
        with self.assertRaises(RuntimeError):
            fence("1234567890", doc_name="LOTE-NEW-0001")
        self.assertTrue(captured["msg"].startswith("CANNOT CREATE"), captured["msg"][:40])

    RAVEN_GOLDEN = HERE.parents[3] / "raven_ai_agent" / "raven_ai_agent" / \
        "skills" / "bom_agent" / "golden.py"

    @unittest.skipUnless(RAVEN_GOLDEN.exists(), "raven_ai_agent not on this bench")
    def test_raven_fuse_mirrors_the_one_fuse(self):
        # Cross-app drift test (the card's condition for shipping a MIRRORED
        # fuse): raven's floor and window must equal golden_number's.
        import datetime as _dt
        tree = ast.parse(self.RAVEN_GOLDEN.read_text(encoding="utf-8"))
        wanted = [n for n in tree.body
                  if (isinstance(n, ast.FunctionDef) and n.name == "_yy_in_window")
                  or (isinstance(n, ast.Assign)
                      and any(getattr(t, "id", "") == "GOLDEN_YY_FLOOR"
                              for t in n.targets))]
        module = ast.Module(body=wanted, type_ignores=[])
        ast.fix_missing_locations(module)
        rns = {}
        exec(compile(module, str(self.RAVEN_GOLDEN), "exec"), rns)
        self.assertIn("GOLDEN_YY_FLOOR", rns, "raven fuse missing — drift")
        self.assertEqual(rns["GOLDEN_YY_FLOOR"], self._real("GOLDEN_YY_FLOOR"))
        amb_fuse = self._real("yy_in_window")
        raven_fuse = rns["_yy_in_window"]
        nxt = (_dt.datetime.now().year + 1) % 100
        for probe in (19, 20, 25, nxt, nxt + 1):
            self.assertEqual(raven_fuse(probe), amb_fuse(probe), probe)


if __name__ == "__main__":
    unittest.main()
