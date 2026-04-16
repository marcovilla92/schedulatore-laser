---
name: Deploy produzione FerroTrack
description: Dettagli server produzione, percorsi, IP, problemi riscontrati durante deploy patch v1.1
type: project
---

Server produzione FerroTrack LS si trova sul PC dell'impiegata Elena (utente LS).

**Percorso app:** `C:\Users\LS\Desktop\schedulatore laser\schedulatore-laser\schedulatore-laser\app`
**IP server:** era 192.168.1.241, cambiato a 192.168.1.33 (IP statico impostato a 192.168.1.33 il 16/04/2026)
**APK tablet:** punta a 192.168.1.33 (ricompilato con questo IP)
**Avvio automatico:** esecuzione automatica Windows (shell:startup)

**Problemi deploy riscontrati:**
- `copy /Y` su Windows non sovrascrive sempre — usare `del` + `copy` come workaround
- File .bat con encoding UTF-8 non funzionano nel prompt Windows — usare ANSI/cp1252
- File .zip con .bat dentro vengono bloccati da email/antivirus — rinominare in .bat.txt
- WebView Android non renderizza PDF in iframe — serve PDF.js (canvas rendering)
- IP dinamico cambia al riavvio — serve IP statico

**Why:** Deploy futuro deve tenere conto di questi problemi per evitare tempo perso.
**How to apply:** Per prossime patch, usare metodo `del` + `copy`, encoding ANSI per bat, e includere PDF.js.
