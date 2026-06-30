"""DXF scanning services: bend detection, welding measurement, threading/countersinking detection.

Extracted from preventivatore 2.0.py — pure functions, no UI references.
"""

import logging
import math
import os

import ezdxf

logger = logging.getLogger(__name__)


def scansiona_dxf_dettagli(path: str, config: dict) -> tuple[int, float, int, int]:
    """Scansiona il DXF e restituisce (pieghe, saldatura_ml, filettatura, svasatura).

    - pieghe: conta le LINE con colore in dxf_colori_piega e lunghezza > soglia
    - saldatura: somma le lunghezze delle LINE con colore in dxf_colori_saldatura
    - filettatura: conta coppie (CIRCLE + ARC semicircolare adiacente)
    - svasatura: conta coppie di CIRCLE concentrici con ratio specifico

    Args:
        path: percorso al file DXF.
        config: dizionario di configurazione con chiavi dxf_colori_piega, ecc.

    Returns:
        (conteggio_pieghe, totale_saldatura_ml, conteggio_filettatura, conteggio_svasatura)
    """
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    # Configurazione parametri
    colori_piega = config.get("dxf_colori_piega", [2])
    colori_sald = config.get("dxf_colori_saldatura", [1])
    lunghezza_minima = float(config.get("dxf_lunghezza_minima", 15))

    tolleranza_centro = float(config.get("dxf_tolleranza_centro", 1.0))
    ratio_min = float(config.get("dxf_svasatura_ratio_min", 1.3))
    ratio_max = float(config.get("dxf_svasatura_ratio_max", 3.0))
    angolo_min = float(config.get("dxf_semicerchio_angolo_min", 150))
    angolo_max = float(config.get("dxf_semicerchio_angolo_max", 210))

    totale_saldatura = 0.0

    # Raccogli geometria per pattern detection
    circles = []  # Lista di (center_x, center_y, radius)
    arcs = []     # Lista di (center_x, center_y, radius, start_angle, end_angle)
    linee_piega = []  # Lista di (x1, y1, x2, y2) per filtro spaziale

    # Controlla se abilitato filtro zona sviluppata
    filtra_zona = config.get("dxf_filtra_zona_sviluppata", False)
    min_x_global = float('inf')
    max_x_global = float('-inf')

    # === PASSO 1: Raccolta cerchi e archi ===
    for entity in msp:
        entity_type = entity.dxftype()

        if entity_type == 'CIRCLE':
            try:
                cx = float(entity.dxf.center.x)
                cy = float(entity.dxf.center.y)
                r = float(entity.dxf.radius)
                circles.append((cx, cy, r))
            except AttributeError:
                continue

        elif entity_type == 'ARC':
            try:
                cx = float(entity.dxf.center.x)
                cy = float(entity.dxf.center.y)
                r = float(entity.dxf.radius)
                start = float(entity.dxf.start_angle)
                end = float(entity.dxf.end_angle)
                arcs.append((cx, cy, r, start, end))
            except AttributeError:
                continue

    # === PASSO 2A: Detection pieghe tramite testi "SU"/"GIU" (Priorità 1) ===
    testi_piega = []
    for entity in msp:
        entity_type = entity.dxftype()
        if entity_type in ['TEXT', 'MTEXT']:
            try:
                testo = entity.dxf.text.strip().upper()
                # Check se inizia con "SU" o "GIU"
                if testo.startswith('SU') or testo.startswith('GIU') or testo.startswith('GIÙ'):
                    if entity_type == 'TEXT':
                        x = float(entity.dxf.insert.x)
                        y = float(entity.dxf.insert.y)
                    else:  # MTEXT
                        x = float(entity.dxf.insert.x)
                        y = float(entity.dxf.insert.y)
                    testi_piega.append((x, y))
            except Exception:
                continue

    # === PASSO 2B: Raccogli tutte le linee ===
    tutte_linee = []  # Lista completa con coordinate
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

            # Aggiorna bounding box globale
            min_x_global = min(min_x_global, x1, x2)
            max_x_global = max(max_x_global, x1, x2)

            # Salva linea completa
            tutte_linee.append({
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                'x_centro': x_centro, 'y_centro': y_centro,
                'lunghezza': lunghezza, 'colore': colore
            })

            # Raccogli linee di piega colorate (per fallback)
            if colore in colori_piega and lunghezza > lunghezza_minima:
                linee_piega.append((x1, y1, x2, y2))

            # Calcola saldature
            if colore in colori_sald and lunghezza > 0:
                totale_saldatura += lunghezza

        except AttributeError:
            continue

    # === PASSO 2C: Detection pieghe con metodo ibrido ===
    x_medio = (min_x_global + max_x_global) / 2 if max_x_global > min_x_global else 0

    # METODO 1: Cerca pieghe tramite testi "SU"/"GIU" (priorità alta)
    pieghe_da_testo = []
    if len(testi_piega) > 0:
        distanza_max = 150.0  # mm - distanza massima testo-linea

        def _dist_punto_segmento(px, py, x1, y1, x2, y2):
            """Distanza minima tra punto (px,py) e segmento (x1,y1)-(x2,y2)."""
            dx, dy = x2 - x1, y2 - y1
            len_sq = dx * dx + dy * dy
            if len_sq == 0:
                return math.sqrt((px - x1)**2 + (py - y1)**2)
            t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / len_sq))
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            return math.sqrt((px - proj_x)**2 + (py - proj_y)**2)

        for (tx, ty) in testi_piega:
            # Trova linea più vicina usando distanza punto-segmento
            # (più accurata del punto-centro per linee lunghe)
            min_dist = float('inf')
            linea_vicina = None

            for linea in tutte_linee:
                # Considera solo linee abbastanza lunghe (probabili linee di piega)
                if linea['lunghezza'] < lunghezza_minima:
                    continue
                dist = _dist_punto_segmento(tx, ty, linea['x1'], linea['y1'], linea['x2'], linea['y2'])
                if dist < min_dist and dist < distanza_max:
                    min_dist = dist
                    linea_vicina = linea

            if linea_vicina:
                # Check zona sinistra se filtro abilitato
                if filtra_zona:
                    if linea_vicina['x_centro'] < x_medio:
                        pieghe_da_testo.append(linea_vicina)
                else:
                    pieghe_da_testo.append(linea_vicina)

    # Se trovati testi SU/GIU, usa il massimo tra:
    # - conteggio testi (semplice e affidabile)
    # - conteggio match testo-linea (validazione geometrica)
    if len(testi_piega) > 0:
        conteggio_pieghe = max(len(testi_piega), len(pieghe_da_testo))
    elif len(pieghe_da_testo) > 0:
        conteggio_pieghe = len(pieghe_da_testo)
    else:
        # METODO 2: Fallback al metodo colore (se nessun testo trovato)
        if filtra_zona and linee_piega and max_x_global > min_x_global:
            # Filtra pieghe colorate nella zona sinistra
            linee_piega_filtrate = []
            for (x1, y1, x2, y2) in linee_piega:
                x_centro_linea = (x1 + x2) / 2
                if x_centro_linea < x_medio:
                    linee_piega_filtrate.append((x1, y1, x2, y2))
            conteggio_pieghe = len(linee_piega_filtrate)
        else:
            # Nessun filtro: conta tutte le pieghe colorate
            conteggio_pieghe = len(linee_piega)

    # === PASSO 3: Detection filettatura ===
    # Calcola bounding box della zona sviluppata (dove ci sono le pieghe)
    zona_sviluppata_min_x = float('inf')
    zona_sviluppata_max_x = float('-inf')
    zona_sviluppata_min_y = float('inf')
    zona_sviluppata_max_y = float('-inf')

    # Usa le linee di piega per definire la zona sviluppata
    if linee_piega:
        for (x1, y1, x2, y2) in linee_piega:
            zona_sviluppata_min_x = min(zona_sviluppata_min_x, x1, x2)
            zona_sviluppata_max_x = max(zona_sviluppata_max_x, x1, x2)
            zona_sviluppata_min_y = min(zona_sviluppata_min_y, y1, y2)
            zona_sviluppata_max_y = max(zona_sviluppata_max_y, y1, y2)
        ha_zona_sviluppata = True
    # Se non ci sono linee di piega, usa i testi "SU"/"GIU" per definire la zona
    elif testi_piega:
        for (tx, ty) in testi_piega:
            zona_sviluppata_min_x = min(zona_sviluppata_min_x, tx)
            zona_sviluppata_max_x = max(zona_sviluppata_max_x, tx)
            zona_sviluppata_min_y = min(zona_sviluppata_min_y, ty)
            zona_sviluppata_max_y = max(zona_sviluppata_max_y, ty)
        ha_zona_sviluppata = True
    else:
        # Se non ci sono pieghe, usa tutto il disegno
        ha_zona_sviluppata = False

    # Espandi la zona per includere elementi vicini alle pieghe
    if ha_zona_sviluppata:
        margine = 100.0  # mm di margine (aumentato per includere fori vicini)
        zona_sviluppata_min_x -= margine
        zona_sviluppata_max_x += margine
        zona_sviluppata_min_y -= margine
        zona_sviluppata_max_y += margine

    def punto_in_zona_sviluppata(x, y):
        """Verifica se un punto è nella zona sviluppata."""
        if not ha_zona_sviluppata:
            return True  # Se non ci sono pieghe, accetta tutto
        return (zona_sviluppata_min_x <= x <= zona_sviluppata_max_x and
                zona_sviluppata_min_y <= y <= zona_sviluppata_max_y)

    filettatura_matched = set()  # Set di (circle_idx, arc_idx)

    for i, (cx_circle, cy_circle, r_circle) in enumerate(circles):
        # Filtra: cerca solo nella zona sviluppata
        if not punto_in_zona_sviluppata(cx_circle, cy_circle):
            continue

        for j, (cx_arc, cy_arc, r_arc, start_angle, end_angle) in enumerate(arcs):
            # Skip se già matchato
            if (i, j) in filettatura_matched:
                continue

            # Check 1: Centri vicini (entro tolleranza)
            dist = math.sqrt((cx_circle - cx_arc)**2 + (cy_circle - cy_arc)**2)
            if dist > tolleranza_centro:
                continue

            # Check 2: Raggio arco leggermente più grande del cerchio
            if r_circle == 0:
                continue
            ratio = r_arc / r_circle
            if not (0.9 <= ratio <= 1.5):
                continue

            # Check 3: Arco è un semicerchio (150° - 210°) o arco grande (240° - 360°)
            arc_angle = end_angle - start_angle
            if arc_angle < 0:
                arc_angle += 360

            # Accetta sia semicerchi piccoli che archi grandi (come 300°)
            is_small_semicircle = angolo_min <= arc_angle <= angolo_max
            is_large_arc = 240 <= arc_angle <= 360

            if is_small_semicircle or is_large_arc:
                filettatura_matched.add((i, j))

    conteggio_filettatura = len(filettatura_matched)

    # === PASSO 4: Detection svasatura ===
    svasatura_matched = set()  # Set di (circle_idx1, circle_idx2)

    for i, (cx1, cy1, r1) in enumerate(circles):
        # Filtra: cerca solo nella zona sviluppata
        if not punto_in_zona_sviluppata(cx1, cy1):
            continue

        for j, (cx2, cy2, r2) in enumerate(circles):
            # Skip stesso cerchio
            if i >= j:
                continue

            # Skip se già matchato
            if (i, j) in svasatura_matched or (j, i) in svasatura_matched:
                continue

            # Check 1: Centri concentrici (entro tolleranza)
            dist = math.sqrt((cx1 - cx2)**2 + (cy1 - cy2)**2)
            if dist > tolleranza_centro:
                continue

            # Check 2: Ratio raggi nel range specificato
            r_outer = max(r1, r2)
            r_inner = min(r1, r2)

            if r_inner == 0:
                continue

            ratio = r_outer / r_inner

            if ratio_min <= ratio <= ratio_max:
                # Check 3: Verifica che NON ci sia un arco nella stessa posizione
                # (che indicherebbe filettatura, non svasatura)
                ha_arco_concentrico = False
                for (cx_arc, cy_arc, r_arc, _, _) in arcs:
                    dist_arc = math.sqrt((cx1 - cx_arc)**2 + (cy1 - cy_arc)**2)
                    if dist_arc <= tolleranza_centro:
                        ha_arco_concentrico = True
                        break

                # Solo se NON c'è un arco, conta come svasatura
                if not ha_arco_concentrico:
                    svasatura_matched.add((i, j))

    conteggio_svasatura = len(svasatura_matched)

    # Converti saldatura da mm (unità DXF) a metri lineari (unità di costo)
    totale_saldatura_ml = totale_saldatura / 1000.0

    return conteggio_pieghe, totale_saldatura_ml, conteggio_filettatura, conteggio_svasatura


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

    Aggiunta Fase 1b merge preventivatore. Complementare a `scansiona_dxf_dettagli`
    (che invece estrae pieghe/saldature/filettature/svasature per i costi post-taglio).

    Convenzioni DXF: tutte le unità in mm.
    - **area_dm2**: area della sagoma esterna del pezzo. Calcolata come area della
      polyline chiusa con BOUNDING BOX più grande (la "shell" esterna). Le
      polyline interne (fori, asole) NON vengono sottratte qui (approssimazione
      conservativa per il PESO MATERIALE, che si calcola sulla lamiera intera
      prima del taglio).
    - **perimetro_taglio_m**: somma di tutte le entità "di taglio" — LINE,
      LWPOLYLINE, POLYLINE, CIRCLE, ARC, SPLINE — ESCLUSE le linee di colore
      piega/saldatura (che non sono tagli laser ma indicazioni grafiche).
    - **n_forature**: count di CIRCLE (ogni cerchio = 1 piercing del laser).

    Args:
        path: percorso al DXF.
        config: dict opzionale con dxf_colori_piega/dxf_colori_saldatura da escludere.

    Returns:
        {area_dm2, perimetro_taglio_m, n_forature, n_polyline_chiuse, area_mm2_raw}
    """
    cfg = config or {}
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

    # Area = bbox di tutte le entità di taglio (= lamiera di partenza necessaria).
    # Sovrastima la sagoma reale ma è coerente con quanto si paga al fornitore
    # (lamiera rettangolare, non sagomata).
    # Se ci sono polyline chiuse, le riportiamo come info aggiuntiva ma la "area"
    # principale resta il bbox per coerenza col calcolo del peso materiale.
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
