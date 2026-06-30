"""Cost estimation based on detected STEP manufacturing features.

Uses the feature data from step_features.analizza_features() to compute
per-operation cost breakdowns: drilling, milling, bending, material,
and surface coating.
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default cost parameters (overridden by config dict)
# ---------------------------------------------------------------------------
_DEFAULTS = {
    # Hourly rates (EUR/h)
    'costo_orario_foratura': 35.0,
    'costo_orario_fresatura': 45.0,
    'costo_orario_piegatura': 40.0,
    # Per-hole time (minutes)
    'tempo_foro_base_min': 0.5,
    'tempo_foro_filettato_extra_min': 0.8,
    'tempo_foro_svasato_extra_min': 0.3,
    # Per-slot time (minutes per 100mm perimeter)
    'tempo_fresatura_per_100mm_min': 1.5,
    # Per-bend time (minutes)
    'tempo_piega_base_min': 0.8,
    'tempo_piega_per_metro_min': 0.5,
    # Material cost (EUR/kg)
    'costo_materiale_acciaio_kg': 1.20,
    'costo_materiale_inox_kg': 4.50,
    'costo_materiale_alluminio_kg': 3.50,
    # Coating cost (EUR/dm^2)
    'costo_verniciatura_dm2': 0.15,
}


def _cfg(config: dict, key: str) -> float:
    """Get a config value with fallback to defaults."""
    val = config.get(key)
    if val is not None:
        try:
            return float(val)
        except (TypeError, ValueError):
            pass
    return _DEFAULTS.get(key, 0.0)


# ---------------------------------------------------------------------------
# Per-feature cost helpers
# ---------------------------------------------------------------------------

def _costo_foro(foro: dict, config: dict) -> dict:
    """Calculate cost for a single hole.

    Through-hole: base drilling time * hourly rate
    Tapped: + threading surcharge
    Countersunk: + countersink surcharge
    Bigger holes take proportionally longer (diameter factor).
    """
    costo_ora = _cfg(config, 'costo_orario_foratura')
    tempo_base = _cfg(config, 'tempo_foro_base_min')

    diametro = foro.get('diametro', 5.0)
    # Larger holes take more time (linear scale, ref = 10mm)
    diam_factor = max(diametro / 10.0, 0.5)
    tempo = tempo_base * diam_factor

    tipo = foro.get('tipo', 'passante')
    if tipo == 'filettato':
        tempo += _cfg(config, 'tempo_foro_filettato_extra_min')
    elif tipo == 'svasato':
        tempo += _cfg(config, 'tempo_foro_svasato_extra_min')

    costo = round(tempo * costo_ora / 60.0, 2)
    return {
        'tipo': tipo,
        'diametro': diametro,
        'filettatura': foro.get('filettatura'),
        'tempo_min': round(tempo, 2),
        'costo': costo,
    }


def _costo_asola(asola: dict, config: dict) -> dict:
    """Calculate cost for a single slot/cutout.

    Based on perimeter length at a milling feed rate.
    """
    costo_ora = _cfg(config, 'costo_orario_fresatura')
    tempo_per_100mm = _cfg(config, 'tempo_fresatura_per_100mm_min')

    larghezza = asola.get('larghezza', 10.0)
    lunghezza = asola.get('lunghezza', 20.0)
    perimetro = 2 * (larghezza + lunghezza)
    tempo = perimetro / 100.0 * tempo_per_100mm

    costo = round(tempo * costo_ora / 60.0, 2)
    return {
        'larghezza': larghezza,
        'lunghezza': lunghezza,
        'perimetro_mm': round(perimetro, 1),
        'tempo_min': round(tempo, 2),
        'costo': costo,
    }


def _costo_piega_3d(piega: dict, config: dict) -> dict:
    """Calculate cost for a single bend detected from 3D geometry.

    Base setup time + length-proportional time.
    """
    costo_ora = _cfg(config, 'costo_orario_piegatura')
    tempo_base = _cfg(config, 'tempo_piega_base_min')
    tempo_per_m = _cfg(config, 'tempo_piega_per_metro_min')

    lunghezza_mm = piega.get('lunghezza_mm', 100.0)
    angolo = piega.get('angolo', 90.0)

    tempo = tempo_base + (lunghezza_mm / 1000.0) * tempo_per_m
    # Non-90-degree bends take ~20% longer
    if abs(angolo - 90.0) > 10.0:
        tempo *= 1.2

    costo = round(tempo * costo_ora / 60.0, 2)
    return {
        'angolo': angolo,
        'lunghezza_mm': lunghezza_mm,
        'raggio_mm': piega.get('raggio_mm', 0),
        'tempo_min': round(tempo, 2),
        'costo': costo,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def stima_costi_da_features(features: dict, config: dict,
                            materiale: str = "acciaio") -> dict:
    """Estimate manufacturing costs from detected features.

    Args:
        features: dict from analizza_features().
        config: application config dict.
        materiale: material type ('acciaio', 'inox', 'alluminio').

    Returns:
        dict with per-operation cost breakdown and totals.
    """
    if not config:
        config = {}

    # --- Per-hole costs ---
    dettaglio_fori = [_costo_foro(f, config) for f in features.get('fori', [])]
    costo_foratura = round(sum(d['costo'] for d in dettaglio_fori), 2)
    tempo_foratura = round(sum(d['tempo_min'] for d in dettaglio_fori), 2)

    # --- Per-slot costs ---
    dettaglio_asole = [_costo_asola(a, config) for a in features.get('asole', [])]
    costo_fresatura = round(sum(d['costo'] for d in dettaglio_asole), 2)
    tempo_fresatura = round(sum(d['tempo_min'] for d in dettaglio_asole), 2)

    # --- Per-bend costs (from 3D detection) ---
    dettaglio_pieghe = [_costo_piega_3d(p, config) for p in features.get('pieghe_3d', [])]
    costo_piegatura_3d = round(sum(d['costo'] for d in dettaglio_pieghe), 2)
    tempo_piegatura = round(sum(d['tempo_min'] for d in dettaglio_pieghe), 2)

    # --- Material cost by weight ---
    mat_key = f'costo_materiale_{materiale}_kg'
    costo_mat_kg = _cfg(config, mat_key)
    peso_kg = features.get('peso_stimato_kg', 0.0)
    costo_materiale = round(peso_kg * costo_mat_kg, 2)

    # --- Coating cost by surface area ---
    area_mm2 = features.get('area_totale_mm2', 0.0)
    area_dm2 = area_mm2 / 10000.0  # mm^2 -> dm^2
    costo_vern_dm2 = _cfg(config, 'costo_verniciatura_dm2')
    costo_verniciatura = round(area_dm2 * costo_vern_dm2, 2)

    # --- Totals ---
    totale = round(costo_foratura + costo_fresatura + costo_piegatura_3d
                   + costo_materiale + costo_verniciatura, 2)

    return {
        'costo_foratura': costo_foratura,
        'costo_fresatura': costo_fresatura,
        'costo_piegatura_3d': costo_piegatura_3d,
        'costo_materiale_stimato': costo_materiale,
        'costo_verniciatura_stimato': costo_verniciatura,
        'tempo_foratura_min': tempo_foratura,
        'tempo_fresatura_min': tempo_fresatura,
        'tempo_piegatura_min': tempo_piegatura,
        'complessita': features.get('complessita', 1),
        'dettaglio_fori': dettaglio_fori,
        'dettaglio_asole': dettaglio_asole,
        'dettaglio_pieghe': dettaglio_pieghe,
        'totale_stimato': totale,
    }
