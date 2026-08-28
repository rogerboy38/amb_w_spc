# Copyright (c) 2026, AMB and contributors
"""LOOP-5 · THE LOT GRAPH — one node per lot identity, resolvable by any of four
identifier classes.

⭐ WHY A LOOKUP AND NOT A LONGER NAME. GS1's AI(10) batch/lot field caps at 20
characters — the same ceiling that produced LOOP-4's overflow — so the limit is
the standard, not an obstacle to defeat. GS1, general lot practice and FSMA 204's
Traceability Lot Code all converge on the same architecture: the lot code is a
short stable ANCHOR, and genealogy lives in LINKED RECORDS, not in the string.
Any fixed width eventually overflows at some future generation; a lookup never
does. That is Hugh's ruling and this module is its implementation.

⭐⭐ TWO MODULES, TWO HALVES — and the card named only one of them.
The LOOP-5 card said to reuse `amb_lot_identity`. It cannot do this job:
`lot_identity.py` imports nothing but `annotations`, touches no database, and
takes a document you ALREADY HAVE. It is a pure RENDERER. A graph needs the
inverse — an identifier STRING to a node — and that already exists:

    historic_lookup.resolve_historic_number()   FINDS   (amb_w_spc, B-3b item 2)
    lot_identity.resolve() / amb_lot_identity() RENDERS (amb_w_tds, LOOP-1)

⛔ Neither is reimplemented here. A second lookup would be a second source of
truth for identity, which is the whole defect this program has been unwinding.

⚠⚠ PERFORMANCE, STATED RATHER THAN DISCOVERED (VMG-P P-12).
`tabBatch AMB` carries exactly three indexes — PRIMARY(name), creation, modified.
So of the four identifier classes only ONE is a key lookup:

    system name            → PRIMARY KEY          seek
    golden number          → custom_golden_number       NOT INDEXED → full scan
    historic FoxPro number → custom_historic_lot_real   NOT INDEXED → full scan
    customer lot           → child .sales_lot           NOT INDEXED → full scan
    tree walk              → parent_batch_amb           NOT INDEXED → full scan PER NODE

    QUERY COUNT   resolve_lot()      : 1 (name probe) + 3 (historic_lookup) = 4
                  family(depth d)    : 4 + (1 ancestor query per level) + 1 children
                                       query per node visited
    ⇒ a single lookup is O(rows); a family walk is O(rows × nodes visited).

An index on those three columns would turn every scan into a seek. Adding one is
a DDL WRITE and therefore out of scope for a zero-writes tool — named here so it
is a decision for whoever owns schema, not a discovery for whoever runs this at
scale.

⛔⛔ ZERO WRITES, AND THAT INCLUDES NOT LOGGING (VMG-P P-5).
This module never calls `frappe.log_error()`. That is deliberate: `log_error`
INSERTS an `Error Log` row, so a "read-only" tool that logs its own failures
writes on every failure. Errors propagate to the caller instead.

⚠ FOUR SCHEMA TRAPS, each of which returns a FALSE CLEAN if taken the obvious way:
  ① `lft`/`rgt` are 0 on every row — NestedSet is NOT maintained here. A tree
     query using them returns zero and reads as healthy. This module walks
     `parent_batch_amb` and never reads lft/rgt.
  ② `batch_level` is 100% NULL; `custom_batch_level` carries the data.
  ③ `work_order` is 100% NULL; `work_order_ref` carries it and is POLYMORPHIC
     (both 'MFG-WO-…' and 'LOTE-…'), so it is returned verbatim and labelled,
     never parsed into a shape it may not have.
  ④ the two capture fields are CUSTOM FIELDS — git-invisible. `capabilities()`
     reports their presence on the SITE, because a git-scoped check goes green
     on a site where they do not exist.

⛔ EXACT EQUALITY ONLY. No LIKE, no prefix, no fuzzy matching anywhere. A prefix
match on this data collides a lot with its own family code — that is measured,
not hypothetical.
"""

import frappe

from amb_w_spc.sfc_manufacturing.historic_lookup import resolve_historic_number

BATCH = "Batch AMB"
CHILD = "Batch Historic Sales Lot"

#: the four identifier classes, in the order a caller should read them
CLASS_SYSTEM_NAME = "system_name"
CLASS_GOLDEN = "golden"
CLASS_HISTORIC_REAL = "historic_lot_real"
CLASS_SALES_LOT = "sales_lot"

IDENTIFIER_CLASSES = (
    CLASS_SYSTEM_NAME,
    CLASS_GOLDEN,
    CLASS_HISTORIC_REAL,
    CLASS_SALES_LOT,
)


def capabilities():
    """Which identifier classes this SITE can actually answer on.

    ⭐ VMG-P P-13 — delivery is a DB fact, not a git fact. Two of the four
    carriers are Custom Fields created by a patch; a check that reads the git
    tree reports them present on a site where they do not exist. This reads
    `tabCustom Field`, so a caller can tell "no match" apart from "this site
    cannot answer that question at all" — which are different answers and only
    one of them is about the lot.
    """
    def has_field(fieldname):
        if frappe.get_meta(BATCH).get_field(fieldname):
            return True
        return bool(frappe.db.exists("Custom Field", {"dt": BATCH, "fieldname": fieldname}))

    return {
        CLASS_SYSTEM_NAME: True,                              # the primary key, always
        CLASS_GOLDEN: has_field("custom_golden_number"),
        CLASS_HISTORIC_REAL: has_field("custom_historic_lot_real"),
        CLASS_SALES_LOT: bool(frappe.db.exists("DocType", CHILD)),
    }


