# Requirements: Schedulatore Laser

**Defined:** 2026-02-19
**Core Value:** Operators see what needs processing next and track completion in real-time

## v1.1 Requirements

Requirements for milestone v1.1 — Fasi per Articolo. Each maps to roadmap phases.

### Modello Dati

- [ ] **DATI-01**: Ogni articolo nell'ordine ha un campo `required_phases` con le fasi assegnate (lista di fasi: LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE — tutte opzionali)
- [ ] **DATI-02**: ProcessingStep viene creato per-articolo in base alle fasi assegnate a quell'articolo (non più un unico step per l'intero ordine)
- [ ] **DATI-03**: Lo stato di ogni articolo è calcolato dalle sue fasi completate (prossima fase, fasi rimanenti, completato)
- [ ] **DATI-04**: Un ordine risulta "completato" quando tutti i suoi articoli hanno finito tutte le fasi assegnate

### Assegnazione Fasi

- [ ] **FASE-01**: L'ufficio può assegnare le fasi a ogni singolo articolo tramite checkbox (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) nella pagina ordini estratti
- [ ] **FASE-02**: Di default, articoli nuovi hanno tutte le 5 fasi attive — l'ufficio rimuove quelle non necessarie
- [ ] **FASE-03**: Le fasi assegnate a un articolo possono essere modificate prima che l'articolo inizi la lavorazione in quella fase

### Viste Reparto

- [ ] **VISTA-01**: Nelle viste reparto (laser.html, piega.html, saldatura.html), l'operatore vede solo gli articoli dell'ordine che devono passare per quella specifica fase
- [ ] **VISTA-02**: L'operatore avvia/completa tutti gli articoli di un ordine presenti in quella fase con un'azione batch (un click per avviare, un click per completare tutti)
- [ ] **VISTA-03**: La dashboard mostra lo stato di avanzamento per articolo — quanti articoli sono in ogni fase, quanti completati

## Future Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### Profili Fase

- **PROF-01**: Template predefiniti per combinazioni di fasi (es. "Solo taglio", "Taglio+piega", "Lavorazione completa")
- **PROF-02**: Applicazione profilo a tutti gli articoli di un ordine con un click

### Ottimizzazione Tecnica

- **OPT-01**: Query `get_orders_by_phase` con JOIN invece di caricare tutti gli ordini
- **OPT-02**: Migrazione da `declarative_base()` a `DeclarativeBase` (SQLAlchemy 2.0)
- **OPT-03**: Sostituzione `datetime.utcnow()` con `datetime.now(UTC)` (Python 3.12+)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Nuove fasi di lavorazione | Le 5 fasi attuali coprono il processo produttivo completo |
| Drag-and-drop riordino fasi | La sequenza fasi è fissa: LASER → PIEGA → SALDATURA → PULIZIA → SPEDIZIONE |
| Assegnazione fasi da PDF | I PDF non contengono info sulle lavorazioni necessarie — decisione umana |
| Gestione operatori/turni | Non richiesto per v1.1, troppa complessità aggiunta |
| Fix tecnici / deprecation | Milestone separato per non mischiare refactoring con nuove feature |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATI-01 | Phase 1: Modello Dati per Articolo | Pending |
| DATI-02 | Phase 1: Modello Dati per Articolo | Pending |
| DATI-03 | Phase 1: Modello Dati per Articolo | Pending |
| DATI-04 | Phase 1: Modello Dati per Articolo | Pending |
| FASE-01 | Phase 2: Assegnazione Fasi | Pending |
| FASE-02 | Phase 2: Assegnazione Fasi | Pending |
| FASE-03 | Phase 2: Assegnazione Fasi | Pending |
| VISTA-01 | Phase 3: Viste Reparto | Pending |
| VISTA-02 | Phase 3: Viste Reparto | Pending |
| VISTA-03 | Phase 3: Viste Reparto | Pending |

**Coverage:**
- v1.1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

---
*Requirements defined: 2026-02-19*
*Last updated: 2026-02-19 after roadmap creation — traceability table populated*
