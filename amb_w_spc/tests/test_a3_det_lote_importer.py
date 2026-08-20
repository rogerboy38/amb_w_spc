"""A-3 importer tests — the ruled parameters, provable without a site.

Site-free by construction: the pure functions are extracted from the importer
by AST and exec'd against a stubbed `frappe`, so these run under plain
`python -m unittest` on any interpreter (the pattern this repo already uses for
the T3-v1 suite).  The write-path assertions are CODE READS over the source
text — VMG-A3-2 requires the path be PROVEN by reading, never declared.
"""

import ast
import pathlib
import re
import sys
import types
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve()
IMPORTER = HERE.parents[1] / "sfc_manufacturing" / "importers" / "det_lote_importer.py"
RECONCILER = HERE.parents[1] / "sfc_manufacturing" / "importers" / "det_lote_reconciler.py"
GOLDEN_PY = HERE.parents[1] / "sfc_manufacturing" / "golden_number.py"

DBF_PATH = "/mnt/e/Claude/local-agent-mode-sessions/foxpro-staging/data/det_lote.dbf"

GOLDEN_RE = re.compile(r"^\d{10}$", re.ASCII)


def _load_pure(names):
    """Exec the named module-level defs from the importer against a stub frappe.

    Module-level Assign nodes ride along: the payload builder reads the field-role
    constants, and a def extracted without them raises NameError at call time.
    """
    tree = ast.parse(IMPORTER.read_text(encoding="utf-8"))
    consts = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
    wanted = [n for n in tree.body
              if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert len(wanted) == len(names), f"missing {set(names) - {n.name for n in wanted}}"
    wanted = consts + wanted
    module = ast.Module(body=wanted, type_ignores=[])
    ast.fix_missing_locations(module)
    stub_golden = types.ModuleType("amb_w_spc.sfc_manufacturing.golden_number")
    stub_golden.GOLDEN_RE = GOLDEN_RE
    pkg = types.ModuleType("amb_w_spc")
    sub = types.ModuleType("amb_w_spc.sfc_manufacturing")
    pkg.sfc_manufacturing = sub
    sub.golden_number = stub_golden
    mods = {
        "amb_w_spc": pkg,
        "amb_w_spc.sfc_manufacturing": sub,
        "amb_w_spc.sfc_manufacturing.golden_number": stub_golden,
    }
    ns = {"frappe": mock.MagicMock(name="frappe"), "GOLDEN_RE": GOLDEN_RE,
          "field": __import__("dataclasses").field,
          "dataclass": __import__("dataclasses").dataclass}
    with mock.patch.dict(sys.modules, mods):
        exec(compile(module, str(IMPORTER), "exec"), ns)
    return ns


class TestRuledFunctions(unittest.TestCase):
    """The A-2 ruling, as code."""

    def setUp(self):
        self.ns = _load_pure(["normalize", "is_golden", "level_for", "is_root", "node_name"])

    def test_one_normalization_strips_the_padding(self):
        n = self.ns["normalize"]
        self.assertEqual(n(b"0227001211  "), "0227001211")
        self.assertEqual(n("0227001211  "), "0227001211")
        self.assertEqual(n(b"0227001211"), n(b"0227001211  "))   # GC-2: one bucket

    def test_golden_membership_uses_the_sealed_regex(self):
        g = self.ns["is_golden"]
        self.assertTrue(g(b"0227001211  "))
        self.assertFalse(g(b"recall      "))
        self.assertFalse(g(b"RECALL      "))    # case pair: neither folded, both refused
        self.assertFalse(g(b"            "))
        self.assertFalse(g("022700121"))        # 9 digits
        self.assertFalse(g("０２２７００１２１１"))  # fullwidth: re.ASCII holds

    def test_level_is_the_ruled_function_and_lands_in_the_select(self):
        lv = self.ns["level_for"]
        for subl in ("", "0", "1"):
            self.assertEqual(lv(subl), "1", subl)
        for subl in ("2", "3", "4", "5", "6", "7", "8"):
            self.assertEqual(lv(subl), "2", subl)
        image = {lv(s) for s in ("", "0", "1", "2", "3", "4", "5", "6", "7", "8")}
        self.assertEqual(image, {"1", "2"})                  # ⊆ Select {1,2,3,4}
        self.assertNotIn("0", image)                          # never the ordinal
        self.assertNotIn("8", image)                          # the copy would write this

    def test_node_name_uses_the_sealed_sublot_shape(self):
        nn = self.ns["node_name"]
        self.assertEqual(nn("0227001211", "0"), "0227001211")
        self.assertEqual(nn("0227001211", "1"), "0227001211")
        self.assertEqual(nn("0227001211", "2"), "0227001211-2")
        sublot_re = re.compile(r"^\d{10}-\d+$", re.ASCII)     # golden_number.SUBLOT_ID_RE
        self.assertTrue(sublot_re.match(nn("0227001211", "3")))


class TestIdempotencyKey(unittest.TestCase):
    """VMG-A3-3: a golden-only key silently collapses 1,434 nodes to 1,090."""

    def setUp(self):
        self.ns = _load_pure(["normalize", "level_for", "is_root", "node_name",
                              "LotGroup", "idempotency_key"])

    def test_key_separates_sublots_of_one_golden(self):
        LotGroup, key = self.ns["LotGroup"], self.ns["idempotency_key"]
        a = LotGroup(golden="0227001211", subl="1")
        b = LotGroup(golden="0227001211", subl="2")
        self.assertNotEqual(key(a), key(b))                   # the collapse guard
        self.assertEqual(key(a), "0227001211|1")

    def test_golden_only_key_would_collapse(self):
        LotGroup = self.ns["LotGroup"]
        nodes = [LotGroup(golden="0227001211", subl=s) for s in ("1", "2", "3", "4")]
        self.assertEqual(len({n.golden for n in nodes}), 1)    # what a golden key sees
        self.assertEqual(len({self.ns["idempotency_key"](n) for n in nodes}), 4)


class TestFolioSet(unittest.TestCase):
    """VMG-A3-11: the three multi-folio groups must carry the SET, not a scalar."""

    def setUp(self):
        self.ns = _load_pure(["normalize", "level_for", "is_root", "node_name",
                              "LotGroup", "_folio_note", "build_doc_payload"])

    def test_every_folio_survives_in_the_note(self):
        LotGroup = self.ns["LotGroup"]
        grp = LotGroup(golden="0729111251", subl="1")
        grp.folios = {"1244", "1245", "1246"}
        note = self.ns["_folio_note"](grp)
        for f in ("1244", "1245", "1246"):
            self.assertIn(f, note)

    def test_scalar_folio_field_only_when_unambiguous(self):
        LotGroup, build = self.ns["LotGroup"], self.ns["build_doc_payload"]
        single = LotGroup(golden="0227001211", subl="0"); single.folios = {"290"}
        multi = LotGroup(golden="0303191251", subl="0"); multi.folios = {"1328", "1479"}
        self.assertEqual(build(single, None)["custom_folio_produccion"], 290)
        self.assertNotIn("custom_folio_produccion", build(multi, None))  # no silent pick
        for f in ("1328", "1479"):
            self.assertIn(f, build(multi, None)["processing_notes"])


class TestExplicitFields(unittest.TestCase):
    """Constraints 2 + 8: level and origin are never left to a default."""

    def setUp(self):
        self.ns = _load_pure(["normalize", "level_for", "is_root", "node_name",
                              "LotGroup", "_folio_note", "build_doc_payload"])

    def test_level_and_origin_always_present(self):
        LotGroup, build = self.ns["LotGroup"], self.ns["build_doc_payload"]
        for subl in ("", "0", "1", "2", "8"):
            payload = build(LotGroup(golden="0227001211", subl=subl), None)
            self.assertIn("custom_batch_level", payload)      # COLUMN_DEFAULT='1' guard
            self.assertEqual(payload["custom_batch_origin"], "Migrated")
            self.assertEqual(payload["custom_golden_number"], "0227001211")

    def test_parent_is_absent_rather_than_null_when_unlinked(self):
        LotGroup, build = self.ns["LotGroup"], self.ns["build_doc_payload"]
        payload = build(LotGroup(golden="0227001211", subl="2"), None)
        self.assertNotIn("parent_batch_amb", payload)          # never a broken Link


def _called_names(path):
    """Every attribute/function name INVOKED in a module — code only.

    A text scan cannot tell code from prose: this file's own docstring says
    "never bulk_insert", and a substring check on the source calls that a
    violation.  The AST sees calls; comments and strings are not calls.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    called, kwargs = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute):
                called.add(f.attr)
            elif isinstance(f, ast.Name):
                called.add(f.id)
            for kw in node.keywords:
                if kw.arg:
                    kwargs.add(kw.arg)
        elif isinstance(node, ast.Attribute):
            called.add(node.attr)
    return called, kwargs


class TestWritePathByCodeRead(unittest.TestCase):
    """VMG-A3-2: the write path is PROVEN by reading the source, not declared."""

    def setUp(self):
        self.src = IMPORTER.read_text(encoding="utf-8")
        self.assertGreater(len(self.src), 0, "empty read = broken instrument, not a clean result")
        self.called, self.kwargs = _called_names(IMPORTER)

    def test_positive_control_the_reader_finds_things(self):
        # the AST instrument must be shown able to find calls before it reports none
        for probe in ("insert", "get_doc", "throw"):
            self.assertIn(probe, self.called, f"control probe {probe} must fire")

    def test_inserts_through_the_document_path(self):
        self.assertIn("insert", self.called)
        self.assertIn("doc.insert(", self.src)          # and it is a DOCUMENT insert

    def test_no_fence_bypassing_api_is_CALLED(self):
        for banned in ("bulk_insert", "db_set"):
            self.assertNotIn(banned, self.called, f"{banned} is CALLED — it bypasses the F-0 fence")
        self.assertNotIn("ignore_validate", self.kwargs, "ignore_validate would disable the hooks")
        self.assertNotIn("ignore_validate", self.called)

    def test_prose_may_name_what_the_code_must_not_call(self):
        # the guard above is AST-based precisely so this stays true
        self.assertIn("bulk_insert", self.src, "the docstring names the banned API")
        self.assertNotIn("bulk_insert", self.called)

    def test_fence_ruling_one_the_importer_calls_the_fence_itself(self):
        """Fence ruling ①: the D1a guard returns before the fence at both mint
        sites (:639→:723, :3181→:3238), so the importer must invoke it."""
        self.assertIn("_enforce_l1_golden_fence", self.called,
                      "ruling ① requires the importer to CALL the sealed fence")
        self.assertIn(
            "from amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb import",
            self.src, "the fence must be imported, never re-implemented")
        # and it must be the sealed function, not a local copy of its SQL
        self.assertNotIn("custom_batch_level IS NULL OR", self.src,
                         "the fence's predicate must not be restated here")

    def test_fence_is_called_for_L1_only(self):
        """A level-2 sublot legally repeats its parent's golden (FI6)."""
        tree = ast.parse(self.src)
        fn = [n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "execute"][0]
        guarded = False
        for node in ast.walk(fn):
            if isinstance(node, ast.If):
                test = ast.dump(node.test)
                if "'1'" in test.replace('"', "'") and "level" in test:
                    for sub in ast.walk(node):
                        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                                and sub.func.id == "_enforce_l1_golden_fence"):
                            guarded = True
        self.assertTrue(guarded, "the fence call must sit under a level == '1' guard")

    def test_reconciler_is_read_only(self):
        rec_called, rec_kwargs = _called_names(RECONCILER)
        self.assertIn("get_all", rec_called, "control: the reconciler does read")
        for banned in ("insert", "save", "db_set", "bulk_insert", "delete_doc", "set_value"):
            self.assertNotIn(banned, rec_called, f"the reconciler must not write ({banned})")

    def test_predicate_is_imported_not_reimplemented(self):
        self.assertIn("from amb_w_spc.sfc_manufacturing.golden_number import GOLDEN_RE", self.src)
        body = self.src.split("REQUIRED_FIELDS")[-1]
        self.assertNotIn("re.compile", body, "the golden predicate must not be restated")


