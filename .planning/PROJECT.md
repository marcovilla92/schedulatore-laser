# Schedulatore Laser

## Cos'e

Un sistema web di gestione ordini e schedulazione taglio laser per carpenteria metallica. Gestisce l'intero ciclo di vita: ricezione PDF, estrazione dati, pianificazione taglio laser, e tracciamento produzione multi-fase (LASER → PIEGA → SALDATURA → PULIZIA → SPEDIZIONE) su postazioni in rete locale.

## Valore Principale

Gli operatori a qualsiasi postazione possono vedere cosa deve essere tagliato/piegato/saldato, avviare/completare fasi, e tracciare il completamento parziale degli articoli — eliminando la schedulazione cartacea.

## Requisiti

### Validati

- Upload PDF ed estrazione automatica dati (16 formati supportati)
- Creazione ordine con articoli, date consegna, info cliente
- Lavorazione multi-fase: LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE
- Completamento parziale articoli per fase
- Timer tracciamento per fase con visualizzazione in tempo reale
- Dashboard con panoramica stato stile Kanban
- Viste specifiche per fase (laser.html, piega.html, saldatura.html)
- Accesso multi-postazione in LAN
- Allegato file disegno DXF/DWG
- Archiviazione ordini
- ✓ Fasi per articolo con required_phases e ProcessingStep per-articolo (v1.1)
- ✓ Assegnazione fasi da UI con checkbox in ordini_estratti (v1.1)
- ✓ Viste reparto filtrate per fasi assegnate con batch start/complete (v1.1)
- ✓ Dashboard con progress bar per-articolo (v1.1)

### Attivi

#### Milestone Attuale: v1.2 Redesign UI/UX Completo

**Obiettivo:** Rifare completamente la UI/UX di tutte le pagine con design industrial/dark raffinato, design system condiviso, ricerca/filtri globali, e responsive PC+tablet.

**Funzionalita target:**
- Eliminare welcome page — atterraggio diretto sulla dashboard
- Dashboard potenziata con KPI + vista produzione + scadenze (panoramica mix)
- Design system condiviso (CSS con variabili/token) per coerenza tra tutte le pagine
- Stile industrial/dark raffinato — glassmorphism evoluto e coerente
- Ricerca/filtri globali accessibili da qualsiasi pagina
- Responsive ottimizzato per PC desktop + tablet in officina
- Redesign completo di tutte le pagine (dashboard, laser, piega, saldatura, ordini_estratti, archive)
- Solo 3 viste reparto dedicate (no PULIZIA/SPEDIZIONE)

### Fuori Ambito

- Profili/template predefiniti per combinazioni di fasi — v2 (checkbox sufficienti)
- Fix tecnici/deprecation (sessioni ORM, API deprecate) — milestone separato
- Nuove fasi di lavorazione oltre le 5 esistenti — non richiesto
- Viste reparto dedicate per PULIZIA e SPEDIZIONE — non servono come pagine separate
- Tema chiaro/scuro toggle — solo dark theme per v1.2
- Notifiche/toast — non in questo milestone
- Funzionalita backend nuove — solo UI/UX, il backend resta invariato

## Contesto

- **Stack**: Python 3.8+ / Flask 2.3 / SQLAlchemy 2.0 / SQLite / Vanilla HTML+CSS+JS
- **Deploy**: Rete locale, server singolo, client browser multipli
- **Utenti**: Operatori di officina (non tecnici, usano PC e tablet), personale d'ufficio (PC)
- **Lingua**: Tutta la UI e il codice in italiano
- **Nessun build step**: Il frontend e puro HTML con CSS/JS inline (o CSS condiviso)
- **16 formati PDF**: Ogni cliente invia ordini in layout PDF diversi
- **Skill disponibile**: ui-ux-pro-max per palette, font, stili e UX guidelines

## Vincoli

- **Stack tecnologico**: Flask + SQLite — niente framework pesanti, deve restare leggero
- **Niente build tools**: Il frontend deve restare vanilla HTML/CSS/JS — niente bundler
- **Solo LAN**: Niente deploy cloud, niente autenticazione esterna
- **Italiano**: Tutto il testo rivolto all'utente in italiano
- **File DB singolo**: SQLite con `check_same_thread=False`
- **Backend invariato**: v1.2 e solo UI/UX — le API REST restano le stesse

## Decisioni Chiave

| Decisione | Motivazione | Esito |
|-----------|-------------|-------|
| SQLite invece di PostgreSQL | Server singolo, <1000 ordini, niente scritture concorrenti | Buono |
| Vanilla JS invece di React | Operatori di fabbrica, nessun build step necessario | Buono |
| PK string UUID | Evitare collisioni integer nella creazione distribuita | Buono |
| Colonne JSON per articoli | Schema flessibile per formato ordine | Buono |
| Redesign UI dark glassmorphism | Look moderno, sistema di design coerente | In corso |
| CSS condiviso per v1.2 | Design tokens e variabili comuni per coerenza tra pagine | — |

---
*Ultimo aggiornamento: 2026-02-19 dopo inizio milestone v1.2*
