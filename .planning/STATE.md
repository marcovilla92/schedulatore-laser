# Stato Progetto — Schedulatore Laser

## Riferimento Progetto

Vedi: .planning/PROJECT.md (aggiornato 2026-02-19)

**Valore principale:** Gli operatori vedono cosa deve essere lavorato e tracciano il completamento in tempo reale
**Focus attuale:** Fase 5 — Aggiornamento Pagine UI (v1.2)

## Posizione Attuale

Fase: 5 di 5 IN CORSO — wave parallela 5 agenti
Piano: 05-05 COMPLETATO (5/5 piani Fase 5)
Stato: 05-05 dashboard.html + welcome.html redirect completati — Fase 5 completata
Ultima attivita: 2026-02-19 — 05-05 dashboard.html KPI/urgenza/refresh completato (3 min)

Progress: [██████████████████████] Fase 5 completata (5/5 piani completati)

## Performance Metrics

**Velocity:**
- Piani totali completati: 6 (v1.1)
- Durata media: ~4.5 min/piano
- Tempo totale esecuzione: ~27 min (v1.1)

**Per Fase (v1.1):**

| Fase | Piani | Totale | Media/Piano |
|------|-------|--------|-------------|
| 1. Modello Dati | 3 | ~15 min | ~5 min |
| 2. Assegnazione Fasi | 1 | ~5 min | ~5 min |
| 3. Viste Reparto | 2 | ~7 min | ~3.5 min |

**Per Fase (v1.2):**

| Fase | Piani | Totale | Media/Piano |
|------|-------|--------|-------------|
| 4. Design System | 1 | 3 min | 3 min |

*Aggiornato dopo ogni completamento piano*
| Phase 05-redesign-tutte-le-pagine P01 | 2 | 1 tasks | 1 files |
| Phase 05-redesign-tutte-le-pagine P05 | 3min | 2 tasks | 2 files |
| Phase 05-redesign-tutte-le-pagine P03 | 4 | 2 tasks | 1 files |
| Phase 05-redesign-tutte-le-pagine P02 | 3 | 2 tasks | 1 files |

## Contesto Accumulato

### Decisioni Rilevanti per v1.2

- CSS condiviso via `design.css` in `frontend/` — servito dal catch-all Flask `/<path:filename>` senza modifiche backend
- Font Inter self-hosted in WOFF2 in `frontend/fonts/` — CDN Google Fonts crea timeout 30sec in LAN
- Per-page accent colors rimangono in blocchi inline `<style>` per-pagina; pattern `body[data-page]` in design.css solo per `--page-accent`
- Fetch/render separati obbligatori prima di aggiungere ricerca a pagine con auto-refresh (implementato in 05-03, replicato in 05-04 e 05-05)
- Roadmap ristrutturata a 2 fasi (da 4) per massimo parallelismo: Fase 4 sequenziale + Fase 5 wave parallela con 5 agenti
- ACCS-01, ACCS-02, FILT-01 sono cross-cutting — ogni piano Fase 5 li implementa autonomamente nella propria pagina
- **[04-01]** CSS @layer cascade a 7 livelli senza !important — stili inline non-layered nelle pagine sovrascrivono automaticamente
- **[04-01]** Inter WOFF2 self-hosted da jsDelivr fontsource — elimina Google Fonts CDN timeout 30sec su LAN
- **[04-01]** body[data-page] per accenti per-pagina in @layer tokens — default cyan, laser=red, piega=amber, saldatura=orange
- **[04-01]** shared.js come classic script (non ES module) — funzioni disponibili globalmente su window senza complessita CORS
- **[05-01]** Pattern fetch/render separati: loadOrders() aggiorna allOrders, applyFiltersAndRender() applica filtri — searchQuery e clienteFilter mai resettati dal setInterval
- **[05-01]** Filtro cliente filter-bar e ricerca navbar si combinano con logica AND su archive.html
- **[05-01]** Chips rimovibili: updateActiveFilters() + window._chipRemovers[] per collegare onclick a closure — pattern disponibile per 05-02/03/04/05
- **[05-01]** escapeHtml() necessaria per XSS protection quando si usa innerHTML con dati dinamici dal backend
- **[05-03]** fetch/render separation laser.html: allOrders invariato al fetch, applyFiltersAndRender() riapplica searchQuery + statusFilter correnti — pattern canonico per piega/saldatura (05-04)
- **[05-03]** var(--page-accent) per tutti i colori accent laser — body[data-page=laser] attiva accent rosso via design.css @layer tokens; chip.active, summary-number, articles-section usano tutti --page-accent

### Architettura Esecuzione v1.2

```
Fase 4 (1 piano, sequenziale)
  └── 04-01: design.css + shared.js + fonts/
        |
        v (blocca fino a completamento)
Fase 5 (5 piani, PARALLELI — wave simultanea)
  ├── 05-01: archive.html
  ├── 05-02: ordini_estratti.html
  ├── 05-03: laser.html (implementazione di riferimento)
  ├── 05-04: piega.html + saldatura.html
  └── 05-05: dashboard.html
```

### Problemi Noti (da v1.1, non risolti in v1.2)

- `declarative_base()` deprecato in SQLAlchemy 2.0 — rimandato a milestone separato
- `datetime.utcnow()` deprecato in Python 3.12+ — rimandato a milestone separato

### Rischi v1.2 da Tenere Presenti

- Auto-refresh distrugge stato filtri: risolvere con separazione fetch/render in ogni piano Fase 5
- Contrasto glassmorphism sotto illuminazione industriale: validare token WCAG AA in Fase 4
- Accent color unification accidentale: documentare pattern `body[data-page]` in design.css
- Conflitti merge tra piani paralleli: ogni piano lavora su file HTML distinti — nessun conflitto atteso

### Todo in Sospeso

Nessuno.

### Blocchi/Problemi

Nessuno.

## Continuita Sessione

Ultima sessione: 2026-02-19
Fermato a: Completato 05-05-PLAN.md — dashboard.html KPI + urgenza + ricerca + welcome redirect
Resume file: None