class TestAgainstTheRealSource(unittest.TestCase):
    """The ruled counts, re-derived from the source when it is reachable."""

    @classmethod
    def setUpClass(cls):
        cls.available = pathlib.Path(DBF_PATH).exists()
        if cls.available:
            try:
                import dbf  # noqa: F401
            except ImportError:
                cls.available = False

    def setUp(self):
        if not self.available:
            self.skipTest("source DBF or the dbf library is not reachable from this interpreter")

    def test_unit_partition_is_1434_equals_1090_plus_344(self):
        import dbf as dbf_lib
        ns = _load_pure(["normalize", "is_golden", "level_for", "is_root", "node_name"])
        table = dbf_lib.Table(DBF_PATH); table.open()
        try:
            nodes, roots = set(), set()
            for rec in table:
                if dbf_lib.is_deleted(rec):
                    continue
                data = bytes(rec._data)
                lote = ns["normalize"](data[306:318])
                if not ns["is_golden"](lote):
                    continue
                subl = ns["normalize"](data[318:321])
                nodes.add((lote, subl))
                if ns["is_root"](subl):
                    roots.add((lote, subl))
        finally:
            table.close()
        self.assertEqual(len(nodes), 1434)
        self.assertEqual(len(roots), 1090)
        self.assertEqual(len(nodes) - len(roots), 344)
        self.assertEqual(len({g for g, _ in roots}), 1090)   # one root per golden


if __name__ == "__main__":
    unittest.main()
