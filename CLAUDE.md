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

### Registro de comprobantes de FactuMov (2026-08-29)

FactuMov emite y `POST /api/invoices/issued` lo registra acá. Lo que llega ya tiene CAE: no se
crea una factura, se copia un hecho consumado. Entra `formal`, `confirmed`, `authorized` y
**impago** — el cobro es otro hecho, con otra fecha.

- **`/api` ahora pide credencial.** Antes se montaba pelado: solo `web_router` llevaba
  `Depends(get_current_user)`, así que cualquiera con la URL leía y escribía. `get_api_user`
  acepta el token de máquina (`Authorization: Bearer`, tabla `api_tokens`, se emite con
  `create_api_token.py`) o la cookie de siempre. Los handlers de 401 y de `Balance360Error`
  responden JSON cuando el path empieza con `/api`: antes el 401 redirigía al login y un
  cliente HTTP recibía el HTML con status 200.
- **El token no caduca: se revoca.** `api_tokens` no tiene expiración, solo `revoked_at`
  (`NULL` = vivo), así que se emite una vez por integración y por base. `revoke_api_token.py`
  es el otro lado del par: sin nombre lista los del usuario con su `last_used_at` —la pregunta
  previa a revocar cualquier credencial vieja—, y con un nombre o un prefijo de id revoca ese.
  Emitir sin poder revocar dejaba una credencial que solo se apagaba con un UPDATE a mano
  contra la base de producción, que es justo lo que no hay que estar haciendo el día que un
  token se filtra.
- **El token se lo emite el que lo va a usar (2026-08-29).** `POST /api/tokens` recibe mail,
  contraseña y un nombre, y devuelve un token nuevo. Es el **único** router de `/api` que se
  monta sin `get_api_user`, y no puede ser de otra manera: es el que autentica. Reemplaza al
  `create_api_token.py` corrido por ssh, que hacía que conectar una integración dependiera de
  quien administra la VM; el script sigue estando para emitir a mano. La contraseña **se usa y
  no se guarda en ningún lado** — ese es todo el punto: el que llama la cambia por una
  credencial que se revoca sola, y se olvida de ella.
- **Emitir revoca el token anterior con el mismo nombre.** Como no caducan, sin esto cada
  reconexión dejaría vivo un secreto que no usa nadie y que nadie va a acordarse de apagar. Por
  nombre y no por usuario: apagar todo lo que la persona tenga emitido porque reconectó
  FactuMov le rompería las otras integraciones sin avisarle.
- **`services/rate_limit.py`: cinco intentos cada quince minutos, por mail.** Es el primer
  límite de intentos de esta app y existe porque `/api/tokens` es el primer endpoint que
  contesta "esa contraseña no es" sin haber autenticado a nadie, o sea un oráculo. Se cuentan
  **los fallidos**, que es lo único que defiende de algo. La clave es el mail y **no la IP**:
  todos los pedidos legítimos vienen de la misma —la del servidor de FactuMov, que llama en
  nombre de cada usuario—, así que por IP el primero que se pasa deja afuera a todos los demás;
  y detrás de Caddy la IP que ve la app es la del proxy salvo que se configure el reenvío,
  mientras que leer `X-Forwarded-For` a mano es un límite que cualquiera esquiva mandando uno
  distinto en cada request. Es un piso, no el techo: el rociado —una contraseña contra mil
  direcciones— se frena en el borde. En memoria y por proceso, igual que el de FactuMov.
- **El mensaje de "no" es el mismo** para un mail que no existe y para una contraseña
  equivocada, y el mail inexistente igual paga un `dummy_verify()`: dos mensajes distintos —o
  dos tiempos distintos— convierten el endpoint en la lista de qué direcciones tienen cuenta
  acá. La cuenta desactivada sí dice qué pasa, porque a esa altura ya demostró la contraseña.
- **Los enums viajan por nombre, no por valor.** `CondicionIva.FINAL` vale 6 acá y 5 en
  FactuMov, que corrigió los códigos contra la tabla de ARCA. Por valor, un consumidor final
  entraría como monotributista sin dar error. **Los códigos de acá siguen sin revisar** — ver
  la nota de FactuMov en `docs/emision-y-envio.md`.
- **`unit_price` pasó a cuatro decimales.** Acá el unitario es siempre neto; en FactuMov una B
  guarda el precio con el IVA adentro. Una B de $100 al 21% necesita un neto de 82,6446: con
  dos decimales el total más cercano es 99,99, un centavo menos que el CAE.
