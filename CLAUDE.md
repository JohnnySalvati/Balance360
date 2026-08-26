# Balance360 — Instrucciones para el asistente

## Rol

Escribís la aplicación y explicás lo que hacés. Johnny tiene conocimientos de Python y sigue
aprendiendo con este proyecto, así que el código tiene que quedar entendible y las decisiones
justificadas — pero el que entrega el código terminado sos vos.

## Regla fundamental — división de responsabilidades

**Escribís vos todo el código** (decisión de Johnny, 2026-08-26). Hasta esa fecha Johnny
escribía el Python y vos solo los templates; ese modo de aprendizaje terminó.

Lo que sigue vigente es la parte docente: mientras escribís, **explicá lo que valga la pena**
que Johnny entienda — la decisión de diseño y por qué se eligió, el patrón que se aplica, el
error que se está evitando. No narres lo obvio ni comentes línea por línea; señalá lo que él
no vería solo leyendo el diff.

## Idioma

- La conversación de mentoría es en **inglés** por defecto (desde 2026-07-24). Johnny cambia a
  español por iniciativa propia cuando el tema es delicado (fiscal, ARCA); seguilo mientras dure
  ese tema y después volvé al inglés.
- Cuando escribe en inglés, cerrá la respuesta con una nota breve de **"Prompt feedback"**
  corrigiendo **su inglés**: gramática, ortografía, elección de palabras, construcciones que
  suenen poco naturales. No es feedback sobre cómo plantea los pedidos. Si no hay nada que
  corregir, no pongas la nota. En español no hay nota.
- Identificadores de código siempre en inglés. Español solo en strings de UI.

## Stack

- **Backend:** FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL 16
- **Frontend:** HTMX + Tailwind CSS + Chart.js (sin build step, sin framework JS)
- **Gestor:** uv. Código en `src/balance360/`, tests en `tests/`
- **Lint/format:** ruff (`E`, `F`, `I`, line-length 100), mypy strict

## Comandos

```bash
uv run pytest                      # tests
uv run ruff check src/ --fix       # lint
uv run ruff format src/            # formato
uv run alembic revision -m "..."   # migración vacía (a mano)
uv run alembic revision --autogenerate -m "..."
uv run alembic upgrade head
uv run uvicorn balance360.main:app --reload
```

La base de desarrollo corre en Docker (`docker-compose.yml`, usuario `postgres`, contenedor
`balance360-db-1`). Producción está en una VM detrás de nginx con `docker-compose.prod.yml`
y **usuario distinto** — ahí siempre `-U "$POSTGRES_USER"`. Ver `docs/DEPLOYMENT.md`.

## Arquitectura

Capas, de afuera hacia adentro:

- `web/` — routers que devuelven HTML (fragmentos para HTMX). Sin lógica de negocio.
- `routers/` — API JSON bajo `/api` (legado del desarrollo inicial).
- `services/` — lógica de negocio y validaciones. **Acá van las reglas**, no en las rutas.
- `crud/` — acceso a datos, una función por operación.
- `models/` — SQLAlchemy. `schemas/` — Pydantic. `dtos/` — objetos de transporte a ARCA.
- `reports.py` — funciones de reporting reutilizables, devuelven `{by_entity, total}`.

### Convenciones establecidas

- **Dinero siempre `Decimal`**, nunca float. Redondeo unificado con `money()`
  (`models/money.py`, ROUND_HALF_UP a 2 decimales). Formato argentino vía el filtro `currency`.
- **Conversión de moneda con la cotización de la fecha** de la transacción, nunca la actual.
  `ars_rate_subquery(source, target)` en `reports.py`; siempre `coalesce(..., 1)` por operando.
- Dependencia `get_X_or_404` para resolver entidades en las rutas.
- PATCH con `exclude_unset=True`; delete recibe el objeto ORM, no el id.
- Errores de dominio: excepciones que heredan de `Balance360Error` (`exceptions.py`). **No se
  atrapan en las rutas** — sube al handler global de `main.py`, que devuelve toast si el request
  es de HTMX (header `HX-Request`) o HTML si es navegación directa. Eso además garantiza el
  rollback: `get_db` hace commit después del `yield` y solo revierte si la excepción sube.
- Sí se atrapan localmente: `ValidationError` de Pydantic (pasa por `format_validation_error`),
  `IntegrityError` de SQLAlchemy, y errores que no son de dominio.

## Dominio

Aplicación de finanzas **multi-entidad y multi-moneda**. Lo difícil: las cuentas físicas
(efectivo, bancos, billeteras, tarjetas) se **comparten** entre entidades, así que el modelo
separa la atribución de la ubicación física del dinero. Los bonos (AL30, GD30) se modelan
como monedas.

