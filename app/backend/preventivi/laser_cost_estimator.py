"""Stimatore costo taglio laser (Fase 1b merge preventivatore).

Calcola il costo del taglio + materiale per un articolo, basandosi su:
- area (dm²) + perimetro_taglio (m) estratti dal DXF (vedi dxf_scanner.estrai_geometria_taglio)
- spessore (mm) + materiale inseriti dal commerciale
- coefficienti dalla config admin (densità kg/dm³, €/kg, velocità taglio m/h, €/h macchina)

Sostituisce il `costo` che nel Preventivatore desktop veniva sempre da Lantek XLSX,
permettendo al commerciale di partire direttamente dai DXF cliente senza aspettare
che Mirko prepari il file in Lantek (sblocca il bottleneck Lantek-first).

Formula:
    peso_kg        = area_dm2 * (spessore_mm / 100) * densita_kg_dm3
    costo_materiale = peso_kg * euro_kg
    ore_taglio     = (perimetro_taglio_m / velocita_taglio_m_h) + (n_forature * tempo_perforazione_sec / 3600)
    costo_taglio   = ore_taglio * euro_h_macchina
    base           = costo_materiale + costo_taglio

Vedi `contract.md` per dettagli.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


DEFAULT_LASER_CONFIG = {
    'materiali': {
        'S235':     {'densita_kg_dm3': 7.85, 'euro_kg': 1.20},
        'INOX_304': {'densita_kg_dm3': 8.00, 'euro_kg': 4.50},
        'INOX_316': {'densita_kg_dm3': 8.00, 'euro_kg': 6.20},
        'ALU_5754': {'densita_kg_dm3': 2.70, 'euro_kg': 3.80},
        'ALU_5083': {'densita_kg_dm3': 2.66, 'euro_kg': 4.20},
    },
    'velocita_taglio_m_h': {
        'S235':     {1: 6000, 2: 3500, 3: 2500, 4: 2000, 5: 1500, 6: 1200, 8: 950, 10: 800, 12: 600, 15: 400, 20: 250},
        'INOX_304': {1: 4500, 2: 2800, 3: 2000, 4: 1500, 5: 1100, 6: 900, 8: 650, 10: 500, 12: 350},
        'INOX_316': {1: 4500, 2: 2800, 3: 2000, 4: 1500, 5: 1100, 6: 900, 8: 650, 10: 500, 12: 350},
        'ALU_5754': {1: 8000, 2: 5000, 3: 3500, 4: 2500, 5: 1800, 6: 1300, 8: 900, 10: 650},
        'ALU_5083': {1: 8000, 2: 5000, 3: 3500, 4: 2500, 5: 1800, 6: 1300, 8: 900, 10: 650},
    },
    'euro_h_macchina': 85.0,
    'tempo_perforazione_sec': 0.5,
}


def _interpola_velocita(velocita_per_spessore: dict, spessore_mm: float) -> float:
    """Velocità di taglio per spessore arbitrario via interpolazione lineare.

    `velocita_per_spessore` ha chiavi int o str. Ritorna m/h interpolato tra
    i due spessori più vicini. Se spessore è oltre il max, usa il max
    (estrapolazione downward conservativa).
    """
    if not velocita_per_spessore:
        return 0.0
    # Normalizza chiavi a float
    items = sorted((float(k), float(v)) for k, v in velocita_per_spessore.items())
    if spessore_mm <= items[0][0]:
        return items[0][1]
    if spessore_mm >= items[-1][0]:
        return items[-1][1]
    # Interpolazione lineare tra i due adiacenti
    for i in range(len(items) - 1):
        s1, v1 = items[i]
        s2, v2 = items[i + 1]
        if s1 <= spessore_mm <= s2:
            t = (spessore_mm - s1) / (s2 - s1)
            return v1 + t * (v2 - v1)
    return items[-1][1]  # fallback


def stima_base(articolo: dict, config: dict | None = None) -> dict:
    """Stima costo base (materiale + taglio) per un articolo.

    Args:
        articolo: dict con almeno {area_dm2, perimetro_taglio_m, n_forature,
                                    spessore_mm, materiale}
        config: dict con sezione 'laser_config'. Se None usa DEFAULT_LASER_CONFIG.

    Returns:
        dict {peso_kg, costo_materiale, ore_taglio, costo_taglio, base,
              warnings: [str]}
        Se mancano dati essenziali, ritorna base=0.0 con warning esplicativo.
    """
    cfg = (config or {}).get('laser_config') or DEFAULT_LASER_CONFIG
    materiali = cfg.get('materiali') or DEFAULT_LASER_CONFIG['materiali']
    velocita_tabella = cfg.get('velocita_taglio_m_h') or DEFAULT_LASER_CONFIG['velocita_taglio_m_h']
    euro_h = float(cfg.get('euro_h_macchina') or DEFAULT_LASER_CONFIG['euro_h_macchina'])
    tempo_perf_sec = float(cfg.get('tempo_perforazione_sec') or DEFAULT_LASER_CONFIG['tempo_perforazione_sec'])

    warnings = []

    area_dm2 = float(articolo.get('area_dm2') or 0.0)
    perimetro_m = float(articolo.get('perimetro_taglio_m') or 0.0)
    n_forature = int(articolo.get('n_forature') or 0)
    spessore_mm = float(articolo.get('spessore_mm') or 0.0)
    materiale = (articolo.get('materiale') or '').strip()

    if not materiale:
        warnings.append('Materiale non specificato')
    if spessore_mm <= 0:
        warnings.append('Spessore non specificato o <= 0')
    if area_dm2 <= 0:
        warnings.append('Area non valida (importa DXF per estrarla)')
    if perimetro_m <= 0:
        warnings.append('Perimetro di taglio non valido (importa DXF)')

    if warnings:
        return {
            'peso_kg': 0.0, 'costo_materiale': 0.0,
            'ore_taglio': 0.0, 'costo_taglio': 0.0, 'base': 0.0,
            'warnings': warnings,
        }

    mat = materiali.get(materiale)
    if not mat:
        warnings.append('Materiale "' + materiale + '" non in tabella')
        return {'peso_kg': 0.0, 'costo_materiale': 0.0, 'ore_taglio': 0.0,
                'costo_taglio': 0.0, 'base': 0.0, 'warnings': warnings}

    # --- Peso e costo materiale ---
    densita = float(mat.get('densita_kg_dm3', 7.85))
    euro_kg = float(mat.get('euro_kg', 0.0))
    # spessore in mm → dm: spessore_dm = spessore_mm / 100
    peso_kg = area_dm2 * (spessore_mm / 100.0) * densita
    costo_materiale = peso_kg * euro_kg

    # --- Tempo e costo taglio ---
    vel_tab = velocita_tabella.get(materiale, {})
    velocita_m_h = _interpola_velocita(vel_tab, spessore_mm)
    if velocita_m_h <= 0:
        warnings.append('Velocità taglio non definita per ' + materiale + ' a ' + str(spessore_mm) + 'mm')
        ore_taglio = 0.0
    else:
        ore_taglio = (perimetro_m / velocita_m_h) + (n_forature * tempo_perf_sec / 3600.0)
    costo_taglio = ore_taglio * euro_h

    base = costo_materiale + costo_taglio

    # Sanity check: se l'area lamiera è >> di quella ricavabile dal perimetro,
    # il DXF probabilmente include il cartiglio. Avvisa il commerciale.
    # Stima area "teorica massima" da perimetro: assumendo pezzo quadrato
    # area_quadrato = (perimetro/4)² in mm² → /10000 in dm²
    if perimetro_m > 0:
        perim_mm = perimetro_m * 1000
        area_max_plausibile_dm2 = ((perim_mm / 4) ** 2) / 10000
        if area_dm2 > area_max_plausibile_dm2 * 3:
            warnings.append(
                'Area sospettamente grande rispetto al perimetro: il DXF '
                'potrebbe includere il cartiglio. Verifica e usa override se necessario.'
            )

    return {
        'peso_kg': round(peso_kg, 4),
        'costo_materiale': round(costo_materiale, 4),
        'ore_taglio': round(ore_taglio, 5),
        'costo_taglio': round(costo_taglio, 4),
        'base': round(base, 2),
        'warnings': warnings,
        # debug info
        '_velocita_taglio_m_h': velocita_m_h,
        '_euro_kg': euro_kg,
    }