- **Las líneas se colapsan a cantidad 1** cuando la letra es B o cuando la cantidad es
  fraccionaria, con el importe de la línea como unitario y la cantidad original en la
  descripción ("Consultoría (1,5 × $8.000)"). `quantity` es entero porque está atado al stock
  y a los seriales; truncar 1,5 facturaría de menos.
- **Se verifica que los importes cierren** contra los que autorizó ARCA, y si no, no se guarda
  nada. Como los totales se derivan de las líneas, una traducción mal hecha no daría error:
  daría un total distinto que nadie mira hasta la declaración del mes siguiente.
- **Idempotente por `invoices.external_source` + `external_id`**, con unique. El que llama
  reintenta, y un comprobante duplicado no se puede borrar sin dejar un agujero en la
  numeración.
- La entidad se deduce del CUIT del emisor, entre las entidades del usuario dueño del token.
  Con más de una candidata se pide explícita: elegir por nuestra cuenta sería mandar plata al
  balance equivocado en silencio.

### Alta propia, confirmación de mail y recuperación de contraseña (2026-08-29)

Las tres pantallas sin sesión —`/login/`, `/register`, `/forgot-password`— más `/confirm-email`
y `/reset-password`. Están en `web/auth.py`, que es el único módulo de `web/` montado sin
`Depends(get_current_user)`.

Lo pidió Johnny después de quedarse afuera: el navegador guarda las contraseñas **por
dominio**, FactuMov y Balance360 viven las dos en `*.insoft.net.ar`, y guardar la de una encima
de la otra le dejó la de acá irrecuperable. Hasta ese día la única salida era que **otro**
usuario entrara a Configuración → Usuarios y se la cambiara — o sea que recuperar la cuenta
propia dependía de que hubiera alguien más adentro.

- **La cuenta que se crea sola nace apagada (`is_active=False`), y esa es la línea que sostiene
  todo lo demás.** Las pantallas de esta app **no filtran por membresía**: `entity_crud.get_all`
  trae todas las entidades y cualquiera adentro ve la contabilidad entera y puede administrar
  usuarios. O sea que "registrarse" no puede significar "entrar": significa anotarse. Prender el
  interruptor es un click en Configuración → Usuarios, y ahí sale el mail de "ya podés entrar".
  La alternativa —dejar entrar y limitar lo que ve— es un sistema de permisos por entidad que
  esta app no tiene, y escribirlo para poder abrir el registro sería empezar por el final.
- **`get_current_user` ahora rechaza a los inactivos**, y no solo el login. La cookie es un JWT
  de ocho horas sin fila que revocar: sin ese chequeo, desactivar a alguien no lo sacaba hasta
  que su sesión venciera sola.
- **Ninguna pantalla dice si una dirección tiene cuenta.** El registro termina siempre en
  "revisá tu casilla" —sus tres ramas mandan un mail, para que las tres tarden parecido y puedan
  fallar igual— y el "olvidé mi contraseña" también le escribe a una dirección sin cuenta: si
  esa rama no mandara nada, sería la única que no puede fallar por SMTP y el error pasaría a
  significar "esa dirección existe". Es el mismo criterio que ya tenía `/api/tokens`.
- **La cuenta desactivada sí dice qué pasa**, igual que en `services/api_token.py`: quien llegó
  hasta ahí ya demostró la contraseña, y "email o contraseña incorrectos" lo mandaría a cambiar
  una que está bien.
- **`email_confirmations` y `password_resets` son dos tablas con la misma forma** que
  `api_tokens` —token opaco de 256 bits guardado como SHA-256, vencimiento en la fila, marca de
  consumo en vez de borrar—. Que se repita es la decisión: una tabla genérica con una columna
  `kind` las obligaría a compartir vencimiento, índices y limpieza, que es justo lo que no
  comparten. La confirmación vive 24 h y el reset **una hora**: un token de confirmación vencido
  cuesta un reenvío, uno de reset vivo es la cuenta entera para cualquiera que llegue a esa
  casilla.
- **Usar un link de reset apaga todos los demás** (`invalidate_all_for_user`); los de
  confirmación no se apagan entre sí. Dos links de confirmación vivos hacen lo mismo y lo que
  hacen ya está hecho; dos de reset son dos oportunidades de cambiar la contraseña, y la segunda
  le queda a quien pidió la primera. Pedir otro **no** rompe el anterior en ninguno de los dos:
  el que no encuentra el primer mail pide un segundo, y dejarlo con dos links muertos sería
  castigarlo por buscar mal.
