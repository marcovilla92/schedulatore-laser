# Summary: Plan 04-01 — Audit Script + Verify

**Completed:** 2026-02-19
**Phase:** 04-audit-parser
**Plan:** 01

## What Was Built

| File | Action | Lines |
|------|--------|-------|
| `app/audit_parsers.py` | Created | 480 |
| `app/audit_reports/` | Auto-created by script | — |

## Baseline Numbers (from audit run 2026-02-19 10:41:35)

**Test set:** 32 PDF files (16 unique × 2 copies) in `C:\Users\39334\Documents\ORDINI`
**Duration:** 3.2s — well under 2-minute limit
**Crash:** 0 (0%) — Unicode fix worked; no files blocked the loop

### Overall Success Rate

| Campo | PASS | Rate | Note |
|-------|------|------|------|
| `cliente` | 28/32 | **87%** | 4 FAIL su ORDINE_LS (2 file senza cliente nel testo) |
| `numero_ordine` | 32/32 | **100%** | — |
| `articoli` | 32/32 | **100%** | — |
| `quantita` | 32/32 | **100%** | Mappato su `quantita_totale` |
| `data_consegna` | 26/32 | **81%** | 6 FALLBACK (datetime.now() default) |

**File status:** OK=26 (81%) · PARTIAL=6 (18%) · FAIL=0 · CRASH=0

### Per-Format Success Rates

| Formato | PDFs | cliente | numero_ordine | articoli | quantita | data_consegna |
|---------|------|---------|---------------|----------|----------|---------------|
| DIVISIONE | 2 | 100% | 100% | 100% | 100% | 100% |
| FOR_ORDINE | 10 | 100% | 100% | 100% | 100% | 80% ⚠ |
| FOR_ORDINE_AZA | 8 | 100% | 100% | 100% | 100% | 100% |
| OAFA | 2 | 100% | 100% | 100% | 100% | 100% |
| ORDINE_LS | 8 | 50% ⚠ | 100% | 100% | 100% | 50% ⚠ |
| PO_BEBITALIA | 2 | 100% | 100% | 100% | 100% | 100% |

⚠ = campo sotto il 100%

### Findings vs Research Predictions

| Predizione ricerca | Risultato effettivo | Delta |
|-------------------|---------------------|-------|
| FOR_ORDINE_AZA mis-rilevato come FOR_ORDINE (0 articoli) | ✅ Correttamente rilevato come FOR_ORDINE_AZA (100% articoli) | **Migliore del previsto** |
| Unicode crash su 4 file con `°` | ✅ 0 crash — fix ha funzionato | Confermato |
| ORDINE_LS 0% su tutti i campi | ❌ ORDINE_LS ha 100% articoli/ordine/quantita; solo cliente=50%, data=50% | **Migliore del previsto** |
| cliente baseline 31% | ❌ Effettivo: 87% | **Molto migliore del previsto** |
| 32 PDF invece di 16 | File duplicati nella cartella (ogni PDF compare 2 volte) | Nota per Phase 5 |

## Requirements Satisfied

- **AUDIT-01** ✅ — Report con success rate per campo per formato generato e salvato
- **AUDIT-02** ✅ — Formati/campi sotto il 100% identificati: ORDINE_LS (cliente 50%, data 50%), FOR_ORDINE (data 80%)

## Baseline File

Salvato in: `app/audit_reports/audit_20260219_104135.txt`
Da usare come riferimento di confronto post-Phase 5.

## Next Phase

**Phase 5: Estrattore Universale** — costruire il parser LLM con Docling + Gemini 2.0 Flash.
I campi da migliorare per Phase 5: `cliente` (87% → 100%), `data_consegna` (81% → 100%).
Focus speciale: ORDINE_LS (2 file senza cliente nel testo).
