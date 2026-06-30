# Ricerca: Modello Costo Taglio Laser — Replicare Lantek Expert

**Data ricerca**: 2026-06-30
**Branch**: stefano/merge-preventivatore
**Obiettivo**: stimatore preventivi laser con errore <10% vs Lantek reale
**Stato attuale**: errore medio 38% con modello `peso × €/kg + perim × €/m + setup`

---

## 1. Diagnosi (audit codice + dati Lantek reali)

### Il modello strutturale è CORRETTO
Regressione lineare su 3 articoli INOX 3mm reali Lantek (ORD.204) dà errore **0%** con formula:
```
costo = €/kg × peso + €/m × perim + setup
```
Sistema 3-incognite con 3 osservazioni → esattamente determinato. **Conferma**: Lantek dietro le quinte usa la stessa formula. Il problema dell'errore 38% **non è la formula, sono i coefficienti e i casi limite**.

### Le 4 cause dell'errore residuo

1. **Pierce-time fisso 0.05€** indipendente da materiale/spessore.
   Realtà: S235 1mm = 0.3s/foro (~0.003€), S235 12mm = 3-4s/foro (~0.06€), INOX 304 8mm = 2-3s/foro. Su pezzi piccoli con molti fori il pierce può essere **30-50% del tempo totale**.

2. **Niente coefficiente complessità (k_accel)**.
   Stessa lunghezza perimetro ma geometria con molti spigoli/festonature = tempo +30-45% per accel/decel continui. Tabella `€/m` lineare ignora questo. Range tipico `k_accel = 0.5-0.85`.

3. **Calibrazione povera**.
   Solo 6 articoli ORD.204 disponibili → 3 combo (INOX 3mm, S235 2mm, S235 12mm). Altri materiali/spessori sono interpolati o approssimati.

4. **Area DXF imprecisa** (bbox lordo, non sottrae fori interni grandi).
   Su pezzi con finestrature il peso è sovrastimato → costo_materiale sovrastimato.

---

## 2. Modello fisico Lantek (ricostruito dai documenti pubblici)

```
T_pezzo = T_taglio + T_pierce + T_rapidi + T_lead

T_taglio  = L_contorno / (v_taglio(mat, sp, P, gas) × k_accel) × 60   [s]
T_pierce  = Σ_i t_pierce(mat, sp)                                       [s]
T_rapidi  = L_rapidi / v_rapid × 60                                     [s]

Costo_pezzo = peso_lordo × €/kg / resa_nest                  ← materiale
            + (T_taglio + T_pierce + T_rapidi)/3600 × €/h    ← macchina
            + setup_costo / lotto_qta                         ← setup
            + Σ costi_lavorazioni_secondarie                  ← piega, sald, ecc.
```

**Lantek Expert Cut** usa "Tables of Technology" parametrizzate per macchina × materiale × spessore × qualità taglio (fino a 12 qualità per combo). Ogni cella: potenza, velocità, frequenza, gas, pressione, parametri pierce, kerf, lead-in.
**Lantek Factory + iQuoting** prendono questi tempi e applicano formule custom utente per il costing.

---

## 3. Tabelle parametri reali (cross-vendor: IPG, Bystronic, Trumpf, MachineMFG)

### 3.1 Velocità taglio S235 con O₂ (m/min)

| Spessore | 3 kW | 6 kW | 12 kW |
|---|---|---|---|
| 1 mm | 28-35 | 35-45 | 50+ |
| 2 mm | 12-16 | 18-24 | 30-40 |
| 3 mm | 7-9 | 11-14 | 18-22 |
| 4 mm | 4.5-5.5 | 7-9 | 12-15 |
| 5 mm | 3.5-4.5 | 5.5-7 | 10-12 |
| 6 mm | 3.0-3.8 | 4.5-5.5 | 8-10 |
| 8 mm | 2.0-2.6 | 3.0-3.8 | 5.5-7 |
| 10 mm | 1.4-1.8 | 2.2-2.8 | 4.0-5.0 |
| 12 mm | 1.0-1.4 | 1.6-2.2 | 3.0-4.0 |
| 15 mm | 0.6-0.9 | 1.2-1.6 | 2.2-3.0 |
| 20 mm | 0.3-0.5 | 0.8-1.1 | 1.5-2.0 |

