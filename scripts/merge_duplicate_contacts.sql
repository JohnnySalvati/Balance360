-- Balance360 — unificar contactos duplicados por CUIT.
--
-- Dos pares de contactos quedaron cargados con el mismo CUIT, y los comprobantes se
-- repartieron entre las dos fichas de cada par:
--
--   30503218107  "AOMA Bs. As."                        creado 2026-06-21, sin domicilio ni mail
--                "Asociacion Obrera Minera Argentina"  creado 2026-05-28, ficha completa  ← se conserva
--
--   30708251514  "Shell"                               creado 2026-06-23
--                "Algavi SA"                           creado 2026-07-13                  ← se conserva
--
-- En los dos casos se conserva la **razón social**, que es lo que dice el padrón y lo que
-- corresponde ver en un comprobante: "AOMA Bs. As." y "Shell" son nombres de uso diario, no
-- el sujeto con el que se opera. Lo decidió Johnny el 2026-09-04.
--
-- Este script mueve TODO lo que cuelga del duplicado al que se conserva y después borra el
-- duplicado. El que se conserva no se toca: su ficha es la completa.
--
-- ── Por qué se puede tocar un comprobante ya autorizado ──────────────────────────────────
-- La regla del proyecto es no editar un comprobante emitido, porque la base tiene que
-- reflejar lo que se declaró a ARCA. Acá no se rompe: **los dos contactos de cada par tienen
-- el mismo CUIT**, y del receptor lo único que viaja en el pedido del CAE es el CUIT. No
-- cambia el sujeto de la operación; cambia a cuál de las dos fichas de ese mismo sujeto
-- apunta la fila. De hecho queda mejor: la razón social del padrón es ASOCIACION OBRERA
-- MINERA ARGENTINA, no "AOMA Bs. As.", así que las reimpresiones muestran el nombre bueno.
--
-- Si el duplicado tuviera OTRO CUIT esto sería otra cosa y no se arreglaría con un UPDATE.
--
-- ── Orden en producción ─────────────────────────────────────────────────────────────────
--   1. Backup (docs/DEPLOYMENT.md, sección 4).
--   2. Este script.
--   3. Verificar que la consulta 3 del final devuelva cero filas.
--   4. Recién ahí el deploy que trae la migración del índice único: mientras quede un CUIT
--      repetido, CREATE UNIQUE INDEX falla, y como corre en el entrypoint antes de uvicorn
--      la app queda en crash-loop.
--
-- Correr una vez por ambiente (dev primero, después prod), como una sola transacción.
-- Idempotente: en la segunda corrida no encuentra duplicados, no mueve nada y no borra nada.
--
-- SIN ids hardcodeados: los contactos se cargaron a mano en cada base, así que los uuid de
-- dev no son los de producción. Cada par se identifica por su CUIT y por un patrón del
-- nombre que se conserva, que es la regla que describe el dato y vale en las dos bases.
--
-- Ver docs/DEPLOYMENT.md para llegar a cada base.

\set ON_ERROR_STOP on

BEGIN;

-- ── Merge ────────────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
    -- Ponelo en false para solo mover los comprobantes y borrar el duplicado a mano desde
    -- Configuración → Contactos. Ojo con dejarlo así: el índice único de la migración no
    -- entra mientras el duplicado siga existiendo.
    delete_duplicates boolean := true;

    pair       record;
    keep_id    uuid;
    keep_name  text;
    dup_ids    uuid[];
    dup_names  text[];
    moved      integer;
    refs       record;
    leftover   bigint;
    total_left bigint;
