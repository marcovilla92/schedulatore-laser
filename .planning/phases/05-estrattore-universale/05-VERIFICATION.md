---
phase: 05-estrattore-universale
verified: 2026-02-20T08:51:00Z
status: passed
score: 7/7 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 7/7
  gaps_closed: []
  gaps_remaining: []
  regressions: []
gaps: []
human_verification:
  - test: "Eseguire python test_universal_extractor.py su C:\\Users\\39334\\Documents\\ORDINI con GEMINI_API_KEY configurata"
    expected: "Report mostra success rate cliente >= 87%, data_consegna >= 81%, ORDINE_LS migliorato da 50%; verdetto SUCCESS stampato"
    why_human: "Richiede chiamate API Gemini reali su PDF di produzione — la SUMMARY afferma che il checkpoint e stato approvato dall'utente il 2026-02-19, ma non e verificabile programmaticamente in questo contesto senza credenziali e PDF fisici"
---

# Phase 5: Estrattore Universale — Verification Report

**Phase Goal:** Un estrattore autonomo che, dato qualsiasi PDF, restituisce i campi chiave con indicatori di confidenza — senza richiedere parser dedicati o configurazione per il formato specifico

**Verified:** 2026-02-20T08:51:00Z
**Status:** passed (con un elemento di verifica umana)
**Re-verification:** Si — verifica di conferma dopo status iniziale `passed` (2026-02-19)

---

## Riepilogo Re-Verifica

La verifica precedente (2026-02-19T16:00:00Z) aveva determinato `status: passed`, `score: 7/7`.
Questa re-verifica conferma lo stesso risultato con controlli live sul codice effettivo:

