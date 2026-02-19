# Roadmap: Schedulatore Laser

## Milestones

- [x] **v1.0 Rilascio Iniziale** — Fasi 1-0 (pre-GSD, completato)
- [x] **v1.1 Fasi per Articolo** — Fasi 1-3 (completato 2026-02-19)
- [ ] **v1.2 Redesign UI/UX Completo** — Fasi 4-5 (in corso)

---

<details>
<summary>v1.1 Fasi per Articolo (Fasi 1-3) — COMPLETATO 2026-02-19</summary>

### Fase 1: Modello Dati per Articolo
**Obiettivo**: Ogni articolo porta le proprie fasi assegnate e traccia il proprio stato di completamento
**Requisiti**: DATI-01, DATI-02, DATI-03, DATI-04
**Criteri di Successo** (cosa deve essere VERO):
  1. Ogni articolo memorizza una lista `required_phases` con le fasi assegnate
  2. ProcessingStep viene creato per articolo, tracciato indipendentemente dagli altri
  3. Stato ordine completato solo quando tutti gli articoli hanno finito le loro fasi
  4. Ordini pre-v1.1 continuano a funzionare (backward compatibility)
**Piani**: 3 plans

Piani:
- [x] 01-01-PLAN.md — Article model + schema migration utility
- [x] 01-02-PLAN.md — Per-article ProcessingStep logic + status derivation
- [x] 01-03-PLAN.md — API routes update + backward compat + E2E verification

### Fase 2: Assegnazione Fasi
**Obiettivo**: Il personale d'ufficio puo assegnare e modificare le fasi per ogni articolo prima della produzione
**Requisiti**: FASE-01, FASE-02, FASE-03
**Criteri di Successo** (cosa deve essere VERO):
  1. Ogni articolo mostra 5 checkbox fasi (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) in ordini_estratti
  2. Nuovi ordini hanno tutte e 5 le fasi preselezionate per default
  3. Modifiche fasi persistono nel backend e sopravvivono al reload pagina
**Piani**: 1 plan

Piani:
- [x] 02-01-PLAN.md — API enhancement + UI checkbox fasi per articolo in ordini_estratti.html

### Fase 3: Viste Reparto
**Obiettivo**: Gli operatori vedono solo gli articoli pertinenti alla loro fase e possono lavorarli in batch
**Requisiti**: VISTA-01, VISTA-02, VISTA-03
**Criteri di Successo** (cosa deve essere VERO):
  1. Ogni vista reparto mostra solo articoli con quella fase nelle loro `required_phases`
  2. Operazioni batch (avvia/completa tutti) disponibili per ordine in ogni vista
  3. Dashboard mostra progress per-articolo con breakdown visivo per fase
  4. Articoli completati non appaiono piu nelle viste reparto
**Piani**: 2 plans

Piani:
- [x] 03-01-PLAN.md — Backend API enrichment + laser.html reference implementation
- [x] 03-02-PLAN.md — piega.html + saldatura.html + dashboard progress breakdown

</details>

---

## v1.2 Redesign UI/UX Completo (In Corso)

**Obiettivo milestone:** Rifare completamente la UI/UX con design system condiviso, stile industrial/dark raffinato, ricerca/filtri globali, e layout responsive PC+tablet su tutte le 6 pagine.

**Struttura parallelismo:**
La v1.2 usa 2 fasi con il massimo parallelismo possibile. La Fase 4 e sequenziale (fondazione obbligatoria). La Fase 5 esegue tutti i piani in PARALLELO — ogni pagina e un agente indipendente che lavora contemporaneamente agli altri.

## Fasi

**Numerazione Fasi:**
- Fasi intere (4, 5): Lavoro pianificato del milestone v1.2
- Fasi decimali (4.1, 4.2): Inserimenti urgenti (marcati con INSERITO)

- [ ] **Fase 4: Design System Condiviso** - Crea `design.css`, `shared.js`, e font Inter self-hosted — la fondazione sequenziale da cui tutto dipende
- [ ] **Fase 5: Redesign Tutte le Pagine** - Redesign completo di tutte le pagine in PARALLELO (5 piani eseguiti simultaneamente come agenti indipendenti)

## Dettagli Fasi

### Fase 4: Design System Condiviso
**Obiettivo**: Un singolo file `design.css` con CSS custom properties, `@layer`, e font Inter self-hosted, piu `shared.js` con utility riutilizzabili — elimina la duplicazione dei token su 7 file e risolve il timeout CDN Google Fonts in LAN
**Dipende da**: Fase 3 (v1.1, completata)
**Requisiti**: DSGN-01, DSGN-02, DSGN-03, DSGN-04
**Criteri di Successo** (cosa deve essere VERO):
  1. Il file `frontend/design.css` esiste ed e accessibile via Flask senza modifiche al backend; tutte le pagine lo possono linkare con `<link rel="stylesheet" href="/design.css">`
  2. Inter WOFF2 (pesi 400/500/600/700) e self-hosted in `frontend/fonts/` con `@font-face` in `design.css` — nessun riferimento a fonts.googleapis.com in nessun file
  3. `design.css` usa `@layer` con cascade esplicita: reset → tokens → tipografia → base → componenti → layout → utility; le regole page-specific inline vincono senza `!important`
  4. `frontend/shared.js` espone `filterOrders()`, `debounce()`, e `hasDataChanged()` come globali — qualsiasi pagina puo caricarli e usarli immediatamente
