# Roadmap: Schedulatore Laser — v1.1 Fasi per Articolo

**Creato:** 2026-02-19
**Milestone:** v1.1
**Fasi totali:** 3
**Requisiti totali:** 10

## Panoramica

Il milestone v1.1 trasforma il sistema di schedulazione dal tracciamento fasi a livello ordine al tracciamento fasi per singolo articolo. Ogni articolo ottiene il proprio set di fasi assegnate, uno stato indipendente, e appare solo nelle viste reparto dove appartiene. Il lavoro si raggruppa in tre confini di rilascio naturali: modifiche al modello dati backend (fondazione), UI assegnazione fasi (flusso ufficio), e aggiornamento viste reparto (flusso officina).

## Fasi

**Numerazione Fasi:**
- Fasi intere (1, 2, 3): Lavoro pianificato del milestone
- Fasi decimali (2.1, 2.2): Inserimenti urgenti (marcati con INSERITO)

- [x] **Fase 1: Modello Dati per Articolo** - Modello backend, API e logica per tracciamento fasi per articolo (2026-02-19)
- [ ] **Fase 2: Assegnazione Fasi** - UI per il personale d'ufficio per assegnare/modificare fasi per articolo
- [ ] **Fase 3: Viste Reparto** - Le viste reparto mostrano e operano sui dati fasi per articolo

## Dettagli Fasi

### Fase 1: Modello Dati per Articolo
**Obiettivo**: Ogni articolo in un ordine porta le proprie fasi assegnate, traccia il proprio stato di completamento, e il sistema deriva correttamente lo stato ordine dai dati a livello articolo
**Dipende da**: Nulla (prima fase)
**Requisiti**: DATI-01, DATI-02, DATI-03, DATI-04
**Criteri di Successo** (cosa deve essere VERO):
  1. Quando un ordine viene creato via API, ogni articolo memorizza una lista `required_phases` che specifica quali fasi (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) quell'articolo deve attraversare
  2. Quando una fase viene avviata/completata per un articolo, viene creato un ProcessingStep per articolo tracciato indipendentemente dagli altri articoli nello stesso ordine
  3. Interrogando lo stato di un articolo si ottiene la prossima fase in sospeso, lista fasi completate e lista fasi rimanenti — derivate dalle fasi assegnate e dagli step completati
  4. Lo stato di un ordine cambia a "completato" solo quando ogni articolo in quell'ordine ha completato tutte le sue fasi individualmente assegnate
  5. Gli ordini esistenti senza dati fasi per articolo continuano a funzionare (compatibilita all'indietro con dati pre-v1.1)
**Piani**: 3 plans

Piani:
- [x] 01-01-PLAN.md — Article model + schema migration utility
- [x] 01-02-PLAN.md — Per-article ProcessingStep logic + status derivation
- [x] 01-03-PLAN.md — API routes update + backward compat + E2E verification

**Complessita stimata:** Alta

### Fase 2: Assegnazione Fasi
**Obiettivo**: Il personale d'ufficio puo assegnare e modificare il set di fasi richieste per ogni articolo in un ordine prima che la produzione inizi
**Dipende da**: Fase 1
**Requisiti**: FASE-01, FASE-02, FASE-03
**Criteri di Successo** (cosa deve essere VERO):
  1. Nella pagina ordini estratti, ogni articolo mostra una riga di 5 checkbox (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) e l'utente puo selezionare/deselezionare qualsiasi combinazione
  2. Quando un nuovo ordine viene creato, tutte e 5 le checkbox fasi sono selezionate per ogni articolo — l'utente rimuove le fasi che non si applicano
  3. L'utente puo cambiare le fasi assegnate a un articolo in qualsiasi momento prima che quell'articolo abbia iniziato la lavorazione nella fase da rimuovere
  4. Il salvataggio delle assegnazioni fasi le persiste nel backend e sopravvivono al reload della pagina
**Piani**: 1 plan

Piani:
- [ ] 02-01-PLAN.md — API enhancement + UI checkbox fasi per articolo in ordini_estratti.html

**Complessita stimata:** Media

### Fase 3: Viste Reparto
**Obiettivo**: Gli operatori di reparto vedono solo gli articoli pertinenti alla loro fase, possono lavorarli in batch, e la dashboard riflette il progresso per articolo
**Dipende da**: Fase 1, Fase 2
**Requisiti**: VISTA-01, VISTA-02, VISTA-03
**Criteri di Successo** (cosa deve essere VERO):
  1. In laser.html, piega.html e saldatura.html, ogni card ordine mostra solo gli articoli che hanno quella specifica fase nelle loro `required_phases` — gli articoli senza la fase non vengono mostrati
  2. L'operatore puo avviare tutti gli articoli mostrati per un ordine in quella fase con un singolo click, e completarli tutti con un singolo click (operazioni batch)
  3. La dashboard mostra il progresso per articolo per ogni ordine: quanti articoli sono in ogni fase, quanti hanno completato tutte le fasi assegnate, mostrato come breakdown visivo
  4. Quando un articolo completa la sua ultima fase assegnata, non appare piu in nessuna vista reparto — vengono mostrati solo gli articoli non completamente finiti
**Piani**: Da definire
**Complessita stimata:** Media

Piani:
- [ ] 03-01: Da definire
- [ ] 03-02: Da definire

## Progresso

**Ordine di Esecuzione:**
Le fasi si eseguono in ordine numerico: 1 → 2 → 3

| Fase | Piani Completi | Stato | Completato |
|------|----------------|-------|------------|
| 1. Modello Dati per Articolo | 3/3 | Complete   | 2026-02-19 |
| 2. Assegnazione Fasi | 1/1 | Complete   | 2026-02-19 |
| 3. Viste Reparto | 0/0 | Non iniziato | - |
