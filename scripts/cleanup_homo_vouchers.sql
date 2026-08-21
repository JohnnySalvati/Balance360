-- Balance360 — reconcile the homologación comprobantes that ended up in the production DB.
--
-- Two of the four were real operations billed from the ARCA portal (their PDFs were
-- checked against the stored rows, line by line): those are corrected in place, keeping
-- their lines, product links and serials. The other two were $1,10 tests: deleted.
--
-- Run once per environment (dev first, then prod), as a single transaction.
-- Idempotent: a second run rewrites the same values and deletes nothing.
--
-- ORDEN EN PRODUCCIÓN: correr este script ANTES del deploy que trae la migración
-- del CHECK (NOT authorized OR cae IS NOT NULL). Si la migración corriera primero,
-- su UPDATE apagaría `authorized` en la factura de Jazbec (todavía sin CAE). Los
-- UPDATE de abajo re-afirman authorized = true, así que el orden deja de ser crítico,
-- pero el camino limpio sigue siendo: backup -> este script -> deploy.
--
-- Audit of 2026-08-20. See docs/DEPLOYMENT.md for how to reach each database.

\set ON_ERROR_STOP on

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. A 00005-00000001 (homo, sin CAE — la que producía el 500 al imprimir)
--    == A 00002-00000134, ARCA portal, 2026-07-15, CAE 86284012161910.
--    Jazbec Juan Carlos · neto 50.000,00 · IVA 21% 10.500,00 · total 60.500,00.
--    Corrected in place so serial 5350 (Base cooler AMD) stays sold — it was delivered.
-- ─────────────────────────────────────────────────────────────────────────────
UPDATE invoices
   SET pos        = 2,
       number     = 134,
       date       = DATE '2026-07-15',
       cae        = '86284012161910',
       cae_expiry = DATE '2026-07-25',
       authorized = true,               -- explícito: así no importa si la migración del CHECK corrió antes
       concepto   = 'both',
       from_date  = DATE '2026-07-15',
       to_date    = DATE '2026-07-15',
       due_date   = DATE '2026-07-15',
       updated_at = now()
 WHERE id = 'e4cacd4d-2451-4e25-b2be-68d65345c02c';

-- Align the line descriptions with the fiscal copy.
UPDATE invoice_lines SET description = 'Soporte Cooler AMD', updated_at = now()
 WHERE id = '573a2d56-39d2-4280-a64c-a13c6b2568a9';   -- 1 x 15.000,00
UPDATE invoice_lines SET description = 'Honorarios', updated_at = now()
 WHERE id = '9aece40d-4fc0-4192-9a68-4fce834e4ce0';   -- 1 x 35.000,00

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. B 00005-00000001 (homo) == B 00002-00000557, ARCA portal, 2026-07-01,
--    CAE 86261939822602. AOMA (exento) · "Servicios Insoft" · total 679.260,00.
--    The stored line (neto 614.714,93 @ 10,5%) reproduces the printed total exactly
--    and its IVA contenido of 64.545,07 — same operation, no doubt.
-- ─────────────────────────────────────────────────────────────────────────────
UPDATE invoices
   SET pos        = 2,
       number     = 557,
       date       = DATE '2026-07-01',
       cae        = '86261939822602',
       cae_expiry = DATE '2026-07-11',
       authorized = true,               -- idem
       concepto   = 'services',
       from_date  = DATE '2026-07-01',
       to_date    = DATE '2026-07-01',
       due_date   = DATE '2026-07-01',
       updated_at = now()
 WHERE id = '9944dd21-c4d1-47d3-b223-260b151f56c7';

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Pure homologación tests ($ 1,10 each): delete.
--    invoice_lines / invoice_tributes cascade. attachments, transactions and
--    invoices.related_invoice_id have NO ondelete, so if any such row appeared
--    after this audit the DELETE fails and the whole transaction rolls back.
-- ─────────────────────────────────────────────────────────────────────────────
DELETE FROM invoices WHERE id IN (
  '78dcf952-b873-4238-82c4-2efcc4bd0b6a',  -- B 00002-00000002  2026-07-22  $ 1,10
  'c9f46180-4bd2-434e-aea5-0e55853251d9'   -- B 00002-00000003  2026-07-22  $ 1,10
);

COMMIT;

-- ── Verification ─────────────────────────────────────────────────────────────
-- Expect 10 authorized invoices, all with a CAE, no duplicate (type, pos, number),
-- and serial 5350 still sold.

SELECT voucher_type, pos, number, date, cae, cae_expiry
  FROM invoices WHERE authorized ORDER BY date;

SELECT count(*) AS authorized_without_cae
  FROM invoices WHERE authorized AND cae IS NULL;

SELECT voucher_type, pos, number, count(*)
  FROM invoices WHERE authorized
 GROUP BY 1, 2, 3 HAVING count(*) > 1;      -- must return no rows

SELECT serial, status FROM serial_numbers WHERE serial = '5350';   -- must stay 'sold'
