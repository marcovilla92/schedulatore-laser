# Checklist DXF da aggiungere alla regression suite

**Regola d'oro**: ogni DXF che ha rotto l'app in produzione diventa un caso permanente. La suite cresce nel tempo, non si accorcia mai.

## Priorita' 1 — casi che hanno fallito al cliente 2026-07-13

Marco: quando torni compila questa lista con i DXF concreti che hanno sbagliato.

- [ ] `<nome-DXF-1>` — cosa faceva sbagliato (contorno preso dal cartiglio? area 3x quella vera?)
- [ ] `<nome-DXF-2>` — ...
- [ ] `<nome-DXF-3>` — ...

## Priorita' 2 — casi da C26-156.zip (DECA S.r.l.)

Lo ZIP di test di ieri ha 22 DXF + 1 assieme. Prioritari per coverage:

- [ ] `12B100114-00.dxf` — Piastra inf. colonna sostegno, S235JR, sp.? (leggere dal cartiglio)
- [ ] `13PA00677-00.DXF` — Scivolo frontale, S235JR sp.3, per 5Lt rast.
- [ ] `13SA0070-00/13SA0070-00.DXF` — Assieme completo CVE 5Lt (importante: caso ASSIEME, non pezzo)
- [ ] `13SA0070-00/13P010103-00.dxf` — componente assieme
- [ ] `13SA0070-00/13PA00188-00.dxf` — componente assieme
- [ ] `191700281-00.DXF` — Staffa sostegno tetto, AISI 304 sp.4
- [ ] `20PA00789-00.dxf` — Lamiera 400x30 sp.2 AISI 304 trafilato
- [ ] `46PA00428-00.dxf` — Piastra 600x550 sp.12 S235JR (piastra grande liscia — attenzione al filtro cornice)
- [ ] `47PA01384-00.dxf` — Nervatura 30x30 sp.4 AISI 304 (pezzo piccolo)
- [ ] `47PA01923-00.dxf` — Lama guida pezzo sp.1 C75 (spessore raro, materiale non standard)

## Priorita' 3 — coverage edge case

Casi che DEVONO essere nella suite anche se non hanno mai rotto (test di non regressione futura):

- [ ] Piastra rettangolare **liscia** senza fori — il vecchio detector la scartava come "cornice cartiglio" (BUG FIX #6). Non deve piu' succedere.
- [ ] DXF con **cornice cartiglio complessa multipla** (>= 3 cornici concentriche) — filtro cornice deve gestirlo
- [ ] DXF con contorno da SolidWorks con **gap 0.6-1.5mm** tra segmenti (BUG FIX #5) — chain walking adattivo deve chiuderlo
- [ ] DXF con **svasature interne** (cerchi concentrici multipli) — regola deterministica deve escluderle dai fori
- [ ] DXF con **filettature** (cerchio+arco concentrico) — regola deterministica deve escluderle
- [ ] DXF ISO **A4/A3/A2 dimensioni esatte** — filtro cartiglio deve escludere solo il frame, non piastre di dimensioni simili

## Come compilare un caso

Vedi [README.md](README.md) — procedura passo-passo.

## Cronologia

- 2026-07-13 — creazione suite, seed self-test 20PA00693 (NON e' regression vera, solo bootstrap infrastruttura)
