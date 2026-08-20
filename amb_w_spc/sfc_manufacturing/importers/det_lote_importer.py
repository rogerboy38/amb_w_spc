"""A-3 · the det_lote → Batch AMB importer (genealogy-20260817).

Carries Hugh's A-2 ruling verbatim:

  UNIT     one Batch AMB per (LOTE, SUBL) node — 1,434 = 1,090 roots + 344 sublot
           children, parent_batch_amb linking each child to its root.
  LEVEL    a DERIVED FUNCTION, never a copy:  1 if SUBL in {blank,'0','1'} else 2.
           SUBL is an ORDINAL (which sublot); custom_batch_level is a NODE-KIND
           level.  Copying the ordinal writes values outside the Select domain.
  PATH     doc.insert() so the F-0 fence FIRES (it is a doc_events validate hook,
           gated by flags.ignore_validate, NOT by flags.in_import).
           NEVER bulk_insert / db_set / ignore_validate — each bypasses the fence.
  DANGLING arrows whose consumed golden was never produced stay UNLINKED and are
           ENUMERATED.  No stubs: a stub would be a new L1 root the fence must
           then reason about.

Scope, stated because it is a real ambiguity in the card: `parent_batch_amb` is
written ONLY for the sublot→root hierarchy, which cannot dangle (every child's
root exists by construction).  The PRODUCTO→LOTE *arrows* are the genealogy tree
(G-B's subject) and are NOT written here; the danglers among them are enumerated
in the plan so the count is on the record without a write.

Read side is deleted-aware by construction (`dbf`, is_deleted) — `dbfread`
silently skips deleted rows and cannot see the flag.
"""

from __future__ import annotations

import datetime
import hashlib
import os
from collections import defaultdict
from dataclasses import dataclass, field

import frappe

# THE predicate, imported from the sealed seam — never re-implemented (cargo by
# predicate: a census built on a restatement measures the restatement).
from amb_w_spc.sfc_manufacturing.golden_number import GOLDEN_RE

TARGET_DOCTYPE = "Batch AMB"
ORIGIN_VALUE = "Migrated"

#: field roles, identified by CONTENT (the decoy `batch_level` (Data) sits beside
#: `custom_batch_level` (Select); the fence keys on the second).
F_GOLDEN = "custom_golden_number"
F_LEVEL = "custom_batch_level"
F_ORIGIN = "custom_batch_origin"
F_PARENT = "parent_batch_amb"
F_FOLIO = "custom_folio_produccion"
F_NOTES = "processing_notes"

REQUIRED_FIELDS = (F_GOLDEN, F_LEVEL, F_ORIGIN, F_PARENT)

#: det_lote column offsets within the 422-byte record (flag byte at 0).  Taken
#: from the published field table (G-1a): 22 fields, record_length 422.
_OFF = {
    "PRODUCTO": (9, 29),
    "CANT": (154, 165),
    "COSTO": (165, 175),
    "IMPORTE": (175, 186),
    "LOTE": (306, 318),
    "SUBL": (318, 321),
    "FOLIO": (321, 326),
    "FECHA": (326, 334),
}


def normalize(value) -> str:
    """THE one normalization (GC-2), used for membership AND for keys.

    det_lote stores goldens as 10 digits space-padded to 12; two normalizations
    would re-split what one folded, silently.
    """
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("latin-1")
    return str(value).strip()


def is_golden(value) -> bool:
    """Golden-shaped under the sealed regex, after the one normalization."""
    return bool(GOLDEN_RE.match(normalize(value)))


def level_for(subl) -> str:
    """The ruled derived function.  Image is {'1','2'} — inside the Select."""
    return "1" if normalize(subl) in ("", "0", "1") else "2"


def is_root(subl) -> bool:
    return level_for(subl) == "1"


