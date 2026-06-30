"""DXF scanning services: bend detection, welding measurement, threading/countersinking detection.

Extracted from preventivatore 2.0.py — pure functions, no UI references.
"""

import logging
import math
import os

import ezdxf

from .dxf_polygon_detector import detect_pezzo_geometry as _detect_v2

logger = logging.getLogger(__name__)


def scansiona_dxf_dettagli(path: str, config: dict) -> tuple[int, float, int, int]:
    """Scansiona il DXF e restituisce (pieghe, saldatura_ml, filettatura, svasatura).

    Versione AGGIORNATA (porting dal desktop main_window.py:1105):
    - pieghe: metodo IBRIDO — priorità ai testi 'SU'/'GIU' nel disegno,
      fallback alle linee con colore in dxf_colori_piega
    - saldatura: somma lunghezze LINE con colore in dxf_colori_saldatura
    - filettatura: CIRCLE+ARC adiacenti (filtrato per zona sviluppata se rilevata)
    - svasatura: CIRCLE concentrici (filtrato per zona sviluppata + escluso se
      c'è arco concentrico = sarebbe filettatura, non svasatura)
    """
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    colori_piega = config.get("dxf_colori_piega", [2])
    colori_sald = config.get("dxf_colori_saldatura", [1])
    lunghezza_minima = float(config.get("dxf_lunghezza_minima", 15))
    tolleranza_centro = float(config.get("dxf_tolleranza_centro", 1.0))
    ratio_min = float(config.get("dxf_svasatura_ratio_min", 1.3))
    ratio_max = float(config.get("dxf_svasatura_ratio_max", 3.0))
    angolo_min = float(config.get("dxf_semicerchio_angolo_min", 150))
    angolo_max = float(config.get("dxf_semicerchio_angolo_max", 210))
    filtra_zona = config.get("dxf_filtra_zona_sviluppata", False)

    totale_saldatura = 0.0
    circles = []
    arcs = []
    linee_piega = []
    min_x_global = float('inf')
    max_x_global = float('-inf')

    # === PASSO 1: Raccolta cerchi e archi ===
    for entity in msp:
        et = entity.dxftype()
        if et == 'CIRCLE':
            try:
                circles.append((float(entity.dxf.center.x), float(entity.dxf.center.y), float(entity.dxf.radius)))
            except AttributeError:
                continue
        elif et == 'ARC':
            try:
                arcs.append((float(entity.dxf.center.x), float(entity.dxf.center.y), float(entity.dxf.radius),
                             float(entity.dxf.start_angle), float(entity.dxf.end_angle)))
            except AttributeError:
                continue

    # === PASSO 2A: Detection pieghe via testi SU/GIU (priorità 1) ===
    testi_piega = []
    for entity in msp:
        et = entity.dxftype()
        if et in ('TEXT', 'MTEXT'):
            try:
                testo = (entity.dxf.text or '').strip().upper()
                if testo.startswith('SU') or testo.startswith('GIU') or testo.startswith('GIÙ'):
                    x = float(entity.dxf.insert.x)
                    y = float(entity.dxf.insert.y)
                    testi_piega.append((x, y))
            except Exception:
                continue

    # === PASSO 2B: Raccogli tutte le linee ===
    tutte_linee = []
    for entity in msp.query('LINE'):
        try:
            colore = entity.dxf.color
            start = entity.dxf.start
            end = entity.dxf.end
            x1, y1 = float(start.x), float(start.y)
            x2, y2 = float(end.x), float(end.y)
            x_centro = (x1 + x2) / 2
            y_centro = (y1 + y2) / 2
            lunghezza = float(start.distance(end))
            min_x_global = min(min_x_global, x1, x2)
            max_x_global = max(max_x_global, x1, x2)
            tutte_linee.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                                'x_centro': x_centro, 'y_centro': y_centro,
                                'lunghezza': lunghezza, 'colore': colore})
            if colore in colori_piega and lunghezza > lunghezza_minima:
                linee_piega.append((x1, y1, x2, y2))
            if colore in colori_sald and lunghezza > 0:
                totale_saldatura += lunghezza
        except AttributeError:
            continue

    # === PASSO 2C: Detection pieghe ibrido ===
    x_medio = (min_x_global + max_x_global) / 2 if max_x_global > min_x_global else 0

    pieghe_da_testo = []
    if testi_piega:
        distanza_max = 150.0
        def _dist_punto_segmento(px, py, x1, y1, x2, y2):
            dx, dy = x2 - x1, y2 - y1
            len_sq = dx * dx + dy * dy
            if len_sq == 0:
                return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
            t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / len_sq))
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)

        for (tx, ty) in testi_piega:
            min_dist = float('inf')
            linea_vicina = None
            for linea in tutte_linee:
                if linea['lunghezza'] < lunghezza_minima:
                    continue
                d = _dist_punto_segmento(tx, ty, linea['x1'], linea['y1'], linea['x2'], linea['y2'])
                if d < min_dist and d < distanza_max:
                    min_dist = d
                    linea_vicina = linea
            if linea_vicina:
                if filtra_zona:
                    if linea_vicina['x_centro'] < x_medio:
                        pieghe_da_testo.append(linea_vicina)
                else:
                    pieghe_da_testo.append(linea_vicina)

    if testi_piega:
        conteggio_pieghe = max(len(testi_piega), len(pieghe_da_testo))
    elif pieghe_da_testo:
        conteggio_pieghe = len(pieghe_da_testo)
    else:
        if filtra_zona and linee_piega and max_x_global > min_x_global:
            linee_filtrate = [l for l in linee_piega if ((l[0] + l[2]) / 2) < x_medio]
            conteggio_pieghe = len(linee_filtrate)
        else:
            conteggio_pieghe = len(linee_piega)

    # === PASSO 3: Bounding box "zona sviluppata" (filtro per filettatura/svasatura) ===
    zona_min_x, zona_max_x = float('inf'), float('-inf')
    zona_min_y, zona_max_y = float('inf'), float('-inf')
    if linee_piega:
        for (x1, y1, x2, y2) in linee_piega:
            zona_min_x = min(zona_min_x, x1, x2)
            zona_max_x = max(zona_max_x, x1, x2)
            zona_min_y = min(zona_min_y, y1, y2)
            zona_max_y = max(zona_max_y, y1, y2)
        ha_zona = True
    elif testi_piega:
        for (tx, ty) in testi_piega:
            zona_min_x = min(zona_min_x, tx)
            zona_max_x = max(zona_max_x, tx)
            zona_min_y = min(zona_min_y, ty)
            zona_max_y = max(zona_max_y, ty)
        ha_zona = True
    else:
        ha_zona = False

    if ha_zona:
        margine = 100.0
        zona_min_x -= margine; zona_max_x += margine
        zona_min_y -= margine; zona_max_y += margine

    def in_zona(x, y):
        if not ha_zona:
            return True
        return zona_min_x <= x <= zona_max_x and zona_min_y <= y <= zona_max_y

    # === PASSO 4: Filettatura (CIRCLE + ARC adiacenti, in zona sviluppata) ===
    filettatura_matched = set()
    for i, (cxc, cyc, rc) in enumerate(circles):
        if not in_zona(cxc, cyc):
            continue
        for j, (cxa, cya, ra, sa, ea) in enumerate(arcs):
            if (i, j) in filettatura_matched:
                continue
            d = math.sqrt((cxc - cxa) ** 2 + (cyc - cya) ** 2)
            if d > tolleranza_centro:
                continue
            if rc == 0:
                continue
            ratio = ra / rc
            if not (0.9 <= ratio <= 1.5):
                continue
            arc_angle = ea - sa
            if arc_angle < 0:
                arc_angle += 360
            if (angolo_min <= arc_angle <= angolo_max) or (240 <= arc_angle <= 360):
                filettatura_matched.add((i, j))
    conteggio_filettatura = len(filettatura_matched)

    # === PASSO 5: Svasatura (CIRCLE concentrici, escluso se c'è arco concentrico = filettatura) ===
    svasatura_matched = set()
    for i, (cx1, cy1, r1) in enumerate(circles):
        if not in_zona(cx1, cy1):
            continue
        for j, (cx2, cy2, r2) in enumerate(circles):
            if i >= j:
                continue
            if (i, j) in svasatura_matched or (j, i) in svasatura_matched:
                continue
            d = math.sqrt((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2)
            if d > tolleranza_centro:
                continue
            r_outer = max(r1, r2)
            r_inner = min(r1, r2)
            if r_inner == 0:
                continue
            ratio = r_outer / r_inner
            if ratio_min <= ratio <= ratio_max:
                ha_arco_concentrico = False
                for (cxa, cya, ra, _, _) in arcs:
                    if math.sqrt((cx1 - cxa) ** 2 + (cy1 - cya) ** 2) <= tolleranza_centro:
                        ha_arco_concentrico = True
                        break
                if not ha_arco_concentrico:
                    svasatura_matched.add((i, j))
    conteggio_svasatura = len(svasatura_matched)

    totale_saldatura_ml = round(totale_saldatura / 1000.0, 2)
    logger.info("DXF %s: pieghe=%d, saldatura=%.2f ml, filettatura=%d, svasatura=%d",
                os.path.basename(path), conteggio_pieghe, totale_saldatura_ml,
                conteggio_filettatura, conteggio_svasatura)
    return conteggio_pieghe, totale_saldatura_ml, conteggio_filettatura, conteggio_svasatura


def _normalize_materiale_cartiglio(raw: str) -> str:
    """Mappa il valore raw del cartiglio al codice del laser_estimator.

    Pattern reali trovati nei DXF cliente: 'AISI 304', '1.0037 (S235JR)', 'S235JR',
    'X5CrNi18-10', 'INOX 316', ecc.
    """
    s = (raw or '').strip().upper()
    if not s:
        return ''
    # INOX 316 (numerazione DIN 1.4401)
    if '316' in s or '1.4401' in s or '1.4404' in s:
        return 'INOX_316'
    # INOX 304 (numerazione DIN 1.4301 / nome X5CrNi)
    if '304' in s or '1.4301' in s or 'X5CRNI' in s or 'INOX' in s or 'AISI' in s or 'STAINLESS' in s:
        return 'INOX_304'
    # Alluminio leghe comuni
    if '5083' in s:
        return 'ALU_5083'
    if 'ALLUM' in s or s.startswith('ALU') or '5754' in s or s == 'AL':
        return 'ALU_5754'
    # Acciai al carbonio S235/S275/S355 (codici DIN 1.0037, 1.0044, 1.0577)
    if 'S235' in s or '1.0037' in s or 'ST37' in s or 'FE 37' in s or 'FE37' in s:
        return 'S235'
    if 'S275' in s or '1.0044' in s:
        return 'S235'  # aggregato a S235 (no S275 in laser_config attuale)
    if 'S355' in s or '1.0577' in s or 'ST52' in s:
        return 'S235'  # aggregato a S235 (caratteristiche taglio simili)
    if 'ACCI' in s or 'STEEL' in s or 'FERRO' in s:
        return 'S235'
    # Acciai al carbonio per molle/lamine (C45, C50, C60, C75)
    import re as _re
    if _re.search(r'\bC\s*\d{2}\b', s):
        return 'S235'  # mappato a S235 per costi taglio simili
    # Lamiere a freddo per imbutitura (DIN EN 10130: DC01..DC06)
    if _re.match(r'^DC0?\d', s) or _re.match(r'^DD1\d', s):
        return 'S235'
    # Acciai E335/E355/E360 (DIN EN 10025)
    if _re.search(r'\bE3[3-9]\d\b', s):
        return 'S235'
    return ''


def estrai_materiale_da_cartiglio(path: str) -> dict:
    """Estrae il materiale dal cartiglio del disegno DXF.

    Strategia: cerca un MTEXT/TEXT con testo "Materiale" (case-insensitive),
    prende il testo più vicino spazialmente come valore. Normalizza via
    `_normalize_materiale_cartiglio` al codice del laser_estimator.

    Returns:
        {materiale: 'S235'|'INOX_304'|..., materiale_raw: stringa originale,
         confidence: float 0..1}.
        Se non trovato: materiale='', confidence=0.
    """
    try:
        doc = ezdxf.readfile(path)
    except Exception as e:
        logger.warning('estrai_materiale_da_cartiglio: lettura DXF fallita: %s', e)
        return {'materiale': '', 'materiale_raw': '', 'confidence': 0.0}
    msp = doc.modelspace()

    testi = []
    for e in msp:
        et = e.dxftype()
        if et in ('MTEXT', 'TEXT'):
            try:
                t = (e.dxf.text or '').strip()
                if not t:
                    continue
                # Pulizia codici DXF per MTEXT (es. \U+00B1, \pxqc, formatting)
                import re
                t_clean = re.sub(r'\\[A-Za-z][^;]*;', '', t)  # rimuovi \pxqc; ecc.
                t_clean = re.sub(r'\{|\}', '', t_clean)
                t_clean = re.sub(r'\\U\+([0-9A-Fa-f]{4})', '', t_clean)  # rimuovi unicode escape
                t_clean = t_clean.strip()
                if not t_clean:
                    continue
                x = float(e.dxf.insert.x)
                y = float(e.dxf.insert.y)
                testi.append((x, y, t_clean))
            except Exception:
                continue

    # Trova "Materiale" etichetta
    label_pos = None
    for x, y, t in testi:
        if t.lower() in ('materiale', 'material:', 'material', 'materiale:'):
            label_pos = (x, y)
            break
    if not label_pos:
        # Fallback: cerca direttamente un testo che sia chiaramente un materiale
        for x, y, t in testi:
            mat = _normalize_materiale_cartiglio(t)
            if mat:
                return {'materiale': mat, 'materiale_raw': t, 'confidence': 0.5}
        return {'materiale': '', 'materiale_raw': '', 'confidence': 0.0}

    # Trova il testo più vicino spazialmente che sia un materiale valido
    import math as _math
    best = None
    best_dist = float('inf')
    lx, ly = label_pos
    for x, y, t in testi:
        if (x, y) == label_pos and t.lower().startswith('material'):
            continue
        d = _math.hypot(x - lx, y - ly)
        if d < best_dist:
            mat = _normalize_materiale_cartiglio(t)
            if mat:
                best_dist = d
                best = (mat, t, d)
    if best:
        # confidence proporzionale alla distanza (più vicino = più alta)
        # entro 50 unità DXF: 1.0, oltre 500: 0.3
        conf = max(0.3, min(1.0, 1.0 - (best[2] / 500.0)))
        return {'materiale': best[0], 'materiale_raw': best[1], 'confidence': round(conf, 2)}
    return {'materiale': '', 'materiale_raw': '', 'confidence': 0.0}


def dxf_to_svg_string(path: str) -> str:
    """Converte un DXF in stringa SVG ad alta fedeltà via ezdxf SVGBackend.

    Rendering completo: colori, spessori, archi, spline, polyline complesse —
    qualunque entità DXF supportata dal `Frontend` di ezdxf viene riprodotta
    fedelmente. Usato dalla preview interattiva in `preview-dxf.html`.
    """
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.svg import SVGBackend
    from ezdxf.addons.drawing import layout

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    backend = SVGBackend()
    ctx = RenderContext(doc)
    frontend = Frontend(ctx, backend)
    frontend.draw_layout(msp)

    return backend.get_string(layout.Page(0, 0))


def estrai_geometria_taglio(path: str, config: dict | None = None) -> dict:
    """Estrae area, perimetro_taglio e n_forature da DXF per stima costo laser.

    Dispatcher v1/v2 via config flag `dxf_scanner_version` (default 'v2').

    - **v2** (default): polygon detection vero (algoritmo CAM standard).
      Identifica outer/inner contours, filtra cartiglio per formati ISO + cornici
      rettangolari grandi, sceglie outer come "poligono con più CIRCLE contenuti".
      Errore tipico <10% su DXF Lantek puliti.

    - **v1** (legacy): euristica bbox + cluster densità. Errore medio 38%.
      Fallback se v2 non rileva geometria (es. DXF molto scadenti).

    Returns:
        Dict con campi compatibili tra v1 e v2:
        {area_dm2, perimetro_taglio_m, n_forature, bbox_width_mm, bbox_height_mm,
         tipo_disegno, ...}.
    """
    cfg = config or {}
    version = cfg.get('dxf_scanner_version', 'v2')

    if version == 'v2':
        try:
            r = _detect_v2(path, cfg)
            # Se v2 ha trovato geometria valida, usa il suo risultato
            if r and r.get('area_dm2', 0) > 0:
                # Compatibilità con vecchio schema (alias n_pierce → n_forature)
                if 'n_pierce' in r and 'n_forature' not in r:
                    r['n_forature'] = r['n_pierce']
                # Garantisci tutti i campi attesi da chi consuma estrai_geometria_taglio
                r.setdefault('n_polyline_chiuse', r.get('poligoni_grezzi', 0))
                r.setdefault('area_mm2_raw', round(r['area_dm2'] * 10000.0, 2))
                r.setdefault('zona_pezzo_filtered', True)
                return r
            logger.warning("dxf_scanner v2 ha restituito area=0 per %s — fallback v1", os.path.basename(path))
        except Exception as e:
            logger.warning("dxf_scanner v2 errore su %s: %s — fallback v1", os.path.basename(path), e)
        # Fallthrough a v1

    # === v1 (legacy euristica) ===
    colori_esclusi = set(cfg.get('dxf_colori_piega', [2])) | set(cfg.get('dxf_colori_saldatura', [1]))

    try:
        doc = ezdxf.readfile(path)
    except Exception as e:
        logger.warning('estrai_geometria_taglio: impossibile aprire %s: %s', path, e)
        return {'area_dm2': 0.0, 'perimetro_taglio_m': 0.0, 'n_forature': 0,
                'n_polyline_chiuse': 0, 'area_mm2_raw': 0.0,
                'bbox_width_mm': 0.0, 'bbox_height_mm': 0.0}
    msp = doc.modelspace()

    perimetro_mm = 0.0
    n_forature = 0
    polyline_chiuse_areas = []  # (area_mm2, bbox_size_mm) per scegliere shell esterna
    # Bounding box delle entità "di taglio" (= dimensione lamiera necessaria, sovrastima conservativa)
    bbox_xs, bbox_ys = [], []
    # Ignora annotazioni DIMENSION/MTEXT/TEXT/INSERT (sono testo, non geometria di taglio)
    TIPI_ANNOTAZIONE = {'DIMENSION', 'MTEXT', 'TEXT', 'INSERT', 'ATTRIB', 'ATTDEF', 'LEADER', 'MULTILEADER'}

    def _len_line(x1, y1, x2, y2):
        return math.hypot(x2 - x1, y2 - y1)

    def _shoelace_area(verts):
        n = len(verts)
        if n < 3:
            return 0.0
        a = 0.0
        for i in range(n):
            x1, y1 = verts[i][0], verts[i][1]
            x2, y2 = verts[(i + 1) % n][0], verts[(i + 1) % n][1]
            a += x1 * y2 - x2 * y1
        return abs(a) / 2.0

    def _bbox_size(verts):
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        return max(max(xs) - min(xs), max(ys) - min(ys))

    def _perim_polyline(verts, closed=False):
        if len(verts) < 2:
            return 0.0
        p = 0.0
        for i in range(len(verts) - 1):
            p += _len_line(verts[i][0], verts[i][1], verts[i + 1][0], verts[i + 1][1])
        if closed:
            p += _len_line(verts[-1][0], verts[-1][1], verts[0][0], verts[0][1])
        return p

    for entity in msp:
        etype = entity.dxftype()
        if etype in TIPI_ANNOTAZIONE:
            continue
        color = entity.dxf.color if hasattr(entity.dxf, 'color') else 7
        if color in colori_esclusi:
            continue

        if etype == 'LINE':
            s = entity.dxf.start
            e = entity.dxf.end
            perimetro_mm += _len_line(s.x, s.y, e.x, e.y)
            bbox_xs += [s.x, e.x]; bbox_ys += [s.y, e.y]

        elif etype == 'CIRCLE':
            c = entity.dxf.center
            r = entity.dxf.radius
            perimetro_mm += 2 * math.pi * r
            n_forature += 1
            bbox_xs += [c.x - r, c.x + r]; bbox_ys += [c.y - r, c.y + r]

        elif etype == 'ARC':
            c = entity.dxf.center
            r = entity.dxf.radius
            sweep = (entity.dxf.end_angle - entity.dxf.start_angle) % 360.0
            perimetro_mm += 2 * math.pi * r * (sweep / 360.0)
            bbox_xs += [c.x - r, c.x + r]; bbox_ys += [c.y - r, c.y + r]

        elif etype == 'LWPOLYLINE':
            verts = [(p[0], p[1]) for p in entity.get_points()]
            closed_flag = bool(entity.closed)
            geom_closed = (len(verts) >= 3 and
                           _len_line(verts[0][0], verts[0][1], verts[-1][0], verts[-1][1]) < 0.1)
            closed = closed_flag or geom_closed
            perimetro_mm += _perim_polyline(verts, closed and not geom_closed)
            if closed and len(verts) >= 3:
                a_mm2 = _shoelace_area(verts)
                if a_mm2 > 0:
                    polyline_chiuse_areas.append((a_mm2, _bbox_size(verts)))
            for vx, vy in verts:
                bbox_xs.append(vx); bbox_ys.append(vy)

        elif etype == 'POLYLINE':
            verts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
            closed_flag = bool(getattr(entity, 'is_closed', False))
            geom_closed = (len(verts) >= 3 and
                           _len_line(verts[0][0], verts[0][1], verts[-1][0], verts[-1][1]) < 0.1)
            closed = closed_flag or geom_closed
            perimetro_mm += _perim_polyline(verts, closed and not geom_closed)
            if closed and len(verts) >= 3:
                a_mm2 = _shoelace_area(verts)
                if a_mm2 > 0:
                    polyline_chiuse_areas.append((a_mm2, _bbox_size(verts)))

        elif etype == 'SPLINE':
            # Approssimazione: lunghezza spline ≈ sum segments dei punti di controllo
            try:
                pts = list(entity.flattening(distance=0.5))
                for i in range(len(pts) - 1):
                    perimetro_mm += _len_line(pts[i].x, pts[i].y, pts[i + 1].x, pts[i + 1].y)
            except Exception:
                pass

    # === Filtro cartiglio via cluster denso ===
    # Strategia: il pezzo è una zona DENSA di entità geometriche concentrate.
    # Il cartiglio è composto da poche entità SPARSE (cornici sui 4 bordi del foglio,
    # piccoli riquadri di registro). Filtrando per percentile 5-95 dei centroidi
    # delle entità di taglio, isolo la zona del pezzo escludendo cornici.

    # Raccogli centroidi di TUTTE le entità di taglio
    centroidi_xs = []
    centroidi_ys = []
    entita = []  # lista di (etype, centroide, dati per ricalcolo) per ri-iterazione
    for entity in msp:
        et = entity.dxftype()
        if et in TIPI_ANNOTAZIONE:
            continue
        color = entity.dxf.color if hasattr(entity.dxf, 'color') else 7
        if color in colori_esclusi:
            continue
        if et == 'LINE':
            s, e = entity.dxf.start, entity.dxf.end
            cx, cy = (s.x + e.x) / 2, (s.y + e.y) / 2
            entita.append(('LINE', cx, cy, (s.x, s.y, e.x, e.y)))
            centroidi_xs.append(cx); centroidi_ys.append(cy)
        elif et == 'CIRCLE':
            c, r = entity.dxf.center, entity.dxf.radius
            entita.append(('CIRCLE', c.x, c.y, (c.x, c.y, r)))
            centroidi_xs.append(c.x); centroidi_ys.append(c.y)
        elif et == 'ARC':
            c, r = entity.dxf.center, entity.dxf.radius
            sweep = (entity.dxf.end_angle - entity.dxf.start_angle) % 360.0
            entita.append(('ARC', c.x, c.y, (c.x, c.y, r, sweep)))
            centroidi_xs.append(c.x); centroidi_ys.append(c.y)
        elif et == 'LWPOLYLINE':
            verts = [(p[0], p[1]) for p in entity.get_points()]
            if not verts:
                continue
            cx = sum(v[0] for v in verts) / len(verts)
            cy = sum(v[1] for v in verts) / len(verts)
            closed = bool(entity.closed) or (
                len(verts) >= 3 and _len_line(verts[0][0], verts[0][1], verts[-1][0], verts[-1][1]) < 0.1)
            entita.append(('LWPOLYLINE', cx, cy, (verts, closed)))
            centroidi_xs.append(cx); centroidi_ys.append(cy)
        elif et == 'POLYLINE':
            verts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
            if not verts:
                continue
            cx = sum(v[0] for v in verts) / len(verts)
            cy = sum(v[1] for v in verts) / len(verts)
            closed_flag = bool(getattr(entity, 'is_closed', False))
            geom_closed = (len(verts) >= 3 and
                           _len_line(verts[0][0], verts[0][1], verts[-1][0], verts[-1][1]) < 0.1)
            closed = closed_flag or geom_closed
            entita.append(('POLYLINE', cx, cy, (verts, closed)))
            centroidi_xs.append(cx); centroidi_ys.append(cy)

    # === IDENTIFICAZIONE ZONA PEZZO ===
    # Due tipi di DXF cliente:
    # 1. SVILUPPATO: pezzo in lamiera con linee di piega marcate (testi SU/GIU
    #    o linee in COLOR 2). Il pezzo è dove ci sono le pieghe → bbox piega
    # 2. A VISTE: disegno tecnico con front/top/side. Niente pieghe → fallback
    #    cluster densità (prende la vista più ricca di entità = principale)

    # Strategia 1: ZONA PIEGA (più affidabile per pezzi sviluppati)
    pieghe_pts = []
    for entity in msp:
        et = entity.dxftype()
        if et in ('TEXT', 'MTEXT'):
            try:
                t = (entity.dxf.text or '').strip().upper()
                if t.startswith('SU') or t.startswith('GIU') or t.startswith('GIÙ'):
                    pieghe_pts.append((float(entity.dxf.insert.x), float(entity.dxf.insert.y)))
            except Exception:
                pass
        elif et == 'LINE':
            try:
                color = entity.dxf.color if hasattr(entity.dxf, 'color') else 7
                if color in cfg.get('dxf_colori_piega', [2]):
                    s, e = entity.dxf.start, entity.dxf.end
                    pieghe_pts.append(((s.x + e.x) / 2, (s.y + e.y) / 2))
            except Exception:
                pass

    # Pezzo è SVILUPPATO (1 lamiera piana con pieghe) o A VISTE (più proiezioni).
    # Sviluppato: zona = bbox delle pieghe + margine 100mm o 50% (= include contorni)
    # A viste:    zona = cluster densità (= vista più ricca di entità)
    is_sviluppato = len(pieghe_pts) > 0
    zona_pezzo_bbox = None

    if is_sviluppato:
        pxs = [p[0] for p in pieghe_pts]
        pys = [p[1] for p in pieghe_pts]
        zx_min, zx_max = min(pxs), max(pxs)
        zy_min, zy_max = min(pys), max(pys)
        w_p = zx_max - zx_min
        h_p = zy_max - zy_min
        # Margine misto: 100mm assoluti OPPURE 50% dimensione bbox piega (il max)
        margine_x = max(100.0, w_p * 0.5)
        margine_y = max(100.0, h_p * 0.5)
        zona_pezzo_bbox = (zx_min - margine_x, zx_max + margine_x,
                           zy_min - margine_y, zy_max + margine_y)

    # Cluster densità SOLO per pezzi a viste (no pieghe)
    if zona_pezzo_bbox is None and len(centroidi_xs) >= 10:
        x_min_tot, x_max_tot = min(centroidi_xs), max(centroidi_xs)
        y_min_tot, y_max_tot = min(centroidi_ys), max(centroidi_ys)
        N_BINS = 20
        cell_w = max(1e-6, (x_max_tot - x_min_tot) / N_BINS)
        cell_h = max(1e-6, (y_max_tot - y_min_tot) / N_BINS)
        grid = {}
        for cx, cy in zip(centroidi_xs, centroidi_ys):
            ix = min(N_BINS - 1, max(0, int((cx - x_min_tot) / cell_w)))
            iy = min(N_BINS - 1, max(0, int((cy - y_min_tot) / cell_h)))
            grid[(ix, iy)] = grid.get((ix, iy), 0) + 1
        if grid:
            max_cell = max(grid, key=grid.get)
            max_count = grid[max_cell]
            threshold = max(1, max_count * 0.20)  # 20% — isola vista più densa
            # BFS espansione greedy
            visited = {max_cell}
            queue = [max_cell]
            while queue:
                ix, iy = queue.pop(0)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = ix + dx, iy + dy
                        if 0 <= nx < N_BINS and 0 <= ny < N_BINS and (nx, ny) not in visited:
                            if grid.get((nx, ny), 0) >= threshold:
                                visited.add((nx, ny))
                                queue.append((nx, ny))
            cxs = [c[0] for c in visited]
            cys = [c[1] for c in visited]
            bx_min = x_min_tot + min(cxs) * cell_w
            bx_max = x_min_tot + (max(cxs) + 1) * cell_w
            by_min = y_min_tot + min(cys) * cell_h
            by_max = y_min_tot + (max(cys) + 1) * cell_h
            # Margine cella per non tagliare entità di bordo
            zona_pezzo_bbox = (bx_min - cell_w * 0.5, bx_max + cell_w * 0.5,
                               by_min - cell_h * 0.5, by_max + cell_h * 0.5)

    if zona_pezzo_bbox:
        x_min_z, x_max_z, y_min_z, y_max_z = zona_pezzo_bbox

        def _in_pezzo(x, y):
            return x_min_z <= x <= x_max_z and y_min_z <= y <= y_max_z

        # Itera le entità collezionate, conta solo quelle nella zona pezzo
        perim_pezzo_mm = 0.0
        n_forature_pezzo = 0
        xs_real, ys_real = [], []  # bbox effettivo delle entità nel pezzo
        for kind, cx, cy, dati in entita:
            if not _in_pezzo(cx, cy):
                continue
            if kind == 'LINE':
                x1, y1, x2, y2 = dati
                perim_pezzo_mm += _len_line(x1, y1, x2, y2)
                xs_real += [x1, x2]; ys_real += [y1, y2]
            elif kind == 'CIRCLE':
                cxx, cyy, r = dati
                perim_pezzo_mm += 2 * math.pi * r
                n_forature_pezzo += 1
                xs_real += [cxx - r, cxx + r]; ys_real += [cyy - r, cyy + r]
            elif kind == 'ARC':
                cxx, cyy, r, sweep = dati
                perim_pezzo_mm += 2 * math.pi * r * (sweep / 360.0)
                xs_real += [cxx - r, cxx + r]; ys_real += [cyy - r, cyy + r]
            elif kind in ('LWPOLYLINE', 'POLYLINE'):
                verts, closed = dati
                perim_pezzo_mm += _perim_polyline(verts, closed)
                for vx, vy in verts:
                    xs_real.append(vx); ys_real.append(vy)

        if xs_real:
            bbox_w_mm = max(xs_real) - min(xs_real)
            bbox_h_mm = max(ys_real) - min(ys_real)
            area_mm2 = bbox_w_mm * bbox_h_mm  # bbox del pezzo (lamiera necessaria)
        else:
            bbox_w_mm = bbox_h_mm = area_mm2 = 0.0
        perimetro_mm = perim_pezzo_mm
        n_forature = n_forature_pezzo
    else:
        # Fallback: nessuna polyline chiusa → uso bbox totale (vecchia logica)
        if bbox_xs and bbox_ys:
            bbox_w_mm = max(bbox_xs) - min(bbox_xs)
            bbox_h_mm = max(bbox_ys) - min(bbox_ys)
            area_mm2 = bbox_w_mm * bbox_h_mm
        else:
            bbox_w_mm = bbox_h_mm = 0.0
            area_mm2 = 0.0

    return {
        'area_dm2': round(area_mm2 / 10000.0, 4),       # mm² → dm² (1 dm² = 10000 mm²)
        'perimetro_taglio_m': round(perimetro_mm / 1000.0, 4),  # mm → m
        'n_forature': n_forature,
        'n_polyline_chiuse': len(polyline_chiuse_areas),
        'area_mm2_raw': round(area_mm2, 2),
        'bbox_width_mm': round(bbox_w_mm, 2),
        'bbox_height_mm': round(bbox_h_mm, 2),
        'zona_pezzo_filtered': zona_pezzo_bbox is not None,
        'tipo_disegno': 'sviluppato' if is_sviluppato else 'a_viste',
    }


def dxf_to_segments(path: str) -> tuple[list, list, list]:
    """Legge un file DXF e restituisce (segments, xs, ys).

    segments: lista di (x1, y1, x2, y2) per LINE, POLYLINE, CIRCLE, ARC, SPLINE.
    xs, ys: liste di coordinate per calcolo bounding box.
    Solleva eccezione se il file non è leggibile.
    """
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    segments = []
    xs = []
    ys = []

    for entity in msp:
        et = entity.dxftype()
        if et == 'LINE':
            try:
                x1, y1 = entity.dxf.start.x, entity.dxf.start.y
                x2, y2 = entity.dxf.end.x, entity.dxf.end.y
                segments.append((x1, y1, x2, y2))
                xs += [x1, x2]
                ys += [y1, y2]
            except Exception:
                continue

        elif et in ('LWPOLYLINE', 'POLYLINE'):
            pts = []
            try:
                pts = list(entity.get_points())
            except Exception:
                try:
                    pts = list(entity.points())
                except Exception:
                    try:
                        pts = [v.dxf.location for v in entity.vertices()]
                    except Exception:
                        pts = []

            cleaned = []
            for p in pts:
                if p is None:
                    continue
                if hasattr(p, 'x') and hasattr(p, 'y'):
                    cleaned.append((float(p.x), float(p.y)))
                elif isinstance(p, (tuple, list)) and len(p) >= 2:
                    cleaned.append((float(p[0]), float(p[1])))

            for a, b in zip(cleaned, cleaned[1:]):
                x1, y1 = a
                x2, y2 = b
                segments.append((x1, y1, x2, y2))
                xs += [x1, x2]
                ys += [y1, y2]

        elif et == 'CIRCLE':
            try:
                c = entity.dxf.center
                r = float(entity.dxf.radius)
                for i in range(24):
                    a1 = 2 * math.pi * i / 24
                    a2 = 2 * math.pi * (i + 1) / 24
                    x1 = c.x + r * math.cos(a1)
                    y1 = c.y + r * math.sin(a1)
                    x2 = c.x + r * math.cos(a2)
                    y2 = c.y + r * math.sin(a2)
                    segments.append((x1, y1, x2, y2))
                    xs += [x1, x2]
                    ys += [y1, y2]
            except Exception:
                continue

        elif et == 'ARC':
            try:
                c = entity.dxf.center
                r = float(entity.dxf.radius)
                start_angle = math.radians(float(entity.dxf.start_angle))
                end_angle = math.radians(float(entity.dxf.end_angle))
                num_segments = 24
                angle_range = end_angle - start_angle
                if angle_range < 0:
                    angle_range += 2 * math.pi
                for i in range(num_segments):
                    a1 = start_angle + angle_range * i / num_segments
                    a2 = start_angle + angle_range * (i + 1) / num_segments
                    x1 = c.x + r * math.cos(a1)
                    y1 = c.y + r * math.sin(a1)
                    x2 = c.x + r * math.cos(a2)
                    y2 = c.y + r * math.sin(a2)
                    segments.append((x1, y1, x2, y2))
                    xs += [x1, x2]
                    ys += [y1, y2]
            except Exception:
                continue

        elif et == 'SPLINE':
            try:
                points = list(entity.flattening(0.1))
                for i in range(len(points) - 1):
                    p1 = points[i]
                    p2 = points[i + 1]
                    x1, y1 = float(p1[0]), float(p1[1])
                    x2, y2 = float(p2[0]), float(p2[1])
                    segments.append((x1, y1, x2, y2))
                    xs += [x1, x2]
                    ys += [y1, y2]
            except Exception:
                continue

    return segments, xs, ys


def crea_mappatura_dxf(dxf_paths: list) -> dict:
    """Crea una mappa {basename_lower: [paths]} dai file DXF selezionati."""
    m = {}
    for p in dxf_paths:
        base = os.path.splitext(os.path.basename(p))[0].lower()
        # conserviamo liste per gestire eventuali omonimi
        m.setdefault(base, []).append(p)
    return m


def trova_dxf_per_codice(codice: str, dxf_map: dict) -> str | None:
    """Tenta di trovare il miglior percorso DXF per `codice` nella mappa.

    Strategie (in ordine):
    - match esatto base==codice
    - match dove codice è substring del basename
    - match dove basename è substring del codice
    Restituisce path string o None.
    """
    key = codice.lower()

    # 1) match esatto
    if key in dxf_map:
        paths = dxf_map[key]
        return paths[0] if paths else None

    # 2) codice è substring del basename
    for base, paths in dxf_map.items():
        if key in base:
            return paths[0]

    # 3) basename è substring del codice
    for base, paths in dxf_map.items():
        if base in key:
            return paths[0]

    return None