def resolve_lot(identifier):
    """An identifier string → the matching node names, PER CLASS.

    Returns::

        {"query": <the string as given>,
         "found": bool,
         "matches": {system_name: [...], golden: [...],
                     historic_lot_real: [...], sales_lot: [...]},
         "nodes": [...]}      # the union, de-duplicated, order-stable

    ⛔ EVERY CLASS IS A LIST, EVEN AT n = 1 (VMG-P P-7). This is not tidiness:
    10.4% of lots carry more than one sales lot (max 9), and 12.3% of sales lots
    draw on more than one real lot (max 11). A scalar-shaped return would
    silently drop one of two prod rows that legitimately share a title — the
    exact case a bench cannot construct and therefore cannot test for directly.

    ⚠ "found" is false for an empty or whitespace-only identifier. It never
    means "the first row".
    """
    value = (identifier or "").strip()
    matches = {c: [] for c in IDENTIFIER_CLASSES}
    if not value:
        return {"query": identifier, "found": False, "matches": matches, "nodes": []}

    # ① system name — the only class that is a primary-key lookup
    if frappe.db.exists(BATCH, value):
        matches[CLASS_SYSTEM_NAME] = [value]

    # ②③④ the other three come from the module that already owns them.
    # ⛔ Not re-queried here: a second implementation of this lookup would be a
    # second source of truth for identity (VMG-P P-2).
    hist = resolve_historic_number(value, include_golden=True)
    matches[CLASS_GOLDEN] = list(hist.get("golden") or [])
    matches[CLASS_HISTORIC_REAL] = list(hist.get("scalar") or [])
    matches[CLASS_SALES_LOT] = list(hist.get("sales_lot") or [])

    nodes, seen = [], set()
    for cls in IDENTIFIER_CLASSES:
        for n in matches[cls]:
            if n not in seen:
                seen.add(n)
                nodes.append(n)

    return {
        "query": identifier,
        "found": bool(nodes),
        "matches": matches,
        "nodes": nodes,
    }


def _identity(doc):
    """The ruled identity for a loaded doc, from the LOOP-1 resolver.

    ⛔ The matrix is NOT re-derived here (VMG-P P-3) — `lot_identity` owns it,
    including which surfaces are still deferred. Importing lazily so this module
    degrades to a clear ImportError if amb_w_tds is absent, rather than failing
    at import time on a site that has only amb_w_spc.
    """
    from amb_w_tds.lot_identity import amb_lot_identity, amb_lot_identity_kind

    return {
        "value": amb_lot_identity(doc, "internal"),
        "kind": amb_lot_identity_kind(doc, "internal"),
    }


def node(batch_name):
    """One node: identity family, tree position, documents, provenance.

    ⚠ Tree position is read from `parent_batch_amb` ONLY. `lft`/`rgt` are zero on
    every row here because NestedSet has never been rebuilt on this doctype, so a
    query against them returns nothing and reads as a clean tree.
    """
    if not batch_name or not frappe.db.exists(BATCH, batch_name):
        return None

    doc = frappe.get_doc(BATCH, batch_name)

    sales_lots = [
        r.get("sales_lot")
        for r in (doc.get("custom_historic_sales_lots") or [])
        if (r.get("sales_lot") or "").strip()
    ]

    children = [
        r[0] for r in frappe.db.sql(
            f"select name from `tab{BATCH}` where parent_batch_amb = %s order by name",
            (batch_name,),
        )
    ]

    return {
        "name": doc.name,
        "identity": _identity(doc),
        "identifiers": {
            CLASS_SYSTEM_NAME: doc.name,
            CLASS_GOLDEN: doc.get("custom_golden_number"),
            CLASS_HISTORIC_REAL: doc.get("custom_historic_lot_real"),
            CLASS_SALES_LOT: sales_lots,          # a LIST — 1:N by design
        },
        "tree": {
            "parent": doc.get("parent_batch_amb"),
            "children": children,
            "level": doc.get("custom_batch_level"),   # ⚠ NOT batch_level (100% NULL)
        },
        "documents": {
            # ⚠ work_order_ref is POLYMORPHIC ('MFG-WO-…' and 'LOTE-…'). Returned
            # verbatim and labelled; parsing it into an assumed shape drops rows.
            "work_order_ref": doc.get("work_order_ref"),
            "title": doc.get("title"),
        },
        "provenance": {
            "origin": doc.get("custom_batch_origin"),   # Migrated / Native
            "creation": str(doc.creation) if doc.creation else None,
        },
    }


def family(identifier, max_depth=10):
    """The full picture for whatever `identifier` resolves to.

    ⚠ `max_depth` is a GUARD, not a tuning knob: `parent_batch_amb` is
    unconstrained, so a cycle would otherwise loop forever. If the guard is hit
    the result says so rather than silently returning a truncated ancestry.
    """
    hit = resolve_lot(identifier)
    if not hit["found"]:
        return {"query": identifier, "found": False, "nodes": [], "roots": []}

    out, roots, truncated = [], [], False
    for name in hit["nodes"]:
        n = node(name)
        if not n:
            continue
        ancestors, cur, depth = [], n["tree"]["parent"], 0
        while cur and depth < max_depth:
            ancestors.append(cur)
            cur = frappe.db.get_value(BATCH, cur, "parent_batch_amb")
            depth += 1
        if cur:
            truncated = True
        n["tree"]["ancestors"] = ancestors
        roots.append(ancestors[-1] if ancestors else n["name"])
        out.append(n)

    return {
        "query": identifier,
        "found": True,
        "matched_by": {c: v for c, v in hit["matches"].items() if v},
        "nodes": out,
        "roots": sorted(set(roots)),
        "depth_truncated": truncated,
    }