- **Usar el link de reset confirma la dirección**: haberlo abierto prueba lo mismo que prueba el
  de confirmación.
- **Ninguno de los dos abre sesión.** El token vivió en una casilla de mail; convertirlo en
  cookie dejaría adentro a cualquiera con acceso a ese mensaje.
- **Registrarse encima de una cuenta sin confirmar emite un token nuevo pero no toca la
  contraseña.** Pisarla es una toma de cuenta completa: al atacante le alcanza con registrarse
  sobre una cuenta pendiente y esperar a que el dueño —que está esperando un mail— abra el link
  que le llegue.
- **El hash de la contraseña se calcula antes de mirar la base**, y en dos de las tres ramas se
  tira. Es lo más caro del camino: hashear solo al crear haría que una dirección ya registrada
  conteste notoriamente más rápido y la respuesta idéntica no serviría de nada. Por eso existe
  `user_crud.create_with_hash`.
- **`get_by_email` pasó a ser insensible a mayúsculas y a espacios.** Comparaba con `==` sobre
  el texto tal cual, así que " Miguel@… " no encontraba al usuario de "miguel@…" — y eso no se
  ve como "no te encontré" sino como "mail o contraseña incorrectos".
- **Los errores se atrapan en las rutas**, contra la convención del proyecto. El handler global
  contesta un `<h1>No se pudo completar la operación</h1>` pelado, que en un login es una pared:
  el usuario no tiene dónde volver a intentar.
- **Las cinco pantallas copian el look de FactuMov** (`templates/auth/_layout.html`): misma
  columna angosta, marca arriba, tarjeta blanca, verde de InSoft en el botón y el crédito de la
  casa abajo. No es prolijidad — la persona que usa las dos apps tiene que reconocer **qué
  contraseña va en cada una**, que es exactamente lo que falló. El ícono
  (`static/balance360-icon.svg`) es el mismo dibujo que la tarjeta de Balance360 en la landing.
- **`reset_password.py` es la salida de emergencia**, del lado del servidor: pide la contraseña
  nueva por consola y no la toma por argumento, para que no quede en el historial del shell. Es
  para cuando el mail no sale o la dirección de la cuenta ya no existe.

### El CUIT de un contacto es único (2026-09-04)

Un CUIT identifica a un sujeto, así que dos `contacts` con el mismo CUIT son dos mitades de la
historia de un mismo cliente y ningún reporte por contacto muestra el total. Pasó con AOMA:
"AOMA Bs. As." y "Asociacion Obrera Minera Argentina", los dos con 30503218107, con los
comprobantes repartidos entre las dos fichas.

- **Dos capas, y las dos hacen falta.** `services/contact.py` da el mensaje que se puede leer
  (nombra al contacto que ya tiene ese CUIT); el índice único parcial `uq_contacts_tax_id` es
  la garantía: dos requests concurrentes pasan los dos por la validación antes de que ninguno
  haya insertado, y cualquier script suelto escribe por `crud` sin pasar por el servicio.
- **Parcial (`WHERE tax_id IS NOT NULL`)**: el contacto sin CUIT es legítimo y frecuente —el
  consumidor final, la persona a la que no se le factura— y de esos tiene que haber muchos.
  En Postgres varios NULL ya conviven en un único; el `WHERE` deja escrito que es la intención.
- **`""` no es NULL** y sí choca contra el índice. El validador de `ContactCreate`/`ContactUpdate`
  normaliza la cadena vacía a NULL, y la migración limpia lo que ya haya entrado por la API JSON.
- **Todas las altas pasan por `services/contact.py`**: el modal de Configuración, el alta rápida
  desde una factura (`web/invoices.py`), el `POST /api/contacts` y el receptor que crea
  `services/issued_invoice.py` cuando llega un comprobante de FactuMov con un CUIT desconocido.
- **`get_by_tax_id` hace `.first()` sobre una consulta sin orden**, así que con duplicados
  devolvía cualquiera de las dos fichas — y es la función que resuelve el receptor de lo que
  llega de FactuMov y el proveedor de un PDF importado. El índice es lo que la vuelve
  determinista.
- **Unificar dos fichas del mismo CUIT sí toca comprobantes ya autorizados**, contra la regla de
  no editar lo emitido, y está bien: del receptor lo único que viaja en el pedido del CAE es el
  CUIT, y el CUIT no cambia. Cambia a cuál de las dos fichas del mismo sujeto apunta la fila.
  Con un CUIT distinto sería otra cosa y no se arreglaría con un UPDATE.
  Herramienta: `scripts/merge_duplicate_contacts.sql`.

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
