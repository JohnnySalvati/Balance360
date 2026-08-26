# Pending — Balance360

Deferred tasks. Added here with context and decision date so they don't get lost.

## v2.0

### Purchases: receiver fiscal identity, letter/IVA validation per CUIT
**Decided:** 2026-08-05 — for now, purchases do **not** validate the voucher type/letter (neither in the form nor in the service).

**Why:** a purchase is anchored to an `Entity`, which has no IVA condition (that lives in `FiscalIdentity`; also, an entity can associate several identities with different conditions). Without the *receiver* fiscal identity, the purchase letter can't be validated rigorously (issuer = supplier, receiver = us), and a partial check would be inconsistent. So it's left unvalidated until the model is resolved.

**Solution scope:**
- Add `fiscal_identity_id` (receiver) to the purchase model + migration with backfill of existing purchases.
- Enable the fiscal-identity select in the purchase form (today it's disabled for purchases).
- Validate the letter in `validate_confirmation` for purchases using the supplier's (issuer) condition and the chosen receiver identity.
- Move the IVA credit in `get_iva_position` (and related reports) to `fiscal_identity`, so it settles per CUIT and not per entity.

## Backlog

### Supplier & customer current accounts (cuentas corrientes)
**Added:** 2026-08-06

**Why:** the system records invoices and payments per contact, but there's no consolidated per-contact balance or statement showing who owes what. Needed to manage receivables (customers) and payables (suppliers).

**Scope:**
- Per-contact ledger/statement: invoices and payments listed chronologically with a running balance and an outstanding total.
- Sign the movements correctly: a sale means the customer owes us; a purchase means we owe the supplier; payments settle in the opposite direction.
- **Open modeling question:** today payment is a boolean (`paid`) on the invoice. A real current account with partial payments and a running balance likely needs a dedicated payments/allocation model (a payment can settle part of one invoice, or span several). Decide this before building the view.
- Multi-currency: balance per currency, plus a converted view reusing `ars_rate_subquery`.
- Respect the entity filter (multi-entity).
- Likely a `current-account` report endpoint + template, reusing the `reports.py` + Chart.js patterns.

### Evolution / trend charts in reports
**Added:** 2026-08-06

**Why:** reports currently show point-in-time or single-period figures (pie/doughnut, single-period tables). Trend lines over months would show trajectory, not just a snapshot.

**Scope:**
- Time-series line/bar charts via Chart.js (already the global chart lib).
- Reuse the reporting functions in `reports.py`; add multi-period aggregation (group by month).
- Honor the established conventions: entity filter, currency "Ver en" selector, and the period partial.
- Candidates: sales/purchases evolution, IVA position over time, and net worth over time (ties into the still-pending net-worth report).

**Partially done 2026-08-26:** profit evolution exists as the "Ganancia (facturas)" line on the dashboard chart (`get_monthly_profit` in `reports.py`). It is not yet a report of its own: no currency selector, no entity/period filters, no table. The monthly grouping pattern to reuse is there.

### Serial numbers: movement history instead of two FK columns
**Added:** 2026-08-25

**Why:** a `SerialNumber` records its trajectory in two columns — `purchase_line_id` (NOT NULL) and `sale_line_id` (nullable) — but a unit's life is a *sequence* of events, not one purchase plus one sale: bought → sold → credited back → sold again → returned to the supplier. Each new sale overwrites `sale_line_id`, so the previous sale disappears from the record.

Confirming a sale credit note makes this immediate: `confirm_invoice` sets `serial.sale_line_id = None`, and since `InvoiceLine.sold_serials` is *defined by* that column, the serials vanish from the collection. The sale is not reversed, it is erased — the serial's history page then shows the purchase and no sale at all, for a unit that was invoiced and (in the real case) authorized by ARCA. A credit note reverses the economic effect; it does not undo the fact that the comprobante was issued.

The second consequence is the one that keeps producing bugs. `status` is a *derived* value — a cached summary of what the movements say — but it is written by hand in 13 places (`services/invoice.py` ×9, `services/serial_number.py` ×3, `web/invoices.py` ×1). Every one of them is a chance to leave the cache disagreeing with the facts. The SODIMM HIKSEMI units stuck in `returned` (fixed 2026-08-25) were exactly that: `confirm_invoice` wrote the summary and `unconfirm_invoice` forgot to unwrite it. Same root cause as the dead sale branches worked around below.

**Scope:**
- New `serial_movements` table: `serial_number_id`, `invoice_line_id`, `created_at`. No movement-kind column — the kind is already implied by the line's invoice (`invoice_type` + `is_nc`), which is the same information `services/stock.py` uses to decide the sign.
- `purchase_line` / `sale_line` become the latest movement of each kind, derived rather than stored.
- `status` computed from the movements in **one** function. It can stay as a column for cheap filtering, but with a single writer instead of 13.
- Un-confirming anything becomes deleting that comprobante's movements and recomputing — which removes the whole class of confirm/unconfirm asymmetry bugs.
- Migration + backfill of the existing serials from the two current columns.
- Rewrite what touches serials: `confirm_invoice`, `unconfirm_invoice`, `delete_invoice`, `validate_confirmation`, `validate_unconfirmation`, `add_serial_to_line`, `remove_serial_from_line`, `stock/serials.html`, `stock/serial_detail.html`.

**Interim workaround (2026-08-25):** un-confirming a sale credit note whose original invoice carries serial-tracked products is rejected outright, because the link needed to restore them no longer exists. The purchase side round-trips correctly (`purchase_line_id` is never cleared) and needs nothing from this entry.

**Trigger — this is a business question, not a scheduling one:** does a unit that came back through a credit note get *resold*? If that happens once a year, this can wait. If it happens regularly, every occurrence silently erases a sale from the record, and that justifies the work.
