# Requisiti: Schedulatore Laser

**Definiti:** 2026-02-19
**Valore Principale:** Gli operatori vedono cosa deve essere lavorato e tracciano il completamento in tempo reale

## Requisiti v1.2

Requisiti per il milestone v1.2 — Redesign UI/UX Completo. Ogni requisito e mappato alle fasi della roadmap.

### Design System

- [ ] **DSGN-01**: Tutte le pagine caricano un unico file `design.css` con CSS custom properties per colori, spacing, tipografia, radii e transizioni
- [ ] **DSGN-02**: Font Inter self-hosted in WOFF2 (4 pesi: 400/500/600/700), nessun riferimento a Google Fonts CDN
- [ ] **DSGN-03**: CSS @layer organizza il cascade: reset → tokens → tipografia → base → componenti → layout → utility
- [ ] **DSGN-04**: File `shared.js` fornisce utility `filterOrders()`, `debounce()`, `hasDataChanged()` come globali riutilizzabili

### Accessibilita

- [ ] **ACCS-01**: Tutti gli elementi interattivi hanno touch target minimo 48px, 56px per azioni critiche (Avvia Fase, Completa)
- [ ] **ACCS-02**: Tutte le combinazioni testo/sfondo rispettano il rapporto di contrasto WCAG AA (4.5:1 minimo)

### Dashboard

- [ ] **DASH-01**: `GET /` atterra direttamente sulla dashboard, welcome page rimossa dalla navigazione
- [ ] **DASH-02**: Riga KPI hero in alto: ordini attivi, scadenze oggi, scadenze settimana, fasi in corso
- [ ] **DASH-03**: Card ordini con urgenza consegna colorata: rosso=scaduto, ambra=oggi, neutro=futuro
- [ ] **DASH-04**: Indicatore auto-refresh visibile ("Aggiornato X sec fa") + pulsante "Aggiorna ora" manuale
- [ ] **DASH-05**: Vista panoramica mista: KPI + riassunto fasi attive + urgenze consegna in una vista unificata

### Ricerca e Filtri

- [ ] **FILT-01**: Barra di ricerca globale nella navbar sticky che filtra i dati della pagina corrente (client-side)
- [ ] **FILT-02**: Filtri per stato nelle viste reparto (in attesa, in corso, completati)
- [ ] **FILT-03**: Filtri attivi visualizzati come chips/pills rimovibili con contatore
- [ ] **FILT-04**: Auto-refresh non resetta lo stato dei filtri (separazione fetch/render)

### Viste Reparto

- [ ] **REPT-01**: Accent theming per fase formalizzato nel design system (laser=rosso, piega=ambra, saldatura=verde/blu)
- [ ] **REPT-02**: Refactoring fetch/render: il polling aggiorna i dati senza ricostruire il DOM, preservando filtri e stato espansione panel
- [ ] **REPT-03**: Layout responsive: ≥1024px multi-colonna desktop, 768-1023px colonna singola tablet

### Pagine Secondarie

- [ ] **PGSC-01**: Ordini estratti ridisegnata con design system condiviso, responsive PC+tablet
- [ ] **PGSC-02**: Archivio ridisegnata con design system condiviso, responsive PC+tablet

## Requisiti v1.1 (Completati)

### Modello Dati

- [x] **DATI-01**: Ogni articolo ha campo `required_phases` con fasi assegnate
- [x] **DATI-02**: ProcessingStep creato per-articolo
- [x] **DATI-03**: Stato articolo calcolato dalle fasi completate
- [x] **DATI-04**: Ordine completato quando tutti gli articoli hanno finito le fasi

### Assegnazione Fasi

- [x] **FASE-01**: Checkbox assegnazione fasi per articolo in ordini estratti
- [x] **FASE-02**: Default 5 fasi attive per articoli nuovi
- [x] **FASE-03**: Fasi modificabili prima dell'inizio lavorazione

### Viste Reparto

