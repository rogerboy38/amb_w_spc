# Copyright (c) 2026, AMB and contributors
"""B-3b — one historic SALES lot attached to a Batch AMB.

⭐ A CHILD TABLE ON THE PARENT, NEVER INSIDE `container_barrels` (G-5 / M90).
Frappe gives every child row `_table_fieldnames = MappingProxyType({})` — empty
and immutable — and both load and save iterate exactly that, so a table nested
inside a child table is never loaded, never saved, and never throws. The grid
renders, accepts input, and silently discards it. Three such grids already exist
in this install and hold zero rows between them.

⇒ `Batch AMB` is a PARENT doctype (`istable=0`), so a child table on it is the
supported shape. That is the whole reason this row lives here.

⚠ Every field is `Data` on purpose. These are historic FoxPro values: folios are
not reliably numeric, a customer may no longer exist as a Link target, and a
leading zero carries meaning. A typed field would reject or silently normalise
exactly the legacy rows this table exists to preserve verbatim.
"""

from frappe.model.document import Document


class BatchHistoricSalesLot(Document):
    pass