Entidades reales: InSoft (empresa), Familia, Escuela. Los clientes son `contact`, no entidades.

### Facturación ARCA (electrónica, en producción)

- `FiscalIdentity` es el emisor fiscal (CUIT, condición IVA, IIBB) y se relaciona con `Entity`
  muchos-a-muchos: una entidad puede facturar con más de un CUIT.
- Estado de un comprobante = tres booleanos: `confirmed`, `paid`, `authorized`. No hay enum de
  estado. Confirmar valida y congela; autorizar pide el CAE a ARCA por WSFE.
- `authorized` implica CAE: **nunca dejes uno autorizado sin CAE**. Un comprobante emitido por
  el portal de ARCA se registra a mano con su punto de venta, número, CAE y vencimiento.
- **Nunca "corrijas" un comprobante ya emitido editando datos.** La base tiene que reflejar lo
  declarado a ARCA; si hay un error real, se corrige con nota de crédito y reemisión, y eso lo
  decide Johnny con su contador.
- Alícuotas de IVA: **electrónica e informática van al 10,5%**, servicios y el resto al 21%.
  No asumas que 21% es siempre lo correcto — Johnny es la autoridad en esto.
- La letra determina la presentación: A discrimina IVA, B lo incluye en el precio, C no aplica
  IVA (`applies_iva` es False para C y NCC). `iva_breakdown` unifica los tres casos.
- Los enums que viajan a ARCA llevan su código como atributo (`arca_code`), definido con
  `__new__` para que `.value` siga siendo el string que persiste SQLAlchemy.
- Punto de venta 2 = portal de ARCA (manual); punto de venta 5 = esta app vía web services.

## Gotchas aprendidos (no repetirlos)

- **HTMX solo hace swap con respuestas 2xx.** Un error 4xx no reemplaza nada en el DOM. Por eso
  los toasts van con 200 + `HX-Trigger` + `HX-Reswap: none`.
- **Jinja se traga los undefined**: una clave mal escrita en el contexto no explota, renderiza
  vacío. Pero acceder a un atributo *de* un undefined sí lanza.
- **`Enum[name]` vs `Enum(value)`**: el paréntesis busca por valor, los corchetes por nombre.
  Pasar un miembro de otro enum a `Enum(...)` lanza `ValueError`.
- **Los `assert` desaparecen con `python -O`.** Nunca los uses como validación en runtime.
- **Alembic `--autogenerate` no detecta check constraints** — esas revisiones se escriben a mano.
  Si una migración necesita limpiar datos, el `UPDATE` va **antes** del constraint, o el
  entrypoint de producción entra en crash-loop.
- **`.scalars()` descarta las columnas extra** de un select con varias expresiones.
- **`Column.in_(...)` sobre una columna nullable da `NULL`, no `False`, cuando la columna es
  `NULL`** (SQL de tres valores). Ese `NULL` se propaga por `and_`/`or_`/`not_` y en un `case()`
  cae al `else_` aunque la condición "lógicamente" debería ser falsa. Bug real: `is_nc` en
  `services/stock.py` usaba `Invoice.voucher_type.in_([NCA, NCB, NCC])` para distinguir NC de
  no-NC; en un comprobante informal `voucher_type` es `NULL`, así que una compra normal (no NC)
  terminaba restando stock en vez de sumarlo. Fix: `func.coalesce(<in_(...)>, False)` para forzar
  un booleano real antes de combinarlo con `and_`/`or_`/`not_`.
- **PostgreSQL: agregar un valor a un enum** requiere `ALTER TYPE ... ADD VALUE`.
- **`str(None)` es truthy** en un contexto de template.
- Los `except` que solo devuelven un mensaje ya no existen: van al handler global.

## Deploy

Producción = VM Ubuntu detrás de `srv-nginx`, con `docker-compose.prod.yml`. El entrypoint corre
`alembic upgrade head` antes de levantar uvicorn, con `set -e`: si una migración falla, la app no
arranca. Todo el procedimiento (deploy, backup, restore, certificados ARCA) está en
`docs/DEPLOYMENT.md`.

**Producción es la fuente de verdad de los datos.** Nunca copies la base de desarrollo encima.
Para arreglar datos en producción se usa un script SQL acotado, con backup previo.

## Trabajo diferido

Las tareas postergadas viven en `PENDING.md` en la raíz, con contexto y fecha de decisión.
Cuando algo se posterga, se anota ahí — no se deja solo en la conversación.

## Commits

Los commits los hacés vos directamente (decisión de Johnny, 2026-08-26): `git add` y
`git commit`, sin pedir confirmación previa del mensaje. Seguí la convención del repo —
Conventional Commits en español, con scope, y el cuerpo explicando el porqué, no el qué.
Los trailers `Co-Authored-By` y `Claude-Session` van siempre.
