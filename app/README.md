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
│   ├── database.py                ORM SQLAlchemy + Manager (Order, User, Barcode, ...)
│   ├── models.py                  modelli DB (Order, OfficinaScan, Pistola, ...)
│   └── pdf_cartellino.py          generazione cartellino A6 con barcode Code128
│
├── frontend/                      pagine HTML (vanilla, no framework)
│   ├── login.html                 login + routing per ruolo
│   ├── impiegata.html             Elena: carico ordini, fatturazione, sospetti finiti
│   ├── capo-officina.html         Stefano/Paolo: KPI operai, ordini attivi, pistole
│   ├── laser.html                 Mirko: calendario laser + visualizzazione PDF
│   ├── admin.html                 utenti, soglie sistema, backup, audit log
│   ├── operaio-info.html          pagina muta per operai (lavorano solo con pistola)
│   └── archivio.html              storico ordini chiusi (read-only)
│
├── scan_hub/                      bridge pistole barcode → server
│   ├── scan_hub.py                servizio Python sul PC hub (Elena)
│   └── scan_hub_config.json       mappa prefisso pistola → operatore
│
├── uploads/{pdfs,drawings}/       file caricati dagli utenti (gitignored)
├── database/scheduler.db          SQLite (gitignored)
├── app_config.json                soglie sistema + orario lavoro
├── backup_config.json             impostazioni backup automatico
├── run.py                         entry point Flask + thread cron (backup, fine turno)
└── backup_db.py                   backup automatico DB con scheduler
```

## Flusso operativo

1. **Elena** carica un PDF di ordine → sistema crea record con cartellino barcode stampabile
2. **Mirko** vede l'ordine in `laser.html`, marca "taglio completato" quando finito
3. **Operai officina** scansionano il cartellino con la pistola → `OfficinaScan` apre sessione
4. Operaio scansiona di nuovo (lo stesso o altro ordine) → chiude la sessione precedente
5. Sistema calcola tempo *lavorativo* (esclude pausa pranzo e ore fuori orario) automaticamente
6. **Capo officina** vede KPI ore/operaio e ordini in lavorazione in `capo-officina.html`
7. Capo o Elena chiudono l'ordine → status `DA_FATTURARE` → Elena emette DDT/fattura

### Ridondanza "ordini sospetti finiti"

Se un ordine ha il taglio completato da N giorni (default 5) e nessuna scansione da M giorni (default 3), compare in una sezione rossa nel pannello capo + Elena. Soglie configurabili da `admin.html` → tab Soglie.

### Chiusura automatica fine turno

Un thread cron in `run.py` chiude tutte le scansioni rimaste aperte all'orario configurato (default 17:30). Orario letto dinamicamente da `app_config.json` — modificabile da admin senza riavvio.

## Database

4 tabelle live:
- `orders` — ordini con cliente, numero, data consegna, status amministrativo
- `users` — operai/capi/impiegate/admin con ruoli e permessi
- `officina_scans` — sessioni di lavoro aperte/chiuse via barcode
- `pistole` — registrazione pistole con mapping operatore

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