- [x] **VISTA-01**: Viste reparto mostrano solo articoli con quella fase assegnata
- [x] **VISTA-02**: Batch start/complete per ordine nelle viste reparto
- [x] **VISTA-03**: Dashboard con progress per-articolo

## Requisiti Futuri

Rimandati a milestone futuri. Tracciati ma non nella roadmap attuale.

### UX Avanzata

- **UXA-01**: Indicatori stato con icone oltre al colore (accessibilita daltonismo)
- **UXA-02**: Empty state in italiano quando una fase non ha ordini
- **UXA-03**: Progress bar minimo 12px con testo "N/M articoli"
- **UXA-04**: Completamento articoli inline su card fasi (ridurre tap)
- **UXA-05**: Striscia calendario settimana compatta sulla dashboard

### Profili Fase (da v1.1)

- **PROF-01**: Template predefiniti per combinazioni di fasi
- **PROF-02**: Applicazione profilo a tutti gli articoli con un click

### Ottimizzazione Tecnica (da v1.1)

- **OPT-01**: Migrazione da `declarative_base()` a `DeclarativeBase` (SQLAlchemy 2.0)
- **OPT-02**: Sostituzione `datetime.utcnow()` con `datetime.now(UTC)` (Python 3.12+)

### Funzionalita Backend

- **BACK-01**: API ricerca full-text per articoli/note (nuovo endpoint)
- **BACK-02**: Aggiornamenti real-time via WebSocket
- **BACK-03**: Grafici analytics throughput nel tempo

## Fuori Ambito

Esplicitamente esclusi. Documentati per prevenire scope creep.

| Funzionalita | Motivazione |
|--------------|-------------|
| Tema chiaro/scuro toggle | Raddoppia manutenzione CSS; migliorare contrasto del tema dark e sufficiente |
| WebSocket real-time | Richiede cambiamento backend (backend congelato per v1.2) |
| Ricerca backend full-text | Richiede nuovo endpoint API (backend congelato) |
| Drag-and-drop riordino ordini | Nessun concetto di priorita nel modello dati; data consegna e il segnale di priorita |
| Virtual scroll / lista infinita | Prematura: tipicamente 5-20 ordini attivi per fase |
| Preferenze per utente | Nessun sistema autenticazione; localStorage su tablet condivisi crea confusione |
| Notifiche toast/push | Nessuna infrastruttura push; richiede HTTPS + service worker (LAN HTTP) |
| Grafici animati | Richiede nuovi endpoint API; consuma GPU su tablet di officina |
| Welcome/splash page | Operatori rifiutano pagine intermedie; la dashboard e la landing page |
| Framework CSS (Tailwind/Bootstrap) | Richiede build tools; vincolo "niente bundler" |

## Tracciabilita

Quali fasi coprono quali requisiti. Aggiornato durante la creazione della roadmap.

| Requisito | Fase | Stato |
|-----------|------|-------|
| DSGN-01 | — | In attesa |
| DSGN-02 | — | In attesa |
| DSGN-03 | — | In attesa |
| DSGN-04 | — | In attesa |
| ACCS-01 | — | In attesa |
| ACCS-02 | — | In attesa |
| DASH-01 | — | In attesa |
| DASH-02 | — | In attesa |
| DASH-03 | — | In attesa |
| DASH-04 | — | In attesa |
| DASH-05 | — | In attesa |
| FILT-01 | — | In attesa |
| FILT-02 | — | In attesa |
| FILT-03 | — | In attesa |
| FILT-04 | — | In attesa |
| REPT-01 | — | In attesa |
| REPT-02 | — | In attesa |
| REPT-03 | — | In attesa |
| PGSC-01 | — | In attesa |
| PGSC-02 | — | In attesa |

**Copertura:**
- Requisiti v1.2: 20 totali
- Mappati a fasi: 0
- Non mappati: 20

---
*Requisiti definiti: 2026-02-19*
*Ultimo aggiornamento: 2026-02-19 dopo definizione milestone v1.2*
