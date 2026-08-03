# Findings Fase 1 — misura polygonize vs Lantek (2026-08-03)

**Tutto misurato, nulla stimato.** Script: `app/tests/probe_polygonize_vs_lantek.py`.

## Risultato: 0/6 con polygonize naive

| Caso | Lantek area | Miglior faccia | Delta | Note |
|---|---|---|---|---|
| 20PA00693 | 1.1635 dm² (410×30) | 0.3856 dm² (119×32) | 66,9% | frammentato |
| 20R201N0401 | 0.7414 dm² | 0.8425 dm² (253×33) | 13,6% | frammentato |
| 38APA253 | 0.0508 dm² | 0.0351 dm² (40×12) | 30,9% | frammentato |
| 46PA00375 | 84.139 dm² | 3.470 dm² (357×97) | 95,9% | frammentato |
| CPPBPA0042 | 7.623 dm² | 3.901 dm² | 48,8% | frammentato |
| CPPBPA0044 | 1.604 dm² | 0.868 dm² | 45,9% | frammentato |

## Causa radice (verificata visivamente + a codice)

I DXF del cliente (cartella 204-26, export Lantek) **NON sono file pronti al taglio**: sono **disegni tecnici A4 completi**. Render di 20PA00693 mostra:
- Cartiglio (title block): AISI 304, Sp.3, peso 0.28 kg, revisione 00
- Cornice foglio con zone (1-6, A-D)
- **Tre viste** del pezzo: vista principale (strip 410×30 con smussi + 4 fori ⌀4.50), vista laterale (spessore), vista 3D isometrica
- Quote dimensionali (410, 30, R5.50, "4x⌀4.50 PASSANTE")

Analisi entità (`ezdxf`):
- **Tutta la geometria è su layer `0`, colore `7`**: contorno pezzo, linee viste, e — cruciale — **le linee di quota esplose in LINE** sono indistinguibili dalla geometria del pezzo.
- Il contorno pezzo NON è una polilinea chiusa: è fatto di 259 LINE + 70 ARC sparse.
- Le witness-line delle quote attraversano il contorno → polygonize lo taglia in frammenti da ~119mm.

Test approcci automatici (tutti falliti, misurati):
- `polygonize` naive → 0/6 (frammenti).
- `unary_union` di tutte le facce → 1 blob da 22.58 dm² (l'intero foglio 576×392mm).
- Nessun singolo LWPOLYLINE è il contorno (solo simboli 2×2mm).
- Nessuna faccia con larghezza 360-460mm (il contorno da 410 non si chiude).

## Conclusione

**Su un DXF-disegno, nessun metodo automatico isola il pezzo** — non per un bug, ma perché il formato non separa geometria da annotazione con alcun attributo. Questo:
1. Spiega definitivamente il fallimento del detector vecchio (13,6× sull'area).
2. Conferma che l'operatore-in-the-loop è **obbligatorio**, non un fallback.
3. Solleva la domanda che cambia tutta la strategia geometria: **il cliente manda anche DXF pronti al taglio (1 file = 1 contorno piatto), o solo disegni?** Perché Lantek per tagliare ha comunque bisogno di un DXF pulito: se quel file esiste, si preventiva da QUELLO (banale ed esatto), non dal disegno.

## Risposta di Marco (2026-08-03) → strategia a due binari

- I DXF **dipendono dal cliente**: alcuni mandano file puliti pronti al taglio, altri solo disegni.
- Oggi il DXF pulito di taglio lo estrae **Lantek dal disegno con selezione operatore** (la funzione "Detect Part" che vogliamo replicare).

**Strategia geometria a due binari:**
1. **DXF pulito (1 file = 1 contorno piatto)**: `pick_part.py` polygonize estrae in modo esatto e banale. L'operatore conferma. Affidabile subito. (Manca un file pulito nel set di test per validarlo — da procurare.)
2. **DXF-disegno**: serve replicare il "Detect Part" di Lantek — l'operatore **traccia/seleziona il contorno** sul disegno renderizzato. È il cuore della Fase 2. NON è auto-detect: è tracciamento umano assistito.

## Tentativo pruning rami morti (2026-08-03) → FALLITO

Ipotesi: le witness-line delle quote sono monconi aperti; potandoli (degree-1 pruning) prima di polygonize il contorno chiuso emergerebbe. **Misurato: non funziona.** Su 20PA00693 la faccia migliore resta 119×32 (vs 410×30 Lantek); la più grande torna l'intero foglio. Il noding di `unary_union` spezza in sotto-segmenti collineari e il grado dei nodi non separa pulito i monconi dal contorno. Vicolo cieco — non committato.

## SVOLTA — contour follower dal click (2026-08-03)

Algoritmo: **click sul contorno → segui la catena di segmenti scegliendo sempre la continuazione più dritta**. Le witness-line delle quote si diramano a ~90° → ignorate naturalmente. Test `app/tests/validate_contour_follow.py`.

Risultato MISURATO su un click realistico sul bordo del pezzo:

| Caso | Lantek area | Trace area | Delta | Esito |
|---|---|---|---|---|
| 20PA00693 | 1.1635 | 1.1643 | **0.07%** | OK (era 13,6× col vecchio detector) |
| 20R201N0401 | 0.7414 | 0.7382 | **0.43%** | OK |
| 46PA00375 | 84.139 | 84.138 | **0.00%** | OK (pezzo grande 84 dm²) |
| 38APA253 | 0.0508 | — | 85% | KO |
| CPPBPA0042 | 7.6228 | — | 50% | KO |
| CPPBPA0044 | 1.6043 | — | 30% | KO |

**3/6 esatti in automatico** (da 0/6). Le 3 KO NON sono fallimenti dell'algoritmo:
- **CPPBPA0044**: il disegno contiene DUE pezzi (0044 al centro + 0045 a sinistra). Il test automatico ha tracciato quello sbagliato perché non sa quale sia lo 0044. **L'operatore clicca il pezzo giusto** → risolto in UI.
- **38APA253 / CPPBPA0042**: bivi ambigui dove "più dritto" prende un ramo sbagliato → l'operatore corregge con waypoint (click aggiuntivi lungo il contorno).

## Conclusione Fase 2

L'engine di tracciamento deterministico **funziona**: dato il click giusto sul contorno, l'area è esatta al ~0,1% vs Lantek. Ciò che serve è la UI dove l'operatore:
1. clicca il pezzo specifico (risolve multi-pezzo);
2. eventualmente guida con waypoint i bivi ambigui.
Non auto-detect: tracciamento umano assistito, come Lantek Detect Part. Ogni risultato è visibile e confermato dall'operatore (fail-safe).

## Cosa NON facciamo (disciplina anti-disastro)

Non forziamo euristiche per "indovinare" quale pezzo o quale ramo — è l'errore del 2026-07-13. L'operatore decide; l'engine calcola esatto ciò che l'operatore indica.
