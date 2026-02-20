---
status: complete
phase: 06-integrazione-pipeline
source: 06-01-SUMMARY.md, 06-02-SUMMARY.md
started: 2026-02-20T10:00:00Z
updated: 2026-02-20T10:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. POST API extract-pdf-data returns structured data
expected: |
  Posting a PDF to /api/extract-pdf-data returns HTTP 200 with success: true and 4 fields: cliente, numero_ordine, data_consegna, articoli
result: pass

### 2. Response includes estrattore field
expected: |
  The /api/extract-pdf-data response always contains an estrattore field set to either "universal" (Gemini used) or "legacy" (fallback to classic parsers)
result: pass

### 3. Fallback to legacy parsers when Gemini unavailable
expected: |
  When Gemini is not available (google-genai not installed or API key missing), the system automatically falls back to classic parsers and returns estrattore="legacy" without errors
result: pass

### 4. Ordini estratti page loads without errors
expected: |
  Opening http://localhost:5000/ordini-estratti in browser loads the page successfully with no console errors or 500 status codes
result: pass

### 5. Upload singolo section is visible
expected: |
  The "Carica PDF singolo" section appears on the page above the "Elabora Tutti i PDF" button with a file input labeled "Seleziona PDF:"
result: pass

### 6. File input accepts .pdf files
expected: |
  Clicking the file input in "Carica PDF singolo" opens file picker, allows selecting a .pdf file, and clicking a .pdf file selects it
result: pass

### 7. Result box shows 4 fields after upload
expected: |
  After selecting and uploading a PDF via the singolo section, a "Risultato Estrazione" box appears showing 4 fields: Cliente, N. Ordine, Data Consegna, Articoli with extracted values
result: pass

### 8. Confidence badges render with correct colors
expected: |
  In the result box, fields with bassa confidence show an amber "! bassa" badge, fields with media confidence show a cyan "~ media" badge
result: pass

### 9. Alta confidence fields have no badge
expected: |
  Fields with alta confidence in the result box display no badge, just the field value (clean appearance for high-confidence fields)
result: pass

### 10. Legacy notice appears when estrattore != universal
expected: |
  When the fallback legacy parser is used (estrattore="legacy"), a blue informational message appears: "Estratto con parser classici (Gemini non disponibile) — i dati sono corretti ma senza indicatori di confidenza" — NOT a red error message
result: pass

### 11. Existing DB orders show no confidence badges
expected: |
  In the main ordini estratti table (orders loaded from database), the existing orders do not show confidence badges or "undefined" text in any cells — confidence fields are transient (upload singolo only)
result: pass

### 12. No console errors on page load
expected: |
  Opening /ordini-estratti in browser and checking the browser console shows no JavaScript errors, network errors, or failed API calls
result: pass

## Summary

total: 12
passed: 12
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
