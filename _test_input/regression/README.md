# Regression suite DXF — fondamenta preventivatore

**Scopo**: garantire che ogni modifica al codice di rilevamento geometria pezzo (`pick_part_from_click`, ex `compute_geometry_from_point`) non regredisca su nessun DXF reale del cliente. Nessuna metrica di affidabilità viene mai stimata: è sempre e solo "M/N test passano".

## Struttura

```
_test_input/regression/
├── README.md               ← questo file
├── _TEMPLATE/              ← modello da copiare per ogni nuovo caso
│   ├── expected.json
│   └── NOTES.md
├── <nome-caso-1>/
│   ├── pezzo.dxf           ← il DXF reale
│   └── expected.json       ← valori attesi + coordinate click
└── ...
```

Il nome della sottocartella deve essere descrittivo e stabile (usato negli output di test): es. `13SA0070-00_assieme`, `deca_46PA00428-00_piastra_S235_sp12`, `sw_solidworks_cornice_multipla`.

## Come aggiungere un caso

1. **Copia il template**:
   ```
   cp -r _TEMPLATE mio_nuovo_caso
   ```

2. **Sostituisci** `mio_nuovo_caso/pezzo.dxf` con il DXF reale.

3. **Compila** `mio_nuovo_caso/expected.json` con i valori misurati (NON stimati):
   - `click_x_mm`, `click_y_mm`: aprire il DXF in un CAD (Lantek, AutoCAD viewer, DraftSight, ezdxf visualizer), individuare un punto sul **contorno esterno** del pezzo, leggere le sue coordinate. Questi sono i pixel che l'operatore cliccherebbe in produzione.
   - `expected.area_dm2`: area netta della lamiera (esclusi i fori), letta dal pannello "Proprietà" del CAD. Convertire da mm² a dm² dividendo per 10 000.
   - `expected.perim_m`: perimetro totale di taglio (contorno esterno + tutti i fori). Convertire da mm a m dividendo per 1000.
   - `expected.n_fori`: conteggio manuale dei fori di taglio (escludere svasature e filettature).
   - `expected.materiale`: dal cartiglio, valore enum standard (S235, INOX_304, ecc.)
   - `expected.spessore_mm`: dal cartiglio.

4. **Compila** `NOTES.md` (opzionale ma consigliato) con:
   - Come sono stati misurati i valori attesi (quale CAD, quale procedura)
   - Perché questo caso è interessante (edge case, ha rotto il vecchio detector, ecc.)
   - Screenshot del DXF se utile

## Come eseguire la suite

Dalla root del progetto:

```
python app/tests/test_regression_dxf.py
```

Output: tabella con `PASS` / `FAIL` per caso, exit code non-zero se qualche test fallisce.

Opzioni:
- `--only <nome-caso>` — esegue solo un caso
- `--verbose` — mostra dettagli su ogni output vs expected

## Tolleranze default

- Area: ±0.5% (misure Shapely vs CAD commerciali possono differire per gestione arrotondamenti su archi/spline flatting)
- Perimetro: ±0.5%
- N fori: ±0 (esatto)
- Materiale, spessore: esatti

Le tolleranze possono essere override per caso in `expected.json` sotto `tolleranze:`.

## Regola operativa

**Nessun commit al codice DXF detection senza far girare questa suite.** Se un test fallisce che prima passava, il commit va rifatto.

Ogni DXF che si rompe in produzione diventa un nuovo caso nella suite. La suite cresce nel tempo, non si accorcia mai.