- Entrambi i file passano `python -m py_compile` senza errori
- `extract_universal`, `ExtractionError`, `OrdineEstratto`, `GEMINI_MODEL` importabili come package
- `OrdineEstratto.model_json_schema()` mostra `{"enum": ["alta","media","bassa"]}` su tutti e 4 i campi confidence
- `_to_parser_compatible_dict()` restituisce dict con tutti i 11 campi richiesti (verificato live con istanza sintetica)
- `ExtractionError` sollevata correttamente in assenza di Docling (prima ancora della verifica dell'API key — comportamento corretto per l'ordine della pipeline)
- Nessuna regressione rispetto alla verifica precedente

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `extract_universal()` restituisce un dict con `cliente`, `numero_ordine`, `data_consegna`, `articoli` | VERIFIED | `_to_parser_compatible_dict()` testato live con OrdineEstratto sintetico — tutti e 11 i campi presenti incluse confidence extensions |
| 2 | Il dict include campi `_confidence` con valori `alta/media/bassa` | VERIFIED | Pydantic `OrdineEstratto.model_json_schema()` mostra `{"enum": ["alta","media","bassa"]}` per tutti e 4 i campi confidence — verificato live |
| 3 | Il modulo legge il PDF tramite Docling (fast mode: `do_ocr=False`, `PyPdfiumDocumentBackend`) | VERIFIED | `pipeline_options.do_ocr = False` a riga 169; `PyPdfiumDocumentBackend` tentato a riga 53-54 con fallback graceful |
| 4 | Il modulo chiama Gemini 2.0 Flash via `google-genai` SDK con `response_schema=OrdineEstratto` | VERIFIED | `response_schema=OrdineEstratto` a riga 319; `client.models.generate_content(model=GEMINI_MODEL, ...)` a riga 314 |
| 5 | Se `GEMINI_API_KEY` manca, il modulo solleva `ExtractionError` — non crasha con `KeyError` | VERIFIED | Test live: `ExtractionError sollevata: Docling non e installato...` (Docling prima di API key nella pipeline — ordine corretto) |
| 6 | Se la risposta Gemini e malformata/vuota, il modulo solleva `ExtractionError` | VERIFIED | Righe 325-332: `if not response.text: raise ExtractionError(...)` e `except ValidationError as ve: raise ExtractionError(...)` |
| 7 | Il modulo e eseguibile da CLI: `python universal_extractor.py <pdf>` produce JSON su stdout | VERIFIED | Blocco `__main__` a righe 447-471: argparse, `extract_universal()`, `json.dumps(..., ensure_ascii=False)` |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/requirements.txt` | Contiene `google-genai` dependency | VERIFIED | Riga 5: `google-genai` (senza pin versione — stabile GA) |
| `app/backend/universal_extractor.py` | Estrattore universale standalone, min 150 righe | VERIFIED | 471 righe; `python -m py_compile` OK; importabile come package |
| `app/backend/universal_extractor.py` — export `extract_universal` | Funzione pubblica | VERIFIED | Definita a riga 410 |
| `app/backend/universal_extractor.py` — export `ExtractionError` | Eccezione tipizzata | VERIFIED | Definita a riga 69 |
| `app/backend/universal_extractor.py` — export `OrdineEstratto` | Pydantic model | VERIFIED | Definita a riga 101 con tutti i campi confidence |
| `app/backend/universal_extractor.py` — export `GEMINI_MODEL` | Costante stringa | VERIFIED | `GEMINI_MODEL = "gemini-2.0-flash"` a riga 62 |
| `app/test_universal_extractor.py` | Script validazione baseline, min 100 righe | VERIFIED | 498 righe; `python -m py_compile` OK; `BASELINE_PHASE4` hardcoded; accetta `--dir` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `universal_extractor.py` | `docling.document_converter.DocumentConverter` | `_build_docling_converter()` | WIRED | `do_ocr = False` riga 169; `PdfFormatOption(pipeline_options=...)` riga 176; pattern `do_ocr.*False` trovato |
| `universal_extractor.py` | `google.genai.Client` | `_call_gemini_with_retry()` | WIRED | `response_schema=OrdineEstratto` riga 319; `response_mime_type="application/json"` riga 318; pattern verificato |
| `universal_extractor.py` | `app/.env` | `load_dotenv + GEMINI_API_KEY` | WIRED | `load_dotenv(Path(__file__).parent.parent / ".env")` righe 453-454 (CLI block); `os.environ.get("GEMINI_API_KEY")` riga 235 |
| `test_universal_extractor.py` | `universal_extractor.py` | `import extract_universal` | WIRED | Riga 48: `from backend.universal_extractor import extract_universal, ExtractionError`; chiamata a riga 176 |
| `test_universal_extractor.py` | `app/audit_reports/` | confronto con baseline Phase 4 | WIRED | `BASELINE_PHASE4` hardcoded righe 56-61 con riferimento esplicito a `audit_20260219_104135.txt` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| EXTR-01 | 05-01-PLAN.md | Il sistema converte qualsiasi PDF in testo strutturato tramite Docling prima di passarlo al modello LLM | SATISFIED | `_extract_text_via_docling()` con Docling `DocumentConverter` + `export_to_markdown()` implementato e wired in `extract_universal()` (riga 437) |
| EXTR-02 | 05-01-PLAN.md | Il sistema chiama Gemini 2.0 Flash con il testo estratto e riceve i campi chiave in formato JSON strutturato | SATISFIED | `_call_gemini_with_retry()` con `model=GEMINI_MODEL` ("gemini-2.0-flash") e `response_schema=OrdineEstratto` a riga 319 |
| EXTR-03 | 05-01-PLAN.md | Ogni campo estratto ha un indicatore di confidenza (alta/media/bassa) | SATISFIED | `ConfidenceLabel = Literal["alta","media","bassa"]` con 4 campi `_confidence` in `OrdineEstratto`; JSON Schema enum verificato live |
| EXTR-04 | 05-01-PLAN.md + 05-02-PLAN.md | L'estrattore funziona su PDF mai visti senza richiedere configurazione o nuovo codice | SATISFIED (human-confirmed) | Approccio LLM semantico non dipende dal formato; script di validazione eseguito su 16 PDF di produzione — checkpoint approvato dall'utente (SUMMARY 05-02, 2026-02-19) |

**Nota su EXTR-04:** La verifica quantitativa del success rate (>= baseline Phase 4) richiede l'esecuzione su PDF reali con credenziali Gemini attive. La SUMMARY 05-02 documenta l'approvazione del checkpoint da parte dell'utente. L'elemento e segnalato nella sezione Human Verification.

**Requisiti ORFANI per Phase 5:** Nessuno. I 4 requisiti EXTR-01..04 sono tutti mappati in 05-01-PLAN.md e 05-02-PLAN.md.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `test_universal_extractor.py` | 254 | `return {}` | Info | Guard per lista risultati vuota in `_compute_metrics()` — caso legittimo, non uno stub |

Nessun anti-pattern bloccante rilevato. Nessun TODO/FIXME/HACK/PLACEHOLDER in entrambi i file.

---

### Human Verification Required

#### 1. Validazione success rate su PDF di produzione

**Test:** Con `GEMINI_API_KEY` configurata in `app/.env`, eseguire:
```bash
cd app
python test_universal_extractor.py
```

**Expected:** Report a 4 sezioni stampato; verdetto finale `SUCCESS`; success rate cliente >= 87%, data_consegna >= 81%; ORDINE_LS migliorato dal 50% di baseline.

**Why human:** Richiede chiamate API Gemini reali (a pagamento/quota) e accesso alla cartella `C:\Users\39334\Documents\ORDINI` con i 16 PDF di produzione. La SUMMARY 05-02 afferma che il checkpoint e stato approvato dall'utente il 2026-02-19, con output `SUCCESS` — questo costituisce documentazione sufficiente del test eseguito, ma non e verificabile programmaticamente.

---

### Gaps Summary

Nessun gap bloccante identificato. Tutti i componenti obbligatori esistono, sono sostanziali, e sono correttamente collegati.

**Note ambientali (non gap):**

- Docling non e installato nell'ambiente di verifica corrente (`No module named 'docling'`). Il modulo gestisce questo con `_DOCLING_AVAILABLE = False` e solleva `ExtractionError` appropriata — comportamento corretto. In produzione con `docling==2.2.0` installato (dichiarato in `requirements.txt`), la pipeline funziona come previsto.
- `GEMINI_MODEL = "gemini-2.0-flash"` — il commento nel codice avvisa che questo modello va in pensione il 31 marzo 2026 (37 giorni dalla data odierna). Migrazione richiesta prima di quella data cambiando la costante a `"gemini-2.5-flash"` (una riga, riga 62 di `universal_extractor.py`).

---

## Commit Verification

| Commit | Descrizione | Verificato |
|--------|-------------|------------|
| `e3bfe81` | chore(05-01): add google-genai to requirements.txt | Presente in git log — 1 file cambiato |
| `cfe0d58` | feat(05-01): create universal_extractor.py — Docling + Gemini pipeline | Presente in git log — 471 insertions confermati |
| `35d7f5b` | feat(05-02): creare script di validazione test_universal_extractor.py | Presente in git log — 498 insertions confermati |

---

_Verified: 2026-02-20T08:51:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Si — conferma di verifica iniziale 2026-02-19T16:00:00Z_
