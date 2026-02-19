# Phase 5: Estrattore Universale - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Costruire un modulo Python standalone (`universal_extractor.py` o simile) che:
1. Prende un file PDF in input
2. Lo converte in testo strutturato tramite Docling
3. Invia il testo a Gemini 2.0 Flash con un prompt strutturato
4. Restituisce un dict Python con i campi chiave + confidence scores

Questa fase NON include: integrazione nella pipeline Flask, UI per confidence scores, caching, batch processing. Quelli sono Phase 6.

</domain>

<decisions>
## Implementation Decisions

### Struttura confidence score
- Il confidence score viene assegnato **per campo** (non un unico score per ordine)
  - Campi che ricevono confidence individuale: `cliente`, `numero_ordine`, `data_consegna`, `articoli`
- La rappresentazione è una **label testuale**: `"alta"`, `"media"`, `"bassa"`
  - Formato nel dict: `{"cliente": "Rossi SRL", "cliente_confidence": "alta"}`
  - Non un numero 0.0-1.0
- Il confidence è **dichiarato da Gemini nel JSON di risposta** — il prompt chiede a Gemini di valutare la propria certezza per ogni campo
  - Non calcolato con euristiche nostre
- Per gli **articoli** (lista): un unico `articoli_confidence` per l'intera lista, non per ogni singolo articolo
  - Formato: `{"articoli": [...], "articoli_confidence": "alta"}`

### Claude's Discretion
- Formato output e compatibilità con i parser esistenti (struttura del dict, nomi campi)
- Gestione errori Gemini (retry logic, timeout, eccezioni tipizzate)
- Ruolo di Docling: se e come riabilitarlo, gestione testo intermedio
- Struttura del prompt Gemini (schema JSON richiesto, istruzioni per confidence)
- Dove posizionare il modulo nel progetto (`app/backend/` vs `app/`)

</decisions>

<specifics>
## Specific Ideas

- Il dict restituito deve includere i confidence score come campi separati con suffisso `_confidence` per ogni campo chiave
- Gemini deve restituire direttamente la label (`"alta"/"media"/"bassa"`) non un numero — il prompt deve specificarlo

</specifics>

<deferred>
## Deferred Ideas

- Nessuna idea fuori scope emersa dalla discussione

</deferred>

---

*Phase: 05-estrattore-universale*
*Context gathered: 2026-02-19*
