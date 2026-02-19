# Stato Progetto — Schedulatore Laser

## Riferimento Progetto

Vedi: .planning/PROJECT.md (aggiornato 2026-02-19)

**Valore principale:** Gli operatori vedono cosa deve essere lavorato e tracciano il completamento in tempo reale
**Focus attuale:** Fase 3 — Viste Reparto (viste reparto con dati fasi per articolo)

## Posizione Attuale

Fase: 3 di 3 (Viste Reparto)
Piano: 1 di 2 nella fase attuale
Stato: Piano 03-01 completato — API arricchita per-articolo + laser.html riscritto
Ultima attivita: 2026-02-19 — Piano 03-01 completato: API phase_status + laser.html con Avvia Tutti e UUID-based completion (VISTA-01/02 soddisfatti)

Progresso: [████████░░] 80%

## Metriche Prestazioni

**Velocita:**
- Piani completati totali: 5
- Durata media: ~4min
- Tempo esecuzione totale: ~20 min

**Per Fase:**

| Fase | Piani | Totale | Media/Piano |
|------|-------|--------|-------------|
| 1. Modello Dati | 3/3 | ~12min | 4min |
| 2. Assegnazione Fasi | 1/1 | ~4min | 4min |
| 3. Viste Reparto | 1/2 | ~4min | 4min |

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
- session.flush() (non commit) per ottenere article.id prima di creare ProcessingStep figli
- Batch mode (no article_id) mantenuto in start_phase/complete_phase per compatibilita frontend esistente
- get_order_details: path v1.1+ (Article records) con fallback a logica JSON per ordini pre-v1.1
- update_order_articles: matching per code+name per identita stabile degli articoli
- PRAGMA table_info() + ALTER TABLE per aggiungere colonne a tabelle esistenti in SQLite (create_all non modifica tabelle esistenti)
- article_records[] nella risposta create_order: UUID articoli disponibili subito senza secondo GET
- 409 Conflict per PUT /phases quando step gia avviati — distingue conflitto di stato da input non valido
- article_records[] aggiunto a get_all_orders_dict (non nuovo endpoint) — backward compat automatica per entrambi i consumer GET
- started_count query per articolo nel loop di get_all_orders_dict — accettabile per dataset tipico (< 500 articoli)
- Pulsante "Salva Fasi" per-ordine anziché per-articolo — UX migliore per modifiche multiple
- pendingChanges JS state tracker per filtrare chiamate API solo alle modifiche reali
- Salvataggio sequenziale async/await (for...of) per evitare race condition sui ProcessingStep
- started_phases calcolato in get_order_details() (database.py) — riutilizzabile da tutte le route senza query extra
- articles_next_phase mantenuto come alias di articles_in_phase in get_orders_by_phase — backward compat
- Seleziona Tutti (seleziona checkbox) + Completa Selezionati (invia) separati nel modale — controllo granulare operatori
- JSON articoli passato via onclick attribute con encoding &quot; — evita fetch aggiuntivo per dati già caricati

### Problemi Noti

- `get_orders_by_phase` ottimizzato con JOIN su Article+ProcessingStep (risolto in 01-02)
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
Fermato a: Completed 03-01-PLAN.md — piano 03-02 pronto per esecuzione
File di ripresa: .planning/phases/03-viste-reparto/03-01-SUMMARY.md
