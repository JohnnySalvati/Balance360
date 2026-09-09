# Previsión de gastos

Ver en la grilla de Transacciones, con estilo fantasma y en sus fechas, lo que todavía no
pasó pero se sabe que va a pasar; y que la pantalla avise cuando el saldo previsto se va a
negativo.

Decidido con Johnny el 2026-09-09. Este documento es el diseño y el porqué de cada decisión;
lo que se difiere está también en `PENDING.md`.

---

## 1. La decisión central: la previsión no se materializa

La opción obvia es guardar las ocurrencias futuras en `transactions` con un flag
`is_projected`. **No se hace, y es la decisión más importante del diseño.**

`transactions` alimenta todo: `get_account_balances`, `get_monthly_evolution`,
`get_iva_position`, `get_expenses_by_category`, `get_monthly_profit`, `get_iibb_on_sales`, el
dashboard y los reportes. Meter filas proyectadas ahí obliga a agregar `is_projected == False`
a esas diez y pico de funciones más las de `crud/`, y **un filtro olvidado no da error: da un
número mentiroso** que nadie mira hasta la declaración del mes siguiente. Es exactamente la
clase de bug ya documentado en `CLAUDE.md` (el `in_()` sobre columna nullable en
`services/stock.py`).

Materializar además trae un problema propio: cuando la transacción real entra por importación
hay que encontrar y borrar el fantasma, que es un problema de matching difuso (fecha
aproximada, monto aproximado) — un subsistema entero.

**En su lugar:** `services/forecast.py` genera `ProjectedTransaction`, un dataclass congelado
sin `id`, a partir de las recurrencias y una ventana de fechas. Nunca toca la base. La grilla
los mezcla solo para mostrar. Costo real: decenas de recurrencias × unas docenas de
ocurrencias.

## 2. La recurrencia es un plan; la transacción es un hecho

La puerta de entrada de la UI es "sobre esta transacción, especifico su frecuencia". Eso está
bien como gesto, pero no como modelo. Si `interval_unit` viviera en `transactions`:

- ¿Qué fila es la dueña de la serie? Borrar esa transacción se llevaría toda la previsión.
- Si sube el alquiler y se edita el monto de la serie, se estaría **editando un hecho pasado**.
  Es el mismo criterio que ya rige para los comprobantes emitidos.

El precedente está en el propio repo: `import_rules` es una entidad aparte y la transacción
lleva `applied_rule_id`. Mismo patrón.

```
recurrences                          transactions
  id                                   ...
  description, amount, type            recurrence_id  ──FK, SET NULL──┐
  account_id (NOT NULL)                                                │
  entity_id / contact_id / category_id                                 │
  is_transfer                                                          │
  interval_unit, interval_count   ◄────────────────────────────────────┘
  starts_on, ends_on
  is_active
```

**Un solo FK, no dos.** Al crear la recurrencia desde la transacción T se le setea
`T.recurrence_id`, y con eso alcanza para las dos preguntas: "T pertenece a la serie" y "la
serie nació en T" (T es la más vieja con ese `recurrence_id`). Un
`created_from_transaction_id` aparte sería redundante.

**`ondelete="SET NULL"`**, igual que `applied_rule_id`: borrar el plan no puede borrar hechos.

**La recurrencia guarda copia de los campos, no los lee de la semilla.** Tres razones: la
semilla se puede borrar y el plan no debería morir con ella; el monto previsto casi nunca es
el último real (se sabe que el alquiler sube antes de que suba); y reclasificar la semilla no
debería cambiar el plan por abajo. El costo aceptado es la contracara: **reclasificar la
semilla no actualiza el plan** — se edita en Previsiones.

De ahí sale la regla de reparto que ordena toda la UI:

> **El modal de la transacción solo fija el ritmo** (cada cuánto y hasta cuándo). El qué —
> monto, descripción, cuenta, categoría — se copia de la semilla al crear el plan, y a partir
> de ahí solo se cambia en la pantalla de Previsiones.

**Pausar, no borrar.** Elegir "No repetir" sobre una transacción que ya tiene serie **apaga**
la recurrencia (`is_active = False`); no la borra. Borrarla dispararía el `SET NULL` sobre
todas las transacciones reales de la serie y se perdería el vínculo histórico. Apagar es
reversible; borrar no.

