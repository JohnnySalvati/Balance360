-- Balance360 — backfill the receiver fiscal_identity_id on historical purchases.
--
-- Purchases never had the receiver identity selectable in the UI until now (the
-- field was disabled for invoice_type = 'purchase'), so every confirmed purchase
-- predating this feature has fiscal_identity_id NULL. All 19 belong to InSoft,
-- which has two identities; the INSCRIPTO one is the receiver of these purchases
-- (confirmed by Johnny). Referenced by id below — see fiscal_identities.
--
-- These invoices are already confirmed, so this only affects reporting
-- (get_iva_position attributing IVA credit per CUIT) — it does not touch
-- validate_confirmation, which only runs pre-confirmation.
--
-- Run once per environment (dev first, then prod), as a single transaction.
-- Idempotent: re-running sets the same value on the same (already-updated) rows.
--
-- See docs/DEPLOYMENT.md for how to reach each database.

\set ON_ERROR_STOP on

BEGIN;

UPDATE invoices
   SET fiscal_identity_id = '86fbb5f2-42ef-4dbe-9f51-5c6969b79693',  -- the INSCRIPTO identity
       updated_at = now()
 WHERE invoice_type = 'purchase'
   AND confirmed
   AND fiscal_identity_id IS NULL
   AND entity_id = '9af2fadf-c918-45ac-afe0-d56135169f4b';  -- InSoft

COMMIT;

-- ── Verification ─────────────────────────────────────────────────────────────
-- Expect 0 rows: no confirmed purchase left without a receiver identity.
SELECT count(*) AS purchases_still_unlinked
  FROM invoices
 WHERE invoice_type = 'purchase' AND confirmed AND fiscal_identity_id IS NULL;

-- Expect 19: all backfilled to that identity.
SELECT count(*) AS backfilled_to_receiver
  FROM invoices
 WHERE invoice_type = 'purchase'
   AND fiscal_identity_id = '86fbb5f2-42ef-4dbe-9f51-5c6969b79693';
