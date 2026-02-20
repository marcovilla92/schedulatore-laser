---
phase: 06-integrazione-pipeline
plan: 01
subsystem: api
tags: [flask, dotenv, gemini, pdf-extraction, universal-extractor, fallback]

# Dependency graph
requires:
  - phase: 05-estrattore-universale
    provides: universal_extractor.py con extract_universal() ed ExtractionError

provides:
  - Pipeline Flask con universal extractor come percorso primario per /api/extract-pdf-data
  - Caricamento automatico GEMINI_API_KEY da app/.env all'avvio (load_dotenv in run.py)
  - Fallback silenzioso a parser classici con campo estrattore="legacy" nella risposta
  - Campo estrattore nella risposta JSON ("universal" o "legacy") per distinzione percorso UI

affects:
  - 07-frontend (se esiste): campo estrattore disponibile in data.data.estrattore
  - ordini_estratti.html: puo mostrare badge "universale" o "classico" basato su estrattore

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Import guard pattern: try/except ImportError con flag booleano _UNIVERSAL_EXTRACTOR_AVAILABLE"
    - "Fallback graceful: ExtractionError senza propagazione HTTP 500, risposta 200 con estrattore=legacy"
    - "load_dotenv prima di qualsiasi import di moduli Flask per garantire os.environ popolato"

key-files:
  created: []
  modified:
    - app/run.py
    - app/start_backend.py
    - app/backend/app.py

key-decisions:
  - "load_dotenv chiamato PRIMA dell'import di backend.app in entrambi gli entry point — garantisce GEMINI_API_KEY in os.environ quando i moduli vengono inizializzati"
  - "Import guard try/except ImportError (non Exception) — evita mascherare errori logici, cattura solo mancanza del package google-genai"
  - "/api/process-pdfs lasciato invariato (batch processing fuori scope Phase 6) — nessuna regressione"
  - "estrattore='legacy' impostato esplicitamente nei fallback path — garantisce campo sempre presente nella risposta"

patterns-established:
  - "Import guard pattern: _UNIVERSAL_EXTRACTOR_AVAILABLE flag per dipendenze opzionali pesanti"
  - "Fallback a due livelli: ImportError (google-genai non installato) vs ExtractionError (Gemini non raggiungibile)"

requirements-completed: [PIPE-01, PIPE-03]

# Metrics
duration: 8min
completed: 2026-02-20
---

# Phase 6 Plan 01: Integrazione Pipeline Summary

**Pipeline Flask con universal extractor (Docling+Gemini) come percorso primario, fallback automatico a parser classici, campo estrattore sempre presente nella risposta JSON**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-20T08:20:51Z
- **Completed:** 2026-02-20T08:28:40Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- run.py e start_backend.py caricano app/.env automaticamente all'avvio via load_dotenv, rendendo GEMINI_API_KEY disponibile senza configurazione manuale dell'environment
- app.py integra extract_universal() come percorso primario in /api/extract-pdf-data con import guard che permette a Flask di avviarsi anche senza google-genai installato
- Risposta JSON di /api/extract-pdf-data include sempre il campo estrattore ("universal" o "legacy") per distinguere il percorso usato

## Task Commits

Ogni task e stato committato atomicamente:

1. **Task 1: Aggiungere load_dotenv in run.py e start_backend.py** - `3c9035c` (chore)
2. **Task 2: Integrare extract_universal() in app.py con guarded import e fallback** - `a04f575` (feat)

## Files Created/Modified

- `app/run.py` — aggiunto load_dotenv(Path(__file__).parent / ".env") prima di import backend.app
- `app/start_backend.py` — aggiunto load_dotenv con os.path.abspath prima del blocco try
- `app/backend/app.py` — aggiunto import guard _UNIVERSAL_EXTRACTOR_AVAILABLE e blocco try/except extract_universal in /api/extract-pdf-data

## Decisions Made

- load_dotenv posizionato PRIMA dell'import di backend.app in entrambi gli entry point per garantire che os.environ contenga GEMINI_API_KEY quando i moduli vengono inizializzati a livello di package
- Import guard usa `except ImportError` (non `except Exception`) per evitare mascherare errori logici — cattura solo la mancanza del package google-genai
- /api/process-pdfs lasciato invariato: batch processing fuori scope di Phase 6, nessuna regressione
- estrattore="legacy" impostato esplicitamente in tutti i fallback path per garantire che il campo sia sempre presente nella risposta

## Deviations from Plan

None — piano eseguito esattamente come scritto.

## Issues Encountered

Nessuno. Verifica post-integrazione ha confermato che _UNIVERSAL_EXTRACTOR_AVAILABLE = True con google-genai installato. Docling mostra [WARNING] se non installato ma non blocca l'avvio di Flask (warning su stderr, non eccezione). Il fallback ExtractionError gestira questo caso a runtime.

## User Setup Required

None - nessuna configurazione di servizi esterni richiesta. GEMINI_API_KEY deve essere presente in app/.env (gia documentato come blocker noto in STATE.md dalla Phase 5).

## Next Phase Readiness

- Pipeline completamente integrata: qualsiasi PDF caricato via /api/extract-pdf-data tenta prima l'estrazione universale
- Il campo estrattore nella risposta permette alla UI di mostrare badge distintivi (es. "Gemini" vs "Parser classico")
- /api/process-pdfs rimane con parser classici — candidato per Phase 6 Plan 2 se previsto

---
*Phase: 06-integrazione-pipeline*
*Completed: 2026-02-20*
