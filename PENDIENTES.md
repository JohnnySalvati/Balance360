# Pendientes — Balance360

Tareas diferidas. Se van agregando acá con contexto y fecha de decisión, para no perderlas.

## v2.0

### Compras: identidad fiscal receptora, validación de letra e IVA por CUIT
**Decidido:** 2026-08-05 — por ahora las compras **no** validan el tipo/letra de comprobante (ni en el form ni en el servicio).

**Por qué:** una compra se ancla a una `Entity`, que no tiene condición IVA (vive en `FiscalIdentity`; además una entidad puede asociar varias identidades con condiciones distintas). Sin la identidad fiscal *receptora* no se puede validar con rigor la letra de la compra (emisor = proveedor, receptor = nosotros), y un chequeo parcial sería inconsistente. Por eso se deja sin validación hasta resolver el modelo.

**Alcance de la solución:**
- Agregar `fiscal_identity_id` (receptor) al modelo de compras + migración con backfill de las compras existentes.
- Habilitar el select de identidad fiscal en el form de compras (hoy está deshabilitado para compras).
- Validar la letra en `validate_confirmation` para compras usando la condición del proveedor (emisor) y de la identidad receptora elegida.
- Repuntar el crédito de IVA en `get_iva_position` (y reportes afines) a `fiscal_identity`, para liquidar por CUIT y no por entidad.

## Corto plazo

### Reporte de resultado: línea de `special_iva_credit`
La función `get_invoice_profit` ya devuelve `special_iva_credit` (crédito de IVA por comprobantes solo impositivos = `(gross_profit − margin) − iva_position`). Falta mostrarlo como línea propia en `profit.html`. Al confirmar la etiqueta y ubicación, se agrega al template.