def node_name(golden: str, subl: str) -> str:
    """Verbatim legacy ID.

    Roots take the golden itself; sublots take `<golden>-N`, which is the shape
    `golden_number.SUBLOT_ID_RE` already ships (design §4b D2) — a convention
    that exists in sealed code rather than one invented here.
    """
    golden = normalize(golden)
    return golden if is_root(subl) else f"{golden}-{normalize(subl)}"


@dataclass
class LotGroup:
    """One (LOTE, SUBL) node — the ruled import unit."""

    golden: str
    subl: str
    folios: set = field(default_factory=set)
    dates: set = field(default_factory=set)
    line_rows: int = 0
    importe_total: float = 0.0
    consumed_goldens: set = field(default_factory=set)

    @property
    def level(self) -> str:
        return level_for(self.subl)

    @property
    def name(self) -> str:
        return node_name(self.golden, self.subl)


@dataclass
class ImportPlan:
    """Everything the write needs, and every number the verdict asks for."""

    source_path: str
    source_bytes: int
    source_mtime: str
    physical: int
    active: int
    deleted: int
    groups: dict
    dangling_arrows: list
    produced_goldens: set

    @property
    def roots(self):
        return [g for g in self.groups.values() if g.level == "1"]

    @property
    def children(self):
        return [g for g in self.groups.values() if g.level == "2"]

    def level_image(self) -> set:
        return {g.level for g in self.groups.values()}

    def counts(self) -> dict:
        return {
            "physical": self.physical,
            "active": self.active,
            "deleted": self.deleted,
            "nodes": len(self.groups),
            "roots": len(self.roots),
            "children": len(self.children),
            "distinct_goldens": len(self.produced_goldens),
            "dangling_arrow_edges": len(self.dangling_arrows),
            "dangling_arrow_values": len({p for p, _ in self.dangling_arrows}),
        }


def _slice(data: bytes, key: str) -> str:
    lo, hi = _OFF[key]
    return normalize(data[lo:hi])