BEGIN
    -- Un par por línea: (CUIT, patrón ILIKE del nombre que se CONSERVA). Para unificar otro
    -- par alcanza con agregar una línea acá.
    FOR pair IN
        SELECT * FROM (VALUES
            ('30503218107', 'Asociacion Obrera%'),
            ('30708251514', 'Algavi%')
        ) AS t(tax_id, keep_like)
    LOOP
        -- STRICT a propósito: si el patrón trae cero filas o más de una, esto explota y
        -- revierte todo. Un patrón ambiguo elegiría un ganador al azar y mudaría los
        -- comprobantes a la ficha equivocada sin decir nada.
        SELECT id, name INTO STRICT keep_id, keep_name
          FROM contacts
         WHERE tax_id = pair.tax_id
           AND name ILIKE pair.keep_like;

        SELECT array_agg(id), array_agg(name) INTO dup_ids, dup_names
          FROM contacts
         WHERE tax_id = pair.tax_id
           AND id <> keep_id;

        IF dup_ids IS NULL THEN
            RAISE NOTICE 'CUIT % — sin duplicados, nada que hacer (se conserva "%").',
                pair.tax_id, keep_name;
            CONTINUE;
        END IF;

        RAISE NOTICE 'CUIT % — se conserva "%"; se unifica: %',
            pair.tax_id, keep_name, array_to_string(dup_names, ', ');

        UPDATE invoices SET contact_id = keep_id, updated_at = now()
         WHERE contact_id = ANY(dup_ids);
        GET DIAGNOSTICS moved = ROW_COUNT;
        RAISE NOTICE '  invoices     : % movidos', moved;

        UPDATE transactions SET contact_id = keep_id, updated_at = now()
         WHERE contact_id = ANY(dup_ids);
        GET DIAGNOSTICS moved = ROW_COUNT;
        RAISE NOTICE '  transactions : % movidas', moved;

        UPDATE import_rules SET contact_id = keep_id, updated_at = now()
         WHERE contact_id = ANY(dup_ids);
        GET DIAGNOSTICS moved = ROW_COUNT;
        RAISE NOTICE '  import_rules : % movidas', moved;

        -- ── Precondición del DELETE ──────────────────────────────────────────────────────
        -- Esas tres son las tablas que hoy referencian contacts, pero el que corra esto en
        -- producción dentro de seis meses no tiene por qué saberlo. En vez de confiar en la
        -- lista se le pregunta al catálogo qué tablas apuntan a contacts y se cuenta en cada
        -- una. Si apareciera una cuarta que este script no mueve, la encuentra y revierte,
        -- en lugar de morir con una violación de foreign key que no dice qué faltó.
        total_left := 0;
        FOR refs IN
            SELECT c.conrelid::regclass AS tbl,
                   a.attname            AS col
              FROM pg_constraint c
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
             WHERE c.contype = 'f'
               AND c.confrelid = 'contacts'::regclass
        LOOP
            EXECUTE format('SELECT count(*) FROM %s WHERE %I = ANY($1)', refs.tbl, refs.col)
               INTO leftover USING dup_ids;
            IF leftover > 0 THEN
                RAISE NOTICE '  PENDIENTE: %.% tiene % fila(s) apuntando al duplicado',
                    refs.tbl, refs.col, leftover;
                total_left := total_left + leftover;
            END IF;
        END LOOP;

        IF total_left > 0 THEN
            RAISE EXCEPTION
                'CUIT %: quedan % fila(s) apuntando al contacto duplicado. Revierto: el '
                'script no conoce todas las tablas que lo referencian.', pair.tax_id, total_left;
        END IF;

        IF delete_duplicates THEN
            DELETE FROM contacts WHERE id = ANY(dup_ids);
            GET DIAGNOSTICS moved = ROW_COUNT;
            RAISE NOTICE '  contactos duplicados eliminados: %', moved;
        ELSE
            RAISE NOTICE '  duplicados NO eliminados (delete_duplicates = false): %',
                array_to_string(dup_names, ', ');
        END IF;
    END LOOP;
END $$;

COMMIT;

-- ── Verificación ─────────────────────────────────────────────────────────────────────────

-- 1. Cómo quedaron los dos: una sola fila por CUIT, la de la ficha completa.
SELECT id, name, tax_id, contact_type, condicion_iva, email, address
  FROM contacts
 WHERE tax_id IN ('30503218107', '30708251514')
 ORDER BY tax_id;

-- 2. Los comprobantes que quedaron colgando de esos contactos.
SELECT c.name, i.invoice_type, i.voucher_type, i.pos, i.number, i.date, i.authorized, i.cae
  FROM invoices i
  JOIN contacts c ON c.id = i.contact_id
 WHERE c.tax_id IN ('30503218107', '30708251514')
 ORDER BY c.name, i.date, i.pos, i.number;

-- 3. CUIT que siguen repetidos. **Tiene que dar cero filas antes de deployar la migración
--    del índice único**: si aparece un par nuevo, se agrega su línea al VALUES de arriba
--    —con el nombre que se conserva— y se vuelve a correr el script.
SELECT tax_id,
       count(*)                                    AS contactos,
       string_agg(name, ' | ' ORDER BY created_at) AS nombres
  FROM contacts
 WHERE tax_id IS NOT NULL AND tax_id <> ''
 GROUP BY tax_id
HAVING count(*) > 1
 ORDER BY tax_id;

-- 4. tax_id en cadena vacía en lugar de NULL: la migración los normaliza, pero si aparecen
--    muchos conviene mirarlos antes.
SELECT count(*) AS tax_id_vacios FROM contacts WHERE tax_id = '';
