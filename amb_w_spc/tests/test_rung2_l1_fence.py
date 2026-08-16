"""Rung 2 / F-1 unit tests — the L1 create fence (FI10: minimum five, two interpreters).

Site-free: the fence function (LAST module-level def — the shadowing lesson) is
extracted by AST and exec'd against a stubbed frappe. Source-order invariants are
asserted ratchet-style on the file itself.
"""

import ast
import pathlib
import sys
import types
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve()
PY_PATH = HERE.parents[1] / "sfc_manufacturing" / "doctype" / "batch_amb" / "batch_amb.py"


class _Refusal(Exception):
    pass


def _load_fence():
    src = PY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name == "_enforce_l1_golden_fence"]
    assert defs, "fence not found"
    fn = defs[-1]                      # Python binds the LAST def
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    stub = mock.MagicMock(name="frappe")
    def throw(msg, title=None):
        raise _Refusal(str(msg))
    stub.throw.side_effect = throw
    ns = {"frappe": stub, "_": lambda x: x}
    exec(compile(module, str(PY_PATH), "exec"), ns)
    return ns["_enforce_l1_golden_fence"], stub


class TestFenceBehaviour(unittest.TestCase):

    def test_clean_mint_passes(self):
        fence, stub = _load_fence()
        stub.db.sql.return_value = []
        fence("0334069264", doc_name="LOTE-NEW")          # no raise
        stub.db.sql.assert_called_once()

    def test_duplicate_l1_refuses_naming_both(self):
        fence, stub = _load_fence()
        stub.db.sql.return_value = [("LOTE-26-24-0003",)]
        with self.assertRaises(_Refusal) as cm:
            fence("1310058264", doc_name="LOTE-NEW-0001")
        msg = str(cm.exception)
        self.assertIn("1310058264", msg)                  # the value
        self.assertIn("LOTE-26-24-0003", msg)             # the holder
        self.assertIn("LOTE-NEW-0001", msg)               # the refused document
        self.assertIn("Nothing has been written", msg)    # K4, in the sentence itself

    def test_self_update_excluded(self):
        fence, stub = _load_fence()
        stub.db.sql.return_value = []
        fence("0334069264", doc_name="LOTE-26-24-0003")
        args, _kw = stub.db.sql.call_args
        self.assertEqual(args[1], ("0334069264", "LOTE-26-24-0003"))   # K6 param carried
        self.assertIn("name != IFNULL(%s, '')", args[0])               # K6 in the predicate

    def test_empty_golden_no_query(self):
        fence, stub = _load_fence()
        fence("", doc_name="X")
        fence(None, doc_name="X")
        stub.db.sql.assert_not_called()

    def test_null_level_counts_as_l1(self):
        fence, stub = _load_fence()
        stub.db.sql.return_value = []
        fence("0334069264")
        args, _kw = stub.db.sql.call_args
        self.assertIn("custom_batch_level IS NULL OR custom_batch_level IN ('', '1')", args[0])  # K5


class TestSourceInvariants(unittest.TestCase):
    """Ratchet-style: order and scope, on the file itself."""

    def setUp(self):
        self.src = PY_PATH.read_text(encoding="utf-8")
        tree = ast.parse(self.src)
        self.spans = {}
        for n in tree.body:
            if isinstance(n, ast.FunctionDef):
                self.spans[n.name] = (n.lineno, n.end_lineno)
            if isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, ast.FunctionDef):
                        self.spans[f"{n.name}.{m.name}"] = (m.lineno, m.end_lineno)

    def _segment(self, key):
        a, b = self.spans[key]
        return "\n".join(self.src.splitlines()[a - 1:b])

    def test_fence_before_pair_write_both_sites(self):
        for key, write in (("BatchAMB.set_batch_naming",
                            "self.custom_golden_number = base_golden_number"),
                           ("_run_golden_number_logic",
                            "doc.custom_golden_number = golden_number")):
            seg = self._segment(key)
            self.assertIn("_enforce_l1_golden_fence(", seg, key)
            self.assertLess(seg.index("_enforce_l1_golden_fence("),
                            seg.index(write), f"{key}: fence must precede the pair-write")

    def test_inherited_docs_never_reach_fence(self):
        seg = self._segment("BatchAMB.set_batch_naming")
        # the D1a early-return (GOLDEN_RE guard) precedes the fence call
        self.assertLess(seg.index("GOLDEN_RE.match(existing_golden)"),
                        seg.index("_enforce_l1_golden_fence("))

    def test_child_inheritance_untouched(self):
        seg = self._segment("create_child_batch")
        self.assertNotIn("_enforce_l1_golden_fence", seg)     # FI6

    def test_no_regeneration_branch(self):
        # FI1: the fence never mutates — no suffix/retry vocabulary in its CODE.
        # The docstring is stripped first: the invariant's own prose ("no silent
        # suffix…") must not trip the scanner that enforces it.
        tree = ast.parse(self.src)
        fn = [n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "_enforce_l1_golden_fence"][-1]
        body = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                              and isinstance(fn.body[0].value, ast.Constant)) else fn.body
        code = "\n".join(ast.unparse(n) for n in body)
        for banned in ("+ str(", "retry_golden", "regenerate", ".zfill(", "suffix"):
            self.assertNotIn(banned, code)


if __name__ == "__main__":
    unittest.main()
