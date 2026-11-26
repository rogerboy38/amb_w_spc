# TASKS-384 B2 (spc half), DB-free: the lot record carries a link to its internal certificate (`coa_amb2`,
# Link -> COA AMB2, beside `coa_reference`), and a saved lot's form has a "Certificate" button that asks the
# certificates app for a new certificate of this lot and opens what the server returns.
#
# The button is run under node with a stubbed `frappe` (skipped when node is not installed); the field is read
# from the DocType JSON.
#
# Run: python -m unittest amb_w_spc.tests.test_lot_certificate_link   (no site needed)

import json
import pathlib
import shutil
import subprocess
import unittest

DOCTYPE_DIR = pathlib.Path(__file__).resolve().parent.parent / "sfc_manufacturing" / "doctype" / "batch_amb"
JSON_PATH = DOCTYPE_DIR / "batch_amb.json"
JS_PATH = DOCTYPE_DIR / "batch_amb.js"
METHOD = "amb_w_tds.api.certificate.make_certificate_for_lot"

RUNNER = r"""
const fs = require("fs"), vm = require("vm");
const cfg = JSON.parse(process.argv[1]);
const src = fs.readFileSync(process.argv[2], "utf8");
const out = { handlers: 0, buttons: [], calls: [], routes: [], msgs: [] };
const loose = () => new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => "" : loose()), apply: () => loose() });
const forms = {};
const frappe = {
  ui: { form: { on(dt, h) { forms[dt] = Object.assign(forms[dt] || {}, h); } } },
  call(opts) {
    out.calls.push({ method: opts.method, args: opts.args });
    if (cfg.reply !== undefined) opts.callback(cfg.reply);
  },
  set_route(...a) { out.routes.push(a); },
  msgprint(m) { out.msgs.push(m); },
  provide() {}, require() {}, realtime: loose(), utils: loose(), model: loose(), db: loose(),
};
const ctx = { frappe, __: (s) => s, console: { log() {}, warn() {}, error() {} }, $: loose(), cur_frm: null,
              setTimeout() {}, setInterval() {}, window: {}, document: loose(), flt: Number, cint: Number };
vm.createContext(ctx);
vm.runInContext(src, ctx, { filename: "batch_amb.js" });
out.handlers = Object.keys(forms["Batch AMB"] || {}).length;
const frm = {
  doc: { name: cfg.name, docstatus: 0 },
  is_new: () => cfg.is_new,
  add_custom_button(label, fn, group) { out.buttons.push([label, group || null]); if (label === "Certificate") frm._cert = fn; },
};
if (cfg.via === "function") {
  ctx.add_certificate_button(frm);
} else {
  // the real refresh handler, its other steps made inert: is the button wired for a saved lot only?
  for (const k of Object.keys(ctx)) {
    if (typeof ctx[k] === "function" && k !== "add_certificate_button" && !["__", "$", "flt", "cint", "setTimeout", "setInterval"].includes(k)) ctx[k] = () => {};
  }
  vm.runInContext(cfg.inert.map((n) => `${n} = function () {};`).join("\n"), ctx);
  frm.page = { set_primary_action() {} }; frm.save = () => {};
  forms["Batch AMB"].refresh(frm);
}
if (frm._cert && cfg.click) frm._cert();
console.log(JSON.stringify(out));
"""

# the functions the refresh handler calls besides the certificate button (made inert in the "refresh" runs)
REFRESH_STEPS = [
	"setup_custom_buttons",
	"apply_field_filters",
	"setup_field_dependencies",
	"show_status_indicators",
	"should_auto_generate",
	"generate_batch_code",
	"add_level_specific_buttons",
	"update_weight_totals",
	"add_serial_tracking_buttons",
	"load_batch_announcements",
	"add_debug_button",
]


def fields():
	return json.loads(JSON_PATH.read_text(encoding="utf-8"))["fields"]


def form_order():
	"""Fieldnames in the order the form shows them: by `idx`, a field without one taking its list position
	(what BaseDocument.append gives it when the DocType JSON is imported)."""
	rows = []
	for pos, f in enumerate(fields(), 1):
		rows.append((f.get("idx") or pos, pos, f["fieldname"]))
	return [name for _idx, _pos, name in sorted(rows)]


class TestField(unittest.TestCase):
	def test_coa_amb2_is_a_link_to_the_internal_certificate(self):
		(f,) = [f for f in fields() if f["fieldname"] == "coa_amb2"]
		self.assertEqual((f["fieldtype"], f["options"]), ("Link", "COA AMB2"))
		self.assertFalse(f.get("reqd"))

	def test_it_sits_right_after_coa_reference_which_is_unchanged(self):
		order = form_order()
		self.assertEqual(order.index("coa_amb2"), order.index("coa_reference") + 1)
		(ref,) = [f for f in fields() if f["fieldname"] == "coa_reference"]
		self.assertEqual((ref["fieldtype"], ref["options"]), ("Link", "COA AMB"))

	def test_no_two_fields_share_a_position(self):
		# the new field was given a position of its own: the fields after it moved down by one
		idx = [f["idx"] for f in fields() if f.get("idx")]
		self.assertEqual(len(idx), len(set(idx)))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestButton(unittest.TestCase):
	def run_js(self, **cfg):
		cfg.setdefault("name", "LOTE-00001")
		cfg.setdefault("is_new", False)
		cfg.setdefault("click", True)
		cfg.setdefault("via", "function")
		cfg.setdefault("inert", REFRESH_STEPS)
		p = subprocess.run(
			["node", "-e", RUNNER, json.dumps(cfg), str(JS_PATH)], capture_output=True, text=True, timeout=60
		)
		self.assertEqual(p.returncode, 0, p.stderr)
		return json.loads(p.stdout.strip().splitlines()[-1])

	def test_the_button_calls_the_certificates_app_with_the_lot_and_opens_what_it_returns(self):
		out = self.run_js(reply={"message": {"doctype": "COA AMB2", "name": "COA2-0001"}})
		self.assertIn(["Certificate", "Create"], out["buttons"])
		self.assertEqual(out["calls"], [{"method": METHOD, "args": {"lot": "LOTE-00001"}}])
		self.assertEqual(out["routes"], [["Form", "COA AMB2", "COA2-0001"]])

	def test_it_opens_whichever_type_the_server_chose(self):
		out = self.run_js(reply={"message": {"doctype": "COA AMB", "name": "COA-0007"}})
		self.assertEqual(out["routes"], [["Form", "COA AMB", "COA-0007"]])

	def test_a_refusal_routes_nowhere_and_is_not_replaced_by_a_message_of_ours(self):
		# frappe.call itself shows the server's message; the button adds none and does not navigate
		for reply in (
			{"exc": "ValidationError"},
			{},
			{"message": None},
			{"message": {"doctype": "COA AMB2"}},
		):
			out = self.run_js(reply=reply)
			self.assertEqual(len(out["calls"]), 1)
			self.assertEqual(out["routes"], [], reply)
			self.assertEqual(out["msgs"], [], reply)

	def test_refresh_shows_it_on_a_saved_lot_only(self):
		saved = self.run_js(via="refresh", click=False)
		self.assertGreater(saved["handlers"], 0)
		self.assertIn(["Certificate", "Create"], saved["buttons"])
		new = self.run_js(via="refresh", click=False, is_new=True)
		self.assertNotIn(["Certificate", "Create"], new["buttons"])


if __name__ == "__main__":
	unittest.main()