def read_plan(dbf_path: str) -> ImportPlan:
    """Read the source. NO writes, NO frappe calls — pure measurement.

    Deleted-aware: the deleted set is counted but never imported (the ruled
    population is ACTIVE).  Arrows are collected for enumeration only.
    """
    import dbf as dbf_lib  # ethanfurman; exposes recno()/is_deleted()

    st = os.stat(dbf_path)
    table = dbf_lib.Table(dbf_path)
    table.open()
    try:
        physical = active = deleted = 0
        groups: dict = {}
        produced: set = set()
        ever_lote: set = set()
        arrows: set = set()
        for rec in table:
            physical += 1
            data = bytes(rec._data)
            lote = _slice(data, "LOTE")
            if is_golden(lote):
                ever_lote.add(lote)
            if dbf_lib.is_deleted(rec):
                deleted += 1
                continue
            active += 1
            if not is_golden(lote):
                continue
            subl = _slice(data, "SUBL")
            key = (lote, subl)
            grp = groups.get(key)
            if grp is None:
                grp = groups[key] = LotGroup(golden=lote, subl=subl)
            produced.add(lote)
            grp.line_rows += 1
            folio = _slice(data, "FOLIO")
            if folio:
                grp.folios.add(folio)
            fecha = _slice(data, "FECHA")
            if fecha:
                grp.dates.add(fecha)
            importe = _slice(data, "IMPORTE")
            try:
                grp.importe_total += float(importe or 0)
            except ValueError:
                pass
            producto = _slice(data, "PRODUCTO")
            if is_golden(producto) and producto != lote:
                grp.consumed_goldens.add(producto)
                arrows.add((producto, lote))
    finally:
        table.close()

    dangling = sorted(a for a in arrows if a[0] not in ever_lote)
    mtime = datetime.datetime.fromtimestamp(
        st.st_mtime, datetime.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ImportPlan(
        source_path=dbf_path,
        source_bytes=st.st_size,
        source_mtime=mtime,   # M19: the SUBSTRATE's own moment, beside the reading's
        physical=physical,
        active=active,
        deleted=deleted,
        groups=groups,
        dangling_arrows=dangling,
        produced_goldens=produced,
    )


def preflight(plan: ImportPlan) -> dict:
    """Assertions that must hold before any document is constructed.

    `custom_batch_origin` is a DB-only Custom Field (reqd, Select) — it is NOT
    fixture-shipped, so a freshly migrated tier can lack it entirely.  Writing
    to a field that does not exist fails silently at the object and loudly at
    the column; check first.
    """
    meta = frappe.get_meta(TARGET_DOCTYPE)
    missing = [f for f in REQUIRED_FIELDS if not meta.get_field(f)]
    if missing:
        frappe.throw(
            f"A-3 pre-flight: {TARGET_DOCTYPE} is missing required field(s) {missing}. "
            "custom_batch_origin is a Custom Field and is not fixture-shipped."
        )
    level_field = meta.get_field(F_LEVEL)
    options = [o for o in (level_field.options or "").split("\n") if o]
    image = plan.level_image()
    outside = sorted(image - set(options))
    if outside:
        frappe.throw(f"A-3 pre-flight: level image {sorted(image)} outside Select {options}")
    return {
        "fields_present": list(REQUIRED_FIELDS),
        "level_options": options,
        "level_image": sorted(image),
        "out_of_domain": outside,
    }


def _folio_note(group: LotGroup) -> str:
    """Carry the folio SET, never a scalar.

    `custom_folio_produccion` is an Int and holds one value; three lot-groups
    carry more than one folio, and a one-folio importer would look correct on
    99.79% of the load while dropping exactly the values the adjudication
    meeting is about.
    """
    folios = sorted(group.folios)
    return f"[A-3] source=det_lote folios={folios} dates={sorted(group.dates)} line_rows={group.line_rows}"


def build_doc_payload(group: LotGroup, parent: str | None) -> dict:
    """The payload for one node. Every ruled field set EXPLICITLY."""
    folios = sorted(group.folios)
    payload = {
        "doctype": TARGET_DOCTYPE,
        "name": group.name,
        F_GOLDEN: group.golden,
        F_LEVEL: group.level,      # constraint 8: never omitted (COLUMN_DEFAULT='1')
        F_ORIGIN: ORIGIN_VALUE,    # constraint 2: reqd Select, never auto-filled
        F_NOTES: _folio_note(group),
    }
    if parent:
        payload[F_PARENT] = parent
    if len(folios) == 1 and folios[0].isdigit():
        payload[F_FOLIO] = int(folios[0])
    return payload


def _root_name_for(golden: str, groups: dict) -> str | None:
    for (g, subl) in groups:
        if g == golden and is_root(subl):
            return node_name(g, subl)
    return None


def idempotency_key(group: LotGroup) -> str:
    """(LOTE, SUBL) — measured unique 1,434/1,434.

    A golden-only key silently collapses 1,434 nodes to 1,090 and looks correct.
    """
    return f"{group.golden}|{group.subl}"


def execute(plan: ImportPlan, dry_run: bool = True, limit: int | None = None) -> dict:
    """Create one Batch AMB per node, roots first, through the fence.

    ⛔ doc.insert() ONLY.  No bulk_insert, no db_set, no ignore_validate — each
    would bypass the F-0 fence, which is the entire point of the A-2 ruling.

    ⭐ `frappe.flags.in_import` is REQUIRED and its trade is measured, not assumed:

        naming.py:158  `if autoname... and not frappe.flags.in_import: doc.name = None`
            OFF → autoname REPLACES the verbatim legacy id (measured: `0227022211`
                  became `LOTE-26-34-0001`), tabSeries ADVANCES (constraint 4
                  violated), and every child's parent Link then dangles.
            ON  → the supplied name survives and tabSeries stays static.

        base_document.py:1091  `_validate_selects` short-circuits under the same
            flag — so the Select is UNVALIDATED and the importer is the ONLY guard
            for the level value.  That is constraint 8, and it is why every payload
            sets custom_batch_level explicitly rather than trusting the column
            default ('1', which would silently mint an L1 root).

        document.py:1315  `run_before_save_methods` fires validate/before_save
            gated by `flags.ignore_validate` ONLY — NOT by in_import.  ⭐ The F-0
            fence therefore STILL FIRES under this flag; that is the measured
            reason the ruled path survives the import context at all.

    The flag is restored in a finally block: leaving it set would silently disable
    Select validation for everything that ran afterwards in the same process.
    """
    checks = preflight(plan)
    ordered = plan.roots + plan.children  # roots first: children Link to them
    if limit:
        ordered = ordered[:limit]

    # ⭐ FENCE RULING ① (Hugh, 2026-08-20).  The F-0 fence is NOT REACHED by this
    # write: the D1a stability guard returns first at BOTH live mint sites —
    # batch_amb.py:639 returns, the fence sits at :723; the mirror at :3181
    # returns, its fence sits at :3238 — whenever custom_golden_number is already
    # populated, which every Migrated row does.  Measured live: a planted second
    # L1 root on the same golden inserted WITHOUT refusal.  So the importer calls
    # THE fence itself — the sealed function, never a re-implementation.
    #
    # Audited side-effect-free before being trusted (blob 910282251f94, md5
    # 80e11fd7): the whole body is `db.sql(SELECT …)` + `frappe.throw(…)`, with
    # ZERO attribute assignments — and the same audit sees 9 assignments inside
    # set_batch_naming, so it can detect mutation when mutation is there.
    from amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb import (
        _enforce_l1_golden_fence,
    )

    created, skipped, refused = [], [], []
    prior_flag = frappe.flags.in_import
    if not dry_run:
        frappe.flags.in_import = True
    try:
        for group in ordered:
            name = group.name
            if frappe.db.exists(TARGET_DOCTYPE, name):
                skipped.append(name)          # idempotency: re-run creates nothing
                continue
            parent = None
            if group.level == "2":
                parent = _root_name_for(group.golden, plan.groups)
                if parent and not (dry_run or frappe.db.exists(TARGET_DOCTYPE, parent)):
                    parent = None             # never write a broken Link
            payload = build_doc_payload(group, parent)
            if dry_run:
                created.append(name)
                continue
            if group.level == "1":
                # L1 ROOTS ONLY: F-0 is a uniqueness rule among L1 roots; a level-2
                # sublot legally repeats its parent's golden (inheritance, FI6).
                try:
                    _enforce_l1_golden_fence(group.golden, doc_name=name)
                except frappe.ValidationError as refusal:
                    refused.append({"name": name, "golden": group.golden,
                                    "stage": "fence", "message": str(refusal)})
                    continue
            doc = frappe.get_doc(payload)
            try:
                doc.insert(ignore_permissions=True)
            except frappe.ValidationError as refusal:
                refused.append({"name": name, "golden": group.golden,
                                "stage": "insert", "message": str(refusal)})
                continue
            if doc.name != name:
                # autoname overrode the verbatim id — the in_import contract broke.
                frappe.throw(
                    f"A-3: verbatim id not preserved ({name!r} became {doc.name!r}); "
                    "naming.py:158's in_import gate did not hold — STOP, do not continue."
                )
            created.append(doc.name)
    finally:
        frappe.flags.in_import = prior_flag

    return {
        "dry_run": dry_run,
        "preflight": checks,
        "counts": plan.counts(),
        "created": len(created),
        "skipped_existing": len(skipped),
        "refused": refused,
        "refused_count": len(refused),
        "dangling_enumerated": len(plan.dangling_arrows),
    }


def plan_digest(plan: ImportPlan) -> str:
    """A stable digest of the planned write, so two seats can compare plans."""
    payloads = []
    for group in sorted(plan.groups.values(), key=lambda g: (g.golden, g.subl)):
        parent = _root_name_for(group.golden, plan.groups) if group.level == "2" else None
        payloads.append(repr(sorted(build_doc_payload(group, parent).items())))
    return hashlib.sha256("\n".join(payloads).encode()).hexdigest()
