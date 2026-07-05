"""Worker functions per import DXF batch parallelizzato.

Ogni funzione è top-level (serializzabile per multiprocessing/threading) e
esegue una singola unità di parsing. L'endpoint batch le chiama in pool.

Design:
- process_single_dxf: legge il file, calcola hash, cache lookup, se miss
  fa parsing completo (scansiona + detector + cartiglio + spessore) e cache put.
- Ritorna sempre un dict serializzabile.
- Errori non fanno crash del worker: catturati e ritornati come {success: False}.

Perché ThreadPool e non ProcessPool:
- Flask dev server ha già `threaded=True`, quindi thread interni sono nativi.
- ezdxf e Shapely rilasciano il GIL su chiamate C-level → parallelismo effettivo
  anche con ThreadPool.
- ProcessPool su Windows richiede spawn (lento all'avvio) + serializzazione
  pickle di grossi oggetti.
- Cache SHA256 SQLite: SQLite è thread-safe per default (`check_same_thread=False`).
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def process_single_dxf(dxf_path: str, filename: str, dxf_cfg: dict) -> dict:
    """Esegue il pipeline completo di parsing su un singolo file DXF.

    Args:
        dxf_path: percorso del file già salvato su disco
        filename: nome file originale (per audit/log)
        dxf_cfg: config estrazione (colori piega/saldatura, tolleranze)

    Returns:
        dict payload (stesso schema di POST /import-dxf single):
        {success, filename, lavorazioni, geometria, cartiglio, spessore,
         _cache_hit?, error?}
    """
    from . import dxf_cache, dxf_scanner
    from .dxf_polygon_detector_v3 import detect_pezzo_geometry_v3

    # ---- Cache lookup ----
    try:
        file_hash = dxf_cache.hash_file(dxf_path)
        cached = dxf_cache.get(file_hash)
    except Exception as e:
        logger.warning('[%s] cache lookup fail: %s', filename, e)
        file_hash = None
        cached = None
    if cached and cached.get('payload'):
        payload = dict(cached['payload'])
        payload['filename'] = filename
        payload['_cache_hit'] = True
        return payload

    # ---- Parsing completo ----
    try:
        pieghe, sald_ml, fil, svas = dxf_scanner.scansiona_dxf_dettagli(dxf_path, dxf_cfg)
        try:
            geo = detect_pezzo_geometry_v3(dxf_path, dxf_cfg)
            if not geo or geo.get('area_dm2', 0) == 0:
                geo = dxf_scanner.estrai_geometria_taglio(dxf_path, dxf_cfg)
        except Exception as _e:
            logger.warning('[%s] detector v3 fallito: %s', filename, _e)
            geo = dxf_scanner.estrai_geometria_taglio(dxf_path, dxf_cfg)
        cartiglio = dxf_scanner.estrai_materiale_da_cartiglio(dxf_path)
        mat_for_calc = cartiglio.get('materiale') if cartiglio.get('confidence', 0) >= 0.5 else None
        spessore = dxf_scanner.estrai_spessore_da_cartiglio(
            dxf_path,
            area_dm2=(geo or {}).get('area_dm2'),
            materiale=mat_for_calc,
        )
        if geo and geo.get('needs_manual_select'):
            spessore = {**spessore, 'confidence': min(spessore.get('confidence', 0), 0.4)}

        payload = {
            'success': True,
            'filename': filename,
            'lavorazioni': {
                'pieghe': pieghe, 'saldatura_ml': sald_ml,
                'filettatura_pz': fil, 'svasatura_pz': svas,
            },
            'geometria': geo,
            'cartiglio': cartiglio,
            'spessore': spessore,
        }
        # Cache put (best effort)
        if file_hash:
            try:
                dxf_cache.put(file_hash, filename, payload)
            except Exception as e:
                logger.warning('[%s] cache put fail: %s', filename, e)
        return payload
    except Exception as e:
        logger.exception('[%s] parsing fallito', filename)
        return {'success': False, 'filename': filename, 'error': str(e)}
