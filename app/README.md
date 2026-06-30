# FerroTrack — Schedulatore Laser

Sistema web per la gestione degli ordini di carpenteria metallica con tracciamento tempi tramite **pistole barcode WiFi**. Sostituisce il vecchio time tracking manuale per fasi (LASER/PIEGA/SALDATURA): l'operaio scansiona inizio/fine ordine, il sistema calcola le ore lavorate scorporando automaticamente pausa pranzo e ore non lavorative.

## Avvio rapido

```bash
cd app
pip install -r requirements.txt
python run.py
```

Server su `http://localhost:5000`. Database SQLite e cartelle upload create al primo avvio. Per accesso da LAN: `http://<server-ip>:5000`.

Su Windows: usa `START_BACKEND.bat`. Per scoprire l'IP del server in rete: `FIND_IP.bat`.

## Struttura

```
app/
├── backend/                       Flask API + business logic
│   ├── app.py                     route HTTP, endpoint REST
│   ├── database.py                ORM SQLAlchemy + Manager (Order, User, Barcode, Preventivo, ...)
│   ├── models.py                  modelli DB (Order, OfficinaScan, Pistola, Preventivo*, ...)
│   ├── events.py                  OrderEventBus (hook gestionale esterno futuro)
│   ├── pdf_cartellino.py          generazione cartellino A6 con barcode Code128
│   └── preventivi/                porting servizi Preventivatore desktop
│       ├── xlsx_importer.py       parsing Lantek XLSX
│       ├── dxf_scanner.py         analisi DXF: pieghe/saldature + area/perimetro
│       ├── laser_cost_estimator.py stima costo taglio laser da geometria + materiale
│       ├── cost_calculator.py     calcolo costi/totali con margine/sconto
│       ├── pdf_exporter.py        generazione PDF preventivo
│       ├── step_*.py              analisi STEP 3D (assiemi, tubolari, piastre)
│       └── contract.md            contratto JSON modello preventivo
│
├── frontend/                      pagine HTML (vanilla, no framework)
│   ├── login.html                 login + routing per ruolo
│   ├── impiegata.html             Elena: carico ordini, fatturazione, sospetti finiti
│   ├── capo-officina.html         Stefano/Paolo: KPI operai, ordini attivi, pistole
│   ├── laser.html                 Mirko: calendario laser + visualizzazione PDF
│   ├── preventivi.html            Commerciale: preventivi (import XLSX/DXF, calcolo, accetta)
│   ├── admin.html                 utenti, soglie sistema, backup, audit log
│   ├── operaio-info.html          pagina muta per operai (lavorano solo con pistola)
│   └── archivio.html              storico ordini chiusi (read-only)
│
├── scan_hub/                      bridge pistole barcode → server
│   ├── scan_hub.py                servizio Python sul PC hub (Elena)
│   └── scan_hub_config.json       mappa prefisso pistola → operatore
│
├── migrations/                    Alembic — versioning schema DB
│   └── versions/                  rev: 34f2aa86f9e3 baseline → 72e7509bff4a origine su orders
│
├── uploads/{pdfs,drawings}/       file caricati dagli utenti (gitignored)
├── database/scheduler.db          SQLite (gitignored)
├── app_config.json                soglie sistema + orario lavoro + laser_config
├── backup_config.json             impostazioni backup automatico
├── alembic.ini                    config Alembic
├── run.py                         entry point Flask + thread cron (backup, fine turno)
└── backup_db.py                   backup automatico DB con scheduler
```

## Flusso operativo

FerroTrack ha **due punti di ingresso** ordini, indipendenti e paralleli:

**A) Elena carica PDF** (flusso storico):

1. **Elena** carica un PDF di ordine → sistema crea record con cartellino barcode stampabile
2. **Mirko** vede l'ordine in `laser.html`, marca "taglio completato" quando finito
3. **Operai officina** scansionano il cartellino con la pistola → `OfficinaScan` apre sessione
4. Operaio scansiona di nuovo (lo stesso o altro ordine) → chiude la sessione precedente
5. Sistema calcola tempo *lavorativo* (esclude pausa pranzo e ore fuori orario) automaticamente
6. **Capo officina** vede KPI ore/operaio e ordini in lavorazione in `capo-officina.html`
7. Capo o Elena chiudono l'ordine → status `DA_FATTURARE` → Elena emette DDT/fattura

**B) Commerciale accetta preventivo** (flusso nuovo, modulo Preventivatore unificato):

1. **Commerciale** apre `preventivi.html` → "+ Nuovo preventivo" con cliente/quantità/margine
2. Importa DXF cliente → `dxf_scanner` estrae lavorazioni + area + perimetro; opzionalmente importa XLSX Lantek per costi materiale precisi
3. Per ogni articolo imposta materiale + spessore → click "Stima costo laser" usa `laser_cost_estimator` per generare il costo base (lamiera + taglio); l'utente può sovrascrivere con costo_base_override
4. Sistema mostra totali (pezzo, con margine, lotto) live
5. "Invia al cliente" → status BOZZA → INVIATO (preventivo diventa immutabile)
6. Cliente accetta esternamente → commerciale clicca "Accetta e manda in produzione" → modal preview → conferma
7. **Backend atomico**: status diventa ACCETTATO + crea Order FerroTrack con `origine='PREVENTIVO'` + numero auto `PREV-{anno}-{NNNN}` + cartellino A6 barcode + notifica capi
8. Da qui il flusso prosegue identico al punto A (Mirko taglia, operai scansionano, capo chiude, Elena fattura). Elena distingue gli ordini da preventivo dal badge `PREV` nella sua lista

