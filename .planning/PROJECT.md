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

### Attivi

#### Milestone Attuale: v1.1 Fasi per Articolo

**Obiettivo:** Ogni articolo ha il proprio percorso di fasi indipendente, assegnato dall'ufficio, con gestione batch nelle viste di reparto.

**Funzionalita target:**
- Assegnazione fasi per articolo (checkbox per LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE — tutte opzionali)
- Stato indipendente per articolo (ogni articolo traccia il proprio avanzamento)
- Viste reparto mostrano solo articoli pertinenti a quella fase
- Batch start/complete per ordine dentro ogni fase
- Ordine completato quando tutti gli articoli hanno finito le loro fasi assegnate

### Fuori Ambito

- Profili/template predefiniti per combinazioni di fasi — v2 (checkbox sufficienti per v1.1)
- Fix tecnici/deprecation (sessioni ORM, API deprecate) — milestone separato
- Nuove fasi di lavorazione oltre le 5 esistenti — non richiesto

## Contesto

- **Stack**: Python 3.8+ / Flask 2.3 / SQLAlchemy 2.0 / SQLite / Vanilla HTML+CSS+JS
- **Deploy**: Rete locale, server singolo, client browser multipli
- **Utenti**: Operatori di officina (non tecnici), personale d'ufficio
- **Lingua**: Tutta la UI e il codice in italiano
- **Nessun build step**: Il frontend e puro HTML con CSS/JS inline
- **16 formati PDF**: Ogni cliente invia ordini in layout PDF diversi

## Vincoli

- **Stack tecnologico**: Flask + SQLite — niente framework pesanti, deve restare leggero
- **Niente build tools**: Il frontend deve restare vanilla HTML/CSS/JS — niente bundler
- **Solo LAN**: Niente deploy cloud, niente autenticazione esterna
- **Italiano**: Tutto il testo rivolto all'utente in italiano
- **File DB singolo**: SQLite con `check_same_thread=False`

## Decisioni Chiave

| Decisione | Motivazione | Esito |
|-----------|-------------|-------|
| SQLite invece di PostgreSQL | Server singolo, <1000 ordini, niente scritture concorrenti | Buono |
| Vanilla JS invece di React | Operatori di fabbrica, nessun build step necessario | Buono |
| PK string UUID | Evitare collisioni integer nella creazione distribuita | Buono |
| Colonne JSON per articoli | Schema flessibile per formato ordine | Buono |
| Redesign UI dark glassmorphism | Look moderno, sistema di design coerente | In corso |

---
*Ultimo aggiornamento: 2026-02-19 dopo definizione milestone v1.1*
