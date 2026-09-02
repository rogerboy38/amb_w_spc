#!/usr/bin/env node
/*
 * Track 5 (2026-09-02) — structural check of the Print Recommended Format
 * handler in batch_amb.js. Not a browser/DOM test (no frappe runtime
 * available standalone); verifies the SOURCE contains exactly what the
 * card specifies: a frappe.ui.Dialog gated to Label Small 8 (Container),
 * exactly 4 Check fields in fixed order with the exact phrase labels,
 * default off, and sample_tags threaded into the print_label_pdf call.
 *
 * Run: node tests/test_track5_print_dialog.js
 */
const fs = require('fs');

const path = 'amb_w_spc/sfc_manufacturing/doctype/batch_amb/batch_amb.js';
const src = fs.readFileSync(path, 'utf8');

let failures = 0;
function check(label, cond, detail) {
    const status = cond ? 'PASS' : 'FAIL';
    console.log(`[${status}] ${label}` + (!cond && detail ? ` -- ${detail}` : ''));
    if (!cond) failures++;
}

// Isolate the handler body (from the button registration to its closing).
const handlerMatch = src.match(
    /Print Recommended Format[\s\S]*?frm\.add_custom_button[\s\S]*?\}, actions_group\);/
);
check('1. handler for Print Recommended Format found', !!handlerMatch);
const body = handlerMatch ? handlerMatch[0] : '';

check('2. contains a frappe.ui.Dialog', /new frappe\.ui\.Dialog/.test(body));

check('3. dialog is gated to Label Small 8 (Container) only',
    /fmt === 'Label Small 8 \(Container\)'/.test(body));

const checkFieldMatches = [...body.matchAll(/fieldtype:\s*'Check'/g)];
check('4. exactly 4 Check fields', checkFieldMatches.length === 4,
    `found ${checkFieldMatches.length}`);

const expectedOrder = [
    'Microbiological Analysis Sample',
    'Customer Retention Sample',
    'Distributor Retention Sample',
    'AMB Wellness Retention',
];
const labelMatches = [...body.matchAll(/\blabel:\s*__\('([^']+)'\)/g)].map(m => m[1]);
check('5. labels present, fixed order',
    JSON.stringify(labelMatches) === JSON.stringify(expectedOrder),
    `got ${JSON.stringify(labelMatches)}`);

const defaultZeroCount = [...body.matchAll(/default:\s*0/g)].length;
check('6. all 4 Check fields default to 0 (off)', defaultZeroCount === 4,
    `found ${defaultZeroCount}`);

check('7. exact phrase text pushed matches the four fixed phrases',
    body.includes("'MICROBIOLOGICAL ANALYSIS SAMPLE'") &&
    body.includes("'CUSTOMER RETENTION SAMPLE'") &&
    body.includes("'DISTRIBUTOR RETENTION SAMPLE'") &&
    body.includes("'AMB WELLNESS RETENTION'") &&
    !body.includes("'AMB WELLNESS RETENTION SAMPLE'")); // the 4th has NO "SAMPLE" suffix

const printCallIdx = body.indexOf("method: 'amb_print.amb_print.api.print_label_pdf'");
const sampleTagsIdx = body.indexOf('sample_tags:', printCallIdx);
check('8. sample_tags threaded into the print_label_pdf call args',
    printCallIdx !== -1 && sampleTagsIdx !== -1 && (sampleTagsIdx - printCallIdx) < 600,
    `printCallIdx=${printCallIdx} sampleTagsIdx=${sampleTagsIdx}`);

check('9. non-Label-Small-8 formats still print directly (no dialog gate skipped)',
    /\} else \{\s*do_print\(null\);\s*\}/.test(body));

console.log(`\n${failures === 0 ? 'ALL PASS' : failures + ' FAILURE(S)'}`);
process.exit(failures ? 1 : 0);
