---
phase: 04-design-system-condiviso
plan: 01
subsystem: ui
tags: [css, design-system, fonts, inter, woff2, css-layer, shared-js, flask]

# Dependency graph
requires: []
provides:
  - "app/frontend/design.css — CSS design system con @layer cascade a 7 livelli, token CSS, componenti condivisi (nav, glass-card, bottoni, messaggi, spinner)"
  - "app/frontend/shared.js — Utility JS globali: filterOrders, debounce, hasDataChanged"
  - "app/frontend/fonts/ — 4 file WOFF2 Inter self-hosted (400/500/600/700), nessuna dipendenza CDN"
affects:
  - 05-aggiornamento-pagine-ui
  - laser.html
  - piega.html
  - saldatura.html
  - archive.html
  - dashboard.html
  - ordini_estratti.html
  - welcome.html

# Tech tracking
tech-stack:
  added:
    - "CSS @layer cascade (baseline Chrome 99+, Firefox 97+, Safari 15.4+)"
    - "Inter WOFF2 self-hosted via jsDelivr fontsource (pesi 400/500/600/700)"
    - "font-display: swap per caricamento font ottimale su LAN"
  patterns:
    - "CSS @layer con dichiarazione ordine esplicito in cima al file: reset, tokens, tipografia, base, componenti, layout, utility"
    - "Per-page accent color via body[data-page] selector in @layer tokens — pagine sovrascrivono via <style> inline (non in layer = priorita superiore)"
    - "@font-face fuori dai layer con url('./fonts/') relativo all'URL del CSS file"
    - "Classic <script> tag (non type=module) per esporre utility su window globale"

key-files:
  created:
    - app/frontend/design.css
    - app/frontend/shared.js
    - app/frontend/fonts/inter-latin-400-normal.woff2
    - app/frontend/fonts/inter-latin-500-normal.woff2
    - app/frontend/fonts/inter-latin-600-normal.woff2
    - app/frontend/fonts/inter-latin-700-normal.woff2
  modified: []

key-decisions:
  - "CSS @layer ordine: reset, tokens, tipografia, base, componenti, layout, utility — stili inline non-layered nelle pagine vincono automaticamente senza !important"
  - "Inter WOFF2 scaricato da jsDelivr fontsource (CDN) a build-time e servito localmente — elimina timeout 30sec Google Fonts su rete LAN"
  - "shared.js come classic script (non ES module) — le funzioni vanno su window senza CORS o complessita di import"
  - "body[data-page] per accenti per-pagina in design.css tokens layer — laser=red, piega=amber, saldatura=orange, altri=cyan default"
  - "NO JetBrains Mono in design.css — rimandato ai piani Fase 5 per piega.html e saldatura.html"

patterns-established:
  - "Pattern @layer: dichiarare tutti i layer name in cima al file prima di qualsiasi regola"
  - "Pattern font-face: URL relativo './fonts/' non assoluto '/fonts/' — entrambi funzionano ma il relativo e coerente con la struttura frontend/"
  - "Pattern shared.js: caricare PRIMA dello script inline in ogni pagina per evitare ReferenceError"

requirements-completed: [DSGN-01, DSGN-02, DSGN-03, DSGN-04]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 4 Plan 01: Design System Condiviso Summary

**CSS @layer cascade a 7 livelli con Inter WOFF2 self-hosted (4 pesi) e 3 utility JS globali — fondamenta condivise pronte per integrazione Fase 5 in 7 pagine HTML**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T11:46:02Z
- **Completed:** 2026-02-19T11:49:17Z
- **Tasks:** 2
- **Files modified:** 6 (4 font WOFF2 + design.css + shared.js)

## Accomplishments