**Piani**: 1 plan

Piani:
- [ ] 04-01-PLAN.md — design.css con @layer cascade + Inter WOFF2 self-hosted + shared.js utility globali

### Fase 5: Redesign Tutte le Pagine
**Obiettivo**: Tutte le 6 pagine sono completamente ridisegnate con il design system condiviso, ricerca/filtri globali, accessibilita WCAG AA, e layout responsive PC+tablet

**ARCHITETTURA DI ESECUZIONE: WAVE PARALLELA**
Tutti i 5 piani della Fase 5 si eseguono in PARALLELO come agenti indipendenti — ogni piano e assegnato a un agente separato che lavora contemporaneamente agli altri. Non c'e dipendenza tra i piani: ognuno consuma i file `design.css` e `shared.js` gia creati in Fase 4 e lavora su file HTML distinti. Nessun piano modifica i file di un altro piano.

**Dipende da**: Fase 4 (design.css, shared.js, e fonts/ devono esistere prima di avviare la wave)
**Requisiti**: ACCS-01, ACCS-02, DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, FILT-01, FILT-02, FILT-03, FILT-04, REPT-01, REPT-02, REPT-03, PGSC-01, PGSC-02
**Criteri di Successo** (cosa deve essere VERO):

*Archive e Ordini Estratti (Piano 05-01, 05-02):*
  1. `archive.html` e `ordini_estratti.html` caricano `design.css` e `shared.js`; i blocchi `<style>` inline sono ridotti a regole page-specific (non piu di ~100 righe ciascuno)
  2. I filtri attivi su entrambe le pagine sono visualizzati come chips/pills rimovibili con contatore — l'utente rimuove un filtro cliccando la X sul chip

*Laser — implementazione di riferimento (Piano 05-03):*
  3. `laser.html` implementa il pattern completo: accent theming rosso via `body[data-page]`, fetch/render separati, filtri per stato (in attesa/in corso/completati) che sopravvivono al polling di auto-refresh, e responsive 1024px/768px
  4. Filtri per stato su laser.html mantengono lo stato dopo 3+ cicli di auto-refresh — i dati si aggiornano ma il filtro non viene azzerato

*Piega e Saldatura (Piano 05-04):*
  5. `piega.html` e `saldatura.html` replicano il pattern da laser.html con accent theming distinto (ambra e verde) — un operatore identifica immediatamente in quale reparto si trova

*Dashboard (Piano 05-05):*
  6. Navigando a `http://<server>/` il browser arriva direttamente alla dashboard — nessuna welcome page intermedia
  7. In cima alla dashboard una riga KPI mostra: ordini attivi, scadenze oggi, scadenze settimana, fasi in corso — aggiornata ad ogni refresh
  8. Le card ordini con data consegna passata sono in rosso, quelle con scadenza oggi in ambra, quelle future in neutro — distinguibile a colpo d'occhio
  9. Un indicatore visibile mostra "Aggiornato X sec fa" con un pulsante "Aggiorna ora"

*Cross-cutting (tutti i piani):*
  10. Tutti gli elementi interattivi su tutte le pagine hanno touch target minimo 48px; le azioni critiche (Avvia Fase, Completa) hanno 56px
  11. Una barra di ricerca globale nella navbar sticky di ogni pagina filtra i dati client-side senza chiamate API aggiuntive
  12. Ogni combinazione testo/sfondo rispetta WCAG AA (4.5:1 minimo)

**Piani**: 5 (eseguiti in parallelo)

Piani:
- [ ] 05-01-PLAN.md — archive.html redesign (PGSC-02, applica ACCS-01, ACCS-02, FILT-01, FILT-03)
- [ ] 05-02-PLAN.md — ordini_estratti.html redesign (PGSC-01, applica ACCS-01, ACCS-02, FILT-01, FILT-03)
- [ ] 05-03-PLAN.md — laser.html redesign — implementazione di riferimento (REPT-01, REPT-02, REPT-03, FILT-02, FILT-04, applica ACCS-01, ACCS-02, FILT-01)
- [ ] 05-04-PLAN.md — piega.html + saldatura.html redesign — replica da laser (REPT-01, applica ACCS-01, ACCS-02)
- [ ] 05-05-PLAN.md — dashboard.html redesign (DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, applica ACCS-01, ACCS-02, FILT-01, FILT-04)

## Progresso

**Ordine di Esecuzione:**
Fase 4 (sequenziale) → Fase 5 (wave parallela: tutti i 5 piani simultaneamente)

| Fase | Milestone | Piani Completi | Stato | Completato |
|------|-----------|----------------|-------|------------|
| 1. Modello Dati per Articolo | v1.1 | 3/3 | Complete | 2026-02-19 |
| 2. Assegnazione Fasi | v1.1 | 1/1 | Complete | 2026-02-19 |
| 3. Viste Reparto | v1.1 | 2/2 | Complete | 2026-02-19 |
| 4. Design System Condiviso | v1.2 | 0/1 | Planned | - |
| 5. Redesign Tutte le Pagine | 4/5 | In Progress|  | - |
