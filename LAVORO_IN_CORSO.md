# Lavoro in Corso — Schedulatore Laser

> **REGOLA:** Prima di iniziare a lavorare su qualcosa, aggiorna questo file e fai push.
> Cosi l'altro sa cosa stai toccando e non lavora sugli stessi file.

## Chi sta facendo cosa

| Chi | Branch | Sta lavorando su | File coinvolti | Ultimo aggiornamento |
|-----|--------|------------------|----------------|----------------------|
| Marco | `test/claude-documentation` | Bug fix fasi miste + calendario | `database.py`, `dashboard.html` | 2026-02-19 |
| Stefano | `stefano/sviluppo` | — (da assegnare) | — | — |

## File "occupati" (non toccare!)

Quando lavori su un file, aggiungilo qui. Quando hai finito, rimuovilo.

| File | Occupato da | Motivo | Da quando |
|------|-------------|--------|-----------|
| — | — | — | — |

## Aree del progetto

Dividetevi il lavoro per area cosi da evitare conflitti:

| Area | Descrizione | File principali |
|------|-------------|-----------------|
| **Backend API** | Route Flask, endpoint | `app/backend/app.py` |
| **Backend DB** | Modelli, CRUD, logica | `app/backend/models.py`, `app/backend/database.py` |
| **Parser PDF** | Estrazione dati PDF | `app/backend/pdf_parser.py`, `app/backend/parsers_*.py` |
| **Dashboard** | Calendario, statistiche | `app/frontend/dashboard.html` |
| **Laser** | Vista reparto laser | `app/frontend/laser.html` |
| **Piega** | Vista reparto piega | `app/frontend/piega.html` |
| **Saldatura** | Vista reparto saldatura | `app/frontend/saldatura.html` |
| **Archivio** | Ordini completati | `app/frontend/archive.html` |
| **Welcome** | Form creazione ordini | `app/frontend/welcome.html` |
| **Ordini Estratti** | Lista ordini da PDF | `app/frontend/ordini_estratti.html` |

## Come usare questo file

### Prima di lavorare:
1. `git pull origin <tuo-branch>` per avere l'ultimo stato
2. Controlla la tabella "File occupati" — se il file che ti serve e occupato, parlane con l'altro
3. Aggiungi i tuoi file alla tabella "File occupati"
4. Aggiorna la riga "Chi sta facendo cosa"
5. `git add LAVORO_IN_CORSO.md && git commit -m "occupo: <file>" && git push`

### Quando hai finito:
1. Rimuovi i tuoi file dalla tabella "File occupati"
2. Aggiorna la riga "Chi sta facendo cosa"
3. `git add LAVORO_IN_CORSO.md && git commit -m "libero: <file>" && git push`

## Prossime cose da fare

Scrivete qui cosa volete fare, cosi l'altro puo scegliere:

- [ ] **Fase 1 — Modello Dati per Articolo** (backend) — vedi `.planning/ROADMAP.md`
- [ ] **Fase 2 — Assegnazione Fasi** (UI ufficio)
- [ ] **Fase 3 — Viste Reparto** (UI officina)
- [ ] Aggiungere nuovi parser PDF
- [ ] Migliorare responsive mobile
- [ ] Test automatizzati

## Note

- Se dovete lavorare sullo **stesso file**, parlatevi prima e dividetevi le sezioni
- Fate **commit piccoli e frequenti** — piu facili da mergiare
- Quando finite una feature, fate **PR su master** e l'altro da un'occhiata prima del merge
