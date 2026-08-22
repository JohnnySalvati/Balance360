-- Balance360 — backfill the receiver fiscal_identity_id on historical purchases.
--
-- Purchases never had the receiver identity selectable in the UI until now (the
-- field was disabled for invoice_type = 'purchase'), so every confirmed purchase
-- predating this feature has fiscal_identity_id NULL. They all belong to InSoft,
-- which has two identities; the INSCRIPTO one is the receiver of these purchases
-- (confirmed by Johnny). Referenced by id below — see fiscal_identities.
--
-- These invoices are already confirmed, so this only affects reporting
-- (get_iva_position attributing IVA credit per CUIT) — it does not touch
-- validate_confirmation, which only runs pre-confirmation.
--
-- Run once per environment (dev first, then prod), as a single transaction.
-- Idempotent: re-running updates nothing and still passes its checks.
--
-- NO hardcoded ids. The fiscal_identities rows were created by migration
-- 194d0f0a9da5 with gen_random_uuid(), which runs independently in every
-- database — so dev's ids do NOT match production's. Instead each purchase is
-- linked to the INSCRIPTO identity associated with its own entity, which is the
-- rule that actually describes the data ("we receive as the responsable
-- inscripto") and is environment-independent.
--
-- If an entity had two INSCRIPTO identities the subquery would raise (more than
-- one row) and roll back — a safe failure, not a wrong guess.
--
-- See docs/DEPLOYMENT.md for how to reach each database.

\set ON_ERROR_STOP on

BEGIN;

-- ── Backfill ─────────────────────────────────────────────────────────────────
UPDATE invoices i
   SET fiscal_identity_id = (
           SELECT fi.id
             FROM fiscal_identities fi
             JOIN entity_fiscal_identities efi ON efi.fiscal_identity_id = fi.id
            WHERE efi.entity_id = i.entity_id
              AND fi.condicion_iva = 'INSCRIPTO'
       ),
       updated_at = now()
 WHERE i.invoice_type = 'purchase'
   AND i.confirmed
   AND i.fiscal_identity_id IS NULL;

-- ── Postcondition ────────────────────────────────────────────────────────────
-- Every confirmed purchase must now have a receiver. A leftover means its entity
-- has no INSCRIPTO identity associated, so the subquery above returned NULL:
-- abort rather than leave the data half-attributed.
DO $$
DECLARE
    leftover integer;
BEGIN
    SELECT count(*) INTO leftover
      FROM invoices
     WHERE invoice_type = 'purchase' AND confirmed AND fiscal_identity_id IS NULL;

    IF leftover > 0 THEN
        RAISE EXCEPTION
            '% confirmed purchase(s) still have no receiver fiscal identity. '
            'Rolling back — they likely belong to an entity this script does not cover.',
            leftover;
    END IF;
END $$;

COMMIT;

-- ── Report ───────────────────────────────────────────────────────────────────
-- Informational: how the confirmed purchases ended up attributed.
SELECT fi.name AS receiver, count(*) AS purchases
  FROM invoices i
  JOIN fiscal_identities fi ON fi.id = i.fiscal_identity_id
 WHERE i.invoice_type = 'purchase' AND i.confirmed
 GROUP BY fi.name
 ORDER BY fi.name;

-- Formal invoices with no fiscal identity at all (sales included). These are not
-- touched by this script: a formal sale needs an issuer identity to be authorized,
-- so anything listed here needs a decision. Expect no rows.
SELECT id, invoice_type, voucher_type, pos, number, date, confirmed, authorized
  FROM invoices
 WHERE formal AND fiscal_identity_id IS NULL
 ORDER BY date;