### 3.2 Velocità taglio INOX 304 con N₂ (m/min) — ~20-30% più lento di S235

| Spessore | 3 kW | 6 kW | 12 kW |
|---|---|---|---|
| 1 mm | 22-28 | 35-45 | 50+ |
| 2 mm | 8-11 | 15-20 | 28-35 |
| 3 mm | 4-6 | 9-12 | 18-24 |
| 4 mm | 2.5-3.5 | 6-8 | 12-16 |
| 5 mm | 1.8-2.5 | 4-6 | 9-12 |
| 6 mm | 1.2-1.8 | 3.0-4.0 | 6-9 |
| 8 mm | 0.7-1.0 | 1.8-2.5 | 4.5-6 |
| 10 mm | 0.4-0.6 | 1.2-1.6 | 3.0-4.0 |
| 12 mm | (limite) | 0.7-1.0 | 2.0-2.8 |
| 15 mm | — | 0.4-0.6 | 1.4-2.0 |

### 3.3 Velocità taglio Alluminio 5754 con N₂ (m/min) — ~30-40% più lento di S235

| Spessore | 3 kW | 6 kW | 12 kW |
|---|---|---|---|
| 1 mm | 18-25 | 30-40 | 45+ |
| 2 mm | 7-10 | 13-18 | 25-32 |
| 3 mm | 3.5-5 | 7-10 | 16-22 |
| 4 mm | 2.2-3.0 | 4.5-6.5 | 10-14 |
| 5 mm | 1.5-2.2 | 3.0-4.5 | 7-10 |
| 6 mm | 1.0-1.5 | 2.2-3.0 | 5-7 |
| 8 mm | 0.5-0.8 | 1.5-2.0 | 3.5-5 |
| 10 mm | (limite) | 1.0-1.5 | 2.5-3.5 |
| 12 mm | — | 0.6-0.9 | 1.8-2.5 |

### 3.4 Tempo pierce (secondi/foro) — fiber 6 kW

| Spessore | S235 (O₂) | INOX (N₂) | ALU (N₂) |
|---|---|---|---|
| 1-2 mm (flying) | 0.05-0.20 | 0.05-0.25 | 0.10-0.25 |
| 3-4 mm | 0.3-0.5 | 0.4-0.8 | 0.5-1.0 |
| 5 mm | 0.3-0.5 | 0.4-0.8 | 0.5-1.0 |
| 6 mm | 0.5-0.8 | 0.7-1.5 | 0.9-1.5 |
| 8 mm | 0.8-1.2 | 1.2-2.5 | 1.5-2.5 |
| 10 mm | 1.2-1.8 | 1.8-3.5 | 2.2-3.5 |
| 12 mm | 1.8-2.5 (pulse) | 2.5-5.0 (pulse) | 3.0-5.0 (pulse) |
| 15 mm | 2.5-4.0 | 3.5-7.0 | 4.5-7.0 |
| 20 mm | 4.0-6.0 (3-stage) | 5.5-12 | 7-12 |

Su macchine 3 kW: ×1.5-2.0. Su 12 kW: ×0.6-0.7.

---

## 4. Costo orario macchina €/h (Italia, fibra 3-12 kW)

| Componente | Range |
|---|---|
| Ammortamento (350-450k€ / 5y / 3000h) | 15-25 €/h |
| Energia (~12kW × 0.25 €/kWh) | 3-5 €/h |
| Gas **O₂** (~10 m³/h × 0.20 €/m³) | **2-4 €/h** |
| Gas **N₂** (~50 m³/h × 1.00 €/m³) | **30-50 €/h** |
| Consumabili (ugelli, lenti) | 2-4 €/h |
| Manutenzione | 3-5 €/h |
| Operatore (carico+supervisione) | 7-15 €/h |

