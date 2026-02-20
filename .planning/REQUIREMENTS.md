# Requirements: Schedulatore Laser

**Defined:** 2026-02-19
**Core Value:** Operators see what needs processing next and track completion in real-time

## v1.2 Requirements

Requirements for milestone v1.2 — Parser Universale. Each maps to roadmap phases.

### Audit

- [ ] **AUDIT-01**: Il sistema esegue un test di estrazione su tutti i PDF nella cartella di test e produce un report con success rate per campo (cliente, numero_ordine, articoli, quantita, data_consegna) per ciascun formato noto
- [ ] **AUDIT-02**: Il report identifica quali formati e quali campi specifici falliscono o producono dati incompleti/errati, fornendo una baseline misurabile

### Estrattore Universale

- [x] **EXTR-01**: Il sistema converte qualsiasi PDF in testo strutturato tramite Docling prima di passarlo al modello LLM
- [x] **EXTR-02**: Il sistema chiama Gemini 2.0 Flash con il testo estratto e riceve i campi chiave in formato JSON strutturato (cliente, numero_ordine, data_consegna, articoli con quantita e descrizione)
- [x] **EXTR-03**: Ogni campo estratto ha un indicatore di confidenza (alta/media/bassa) restituito insieme ai dati
- [x] **EXTR-04**: L'estrattore funziona su PDF mai visti in precedenza senza richiedere configurazione o nuovo codice

### Integrazione Pipeline

- [x] **PIPE-01**: La pipeline di parsing usa l'estrattore universale come primo tentativo; i parser specifici esistenti rimangono disponibili come fallback per i 16 formati noti
- [ ] **PIPE-02**: Nella pagina ordini estratti, i campi con confidenza bassa sono evidenziati visivamente cosi l'utente sa cosa verificare manualmente
- [x] **PIPE-03**: Se Gemini API non e raggiungibile, il sistema cade in fallback sui parser esistenti senza errori bloccanti per l'utente

## Future Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### Miglioramenti Parser

- **PARSER-01**: Correzione parser specifici per i formati con success rate basso identificati dall'audit (se l'estrattore universale non li copre adeguatamente)
- **PARSER-02**: Cache dei risultati Gemini per PDF identici (stesso hash) — evita chiamate API ridondanti

### Fasi per Articolo (v1.1 deferred)

- **FASE-01**: Assegnazione fasi per articolo tramite checkbox nella pagina ordini estratti
- **FASE-02**: Stato indipendente per articolo con avanzamento per fase
- **FASE-03**: Viste reparto filtrate per articolo con batch start/complete

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Training/fine-tuning di modelli custom | Gemini off-the-shelf e sufficiente, troppa complessita |
| Parser specifici per nuovi formati | L'estrattore universale li gestisce automaticamente |
| UI per gestire template PDF | L'approccio LLM elimina la necessita di template manuali |
| Supporto multi-LLM configurabile | Gemini 2.0 Flash e la scelta fissa per questa milestone |
| Estrazione da immagini scansionate (OCR puro) | Docling gestisce PDF nativi; scansioni di bassa qualita fuori scope |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUDIT-01 | Phase 4: Audit Parser | Pending |
| AUDIT-02 | Phase 4: Audit Parser | Pending |
| EXTR-01 | Phase 5: Estrattore Universale | Complete |
| EXTR-02 | Phase 5: Estrattore Universale | Complete |
| EXTR-03 | Phase 5: Estrattore Universale | Complete |
| EXTR-04 | Phase 5: Estrattore Universale | Complete |
| PIPE-01 | Phase 6: Integrazione Pipeline | Complete |
| PIPE-02 | Phase 6: Integrazione Pipeline | Pending |
| PIPE-03 | Phase 6: Integrazione Pipeline | Complete |

**Coverage:**
- v1.2 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0

---
*Requirements defined: 2026-02-19*
*Last updated: 2026-02-20 — Phase 6 Plan 1 complete, PIPE-01 e PIPE-03 completati*
