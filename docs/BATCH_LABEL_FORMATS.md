# Batch AMB Label Formats — Print Designer Recipe

This document is a step-by-step recipe for building the two Print Designer formats
that pair with the **Generate Label Cells** button on Batch AMB.

The server method `amb_w_spc.sfc_manufacturing.api.generate_label_cells_for_batch`
populates the per-row label fields on `Container Barrels`. The companion method
`get_print_format_for_batch` inspects `barrel_serial_number` prefixes and returns
which format to render:

| Serial prefix | Format name                  | Layout       |
|---------------|------------------------------|--------------|
| `SMP-...`     | `Label Small 8 (Container)`  | 2 × 4 cells  |
| `BRL-...`     | `Label 4 (Container)`        | 2 × 2 cells  |
| Mixed         | warning, manual selection    | n/a          |

Both formats target **Letter** paper and are built against doctype **Batch AMB**.

---

## Format A — `Label Small 8 (Container)`

- **Doctype**: Batch AMB
- **Page**: Letter
- **Layout**: 2 columns × 4 rows = 8 cells per page
- **Cell size**: ~95mm × 65mm
- **Iterates**: `doc.container_barrels`
- **Filter inside the loop**: only render when
  `row.label_is_active` AND `row.barrel_serial_number` starts with `"SMP"`

### Per-cell content (top to bottom)

1. **Item name** — bold, larger text:
   ```
   {{ row.label_item_name }}
   ```

2. **Lot identifier**:
   ```
   LOTE: {{ row.label_lot }}
   ```

3. **Manufacturing and expiration dates** (single line):
   ```
   M.D. {{ row.label_manufacture_date }}    E.D. {{ row.label_expiration_date }}
   ```

4. **Net weight** (3 decimals):
   ```
   NET WEIGHT: {{ "%.3f" % row.net_weight }} kg
   ```

5. **Sample tag** — render only if present, red bold:
   ```
   {% if row.label_sample_tag %}
     {{ row.label_sample_tag }}
   {% endif %}
   ```

6. **Disclaimer** — small text:
   ```
   No commercial value. For sample use only
   ```

7. **Country of origin** — small bold:
   ```
   PRODUCT OF MEXICO
   ```

---

## Format B — `Label 4 (Container)`

- **Doctype**: Batch AMB
- **Page**: Letter
- **Layout**: 2 columns × 2 rows = 4 cells per page
- **Cell size**: ~95mm × 130mm (twice the height of Format A)
- **Iterates**: `doc.container_barrels`
- **Filter inside the loop**: only render when
  `row.label_is_active` AND `row.barrel_serial_number` starts with `"BRL"`

### Per-cell content

Same blocks as Format A, **plus** a barcode block placed near the top:

- **Barcode** — Code 128, encoding `row.barrel_serial_number`. Use the
  Print Designer **Barcode** element. Make it large enough to scan reliably
  (~60–80mm wide).
- **Serial number** — plain text directly below the barcode:
  ```
  {{ row.barrel_serial_number }}
  ```

Then the same item name / LOTE / M.D. / E.D. / net weight / sample tag /
disclaimer / country-of-origin blocks as Format A.

---

## How to build each format in the desk

1. Open **Print Designer** (Frappe → Print → Print Designer).
2. Click **New** and choose:
   - DocType: `Batch AMB`
   - Page Size: Letter
   - Format Name: exactly `Label Small 8 (Container)` or `Label 4 (Container)`
3. Add a **Table / Loop** element bound to `doc.container_barrels`.
4. Configure the loop's grid: 2 columns × 4 rows (Format A) or 2 × 2 (Format B).
5. Inside the row template, add a Jinja `{% if %}` guard at the top:
   ```
   {% if row.label_is_active and row.barrel_serial_number.startswith("SMP") %}
     ... cell content ...
   {% endif %}
   ```
   (Use `BRL` for Format B.)
6. Drop in the text and (for Format B) barcode elements as listed above.
7. **Save** and **Publish** the format.

The format names must match exactly — `get_print_format_for_batch` returns these
strings literally and the JS opens `/printview?...&format=<that string>`.

---

## Validation

Once both formats are saved:

1. Open a Batch AMB whose container_barrels have **SMP-** prefixed serials.
2. Click **Labels / Etiquetas → Generate Label Cells**. Confirm rows show
   `label_item_name`, `label_lot`, `label_manufacture_date`,
   `label_expiration_date`, `label_sample_tag` (when applicable), `label_is_active`.
3. Click **Labels / Etiquetas → Print Recommended Format**. The print preview
   should open with `Label Small 8 (Container)` selected.
4. Repeat with a Batch AMB that has **BRL-** prefixed serials. The preview should
   open with `Label 4 (Container)` selected and a scannable Code 128 barcode in
   each cell.
5. With a mixed batch (SMP + BRL serials), the button should pop a warning and
   not auto-open a format.

---

## Notes on the data model

- `label_lot` is set to the Batch AMB document name (the LOT identifier itself).
- `label_manufacture_date` is derived from `Batch AMB.creation`, formatted `dd/mm/yy`.
- `label_expiration_date` is `creation + Item.shelf_life_in_days`. If
  `shelf_life_in_days` is unset, falls back to `Batch AMB.expiry_date`.
- `label_sample_tag` is inferred from any matching `Sample Request AMB Item`
  whose parent has `batch_reference == <this batch>` and `item == <this item>`.
  Tag priority: Microbiology → Customer → Distributor → Retention → External Lab.
  This lookup is done via raw SQL so this app does not need to import the
  `Sample Request AMB` doctype (which lives in `amb_w_tds`).
- `label_is_active` defaults to `1` and is what the Print Designer loop should
  filter on so deactivated barrels are skipped without losing their data.
- The server method **only fills empty fields** — existing manual edits are
  preserved.
