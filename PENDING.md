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

### Evolution / trend charts: IVA position and net worth over time
**Added:** 2026-08-06 — **narrowed 2026-08-26**

**Done 2026-08-26:** sales/purchases/profit evolution shipped as `/reports/evolution`, built on `get_monthly_evolution` in `reports.py`, with the entity filter, the currency selector and the period partial. The dashboard's "Ganancia (facturas)" line is the same function.

**Still pending:** the other two candidates from the original entry.
- **IVA position over time.** `get_iva_position` groups by entity over one period; it needs the same year/month treatment `get_monthly_evolution` got. Worth having: the IVA position swings month to month and only the trend shows whether a credit balance is being consumed or accumulating.
- **Net worth over time.** Harder, and not the same shape of problem: account balances are a running total, not a per-month aggregate, so it needs the balance *as of* the end of each month, converted at that month's exchange rate. Reusing `ars_rate_subquery` with a per-month reference date is the crux.

**Reusable pattern:** `month_range()` / `month_idx()` / `MONTH_NAMES` in `reports.py` build the month window, and `MAX_EVOLUTION_MONTHS` caps it — "todos los años" in the period filter resolves to 1900-01-01, which would otherwise be a thousand columns.

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

### Per-entity authorization for the web screens
**Added:** 2026-08-29 — surfaced by the public sign-up

**Why:** `web/` shows everything to anyone who is logged in. `entity_crud.get_all(db)` is what
transactions, reports, invoices and the dashboard call; `get_by_user` exists but only the `/api`
side uses it, to route an incoming FactuMov invoice to the right entity. Any user also reaches
Configuración → Usuarios, where they can create accounts and reset anybody's password.

That was defensible while every user was created by hand by the one person who owns all three
entities. It stopped being invisible the day the login grew a "Crear cuenta" link: from then on,
the only thing standing between a stranger and InSoft's, Familia's and Escuela's books is
`is_active=False` on the new account plus a human deciding to flip it.

**The gate is real, and it is also the whole defense.** That is the part worth writing down: the
sign-up is safe *because* of one boolean, not because the data is scoped.

**Scope:**
- Filter every `get_all` behind the screens by the current user's memberships — the entity
  selector, the lists, the reports, the dashboard.
- Decide what a user with no memberships sees: an empty app is fine, an error page is not.
- Separate "can use the app" from "can administer users": today they are the same thing, and
  every activated account can deactivate the one that activated it.
- Only then is it worth reconsidering whether a confirmed account could be activated
  automatically instead of by hand.

### Switching a comprobante to informal leaves its lines carrying IVA
**Added:** 2026-09-06 — surfaced next to the scan-serial IVA bug (that one is fixed)

**Why:** `normalize_fields_by_formality` (`services/invoice.py`) clears the header fiscal
fields when a comprobante is set to informal, but never touches the lines. A comprobante built
formal with 21%/10,5% lines, then unchecked to informal, keeps those `iva_aliquot` values.

Two things then conspire. `Invoice.applies_iva` is `voucher_type not in (C, NCC)`, and an
informal has `voucher_type = None` — `None not in (...)` is `True` in Python, so an informal
wrongly reports `applies_iva = True`. `iva_breakdown` then takes the "IVA incluido" branch and
derives a phantom IVA amount that the totals show, even though the per-line IVA column is
hidden (`shows_iva` also needs `invoice.formal`). Confirmation catches it — `_validate_formality`
rejects any line with `iva_rate != 0` — but there is no in-UI way to fix it: the informal form
shows no alícuota selector, so the only recourse is deleting and re-adding every line.

**Scope:**
- `normalize_fields_by_formality`: when going informal, reset every line to `IvaAliquot.exempt`
  (mirrors what `_validate_formality` already demands, and what the scan path now does on create).
- `applies_iva`: make it `False` when `voucher_type is None` (informal) — both the Python
  property and `_applies_iva_expression`. Probably `self.formal and voucher_type not in (...)`.
- Check `iva_breakdown` / `discriminates_iva` for the same `voucher_type IS NULL` three-valued
  logic trap flagged for `is_nc` in CLAUDE.md's gotchas.

**Trigger:** low — needs someone to build formal then toggle. But it is a silent wrong total
until confirmation, and the fix is small.

### Password reset can't close the sessions that are already open
**Added:** 2026-08-29

**Why:** FactuMov revokes every `user_sessions` row when a password is reset — whoever resets
because they suspect someone got in has to be left alone inside. Here the session is a JWT
signed with `SECRET_KEY` and carrying its own 8-hour expiry: there is no row to revoke, so a
session opened by someone else survives the reset for up to eight hours.

**Scope (two options, pick when it matters):**
- A `token_version` column on `users`, bumped on reset and carried in the JWT payload;
  `get_current_user` compares them. Cheap, no new table, and it invalidates *all* sessions.
- Or move to opaque sessions in a table, like FactuMov, which also buys "log out this device".

**Trigger:** the day an account is actually compromised, or the first time someone asks to see
their open sessions. Until then the 8-hour window plus the `is_active` switch — which *does*
take effect on the next request — is enough.
### Two pytest runs at once destroy each other's test database
**Added:** 2026-09-07 — cost about half an hour of chasing a phantom regression

**Why:** `tests/conftest.py` has one session-scoped `tables` fixture that does
`Base.metadata.create_all(engine)` on entry and `drop_all(engine)` on exit, against the single
`balance360_test` database named in `.env`. There is nothing keyed to the process. Two pytest
runs at the same time — two terminals, two agent sessions on the same checkout, or the day
someone adds `pytest-xdist` — share that database, and whichever finishes first drops the whole
schema out from under the other. The victim reports `psycopg.errors.UndefinedTable: relation
"users" does not exist` in the middle of an otherwise healthy run.

**What makes it expensive is that it does not look like an infrastructure problem.** The
failures land in clusters, move between modules from run to run, and name whatever table the
victim touched next, so they read as a regression in the code being written at that moment.
The tell is `UndefinedTable` on a table nobody's change went near.

**Scope:**
- Give each run its own database — a name suffixed with the PID, or a template database cloned
  per run — so `create_all` / `drop_all` can't cross process boundaries.
- Or take a Postgres advisory lock in the `tables` fixture, so the second run waits instead of
  interleaving. Cheaper, and enough for the two-terminals case; it does not help xdist.
- While in there: `models/__init__.py` imports every model **except** `api_token`, so
  `Base.metadata` is complete only for code that happens to import
  `balance360.models.api_token` some other way. The suite gets away with it because
  `tests/test_api_token.py` imports it during collection; anything else that calls `drop_all`
  fails on `DependentObjectsStillExist: cannot drop table users ... constraint
  api_tokens_user_id_fkey`, and the table survives. One import line.

**Trigger:** low as long as one person runs the suite from one terminal. It becomes a real
blocker the moment two sessions work on the checkout at once — which is exactly when it is
hardest to read, because there is a fresh diff to blame.
