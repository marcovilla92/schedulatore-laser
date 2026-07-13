# CPPBPA0042-00

- **Fornitore/OEM**: articolo ordine 204-26 (dati Lantek reali)
- **Materiale**: FERRO (normalizzato: S235)
- **Spessore**: 2 mm
- **Bbox**: 152.921239 × 561.842477 mm
- **Peso Lantek**: 1.196784 kg
- **Area Lantek**: 0.076228 m² (7.623 dm²)
- **Perimetro Lantek**: 1.560863 m

## Come sono stati misurati i valori attesi

Estratti dall'export Lantek ORD.204.xlsx generato dal cliente. Sono i valori
che Lantek ha calcolato quando questo pezzo e' stato lavorato in produzione.

## TODO per attivare il caso

1. Aprire `pezzo.dxf` in Lantek (o vero CAD)
2. Leggere le coord (x,y) di un punto sul contorno esterno del pezzo
3. Compilare `click_x_mm` e `click_y_mm` in expected.json
4. Contare i fori di taglio (escludere svasature/filettature)
5. Compilare `expected.n_fori`
6. Rimuovere il campo TODO da expected.json

Finche' click_x/y sono null, il test skippa questo caso.