- Creato `app/frontend/design.css` con @layer cascade a 7 livelli (reset, tokens, tipografia, base, componenti, layout, utility), @font-face per Inter a 4 pesi, token CSS completi e componenti condivisi (nav, glass-card, bottoni, messaggi, spinner, animazioni)
- Scaricati 4 file Inter WOFF2 da jsDelivr fontsource in `app/frontend/fonts/` — elimina la dipendenza da Google Fonts CDN che causa timeout 30sec su LAN
- Creato `app/frontend/shared.js` come classic script con 3 utility globali: `filterOrders()`, `debounce()`, `hasDataChanged()`
- Flask serve tutti i nuovi file (HTTP 200) tramite route catch-all `/<path:filename>` esistente — zero modifiche al backend
- Nessuna delle 7 pagine HTML esistenti modificata — Fase 5 le integrera

## Task Commits

Ogni task e stato committato atomicamente:

1. **Task 1: Download Inter WOFF2 fonts and create design.css** - `7f4444b` (feat)
2. **Task 2: Create shared.js with global utility functions** - `561403a` (feat)

**Metadata piano:** commit finale docs incluso in questo step

## Files Created/Modified

- `app/frontend/design.css` — Design system condiviso: @font-face Inter 4 pesi, @layer cascade 7 livelli, token CSS (:root + body[data-page] accents), reset, tipografia, base (animazioni, keyframes), componenti (nav, glass-card, bottoni, messaggi, spinner), layout (main, grid), utility (responsive 768px)
- `app/frontend/shared.js` — Script classico con 3 funzioni globali: filterOrders (filtra per cliente/id), debounce (rate limiting input), hasDataChanged (comparazione JSON.stringify per evitare re-render)
- `app/frontend/fonts/inter-latin-400-normal.woff2` — Inter Regular (23664 bytes)
- `app/frontend/fonts/inter-latin-500-normal.woff2` — Inter Medium (24272 bytes)
- `app/frontend/fonts/inter-latin-600-normal.woff2` — Inter SemiBold (24452 bytes)
- `app/frontend/fonts/inter-latin-700-normal.woff2` — Inter Bold (24356 bytes)

## Decisions Made

- **@layer senza !important**: Le regole in @layer hanno priorita inferiore agli stili inline non-layered. Nessun !important necessario — le pagine sovrascrivono automaticamente.
- **Inter WOFF2 locale**: Scaricato da jsDelivr fontsource a build-time, non a runtime. Elimina il timeout da Google Fonts CDN in ambienti LAN senza accesso internet.
- **body[data-page] per accenti**: Il token `--page-accent` e definito nel @layer tokens con default cyan. Ogni pagina puo sovrascriverlo via attributo data-page sul body o via `<style>` inline.
- **JetBrains Mono escluso**: piega.html e saldatura.html lo usano per display timer. Non incluso in design.css — gestito da piani Fase 5.
- **Classic script per shared.js**: Nessun type="module" — le funzioni vanno direttamente su window, zero complessita CORS con Flask.

## Deviations from Plan

None — piano eseguito esattamente come scritto.

## Issues Encountered

None — tutti i file scaricati e creati senza errori. Flask serve tutti i nuovi endpoint a HTTP 200 tramite catch-all route esistente.

## User Setup Required

None — nessuna configurazione esterna richiesta. I file WOFF2 sono inclusi nel repository.

## Next Phase Readiness

Fase 5 puo procedere immediatamente. Ogni piano Fase 5 deve:
1. Aggiungere `<link rel="stylesheet" href="/design.css">` come primo elemento in `<head>` (rimuovendo i 3 link Google Fonts)
2. Aggiungere `<script src="/shared.js"></script>` prima dello script inline
3. Aggiungere `data-page="[pagename]"` all'attributo `<body>` per attivare l'accento corretto
4. Spostare gli stili page-specific in blocchi `<style>` inline (non-layered = priorita automatica su design.css)

I 5 piani Fase 5 possono procedere in parallelo (wave simultanea) poiche lavorano su file HTML distinti senza conflitti di merge.

---
*Phase: 04-design-system-condiviso*
*Completed: 2026-02-19*
