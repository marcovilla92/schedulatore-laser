# Roadmap: Schedulatore Laser

**Last updated:** 2026-02-20

## Milestones

- [ ] **v1.1 Fasi per Articolo** — Phases 1-3 (deferred, not yet executed)
- [ ] **v1.2 Parser Universale** — Phases 4-6 (current, in progress)

---

## Phases

<details>
<summary>v1.1 Fasi per Articolo (Phases 1-3) — DEFERRED, not yet executed</summary>

### Phase 1: Modello Dati per Articolo
**Goal**: Every article in an order carries its own assigned phases, tracks its own completion status, and the system correctly derives order-level status from article-level data
**Depends on**: Nothing (first phase of v1.1)
**Requirements**: DATI-01, DATI-02, DATI-03, DATI-04
**Success Criteria** (what must be TRUE):
  1. When an order is created via API, each article stores a `required_phases` list specifying which phases (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) that article must go through
  2. When a phase is started/completed for an article, a per-article ProcessingStep is created and tracked independently from other articles in the same order
  3. Querying an article's status returns its next pending phase, list of completed phases, and list of remaining phases — derived from its assigned phases and completed steps
  4. An order's status changes to "completato" only when every article in that order has completed all of its individually assigned phases
  5. Existing orders without per-article phase data continue to work (backward compatibility with pre-v1.1 data)
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Assegnazione Fasi
**Goal**: Office staff can assign and modify the set of required phases for each article in an order before production begins
**Depends on**: Phase 1
**Requirements**: FASE-01, FASE-02, FASE-03
**Success Criteria** (what must be TRUE):
  1. On the ordini estratti page, each article displays a row of 5 checkboxes (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) and the user can check/uncheck any combination
  2. When a new order is created, all 5 phase checkboxes default to checked for every article — the user removes phases that do not apply
  3. The user can change an article's assigned phases at any time before that article has started processing in the phase being removed
  4. Saving phase assignments persists them to the backend and they survive page reload
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Viste Reparto
**Goal**: Department operators see only the articles relevant to their phase, can batch-process them, and the dashboard reflects per-article progress
**Depends on**: Phase 1, Phase 2
**Requirements**: VISTA-01, VISTA-02, VISTA-03
**Success Criteria** (what must be TRUE):
  1. In laser.html, piega.html, and saldatura.html, each order card shows only the articles that have that specific phase in their `required_phases` — articles without the phase are not displayed
  2. The operator can start all displayed articles for an order in that phase with a single click, and complete all of them with a single click (batch operations)
  3. The dashboard shows per-article progress for each order: how many articles are in each phase, how many have completed all their assigned phases, displayed as a visual breakdown
  4. When an article completes its last assigned phase, it no longer appears in any department view — only fully-incomplete articles are shown
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

</details>

---

### v1.2 Parser Universale (Current Milestone)

**Milestone Goal:** Il sistema estrae automaticamente cliente, articoli, quantita e data di consegna da qualsiasi PDF — inclusi formati mai visti — usando Docling + Gemini 2.0 Flash API, senza dover scrivere parser specifici per ogni nuovo cliente.

#### Phase 4: Audit Parser
- [x] **Phase 4: Audit Parser** — Misura il success rate dei parser esistenti su PDF reali, producendo una baseline documentata per campo e per formato

#### Phase 5: Estrattore Universale
- [x] **Phase 5: Estrattore Universale** — Costruisce l'estrattore Docling + Gemini 2.0 Flash con confidence scoring, capace di estrarre dati strutturati da qualsiasi PDF senza configurazione (completed 2026-02-19)

#### Phase 6: Integrazione Pipeline
- [x] **Phase 6: Integrazione Pipeline** — Integra l'estrattore universale nella pipeline esistente con fallback ai parser noti, indicatori di confidenza in UI, e gestione degradata senza Gemini (2/2 piani completati — 2026-02-20)

## Phase Details

### Phase 4: Audit Parser
**Goal**: Conoscere esattamente dove i parser esistenti falliscono — quale campo, quale formato, quale percentuale di successo — per avere una baseline misurabile prima di costruire l'alternativa
**Depends on**: Test PDFs at C:\Users\39334\Documents\ORDINI (outside repo — must exist before execution)
**Requirements**: AUDIT-01, AUDIT-02
**Success Criteria** (what must be TRUE):
  1. Eseguendo lo script di audit su tutti i PDF in C:\Users\39334\Documents\ORDINI, si ottiene un report con success rate percentuale per ciascun campo (cliente, numero_ordine, articoli, quantita, data_consegna) suddiviso per formato noto
  2. Il report elenca i formati con success rate sotto il 100% e indica quali campi specifici mancano o contengono dati errati per ciascun formato
  3. Il report e leggibile senza strumenti speciali (file di testo o stdout strutturato) e costituisce una baseline documentata per confrontare i risultati post-Phase 5
  4. Il report viene generato in meno di 2 minuti sull'intero set di PDF disponibili
