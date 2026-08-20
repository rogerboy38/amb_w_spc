"""A-5 · the reconciler for the A-3 import (genealogy-20260817).

Built WITH the importer, never after: a load without a reconciler is an
unverifiable write.

It re-derives the source side from raw bytes in its OWN pass — it does not read
the importer's log and it does not import the importer's reader, because a
reconciler that trusts the loader's own count reconciles the loader with itself.
The only thing shared is the sealed predicate (`GOLDEN_RE`) and the ruled level
function, which are the specification rather than the measurement.

Every figure returned carries its predicate; the word "rows" never appears bare.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict

import frappe

from amb_w_spc.sfc_manufacturing.golden_number import GOLDEN_RE

TARGET_DOCTYPE = "Batch AMB"
ORIGIN_VALUE = "Migrated"

_LOTE = (306, 318)
_SUBL = (318, 321)
_FOLIO = (321, 326)
_IMPORTE = (175, 186)


def _norm(raw: bytes) -> str:
    return raw.decode("latin-1").strip()


def _golden(raw: bytes):
    v = _norm(raw)
    return v if GOLDEN_RE.match(v) else None


def _level(subl: str) -> str:
    return "1" if subl in ("", "0", "1") else "2"


def source_side(dbf_path: str) -> dict:
    """Independent second pass over the source. Read-only, deleted-aware."""
    import dbf as dbf_lib

    st = os.stat(dbf_path)
    table = dbf_lib.Table(dbf_path)
    table.open()
    try:
        physical = active = deleted = 0
        nodes = defaultdict(lambda: {"folios": set(), "importe": 0.0, "lines": 0})
        for rec in table:
            physical += 1
            data = bytes(rec._data)
            if dbf_lib.is_deleted(rec):
                deleted += 1
                continue
            active += 1
            golden = _golden(data[_LOTE[0]:_LOTE[1]])
            if not golden:
                continue
            subl = _norm(data[_SUBL[0]:_SUBL[1]])
            node = nodes[(golden, subl)]
            node["lines"] += 1
            folio = _norm(data[_FOLIO[0]:_FOLIO[1]])
            if folio:
                node["folios"].add(folio)
            try:
                node["importe"] += float(_norm(data[_IMPORTE[0]:_IMPORTE[1]]) or 0)
            except ValueError:
                pass
    finally:
        table.close()

    roots = {k for k in nodes if _level(k[1]) == "1"}
    return {
        "substrate": dbf_path,
        "substrate_bytes": st.st_size,
        "substrate_mtime_epoch": int(st.st_mtime),
        "physical_records": physical,
        "active_records": active,
        "deleted_records": deleted,
        "golden_bearing_lot_nodes": len(nodes),
        "level_1_nodes": len(roots),
        "level_2_nodes": len(nodes) - len(roots),
        "distinct_goldens": len({g for g, _ in nodes}),
        "multi_folio_nodes": sorted(
            f"{g}/{s}" for (g, s), v in nodes.items() if len(v["folios"]) > 1
        ),
        "importe_total": round(sum(v["importe"] for v in nodes.values()), 2),
        "_nodes": nodes,
    }


def target_side() -> dict:
    """What the tier actually holds, by the same predicates."""
    docs = frappe.get_all(
        TARGET_DOCTYPE,
        filters={"custom_batch_origin": ORIGIN_VALUE},
        fields=["name", "custom_golden_number", "custom_batch_level", "parent_batch_amb",
                "custom_folio_produccion", "processing_notes"],
        limit_page_length=0,
    )
    levels = defaultdict(int)
    for d in docs:
        levels[str(d.custom_batch_level or "")] += 1
    return {
        "migrated_documents": len(docs),
        "level_counts": dict(levels),
        "level_image": sorted(levels),
        "distinct_goldens": len({d.custom_golden_number for d in docs if d.custom_golden_number}),
        "with_parent": sum(1 for d in docs if d.parent_batch_amb),
        "total_documents_any_origin": frappe.db.count(TARGET_DOCTYPE),
        "_docs": docs,
    }


def reconcile(dbf_path: str) -> dict:
    """Compare the two sides and return the deltas as NUMBERS.

    A zero delta is only meaningful beside a positive control, so the folio
    check reports both the nodes that should carry a set and whether the target
    preserved it.
    """
    src = source_side(dbf_path)
    tgt = target_side()

    folio_loss = []
    notes_by_name = {d.name: (d.processing_notes or "") for d in tgt["_docs"]}
    for (golden, subl), v in src["_nodes"].items():
        if len(v["folios"]) < 2:
            continue
        name = golden if _level(subl) == "1" else f"{golden}-{subl}"
        note = notes_by_name.get(name)
        if note is None:
            folio_loss.append({"node": name, "reason": "document absent"})
            continue
        carried = set(re.findall(r"\d+", note.split("folios=")[-1].split("]")[0])) if "folios=" in note else set()
        if not v["folios"].issubset(carried):
            folio_loss.append({
                "node": name,
                "source_folios": sorted(v["folios"]),
                "carried": sorted(carried),
            })

    deltas = {
        "documents": tgt["migrated_documents"] - src["golden_bearing_lot_nodes"],
        "level_1": tgt["level_counts"].get("1", 0) - src["level_1_nodes"],
        "level_2": tgt["level_counts"].get("2", 0) - src["level_2_nodes"],
        "distinct_goldens": tgt["distinct_goldens"] - src["distinct_goldens"],
    }
    return {
        "source": {k: v for k, v in src.items() if not k.startswith("_")},
        "target": {k: v for k, v in tgt.items() if not k.startswith("_")},
        "deltas": deltas,
        "reconciled": all(v == 0 for v in deltas.values()) and not folio_loss,
        "folio_set_losses": folio_loss,
        "multi_folio_nodes_expected": src["multi_folio_nodes"],
    }
