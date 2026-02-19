# Milestones — Schedulatore Laser

## v1.1: Fasi per Articolo (2026-02-19)

**Obiettivo:** Ogni articolo ha il proprio percorso di fasi indipendente, assegnato dall'ufficio, con gestione batch nelle viste di reparto.

**Fasi:** 3 (Fase 1–3)
**Requisiti:** 10 (tutti completati)
**Durata esecuzione:** ~27 min

### Cosa e stato consegnato

- Modello dati per articolo con `required_phases` e ProcessingStep per-articolo
- UI assegnazione fasi con checkbox in ordini_estratti
- Viste reparto (laser, piega, saldatura) filtrate per fasi assegnate
- Batch start/complete per ordine nelle viste reparto
- Dashboard con progress bar per-articolo
- Backward compatibility con ordini pre-v1.1

### Decisioni chiave

- required_phases come colonna JSON (non tabella normalizzata)
- ProcessingStep.article_id nullable per zero costo migrazione
- Batch mode mantenuto per compatibilita frontend
- Salvataggio sequenziale per evitare race condition

---

## v1.0: Rilascio Iniziale (Pre-GSD)

**Obiettivo:** Sistema base di gestione ordini e schedulazione taglio laser.

**Cosa e stato consegnato:**

- Upload PDF ed estrazione automatica dati (16 formati)
- Creazione ordine con articoli, date consegna, info cliente
- Lavorazione multi-fase: LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE
- Timer tracciamento per fase
- Dashboard stile Kanban
- Viste specifiche per fase
- Accesso multi-postazione LAN
- Allegato file DXF/DWG
- Archiviazione ordini
- UI dark glassmorphism (7 pagine)

---
*Ultimo aggiornamento: 2026-02-19*
