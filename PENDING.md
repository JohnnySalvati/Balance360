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
- Candidates: sales/purchases evolution, profit evolution, IVA position over time, and net worth over time (ties into the still-pending net-worth report).

### Per-entity email identity (surfaced 2026-08-06)
**Added:** 2026-08-06

**Why:** with "send comprobante by email", the SMTP transport should stay global (one authenticated mailbox on `insoft.net.ar` with SPF/DKIM — that's the deliverability lever). But once more than one entity emits comprobantes, the *visible* sender should reflect the issuing entity.

**Scope:**
- Keep SMTP host/user/password global in `Settings`.
- Store a display name / reply-to / signature per entity (or per `FiscalIdentity`).
- Keep `send_email` taking `from_display` / `reply_to` as parameters, so this becomes a call-site change with no transport change and no risky migration.
- Deliverability note: don't put an arbitrary, unauthenticated address in `From`; use `Reply-To` for the entity's address instead.
