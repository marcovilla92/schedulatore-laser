# Stato Progetto — Schedulatore Laser

## Riferimento Progetto

Vedi: .planning/PROJECT.md (aggiornato 2026-02-19)

**Valore principale:** Gli operatori vedono cosa deve essere lavorato e tracciano il completamento in tempo reale
**Focus attuale:** Fase 1 — Modello Dati per Articolo (base backend per fasi per articolo)

## Posizione Attuale

Fase: 1 di 3 (Modello Dati per Articolo)
Piano: 1 di 3 nella fase attuale
Stato: Piano 01-01 completato
Ultima attivita: 2026-02-19 — Piano 01-01 eseguito: Article model + migration utility

Progresso: [█░░░░░░░░░] 10%

## Metriche Prestazioni

**Velocita:**
- Piani completati totali: 0
- Durata media: —
- Tempo esecuzione totale: 0 ore

**Per Fase:**

| Fase | Piani | Totale | Media/Piano |
|------|-------|--------|-------------|
| 1. Modello Dati | 1/3 | ~2min | 2min |
| 2. Assegnazione Fasi | 0/0 | — | — |
| 3. Viste Reparto | 0/0 | — | — |

## Contesto Accumulato

### Da v1.0 (Pre-GSD)

- Revisione backend ha corretto 14 bug critici/alti (2026-02-18)
- UI ridisegnata: 7 pagine con dark glassmorphism
- GSD v1.20.4 installato con ecosistema skill completo

### Decisioni

- flag_modified() necessario per mutazioni JSON in SQLAlchemy
- Limite upload 50MB per sicurezza
- Default lambda per colonne con valori mutabili
- Modello fasi per articolo scelto rispetto a fasi per ordine (decisione core v1.1)
- required_phases come colonna JSON (non tabella normalizzata) — coerente con pattern esistenti
- attributes JSON catch-all per campi extra dai formati PDF — schema flessibile senza proliferare colonne
- ProcessingStep.article_id nullable — zero costo di migrazione per step pre-v1.1

### Problemi Noti

- `get_orders_by_phase` carica TUTTI gli ordini (ottimizzare con JOIN quando il volume cresce)
- `declarative_base()` deprecato in SQLAlchemy 2.0
- `datetime.utcnow()` deprecato in Python 3.12+

### Bug Risolti (sessione 2026-02-19)

- Bug #1: `complete_phase` non popolava `completed_articles` — corretto
- Bug #2: Ordini con fasi miste bloccati su RICEVUTO — corretto (derive fasi da articoli)
- Bug #3: Calendario Dashboard non mostrava date consegna — corretto

### Todo in Sospeso

Nessuno.

### Blocchi/Problemi

Nessuno.

## Continuita Sessione

Ultima sessione: 2026-02-19
Fermato a: Completato 01-01-PLAN.md — Article model + migration utility
File di ripresa: .planning/phases/01-modello-dati-per-articolo/01-01-SUMMARY.md
