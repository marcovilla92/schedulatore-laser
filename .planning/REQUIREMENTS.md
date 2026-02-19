# Requisiti: Schedulatore Laser

**Definiti:** 2026-02-19
**Valore Principale:** Gli operatori vedono cosa deve essere lavorato e tracciano il completamento in tempo reale

## Requisiti v1.1

Requisiti per il milestone v1.1 — Fasi per Articolo. Ogni requisito e mappato alle fasi della roadmap.

### Modello Dati

- [x] **DATI-01**: Ogni articolo nell'ordine ha un campo `required_phases` con le fasi assegnate (lista di fasi: LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE — tutte opzionali)
- [x] **DATI-02**: ProcessingStep viene creato per-articolo in base alle fasi assegnate a quell'articolo (non piu un unico step per l'intero ordine)
- [x] **DATI-03**: Lo stato di ogni articolo e calcolato dalle sue fasi completate (prossima fase, fasi rimanenti, completato)
- [x] **DATI-04**: Un ordine risulta "completato" quando tutti i suoi articoli hanno finito tutte le fasi assegnate

### Assegnazione Fasi

- [ ] **FASE-01**: L'ufficio puo assegnare le fasi a ogni singolo articolo tramite checkbox (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) nella pagina ordini estratti
- [ ] **FASE-02**: Di default, articoli nuovi hanno tutte le 5 fasi attive — l'ufficio rimuove quelle non necessarie
- [ ] **FASE-03**: Le fasi assegnate a un articolo possono essere modificate prima che l'articolo inizi la lavorazione in quella fase

### Viste Reparto

- [ ] **VISTA-01**: Nelle viste reparto (laser.html, piega.html, saldatura.html), l'operatore vede solo gli articoli dell'ordine che devono passare per quella specifica fase
- [ ] **VISTA-02**: L'operatore avvia/completa tutti gli articoli di un ordine presenti in quella fase con un'azione batch (un click per avviare, un click per completare tutti)
- [ ] **VISTA-03**: La dashboard mostra lo stato di avanzamento per articolo — quanti articoli sono in ogni fase, quanti completati

## Requisiti Futuri

Rimandati a milestone futuri. Tracciati ma non nella roadmap attuale.

### Profili Fase

- **PROF-01**: Template predefiniti per combinazioni di fasi (es. "Solo taglio", "Taglio+piega", "Lavorazione completa")
- **PROF-02**: Applicazione profilo a tutti gli articoli di un ordine con un click

### Ottimizzazione Tecnica

- **OPT-01**: Query `get_orders_by_phase` con JOIN invece di caricare tutti gli ordini
- **OPT-02**: Migrazione da `declarative_base()` a `DeclarativeBase` (SQLAlchemy 2.0)
- **OPT-03**: Sostituzione `datetime.utcnow()` con `datetime.now(UTC)` (Python 3.12+)

## Fuori Ambito

Esplicitamente esclusi. Documentati per prevenire scope creep.

| Funzionalita | Motivazione |
|--------------|-------------|
| Nuove fasi di lavorazione | Le 5 fasi attuali coprono il processo produttivo completo |
| Drag-and-drop riordino fasi | La sequenza fasi e fissa: LASER → PIEGA → SALDATURA → PULIZIA → SPEDIZIONE |
| Assegnazione fasi da PDF | I PDF non contengono info sulle lavorazioni necessarie — decisione umana |
| Gestione operatori/turni | Non richiesto per v1.1, troppa complessita aggiunta |
| Fix tecnici / deprecation | Milestone separato per non mischiare refactoring con nuove feature |

## Tracciabilita

Quali fasi coprono quali requisiti. Aggiornato durante la creazione della roadmap.

| Requisito | Fase | Stato |
|-----------|------|-------|
| DATI-01 | Fase 1: Modello Dati per Articolo | Completato (01-01) |
| DATI-02 | Fase 1: Modello Dati per Articolo | In attesa |
| DATI-03 | Fase 1: Modello Dati per Articolo | In attesa |
| DATI-04 | Fase 1: Modello Dati per Articolo | In attesa |
| FASE-01 | Fase 2: Assegnazione Fasi | In attesa |
| FASE-02 | Fase 2: Assegnazione Fasi | In attesa |
| FASE-03 | Fase 2: Assegnazione Fasi | In attesa |
| VISTA-01 | Fase 3: Viste Reparto | In attesa |
| VISTA-02 | Fase 3: Viste Reparto | In attesa |
| VISTA-03 | Fase 3: Viste Reparto | In attesa |

**Copertura:**
- Requisiti v1.1: 10 totali
- Mappati a fasi: 10
- Non mappati: 0

---
*Requisiti definiti: 2026-02-19*
*Ultimo aggiornamento: 2026-02-19 dopo esecuzione 01-01 — DATI-01 completato*
