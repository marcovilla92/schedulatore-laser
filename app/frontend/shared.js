// shared.js — Utility globali per Schedulatore Laser
// Caricato come script classico (NON type="module") prima dello script inline di ogni pagina.
// Le funzioni qui dichiarate sono disponibili globalmente su window (es. filterOrders(), debounce()).
// Ordine di caricamento nelle pagine: <script src="/shared.js"></script> PRIMA di <script> inline.

/**
 * filterOrders — filtra un array di ordini per cliente o ID.
 * Basato sul pattern esistente in archive.html (applyFilters).
 *
 * @param {Array}  orders — array di ordini dal backend
 * @param {string} query  — stringa di ricerca (case-insensitive, cerca su cliente e id)
 * @returns {Array} ordini filtrati (array completo se query vuota/nulla)
 *
 * Uso: const filtered = filterOrders(allOrders, searchQuery);
 */
function filterOrders(orders, query) {
  if (!query || !query.trim()) return orders;
  const q = query.trim().toLowerCase();
  return orders.filter(order =>
    (order.cliente || '').toLowerCase().includes(q) ||
    (order.id || '').toLowerCase().includes(q)
  );
}

/**
 * debounce — ritarda l'esecuzione di una funzione per evitare chiamate eccessive.
 * Utile per input di ricerca con auto-refresh attivo.
 *
 * @param {Function} fn    — funzione da ritardare
 * @param {number}   delay — millisecondi di attesa dopo l'ultimo invocazione (consigliato: 300)
 * @returns {Function} versione debounced della funzione originale
 *
 * Uso: const debouncedFilter = debounce(() => applyFilters(), 300);
 *      inputElement.addEventListener('input', debouncedFilter);
 */
function debounce(fn, delay) {
  let timer;
  return function(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * hasDataChanged — confronta nuovi dati con un hash precedente per rilevare cambiamenti.
 * Evita re-render inutili nelle pagine con auto-refresh a intervalli regolari.
 * Basato sul pattern esistente in laser.html (confronto JSON.stringify).
 *
 * @param {any}         newData  — nuovi dati dal backend (qualsiasi tipo serializzabile)
 * @param {string|null} lastHash — hash precedente (JSON.stringify), null alla prima chiamata
 * @returns {{ changed: boolean, newHash: string }}
 *
 * Uso:
 *   const { changed, newHash } = hasDataChanged(orders, lastDataHash);
 *   if (changed) {
 *     lastDataHash = newHash;
 *     renderOrders(orders);
 *   }
 */
function hasDataChanged(newData, lastHash) {
  const newHash = JSON.stringify(newData);
  return { changed: newHash !== lastHash, newHash };
}
