// Lógica compartida por el alta y la edición de comprobantes
// (new_form.html / partials/header_form.html, campos en partials/_header_fields.html).
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
//   - Debe definir una función global `filterContacts()` (difiere igual:
//     el alta cae en el placeholder cuando lo elegido deja de corresponder al tipo,
//     la edición solo oculta). La llama el listener de `contactCreated`.
//   - Debe existir en el DOM: #invoice-type, #voucher-type-select, #contact-select,
//     #fiscal-identity-select, #fiscal-identity-label, #formal-check, #service-dates,
//     #voucher-id, #informal-note, #pos-input, #number-input, y las celdas que solo
//     valen para un comprobante formal marcadas con la clase .formal-only.

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

// Las tres fechas de servicio son una sola celda de la grilla (grid-cols-3), así
// que al mostrarlas hay que devolverles `grid` y no `flex`.
function toggleConcepto(value) {
    const wrap = document.getElementById('service-dates');
    const show = value !== 'products';
    wrap.style.display = show ? 'grid' : 'none';
    wrap.querySelectorAll('input').forEach(input => {
        input.required = show;
        input.disabled = !show;
        if (!show) input.value = '';
    });
}

function toggleFiscalIdentity(invoiceType) {
    // Aplica a los dos tipos: en una venta es nuestra identidad la que emite,
    // en una compra es la que recibe. Solo cambia la etiqueta; la visibilidad
    // depende de `formal` y la maneja syncFormalFields.
    const label = document.getElementById('fiscal-identity-label');
    label.textContent = invoiceType === 'sale'
        ? 'Identidad fiscal (emisor)'
        : 'Identidad fiscal (receptor)';
}