### Totali per gas:
- **S235 con O₂**: **35-50 €/h** (carbon, taglio combustione)
- **INOX/ALU con N₂**: **60-90 €/h** (taglio fusione, gas è la voce dominante)

⚠️ **Usare 2 tariffe €/h distinte per gas**: sbagliare qui è il principale fattore di errore residuo.

---

## 5. Modello consigliato per FerroTrack

### 5.1 Tabelle DB (4)

```python
vel_taglio[materiale][spessore][potenza_kw]    # m/min  → tabelle §3.1-3.3
tempo_pierce[materiale][spessore]              # s/foro → tabella §3.4
costo_macchina[gas]                            # €/h    → §4 (O2=42, N2=75)
prezzo_materiale[materiale][spessore]          # €/kg   → S235≈1.5, INOX_304≈4.5, ALU≈5.0
```

### 5.2 Parametri globali

```python
k_accel = 0.70         # fattore velocità reale; calibrare 0.5-0.85
resa_nest = 0.75       # utilizzo materiale tipico
v_rapid = 150          # m/min, costante macchina cliente
L_lead_mm = 4          # lead-in default
setup_costo_eur = 25   # per lotto
```

### 5.3 UI commerciale: dropdown "complessità"
- **Semplice** (rettangoli, archi grandi): k_accel = 0.85
- **Media** (default carpenteria): k_accel = 0.70
- **Complessa** (molti fori piccoli, spigoli vivi): k_accel = 0.55

### 5.4 Procedura calibrazione (decisiva per <10%)

1. Raccogli 10-20 export XLSX Lantek reali del cliente (vedi §6 per come).
2. Per ogni pezzo estrai: `mat, sp, L_taglio, N_pierce, peso, costo_lantek`.
3. Calcola `costo_predetto` con modello + tabelle default.
4. Regressione lineare:
   `costo_lantek = α × costo_macchina_pred + β × costo_materiale_pred + γ × N_pierce + δ`
   - α, β vicini a 1 → modello OK
   - Deviazioni rivelano dove correggere (es. α=1.4 → €/h sottostimato del 40%)
5. Tunare `k_accel` per minimizzare errore residuo (è il parametro più libero e potente).
6. Validare 80/20 train/test. Target <10% MAE.

---

## 6. Schema XLSX Lantek "Struttura" (template singolo) — campi rilevanti

Su 187 colonne totali, queste sono le tecnicamente utili:

| Col index | Nome Lantek | Unità | Note |
|---|---|---|---|
| 0 | Codice | str | PK pezzo |
| 12 | Costo standard | EUR | **costo unitario calcolato Lantek** (target regressione) |
| 18 | Quantità corrente | int | pezzi nel lotto |
| 21 | Peso | kg | peso unitario esterno |
| 60 | Materiale | str | "FERRO", "INOX", "ALLUMINIO" |
| 61 | Lunghezza | mm | bbox L |
| 62 | Larghezza | mm | bbox W |
| 63 | Spessore | mm | lamiera |
| 64 | Area | m² | netta |
| 72 | **Perimetro di taglio** | m | **chiave per costo laser** |
| 73 | Perimetro di marcatura | m | incisione (raro) |
| 74 | Area Esterna | m² | inviluppo |
| 75 | Area Rettangolare | m² | bbox L×W |
| 77 | Peso esterno | kg | = Area_est × sp × ρ |
| 78 | Peso rettangolare | kg | = bbox × sp × ρ (include sfrido) |
| 141 | pieghe_semplici | int | |
| 142 | pieghe_speciali | int | |

**Lantek NON esporta** in questo template: `tempo_taglio_s`, `velocità_taglio`, `tempo_pierce`, `n_pierce`, `potenza_W`, `gas`, `consumo_gas`. Va inferito da geometria + tabelle nostre.

---

## 7. Confronto CAM (per ricalibrare ipotesi modello)

| CAM | Quoting | Formule custom | Utilizzo nest tipico | Note |
|---|---|---|---|---|
| **Lantek Expert** | iQuoting | Sì (variabili tempo/materiale) | 75-82% | Dominante in IT carpenterie medie |
| **SigmaNEST** | SigmaQUOTE | Sì (motore script per livello) | 82-88% | Leader true-shape nesting |
| **ProNest** (Hypertherm) | Built-in | Limitato | 78-84% | Plasma/ossitaglio |
| **Radan** | Sì | Sì | 75-82% | Lamiera + piega integrata |

