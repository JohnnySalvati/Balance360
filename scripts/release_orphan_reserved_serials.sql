-- Balance360 — devolver a "disponible" los seriales que quedaron reservados sin venta.
--
-- Bug: `delete_invoice_line` (web/invoices.py) borraba la línea de un comprobante
-- sin tocar sus seriales. La FK serial_numbers.sale_line_id es ON DELETE SET NULL,
-- así que al borrar la línea el serial perdía el vínculo con la venta pero su
-- `status` quedaba en `reserved` para siempre: fuera del stock disponible y sin
-- comprobante que lo explique. Lo mismo que ya hace `delete_invoice` con sus
-- seriales, la línea suelta no lo hacía.
--
-- Un serial en `reserved` SIEMPRE tiene que tener un sale_line_id: es lo que
-- significa "reservado para una venta". `scan_serial` y `add_serial_to_line`
-- setean los dos juntos; `unconfirm_invoice` vuelve a `reserved` seriales que ya
-- tienen su sale_line. O sea que `reserved` + `sale_line_id IS NULL` no es un
-- estado alcanzable por la app: cada fila así es una víctima de este bug y se
-- puede revertir sin mirar el caso una por una.
--
-- Caso conocido: GMXCS250900824 (Gabinete GAMEMAX NOVA N5), comprado a AIR S.R.L.
-- el 27/08, que Johnny escaneó en una venta informal y después borró la línea.
-- El script arregla ese y cualquier otro que haya quedado igual.
--
-- Idempotente: si no hay huérfanos no cambia nada y avisa. Correr una vez por
-- entorno (dev primero, después prod).
--
-- Orden en producción:
--   1. Backup (docs/DEPLOYMENT.md, sección 4).
--   2. Este script.
--   3. Verificar en Stock → Seriales que GMXCS250900824 figura "Disponible".
--
-- Ver docs/DEPLOYMENT.md para llegar a la base.

\set ON_ERROR_STOP on

BEGIN;

-- ── Qué se va a tocar ────────────────────────────────────────────────────────────
-- Se lista antes de tocar nada, para que quede en el log del deploy.
SELECT sn.id, sn.serial, p.name AS producto, sn.status
  FROM serial_numbers sn
  JOIN products p ON p.id = sn.product_id
 WHERE sn.status = 'reserved'
   AND sn.sale_line_id IS NULL
 ORDER BY sn.serial;

DO $$
DECLARE
    fixed integer;
BEGIN
    UPDATE serial_numbers
       SET status = 'available', updated_at = now()
     WHERE status = 'reserved'
       AND sale_line_id IS NULL;

    GET DIAGNOSTICS fixed = ROW_COUNT;

    IF fixed = 0 THEN
        RAISE NOTICE 'No hay seriales reservados sin venta. Nada que hacer.';
    ELSE
        RAISE NOTICE '% serial(es) devuelto(s) a disponible.', fixed;
    END IF;
END $$;

-- ── Postcondición ────────────────────────────────────────────────────────────────
DO $$
DECLARE
    remaining integer;
BEGIN
    SELECT count(*) INTO remaining
      FROM serial_numbers
     WHERE status = 'reserved' AND sale_line_id IS NULL;
    IF remaining > 0 THEN
        RAISE EXCEPTION 'Quedan % serial(es) reservado(s) sin venta. Revierto.', remaining;
    END IF;
END $$;

COMMIT;

-- ── Verificación ─────────────────────────────────────────────────────────────────
-- El serial conocido tiene que figurar 'available'; ningún reservado sin venta.
SELECT serial, status FROM serial_numbers WHERE serial = 'GMXCS250900824';

SELECT count(*) AS reservados_sin_venta
  FROM serial_numbers
 WHERE status = 'reserved' AND sale_line_id IS NULL;
