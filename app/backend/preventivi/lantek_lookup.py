"""Lookup ricette Lantek reali del cliente (velocità taglio + tempo pierce).

Il file `lantek_recipes.json` è generato una tantum dallo xlsx fornito dal
cliente (`_test_input/parametri_taglio_completi_aggiornati.xlsx`). Contiene
116 ricette calibrate sul suo laser (macchina fibra, potenza da mm/min visti).

Regola gas del cliente (2026-07-02, cfr. Stefano):
- S235 (ferro):  N2 se spessore ≤ 3mm, O2 se spessore > 3mm
- INOX/ALU/ZINCATO/OTTONE: sempre N2

Il modello di stima costo taglio userà:
    tempo_taglio_s  = (perimetro_m × 1000) / velocita_mm_min × 60
    tempo_pierce_s  = n_forature × pierce_time_s
    costo_taglio    = (tempo_taglio_s + tempo_pierce_s) × (€/h_macchina / 3600)
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

_RECIPES_PATH = os.path.join(os.path.dirname(__file__), 'lantek_recipes.json')


@lru_cache(maxsize=1)
def load_recipes() -> dict:
    """Carica il JSON ricette (cached). Ritorna {'metadata': ..., 'ricette': [...]}."""
    try:
        with open(_RECIPES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error('impossibile caricare lantek_recipes.json: %s', e)
        return {'metadata': {}, 'ricette': []}


def default_gas(materiale: str, spessore_mm: float) -> str:
    """Regola di default gas del cliente."""
    if (materiale or '').upper() == 'S235':
        return 'N2' if spessore_mm <= 3.0 else 'O2'
    return 'N2'


def _normalize_mat(mat: str) -> str:
    m = (mat or '').strip().upper()
    aliases = {
        'FERRO': 'S235',
        'INOX': 'INOX_304',
        'INOX_316': 'INOX_304',  # ricette Lantek non hanno 316 → fallback su 304
        'ALLUMINIO': 'ALU',
        'ALU_5083': 'ALU',
        'ALU_5754': 'ALU',
    }
    return aliases.get(m, m)


def lookup_ricetta(materiale: str, spessore_mm: float, gas: str | None = None) -> dict | None:
    """Trova la ricetta Lantek per (materiale, spessore, gas).

    Se spessore non esatto: interpola linearmente fra i due più vicini nella
    stessa serie (materiale+gas). Fuori range: usa il limite più vicino.

    Se gas non specificato: usa `default_gas(materiale, spessore)`.

    Returns:
        dict {materiale, gas, spessore_mm, velocita_mm_min, pierce_time_s,
              source: 'exact'|'interpolated'|'clamped'|'fallback',
              rid_riferimento: int|None}
        oppure None se materiale/gas non presente in tabella.
    """
    mat = _normalize_mat(materiale)
    if not mat:
        return None
    g = (gas or default_gas(mat, spessore_mm)).upper()

    data = load_recipes()
    ricette = data.get('ricette', [])
    serie = [r for r in ricette if r['materiale'] == mat and r['gas'] == g]

    if not serie:
        # Fallback: cerca stesso materiale con qualsiasi gas
        alt = [r for r in ricette if r['materiale'] == mat]
        if not alt:
            return None
        # Usa la serie N2 se disponibile (default per non-ferro), altrimenti la prima
        alt_gases = sorted({r['gas'] for r in alt})
        g_fb = 'N2' if 'N2' in alt_gases else alt_gases[0]
        serie = [r for r in alt if r['gas'] == g_fb]
        if not serie:
            return None
        _fallback_used = g_fb
    else:
        _fallback_used = None

    serie.sort(key=lambda r: r['spessore_mm'])

    # Match esatto
    for r in serie:
        if abs(r['spessore_mm'] - spessore_mm) < 1e-6:
            return {
                'materiale': mat, 'gas': r['gas'], 'spessore_mm': spessore_mm,
                'velocita_mm_min': r['velocita_mm_min'],
                'pierce_time_s': r['pierce_time_s'],
                'source': 'fallback' if _fallback_used else 'exact',
                'rid_riferimento': r['rid'],
                'gas_richiesto': g if _fallback_used else None,
            }

    # Fuori range
    if spessore_mm <= serie[0]['spessore_mm']:
        r = serie[0]
        return {
            'materiale': mat, 'gas': r['gas'], 'spessore_mm': spessore_mm,
            'velocita_mm_min': r['velocita_mm_min'],
            'pierce_time_s': r['pierce_time_s'],
            'source': 'clamped_min', 'rid_riferimento': r['rid'],
        }
    if spessore_mm >= serie[-1]['spessore_mm']:
        r = serie[-1]
        return {
            'materiale': mat, 'gas': r['gas'], 'spessore_mm': spessore_mm,
            'velocita_mm_min': r['velocita_mm_min'],
            'pierce_time_s': r['pierce_time_s'],
            'source': 'clamped_max', 'rid_riferimento': r['rid'],
        }

    # Interpolazione lineare
    for i in range(len(serie) - 1):
        r1, r2 = serie[i], serie[i + 1]
        s1, s2 = r1['spessore_mm'], r2['spessore_mm']
        if s1 <= spessore_mm <= s2:
            t = (spessore_mm - s1) / (s2 - s1)
            vel = r1['velocita_mm_min'] + t * (r2['velocita_mm_min'] - r1['velocita_mm_min'])
            pierce = r1['pierce_time_s'] + t * (r2['pierce_time_s'] - r1['pierce_time_s'])
            return {
                'materiale': mat, 'gas': r1['gas'], 'spessore_mm': spessore_mm,
                'velocita_mm_min': round(vel, 1),
                'pierce_time_s': round(pierce, 4),
                'source': 'interpolated',
                'rid_riferimento_min': r1['rid'], 'rid_riferimento_max': r2['rid'],
            }
    return None


def list_materiali() -> list[str]:
    """Materiali disponibili in tabella (per dropdown frontend)."""
    return load_recipes().get('metadata', {}).get('materiali', [])


def list_spessori(materiale: str, gas: str | None = None) -> list[float]:
    """Spessori disponibili per una serie (per suggerimento UI)."""
    mat = _normalize_mat(materiale)
    ricette = load_recipes().get('ricette', [])
    if gas:
        g = gas.upper()
        return sorted({r['spessore_mm'] for r in ricette if r['materiale'] == mat and r['gas'] == g})
    return sorted({r['spessore_mm'] for r in ricette if r['materiale'] == mat})