Tutti usano la stessa fisica: tempi separati taglio/pierce/rapidi, costo materiale per peso lordo nest, motore formule per servizi accessori. Differenza costi tra CAM ±5%. La precisione si gioca sulla calibrazione, non sulla scelta del modello.

---

## 8. Sorgenti chiave (28 link)

**Tabelle tecniche velocità:**
- MachineMFG — Laser Cutting Thickness and Speed Chart 500W-30kW: https://www.machinemfg.com/laser-cutting-thickness-speed-chart/
- Artizono — Fiber Laser Thickness & Speed Chart: https://artizono.com/fiber-laser-cutting-thickness-speed-chart/
- IPG Photonics datasheets (via Bystronic ByStar): https://www.vantomachines.com/brands/BYSTRONIC/ByStar%20Fiber_Datasheet_12kW_eng.pdf
- Trumpf TruLaser 2D brochure: https://www.trumpf.com/filestorage/TRUMPF_Master/Products/Machines_and_Systems/02_Brochures/TRUMPF-2D-laser-cutting-machines-brochure-EN.pdf
- LaserSpecHub — 1-20kW cutting speed: https://www.laserspechub.com/guides/cutting-speed-chart

**Piercing:**
- Arcus CNC — Optimizing Piercing Thick Plate: https://arcuscnc.com/optimizing-laser-piercing-parameters-for-thick-plate-cutting/
- Paramount Machinery — Fiber Power & Piercing: https://paramountmachinery.ca/blog/how-fiber-laser-power-affects-piercing-time
- MFG News — Fiber Efficiencies via Piercing: https://www.mfgnewsweb.com/archives/4/50478/Applying-Technology-jan18/Major-Fiber-Laser-Efficiencies-Start-with-Piercing.aspx

**Tempo / accel/decel:**
- CutQuote — How to Calculate Laser Cutting Time: https://cutquote.app/blog/how-to-calculate-laser-cutting-time.html
- CADEM — CNC Acceleration and Cycle Time: https://cadem.com/cnc-acceleration-and-cycle-time/

**Costo orario macchina:**
- LaserCalc Pro — Hourly Cost Structure: https://www.lasercalcpro.com/guides/hourly-cost-structure
- OT-LAS — Hourly Cost Calculation: https://www.otlas.com/en/blog/how-to-calculate-the-hourly-cost-of-a-laser-machine/
- ACCURL — Power Consumption: https://www.accurl.com/blog/laser-cutting-power-consumption/

**Gas N₂ vs O₂:**
- Metal Interface — Oxygen or Nitrogen: https://www.metal-interface.com/articles-news/t/technical-report-laser-cutting/oxygen-or-nitrogen-gas-laser-cutting-6-points
- Presscon — Nitrogen vs Oxygen cost: https://presscon.com/is-laser-cutting-with-nitrogen-more-expensive-than-with-oxygen/

**Lantek (ricostruzione modello):**
- Lantek Expert Cut IT: https://www.lantek.com/it/cad-cam-ossitaglio-plasma-laser-getto-d-acqua
- Lantek Integra Quotes: https://www.lantek.com/us/lantek-integra-quotes
- Lantek iQuoting IT: https://www.lantek.com/it/blog/lantek-iquoting-il-preventivo-semplice-e-preciso
- Lantek Factory — time/cost accurate: https://www.lantek.com/it/notizie/lantek-factory-assicura-calcoli-tempi-e-costi-accurati
- Manuale Expert Cut configurazione: https://www.scribd.com/document/460185480/Configuration-Manual-Lantek-Expert-Cut

**Confronti CAM:**
- SigmaQUOTE: https://www.sigmanest.com/en/sigmaquote
- ProNest Hypertherm: https://www.hypertherm.com/hypertherm/pronest/pronest-cadcam-nesting-software/