// Un informal no es un documento fiscal: no tiene identidad fiscal, ni letra, ni
// numeración, ni concepto, ni período de servicio. Ocultar no alcanza —display:none
// no impide que un campo se envíe— así que todo eso además se DESHABILITA, que sí
// lo saca del POST/PATCH: el back lo recibe vacío y guarda NULL.
//
// Deja el identificador visible o reemplazado por #informal-note. Esa celda no es
// .formal-only porque la rotula el propio checkbox `formal`, que tiene que seguir
// viéndose para poder volver a tildarlo.
//
// Ojo con el orden: esto devuelve las celdas a su display por defecto, así que
// después hay que reaplicar toggleConcepto — si no, las fechas de servicio
// reaparecen en un comprobante de productos.
function syncFormalFields(checked) {
    document.querySelectorAll('.formal-only').forEach(cell => {
        cell.style.display = checked ? '' : 'none';
        cell.querySelectorAll('input, select').forEach(control => {
            control.disabled = !checked;
        });
    });
    const box = document.getElementById('voucher-id');
    const note = document.getElementById('informal-note');
    if (box) box.style.display = checked ? 'flex' : 'none';
    if (note) note.style.display = checked ? 'none' : '';
    ['voucher-type-select', 'pos-input', 'number-input'].forEach(id => {
        const control = document.getElementById(id);
        if (control) control.disabled = !checked;
    });
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

// Buscador de contactos. Filtra las opciones del #contact-select por nombre y por
// nombre de fantasía (data-search). `hidden` lo decide acá UNA sola función con los dos
// criterios —tipo de comprobante y texto buscado—: si cada uno lo escribiera por su
// cuenta, el último en correr pisaría al otro y reaparecerían proveedores en una venta.
// La opción sin valor (el placeholder del alta) nunca se oculta.
// Devuelve la primera opción visible, que es lo que filterContacts de cada página usa.
function normalizeText(text) {
    return (text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

function refreshContactOptions() {
    const select = document.getElementById('contact-select');
    const search = document.getElementById('contact-search');
    const query = normalizeText(search ? search.value.trim() : '');
    const invoiceType = document.getElementById('invoice-type').value;
    const allowed = invoiceType === 'purchase' ? ['supplier', 'both'] : ['customer', 'both'];
    let firstVisible = null;
    select.querySelectorAll('option').forEach(opt => {
        const typeOk = !opt.dataset.type || allowed.includes(opt.dataset.type);
        // El placeholder no es un resultado: con texto buscado se oculta.
        const textOk = opt.value
            ? normalizeText(opt.dataset.search).includes(query)
            : query === '';
        opt.hidden = !(typeOk && textOk);
        if (!opt.hidden && !firstVisible) firstVisible = opt;
    });
    return firstVisible;
}

// Un <select> cerrado solo muestra la opción elegida: filtrar sus opciones no se ve
// hasta abrirlo, y a quien escribe le parece que "no pasa nada". Por eso, mientras hay
// texto, el select se despliega como lista (size > 1) superpuesta sobre lo de abajo, con
// solo los contactos que coinciden. Al elegir uno, o al vaciar el buscador, vuelve a ser
// un select común. Las clases son las de Tailwind; sin build step se agregan por JS.
const CONTACT_LIST_CLASSES = ['absolute', 'z-20', 'left-[6.5rem]', 'right-0', 'top-0',
    'bg-white', 'shadow-lg'];

function collapseContactList() {
    const select = document.getElementById('contact-select');
    select.size = 1;
    select.classList.remove(...CONTACT_LIST_CLASSES);
}

function onContactSearch() {
    refreshContactOptions();
    const select = document.getElementById('contact-select');
    const search = document.getElementById('contact-search');
    const matches = Array.from(select.options).filter(opt => opt.value && !opt.hidden);
    if (!search.value.trim()) {
        collapseContactList();
        return;
    }
    // Un solo resultado: se elige solo (y `change` recalcula la letra).
    if (matches.length === 1 && select.value !== matches[0].value) {
        select.value = matches[0].value;
        select.dispatchEvent(new Event('change'));
    }
    select.size = Math.max(2, Math.min(matches.length, 6));
    select.classList.add(...CONTACT_LIST_CLASSES);
}

// Enter elige el primer resultado, flecha abajo pasa a la lista, Escape limpia.
document.addEventListener('keydown', function (e) {
    if (e.target.id !== 'contact-search') return;
    const select = document.getElementById('contact-select');
    const first = Array.from(select.options).find(opt => opt.value && !opt.hidden);
    if (e.key === 'Enter') {
        e.preventDefault();  // un Enter en el buscador no debe enviar el comprobante
        if (first) {
            select.value = first.value;
            select.dispatchEvent(new Event('change'));
        }
        e.target.value = '';
        refreshContactOptions();
        collapseContactList();
    } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        select.focus();
    } else if (e.key === 'Escape') {
        e.target.value = '';
        refreshContactOptions();
        collapseContactList();
    }
});

// Elegir con el mouse en la lista desplegada la cierra y limpia el buscador.
document.addEventListener('change', function (e) {
    if (e.target.id !== 'contact-select' || e.target.size === 1) return;
    const search = document.getElementById('contact-search');
    search.value = '';
    refreshContactOptions();
    collapseContactList();
});

// Alta de contacto desde el propio comprobante: POST /invoices/contacts cierra el
// modal y manda los datos por HX-Trigger.
//
// Se agrega la opción a mano en vez de re-renderizar el select porque el select ya
// tiene estado que el servidor no conoce: qué opciones están ocultas por el tipo de
// comprobante y el `data-condicion` de cada una, que es lo que decide la letra
// admitida. Reponerlo desde el back sería mandar todo eso en la respuesta.
//
// Después se reaplican los dos filtros: filterContacts porque la opción nueva entra
// sin `hidden` y hay que ver si corresponde al tipo, y applyVoucherFilter porque la
// condición IVA del contacto cambia qué letras se pueden emitir.
document.body.addEventListener('contactCreated', function (e) {
    const select = document.getElementById('contact-select');
    if (!select) return;
    const label = e.detail.trade_name ? `${e.detail.name} · ${e.detail.trade_name}` : e.detail.name;
    const opt = new Option(label, e.detail.id);
    opt.dataset.search = `${e.detail.name} ${e.detail.trade_name || ''}`;
    opt.dataset.type = e.detail.contact_type;
    opt.dataset.condicion = e.detail.condicion_iva;
    select.add(opt);
    select.value = e.detail.id;
    // Un buscador con texto lo dejaría fuera de la lista justo después de crearlo.
    const search = document.getElementById('contact-search');
    if (search) search.value = '';
    collapseContactList();
    filterContacts(document.getElementById('invoice-type').value);
    applyVoucherFilter();
});
