-- Balance360 — marcar como impago un comprobante cuyo pago se borró a mano.
--
-- El comprobante 462ddcd0-ac9c-4d8c-9808-89d75e90351a (Venta informal a InSoft,
-- 04/09/2026, $150.000, "Arreglo Notebook") quedó con paid = true después de que
-- Johnny borrara su transacción de pago directamente contra la base de producción.
-- `register_payment` (services/invoice.py) es lo único que marca `invoice.paid`, y
-- lo hace en el mismo movimiento que crea la transacción con `invoice_id`; al
-- borrar esa transacción por afuera de la app, el flag quedó sin nada que lo
-- respalde: el comprobante figura "Pagado", no reaparece el botón "Registrar pago"
-- y el cobro sigue sumando en los reportes aunque su asiento ya no exista.
--
-- Esto es exactamente lo que hace ahora `services/transaction.delete` cuando el
-- borrado pasa por la app; este script arregla la fila que quedó del borrado viejo.
--
-- No se toca un comprobante emitido: es informal, sin numeración y sin CAE. `paid`
-- es independiente de `confirmed` y `authorized` —el cobro es otro hecho—, así que
-- el comprobante simplemente vuelve a "pago pendiente".
--
-- id hardcodeado a propósito: el borrado ocurrió solo en producción, esta fila no
-- existe en dev. Correr una sola vez, contra prod. Idempotente: si ya está impago
-- (o si el id no existe) no cambia nada y avisa.
--
-- Orden en producción:
--   1. Backup (docs/DEPLOYMENT.md, sección 4).
--   2. Este script.
--   3. Verificar en la app que el comprobante quedó en "pago pendiente".
--
-- Ver docs/DEPLOYMENT.md para llegar a la base.

\set ON_ERROR_STOP on

BEGIN;

DO $$
DECLARE
    -- El id va como literal y no como variable de psql: :'...' no se sustituye
    -- adentro de un bloque DO (el dollar-quote es opaco para psql).
    target   uuid := '462ddcd0-ac9c-4d8c-9808-89d75e90351a';
    inv      record;
    tx_count integer;
BEGIN
    SELECT id, paid, confirmed, authorized, formal, number, cae
      INTO inv
      FROM invoices
     WHERE id = target;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe el comprobante %. Revisá el id.', target;
    END IF;

    -- Precondición: el pago tiene que estar realmente huérfano. Si todavía hay una
    -- transacción apuntando a este comprobante, algo no cuadra con la historia
    -- ("borré la transacción") y revertir `paid` dejaría el flag y el asiento en
    -- contradicción. Abortar antes que adivinar.
    SELECT count(*) INTO tx_count FROM transactions WHERE invoice_id = target;
    IF tx_count > 0 THEN
        RAISE EXCEPTION
            'El comprobante % todavía tiene % transacción(es) asociada(s). '
            'Revisá a mano: este script es solo para el pago ya borrado.', target, tx_count;
    END IF;

    IF NOT inv.paid THEN
        RAISE NOTICE 'El comprobante % ya está impago, no hay nada que hacer.', target;
        RETURN;
    END IF;

    UPDATE invoices SET paid = false, updated_at = now() WHERE id = target;
    RAISE NOTICE 'Comprobante % marcado como impago.', target;
END $$;

-- ── Postcondición ────────────────────────────────────────────────────────────────
DO $$
DECLARE
    still_paid boolean;
BEGIN
    SELECT paid INTO still_paid
      FROM invoices
     WHERE id = '462ddcd0-ac9c-4d8c-9808-89d75e90351a';
    IF still_paid THEN
        RAISE EXCEPTION 'El comprobante sigue paid = true. Revierto.';
    END IF;
END $$;

COMMIT;

-- ── Verificación ─────────────────────────────────────────────────────────────────
SELECT i.id, i.invoice_type, i.formal, i.confirmed, i.paid, i.authorized,
       (SELECT count(*) FROM transactions t WHERE t.invoice_id = i.id) AS transacciones
  FROM invoices i
 WHERE i.id = '462ddcd0-ac9c-4d8c-9808-89d75e90351a';