## 3. Frecuencia: `unit` + `count`

`interval_unit` (`day`/`week`/`month`/`year`) más `interval_count` cubre alquiler mensual,
sueldos quincenales, anticipos trimestrales y seguros anuales. RRULE de RFC 5545 es
sobredimensionado y trae dependencia.

### El 31 y el 29 de febrero

Ancla el 31/01 con `every 1 month`: el 31 de febrero no existe. La regla es **conservar el día
del ancla y clampear al último día del mes**, y —esto es lo que importa— **calcular siempre
desde el ancla, nunca incrementando la ocurrencia anterior**:

```
31/01  →  28/02  →  31/03  →  30/04  →  31/05
```

Incrementando desde la anterior, el 31 se perdería para siempre en febrero y la serie quedaría
pegada al 28. Lo mismo con el 29/02 de un año bisiesto y `every 1 year`.

### El salto al primer paso, y por qué no se itera desde el ancla

`occurrences()` **calcula** cuántos saltos hay del ancla al inicio de la ventana en vez de
iterar hasta llegar. Con una recurrencia diaria anclada en 2020 y una ventana en 2026 son más
de dos mil pasos: se comería el tope de seguridad `MAX_OCCURRENCES` y **la previsión saldría
vacía sin dar error**. La estimación usa división entera (nunca sobrestima, porque el clampeo
solo puede correr una fecha hacia atrás dentro de su propio mes) y el bucle descarta las pocas
que todavía caigan antes de la ventana.

## 4. La ventana de fantasmas, y la propiedad que hace segura la feature

Los fantasmas existen solo para fechas **estrictamente posteriores a hoy**:

```
ghost_start = max(period.start, hoy + 1 día)
ghost_end   = period.end
```

Si `ghost_start > ghost_end` no hay una sola ocurrencia que mostrar. De ahí sale la propiedad
que hace que esto se pueda mergear sin miedo:

> **Mirando el pasado, la pantalla se comporta exactamente como antes.** El camino con
> previsión solo se activa cuando la ventana llega al futuro.

Y como `Period` por defecto es el mes corriente, abrir Transacciones un 9 de septiembre
muestra el resto de septiembre previsto sin tocar ningún filtro.

## 5. La grilla: paginación

`transaction_crud.get_all` pagina con `LIMIT/OFFSET` en SQL. Mezclar fantasmas de Python
contra eso rompe todo: la página 1 tendría 50 reales más N fantasmas, los contadores
mentirían, y un fantasma cuya fecha cae en la página 3 aparecería en la 1.

```python
if ghost_start > period.end:
    # sin previsión: SQL pagina como siempre
else:
    # con previsión: reales de la ventana sin limit + fantasmas, merge-sort, paginado en Python
```

El orden es `(fecha, fantasma después de real, desempate estable)`. El desempate importa: sin
él, dos filas del mismo día podrían intercambiarse entre pedidos y una fila saltaría de página
al paginar.

**Sobre el `get_all` sin `limit`:** carga la ventana entera en memoria. Con el período por
defecto son decenas o cientos de filas. Con un `date_to` lejano puede ser toda la tabla — pero
esta pantalla ya hace dos cargas completas por render (`status-chart` y `apply-rules` llaman a
`get_all(db)` sin filtros), así que no es una clase de riesgo nueva. Si algún día molesta, se
arregla para los tres a la vez.

### Los filtros sobre los fantasmas

Los cinco filtros de campo (entidad, cuenta, tipo, categoría, descripción) se comparan en
Python contra los campos del plan. El sexto es el raro:

**`classification_status` seteado ⇒ cero fantasmas.** Un fantasma no está pendiente de
clasificar: no existe. Ese filtro es sobre trabajo de clasificación, y clasificar algo que no
pasó no significa nada.

### Supresión por fecha exacta

Si ya hay una transacción real de esa misma recurrencia **en esa misma fecha**, la ocurrencia
no se genera. Resuelve el caso que la feature crearía sola: dar de alta una transacción con
fecha futura y marcarla como mensual haría que la propia semilla apareciera dos veces, real y
fantasma, el mismo día.