**Plans:** 2/2 plans complete

Plans:
- [x] 04-01-PLAN.md — Script audit_parsers.py con report per-campo per-formato e baseline persistente

### Phase 5: Estrattore Universale
**Goal**: Un estrattore autonomo che, dato qualsiasi PDF, restituisce i campi chiave con indicatori di confidenza — senza richiedere parser dedicati o configurazione per il formato specifico
**Depends on**: Phase 4 (baseline), Gemini API key (utente deve ottenerla prima dell'esecuzione)
**Requirements**: EXTR-01, EXTR-02, EXTR-03, EXTR-04
**Success Criteria** (what must be TRUE):
  1. Dato un PDF mai visto in precedenza, l'estrattore restituisce un dict JSON con i campi cliente, numero_ordine, data_consegna e articoli (con quantita e descrizione) — senza modificare alcun file di configurazione o codice
  2. Ogni campo nel dict JSON restituito include un indicatore di confidenza (alta/media/bassa) come campo separato
  3. L'estrattore usa Docling per convertire il PDF in testo strutturato prima di inviarlo a Gemini 2.0 Flash — il testo Docling intermedio e ispezionabile per il debugging
  4. Testando l'estrattore sui PDF dell'audit (Phase 4), il success rate complessivo supera quello dei parser specifici per i formati con baseline bassa
  5. Se la risposta Gemini e malformata o vuota, l'estrattore solleva un'eccezione tipizzata — non restituisce dati parziali silenziosi
**Plans:** 2 plans

Plans:
- [x] 05-01-PLAN.md — Installa google-genai e costruisce universal_extractor.py (Docling + Gemini + confidence schema)
- [ ] 05-02-PLAN.md — Script di validazione test_universal_extractor.py con confronto baseline Phase 4

### Phase 6: Integrazione Pipeline
**Goal**: L'estrattore universale e il percorso predefinito nella pipeline di parsing — l'utente vede i risultati con indicatori di confidenza, i parser esistenti restano come fallback, e la mancanza di Gemini non blocca il flusso
**Depends on**: Phase 5
**Requirements**: PIPE-01, PIPE-02, PIPE-03
**Success Criteria** (what must be TRUE):
  1. Caricando un PDF di qualsiasi formato nella pagina ordini estratti, i dati estratti appaiono normalmente — senza indicazione all'utente di quale parser o strategia ha prodotto il risultato
  2. I campi estratti con confidenza bassa sono visivamente distinti nella pagina ordini estratti (es. bordo colorato, icona, tooltip) cosi l'utente sa immediatamente cosa deve verificare manualmente
  3. Se l'API Gemini non e raggiungibile al momento del caricamento, il sistema usa automaticamente i parser esistenti e l'utente vede un messaggio informativo — senza errori bloccanti o pagine bianche
  4. I 16 formati noti continuano a estrarre correttamente dopo l'integrazione — nessuna regressione sui parser esistenti
**Plans:** 2 plans

Plans:
- [x] 06-01-PLAN.md — load_dotenv in run.py + integrazione extract_universal() con fallback in app.py (PIPE-01, PIPE-03)
- [x] 06-02-PLAN.md — Sezione upload singolo PDF e confidence badges in ordini_estratti.html (PIPE-02, PIPE-03)

---

## Progress

**Execution Order:**
Phases execute in numeric order: 4 → 5 → 6
(Phases 1-3 from v1.1 are deferred — will resume after v1.2)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Modello Dati per Articolo | v1.1 | 0/0 | Deferred | - |
| 2. Assegnazione Fasi | v1.1 | 0/0 | Deferred | - |
| 3. Viste Reparto | v1.1 | 0/0 | Deferred | - |
| 4. Audit Parser | v1.2 | 1/1 | Complete | 2026-02-19 |
| 5. Estrattore Universale | v1.2 | 2/2 | Complete | 2026-02-19 |
| 6. Integrazione Pipeline | v1.2 | 2/2 | Complete | 2026-02-20 |
