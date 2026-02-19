# Stato Progetto — Schedulatore Laser

## Riferimento Progetto

Vedi: .planning/PROJECT.md (aggiornato 2026-02-19)

**Valore principale:** Gli operatori vedono cosa deve essere lavorato e tracciano il completamento in tempo reale
**Focus attuale:** Milestone v1.2 — Redesign UI/UX Completo

## Posizione Attuale

Fase: Non iniziata (definizione requisiti)
Piano: —
Stato: Definizione requisiti
Ultima attivita: 2026-02-19 — Milestone v1.2 iniziata

## Contesto Accumulato

### Da v1.1 (Fasi per Articolo)

- 3 fasi completate, 10 requisiti soddisfatti, ~27 min esecuzione totale
- Modello dati per articolo con required_phases e ProcessingStep per-articolo
- Assegnazione fasi da UI con checkbox
- Viste reparto filtrate + batch operations + dashboard progress

### Da v1.0 (Pre-GSD)

- Revisione backend ha corretto 14 bug critici/alti (2026-02-18)
- UI ridisegnata: 7 pagine con dark glassmorphism
- GSD v1.20.4 installato con ecosistema skill completo

### Decisioni

- flag_modified() necessario per mutazioni JSON in SQLAlchemy
- Limite upload 50MB per sicurezza
- Default lambda per colonne con valori mutabili
- Modello fasi per articolo scelto rispetto a fasi per ordine (decisione core v1.1)
- required_phases come colonna JSON (non tabella normalizzata)
- ProcessingStep.article_id nullable — zero costo di migrazione per step pre-v1.1
- Batch mode (no article_id) mantenuto per compatibilita frontend esistente
- get_order_details: path v1.1+ (Article records) con fallback a logica JSON per ordini pre-v1.1

### Problemi Noti

- `declarative_base()` deprecato in SQLAlchemy 2.0
- `datetime.utcnow()` deprecato in Python 3.12+

### Todo in Sospeso

Nessuno.

### Blocchi/Problemi

Nessuno.

## Continuita Sessione

Ultima sessione: 2026-02-19
Fermato a: Inizio milestone v1.2 — definizione requisiti