Lo que **no** resuelve es el desfasaje: alquiler previsto el 5, pagado el 3. Ahí el fantasma
del 5 sigue apareciendo y la previsión cuenta de más. El daño está acotado —los fantasmas son
solo futuros, así que la ventana de doble conteo es a lo sumo un intervalo— y el arreglo
correcto (supresión por *bucket* del intervalo, no por fecha) está en `PENDING.md`.

## 6. Fase 2 — el saldo previsto y el tinte

No implementado todavía. Queda escrito acá porque las decisiones ya están tomadas y el
análisis que las sostiene es la parte cara.

**Qué número dispara la alarma:** el saldo corrido proyectado del **total de cuentas líquidas
convertido a ARS** (`bank`, `cash`, `wallet`). Las `credit_card` quedan afuera: su saldo es
deuda, es negativo por naturaleza, y las tintaría la pantalla todos los días para siempre.

**Horizonte:** el que pide el filtro de período de la grilla. Consecuencia asumida: mirando
septiembre no se avisa de un noviembre en cero. Cuando eso moleste, la salida es la curva de
saldo en el dashboard, no cambiar esto.

Tres cosas que el cálculo tiene que hacer distinto de `get_account_balances`:

**a) Filtrar por fecha.** `get_account_balances` **no filtra fechas**: suma todas las
transacciones sin importar cuándo, así que el "saldo de hoy" que muestra ya incluye las de
fecha futura. Arrancar la proyección de ahí y volver a aplicar las reales futuras las contaría
dos veces. La proyección necesita su propia base con `date <= hoy`. No se toca
`get_account_balances`: cambiarle la semántica movería el reporte de Balance por cuenta, y eso
es otra conversación.

**b) Incluir las transferencias, y acotar por tipo de cuenta en vez de por el flag.**
`get_account_balances` excluye `is_transfer` de los dos lados. Para un total de cuentas
líquidas eso rompe el caso más común:

| caso | con `is_transfer` excluido | incluyendo el flag, alcance = líquidas |
|---|---|---|
| Banco → Caja (las dos en alcance) | no se ve (netea igual) | las dos patas entran y netean solas ✅ |
| Banco → pago de tarjeta | **no se ve** ❌ la plata se fue y el saldo no baja | la pata del banco baja el total ✅ |
| Banco → cuenta que no se lleva | **no se ve** ❌ | baja el total ✅ |

El neteo sale gratis cuando las dos patas están en el alcance; excluir por flag es lo que hace
desaparecer el pago de tarjeta. Nota aparte: el mismo razonamiento dice que el saldo *por
cuenta* del reporte de Balance está mal cuando hay transferencias. **No se toca en esta
feature** — anotado en `PENDING.md`.

**c) La cotización futura no existe.** `ars_rate_subquery` hace
`WHERE date <= X ORDER BY date DESC LIMIT 1`, así que una fecha futura **cae sola en la última
cotización conocida**: cero código nuevo. Pero el significado cambió y la franja tiene que
decirlo — *"proyectado a la última cotización conocida"* — o el número se lee como una
predicción de tipo de cambio.

**Cómo se pinta.** El contenedor a tintar está fuera de `#tbody`, que es lo único que se
swapea. Nada de `hx-swap-oob` acrobático: `/transactions/rows` devuelve un
`HX-Trigger: {"forecastResult": {...}}` y un listener pinta franja y clase, que es el mismo
mecanismo de `showRuleConflict` y `refreshChart` (y `apply-rules` ya combina triggers en JSON).

Tres niveles, porque el color solo no dice qué hacer: **franja** con la fecha y el monto del
primer negativo; **tinte** del área (`bg-gray-100` → `bg-red-50`); y **lavado rojo sobre los
fantasmas posteriores al primer negativo**, que es lo que muestra exactamente dónde se rompe.

## 7. Fases

- **Fase 1 (hecha)** — modelo, migración, `occurrences()`, fantasmas en la grilla, pantalla de
  Previsiones, alta y pausa desde el modal de transacción.
- **Fase 2** — saldo base, recorrido, franja y tinte (§6).
- **Fase 3** — ver `PENDING.md`: supresión por bucket del intervalo, confirmar/saltear una
  ocurrencia suelta, curva de saldo proyectado en el dashboard, y la revisión del tratamiento
  de transferencias en `get_account_balances`.