### Ridondanza "ordini sospetti finiti"

Se un ordine ha il taglio completato da N giorni (default 5) e nessuna scansione da M giorni (default 3), compare in una sezione rossa nel pannello capo + Elena. Soglie configurabili da `admin.html` → tab Soglie.

### Chiusura automatica fine turno

Un thread cron in `run.py` chiude tutte le scansioni rimaste aperte all'orario configurato (default 17:30). Orario letto dinamicamente da `app_config.json` — modificabile da admin senza riavvio.

## Database

9 tabelle live:
- `orders` — ordini con cliente, numero, data consegna, status, **origine** (`PDF`|`PREVENTIVO`), **preventivo_id_origine**
- `users` — operai/capi/impiegate/admin/**commerciali** con ruoli e permessi
- `officina_scans` — sessioni di lavoro aperte/chiuse via barcode
- `pistole` — registrazione pistole con mapping operatore
- `preventivi` — preventivi cliente con cliente, qty, margine, status (`BOZZA|INVIATO|ACCETTATO|RIFIUTATO`), totali
- `preventivo_articoli` — articoli del preventivo: codice, qty, materiale, spessore, area, perimetro, costi
- `preventivo_assiemi` — assiemi 3D (STEP) con ore montaggio/saldatura
- `preventivo_tubolari` — tubolari (profili) con lunghezza, peso, costi
- `preventivo_piastre` — piastre con spessore, area, peso, costo

Schema versionato con **Alembic** (`migrations/versions/`). Per modifiche:
`python -m alembic revision -m "..." --autogenerate` poi `python -m alembic upgrade head`.

Tabelle legacy (`processing_steps`, `phase_sessions`, `phase_delegations`, `support_requests`, `operator_clients`) restano in DB ma non vengono più scritte. Servono solo per consultare lo storico vecchio in `archivio.html`.

## Pistole barcode

Vedi `scan_hub/scan_hub.py`. Architettura attuale:
- 5 pistole **Tera 2.4GHz wireless** (dongle USB) collegate al PC di Elena (centrale nel capannone, vetri)
- Ogni pistola programmata con prefisso identificativo (`M:`, `E:`, ...)
- Servizio Python su PC Elena cattura input, parsa prefisso, fa POST a `/api/scan` con `pistola_id`
- L'operaio scansiona solo, non tocca il PC

Endpoint: `POST /api/scan` body `{"pistola_id": "...", "codice": "..."}` → 200 = beep ok, 4xx = beep errore.

## API principali

| Metodo | Path | Scopo |
|---|---|---|
| GET/POST | `/api/orders` | Lista / crea ordini |
| POST | `/api/orders/<id>/close` | Chiudi ordine (status DA_FATTURARE) |
| POST | `/api/orders/<id>/mark-laser-done` | Marca taglio completato (Mirko) |
| GET | `/api/orders/<id>/cartellino` | PDF A6 con barcode |
| GET | `/api/orders/<id>/tempo-officina` | Sessioni + tempo lavorativo cumulato |
| GET | `/api/orders/sospetti-finiti` | Ordini probabilmente finiti |
| POST | `/api/scan` | Scansione barcode (chiamata da pistole) |
| GET | `/api/officina/live-status` | Stato officina live (Elena) |
| GET | `/api/capo/kpi-operai` | Ore lavorate per operaio |
| GET/PUT | `/api/admin/config` | Soglie sistema + orario lavoro |
| CRUD | `/api/admin/pistole` | Gestione pistole registrate |
| GET/POST | `/api/users` | CRUD utenti (riservato capi) |
| CRUD | `/api/preventivi` | CRUD preventivi (Commerciale/Admin/Capi) |
| POST | `/api/preventivi/<id>/import-xlsx` | Upload XLSX Lantek → estrae articoli |
| POST | `/api/preventivi/<id>/import-dxf` | Upload DXF → lavorazioni + area + perimetro |
| POST | `/api/preventivi/<id>/articoli/<a>/stima-base` | Calcola costo laser stimato |
| POST | `/api/preventivi/<id>/invia` | BOZZA → INVIATO (immutabile) |
| POST | `/api/preventivi/<id>/accetta` | INVIATO → ACCETTATO + crea Order FerroTrack |
| POST | `/api/preventivi/<id>/rifiuta` | INVIATO → RIFIUTATO |
| GET/PUT | `/api/admin/laser-config` | Coefficienti stimatore laser (€/kg, velocità taglio, €/h) |
| GET | `/api/admin/export-orders?format=csv\|json` | Export ordini per gestionale esterno |

## Tech stack

- **Backend**: Python 3.10+, Flask, SQLAlchemy (SQLite WAL mode)
- **Frontend**: HTML5 + CSS3 + JS vanilla (Geist + Inter fonts, zero framework)
- **PDF**: PyPDF2, pdfplumber (parsing ordini), reportlab + python-barcode (cartellini)
- **Scan hub**: Python `keyboard` + `requests` su PC dedicato

## Sviluppo

- Sintassi: `python -m py_compile backend/*.py`
- Health check: `curl http://localhost:5000/api/health`
- Backup manuale DB: bottone in `admin.html` → tab Backup, oppure `POST /api/admin/backup`
- Audit log: `admin.html` → tab Audit log (azioni amministrative tracciate)
