// Lógica compartida por el alta y la edición de comprobantes (new_form / edit_form).
//
// Acá vive solo lo que es idéntico en los dos formularios: las reglas fiscales
// (letra admitida según condición IVA, rol de la identidad fiscal) y los toggles
// que dependen de ellas. Lo específico de cada página —el parser de PDF y el alta
// rápida de contacto en el alta, el filtrado de contactos sin auto-selección en la
// edición— se queda en su propio template.
//
// Antes esto estaba duplicado textualmente en los dos templates: un cambio en la
// matriz de letras había que hacerlo dos veces, y era cuestión de tiempo que una
// de las dos copias quedara vieja.
//
// Contrato con el template que lo incluye:
//   - Debe definir una función global `toggleFormal(checked)` (difiere entre alta
//     y edición: el alta además ajusta los `required` de tipo/pto. de venta/número).
//   - Debe existir en el DOM: #invoice-type, #voucher-type-select, #contact-select,
//     #fiscal-identity-select, #fiscal-identity-label, #formal-check, #service-dates.

// Un checkbox deshabilitado no se envía; preservamos el valor con un hidden mientras está bloqueado.
function ensureFormalHidden(add) {
    const existing = document.getElementById('formal-hidden');
    if (add && !existing) {
        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = 'formal';
        hidden.value = 'true';
        hidden.id = 'formal-hidden';
        document.getElementById('formal-check').insertAdjacentElement('afterend', hidden);
    } else if (!add && existing) {
        existing.remove();
    }
}

function toggleTaxOnly(checked) {
    const formalCheck = document.getElementById('formal-check');
    if (checked) {
        // Un comprobante solo impositivo es siempre formal: forzar y bloquear.
        formalCheck.checked = true;
        toggleFormal(true);
        formalCheck.disabled = true;
        ensureFormalHidden(true);
    } else {
        formalCheck.disabled = false;
        ensureFormalHidden(false);
    }
}

function toggleConcepto(value) {
    const wrap = document.getElementById('service-dates');
    const show = value !== 'products';
    wrap.style.display = show ? 'flex' : 'none';
    wrap.querySelectorAll('input').forEach(input => {
        input.required = show;
        if (!show) input.value = '';
    });
}

function toggleFiscalIdentity(invoiceType) {
    // El campo queda visible/habilitado para los dos tipos: en una venta es
    // nuestra identidad la que emite, en una compra es la que recibe.
    const label = document.getElementById('fiscal-identity-label');
    label.textContent = invoiceType === 'sale'
        ? 'Identidad fiscal (emisor)'
        : 'Identidad fiscal (receptor)';
}

// Letra según condición IVA del emisor y del receptor.
function allowedVouchers(emisor, receptor) {
    if (emisor === 'MONOTRIBUTO' || emisor === 'EXENTO') return ['C', 'NCC'];
    if (emisor === 'INSCRIPTO') {
        return receptor === 'INSCRIPTO' ? ['A', 'NCA'] : ['B', 'NCB'];
    }
    return null;  // emisor desconocido → sin restricción
}

function selectedCondicion(selectId) {
    const sel = document.getElementById(selectId);
    const opt = sel ? sel.options[sel.selectedIndex] : null;
    return opt ? opt.dataset.condicion : null;
}

function applyVoucherFilter() {
    const voucherSelect = document.getElementById('voucher-type-select');
    if (!voucherSelect) return;
    // Venta: nosotros (fiscal-identity) emitimos, el contacto recibe.
    // Compra: el contacto (proveedor) emite, nosotros (fiscal-identity) recibimos.
    const isSale = document.getElementById('invoice-type').value === 'sale';
    const allowed = allowedVouchers(
        selectedCondicion(isSale ? 'fiscal-identity-select' : 'contact-select'),
        selectedCondicion(isSale ? 'contact-select' : 'fiscal-identity-select'),
    );
    let firstVisible = null;
    for (const o of voucherSelect.options) {
        if (o.value === '') continue;  // placeholder siempre visible
        const visible = !allowed || allowed.includes(o.value);
        o.hidden = !visible;
        if (visible && !firstVisible) firstVisible = o;
    }
    const cur = voucherSelect.options[voucherSelect.selectedIndex];
    if (cur && cur.hidden) voucherSelect.value = firstVisible ? firstVisible.value : '';
}

// Recalcular las letras cuando cambian las identidades por cambio de entidad.
document.body.addEventListener('htmx:afterSwap', function(e) {
    if (e.target.id === 'fiscal-identity-select') applyVoucherFilter();
});
