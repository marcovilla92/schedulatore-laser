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

        # Fallback cartiglio-descrizione: parsing testuale "45x12 sp.3".
        # - area/perimetro solo se detector geometrico è debole
        # - spessore anche se il detector area è OK ma spessore diretto null
        #   (es. 20PA00690: detector area OK, ma spessore diretto null e
        #   cartiglio contiene 'Sp.3' → deve popolare spessore)
        dim_info = dxf_scanner.estrai_dimensioni_da_descrizione_cartiglio(dxf_path)
        geo_weak = geo and (geo.get('confidence', 0) < 0.5 or geo.get('area_dm2', 0) < 0.01)
        if dim_info and dim_info.get('area_dm2') and geo_weak:
            logger.info('[%s] cartiglio fallback area: %s', filename, dim_info.get('raw_text'))
            geo = {
                **(geo or {}),
                'area_dm2': dim_info['area_dm2'],
                'perimetro_taglio_m': dim_info['perimetro_taglio_m'],
                'n_forature': max(
                    dim_info.get('n_forature', 0),
                    (geo or {}).get('n_forature', 0),
                ),
                'confidence': dim_info['confidence'],
                'confidence_label': 'media (cartiglio)',
                'needs_manual_select': False,
                '_source': 'cartiglio_descrizione',
                '_raw_text': dim_info['raw_text'],
                '_dim_x_mm': dim_info['dim_x_mm'],
                '_dim_y_mm': dim_info['dim_y_mm'],
            }
        # Cartiglio-descrizione (fonte esplicita "sp.3" letta dal disegno) prevale
        # sulla stima peso_area (indiretta) quando confidence maggiore. 20PA00690:
        # peso_area calcola 1.2mm (conf 0.4) ma cartiglio dice sp.3 (conf 0.85).
        if dim_info and dim_info.get('spessore_mm'):
            dim_conf = dim_info.get('confidence', 0) or 0
            curr_sp = spessore.get('spessore_mm')
            curr_conf = spessore.get('confidence', 0) or 0
            if not curr_sp or dim_conf > curr_conf:
                logger.info('[%s] cartiglio fallback spessore: %.1fmm (conf %.2f) sostituisce %s (conf %.2f)',
                            filename, dim_info['spessore_mm'], dim_conf,
                            curr_sp, curr_conf)
                spessore = {
                    'spessore_mm': dim_info['spessore_mm'],
                    'confidence': dim_conf,
                    'source': 'cartiglio_descrizione',
                    'warnings': [],
                    'details': {'raw': dim_info['raw_text']},
                }

        # ---- Auto-cleanup DXF (Fase 1a) ----
        # Se il detector ha alta confidence e sanity check ok, salva DXF pulito
        # (solo pezzo + fori interni al bbox). Il commerciale poi lo verifica
        # nella griglia review post-import. Salvato accanto all'originale come
        # <name>_cleaned.dxf.
        cleaned_info = {'cleaned_dxf_filename': None, 'cleaned_status': None,
                        'cleanup_reason': None, 'cleanup_stats': None}
        try:
            from . import dxf_cleanup
            proceed, reason = dxf_cleanup.should_cleanup(geo)
            cleaned_info['cleanup_reason'] = reason
            if proceed:
                bbox = dxf_cleanup.get_pezzo_bbox(geo)
                if bbox:
                    base, ext = os.path.splitext(dxf_path)
                    cleaned_path = base + '_cleaned' + ext
                    r = dxf_cleanup.save_cleaned_dxf(dxf_path, cleaned_path, bbox)
                    if r.get('success'):
                        cleaned_info['cleaned_dxf_filename'] = os.path.basename(cleaned_path)
                        # 'auto' se confidence alta, 'auto_review' se media
                        conf = float(geo.get('confidence', 0) or 0)
                        cleaned_info['cleaned_status'] = 'auto' if conf >= 0.7 else 'auto_review'
                        cleaned_info['cleanup_stats'] = {
                            'entities_copied': r['entities_copied'],
                            'entities_source': r['entities_source'],
                            'tolerance_mm': r['tolerance_mm'],
                            'warnings': r.get('warnings') or [],
                        }
                        logger.info('[%s] cleanup auto ok: %d/%d entità (%s)',
                                    filename, r['entities_copied'], r['entities_source'],
                                    cleaned_info['cleaned_status'])
                    else:
                        logger.info('[%s] cleanup fallito: %s', filename, r.get('error'))
        except Exception as e:
            logger.warning('[%s] cleanup pipeline error: %s', filename, e)

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
            'cleanup': cleaned_info,
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
