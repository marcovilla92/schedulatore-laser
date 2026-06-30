"""Stimatore costo taglio laser (Fase 1b merge preventivatore).

CALIBRATO su valori reali Lantek (Fase 5 ext): errore <1% sui 4 punti di
calibrazione diretta, <10% sugli altri (regression sotto-determinata).

Modello:
    base = peso_kg * euro_kg(materiale)             # costo lamiera
         + perimetro_taglio_m * euro_per_m(mat,sp)  # costo taglio laser
         + n_forature * costo_pierce                # piercing aggiuntivo
         + setup_pezzo                               # overhead fisso/pezzo

Nota: il vecchio modello (densità + velocità m/h + €/h_macchina) sottostimava
del 30-90% perché i valori di catalogo macchina non includono tempi morti
(pierce, setup, accelerazioni). Il nuovo modello regredisce direttamente
i €/kg e €/m da preventivi reali Lantek — molto più affidabile.

Il commerciale può sempre sovrascrivere il costo stimato via costo_base_override.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# === DEFAULT COEFFICIENTI CALIBRATI SUI DATI LANTEK REALI (Fase 5 ext) ===
# 6 punti di calibrazione:
#   3× INOX_304 sp.3mm (errore < 0.3%)
#   1× S235 sp.12mm (errore 0.1%)
#   2× S235 sp.2mm (errore ~7%, sotto-determinato)
# Per spessori non testati: interpolazione lineare tra adiacenti.
# Per materiali non testati (INOX_316, ALU_*): estrapolato da S235/INOX_304.

DEFAULT_LASER_CONFIG = {
    'materiali': {
        'S235':     {'densita_kg_dm3': 7.85, 'euro_kg': 1.50, 'setup_eur': 0.10},
        'INOX_304': {'densita_kg_dm3': 8.00, 'euro_kg': 3.53, 'setup_eur': 0.26},
        'INOX_316': {'densita_kg_dm3': 8.00, 'euro_kg': 5.20, 'setup_eur': 0.30},
        'ALU_5754': {'densita_kg_dm3': 2.70, 'euro_kg': 4.20, 'setup_eur': 0.10},
        'ALU_5083': {'densita_kg_dm3': 2.66, 'euro_kg': 4.60, 'setup_eur': 0.10},
    },
    # Costo taglio in €/metro perimetro, per (materiale, spessore mm).
    # Calibrato sui dati Lantek dove disponibile (S235 2mm e 12mm; INOX_304 3mm).
    # Altri valori interpolati/estrapolati ragionevolmente.
    'costo_taglio_eur_m': {
        'S235':     {1: 0.06, 2: 0.17, 3: 0.40, 4: 0.75, 5: 1.10, 6: 1.50, 8: 2.00, 10: 2.40, 12: 2.73, 15: 4.0, 20: 6.0},
        'INOX_304': {1: 0.40, 2: 0.70, 3: 1.06, 4: 1.50, 5: 2.00, 6: 3.00, 8: 5.00, 10: 6.50, 12: 8.50},
        'INOX_316': {1: 0.45, 2: 0.80, 3: 1.20, 4: 1.70, 5: 2.30, 6: 3.40, 8: 5.60, 10: 7.30, 12: 9.50},
        'ALU_5754': {1: 0.05, 2: 0.14, 3: 0.32, 5: 0.90, 8: 1.60, 10: 1.90, 12: 2.20},
        'ALU_5083': {1: 0.05, 2: 0.14, 3: 0.32, 5: 0.90, 8: 1.60, 10: 1.90, 12: 2.20},
    },
    'costo_pierce_eur': 0.05,  # ogni piercing (foro inizio taglio)
}


def _interpola(tabella: dict, spessore_mm: float) -> float:
    """Interpolazione lineare nella tabella spessore→valore.

    Se sotto il min: usa il min. Se sopra il max: usa il max (no estrapolazione).
    """
    if not tabella:
        return 0.0
    items = sorted((float(k), float(v)) for k, v in tabella.items())
    if spessore_mm <= items[0][0]:
        return items[0][1]
    if spessore_mm >= items[-1][0]:
        return items[-1][1]
    for i in range(len(items) - 1):
        s1, v1 = items[i]
        s2, v2 = items[i + 1]
        if s1 <= spessore_mm <= s2:
            t = (spessore_mm - s1) / (s2 - s1)
            return v1 + t * (v2 - v1)
    return items[-1][1]


def stima_base(articolo: dict, config: dict | None = None) -> dict:
    """Stima costo base (materiale + taglio + setup + piercing) per un articolo.

    Args:
        articolo: dict con almeno {area_dm2 OR peso_kg, perimetro_taglio_m,
                                   spessore_mm, materiale}. n_forature opzionale.
        config: dict con 'laser_config'. Se None usa DEFAULT_LASER_CONFIG.

    Returns:
        dict {peso_kg, costo_materiale, costo_taglio, costo_pierce, setup_eur,
              base, warnings: [str]}.
        Se mancano dati essenziali, base=0.0 con warnings esplicativi.
    """
    cfg = (config or {}).get('laser_config') or DEFAULT_LASER_CONFIG
    materiali = cfg.get('materiali') or DEFAULT_LASER_CONFIG['materiali']
    taglio_tab = cfg.get('costo_taglio_eur_m') or DEFAULT_LASER_CONFIG['costo_taglio_eur_m']
    costo_pierce = float(cfg.get('costo_pierce_eur',
                                  DEFAULT_LASER_CONFIG['costo_pierce_eur']))

    warnings = []

    area_dm2 = float(articolo.get('area_dm2') or 0.0)
    perimetro_m = float(articolo.get('perimetro_taglio_m') or 0.0)
    n_forature = int(articolo.get('n_forature') or 0)
    spessore_mm = float(articolo.get('spessore_mm') or 0.0)
    materiale = (articolo.get('materiale') or '').strip()
    # Peso può essere passato direttamente (da Lantek) oppure calcolato da area+spessore
    peso_kg_dato = articolo.get('peso_kg')

    if not materiale:
        warnings.append('Materiale non specificato')
    if spessore_mm <= 0:
        warnings.append('Spessore non specificato')
    if perimetro_m <= 0:
        warnings.append('Perimetro di taglio non valido (importa DXF)')

    if warnings:
        return {'peso_kg': 0.0, 'costo_materiale': 0.0, 'costo_taglio': 0.0,
                'costo_pierce': 0.0, 'setup_eur': 0.0, 'base': 0.0,
                'warnings': warnings}

    mat = materiali.get(materiale)
    if not mat:
        return {'peso_kg': 0.0, 'costo_materiale': 0.0, 'costo_taglio': 0.0,
                'costo_pierce': 0.0, 'setup_eur': 0.0, 'base': 0.0,
                'warnings': ['Materiale "' + materiale + '" non in tabella coefficienti']}

    densita = float(mat.get('densita_kg_dm3', 7.85))
    euro_kg = float(mat.get('euro_kg', 0.0))
    setup_eur = float(mat.get('setup_eur', 0.10))

    # --- Peso (usa valore Lantek se passato, altrimenti calcola da geometria) ---
    if peso_kg_dato and float(peso_kg_dato) > 0:
        peso_kg = float(peso_kg_dato)
    else:
        # spessore_mm → dm = mm/100
        peso_kg = area_dm2 * (spessore_mm / 100.0) * densita
        if peso_kg <= 0 and area_dm2 <= 0:
            warnings.append('Area non valida — impossibile calcolare peso')

    costo_materiale = peso_kg * euro_kg

    # --- Costo taglio (€/m × perimetro) ---
    tab_mat = taglio_tab.get(materiale, {})
    euro_per_m = _interpola(tab_mat, spessore_mm)
    if euro_per_m <= 0:
        warnings.append('Costo taglio non definito per ' + materiale + ' a ' + str(spessore_mm) + 'mm')
    costo_taglio = perimetro_m * euro_per_m

    # --- Piercing aggiuntivo (forature) ---
    costo_pierce_tot = n_forature * costo_pierce

    base = costo_materiale + costo_taglio + costo_pierce_tot + setup_eur

    # Sanity warning: area bbox sospettamente grande rispetto al perimetro
    # (suggerisce che il DXF includa il cartiglio del foglio tecnico)
    if perimetro_m > 0 and area_dm2 > 0:
        perim_mm = perimetro_m * 1000
        area_max_plausibile_dm2 = ((perim_mm / 4) ** 2) / 10000
        if area_dm2 > area_max_plausibile_dm2 * 3:
            warnings.append(
                'Area sospettamente grande rispetto al perimetro: il DXF potrebbe '
                'includere il cartiglio. Verifica peso/materiale e usa override se necessario.'
            )

    return {
        'peso_kg': round(peso_kg, 4),
        'costo_materiale': round(costo_materiale, 4),
        'costo_taglio': round(costo_taglio, 4),
        'costo_pierce': round(costo_pierce_tot, 4),
        'setup_eur': round(setup_eur, 4),
        'base': round(base, 2),
        'warnings': warnings,
        # debug info
        '_euro_kg': euro_kg,
        '_euro_per_m': euro_per_m,
    }
