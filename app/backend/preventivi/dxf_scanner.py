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

    Copre i 5 materiali del cliente (S235, ZINCATO, INOX_304, ALU, OTTONE)
    con pattern noti dei principali standard: DIN/EN, ASTM/AISI, UNI, nomi
    commerciali. Se non riconosciuto → stringa vuota (caller può fallback a LLM).

    Pattern reali trovati nei DXF cliente: 'AISI 304', '1.0037 (S235JR)',
    'S235JR', 'X5CrNi18-10', 'INOX 316', 'C75 S', 'S235JR+Z275'.
    """
    import re as _re
    s = (raw or '').strip().upper()
    if not s:
        return ''

    # ---- ZINCATO (prima di S235 perché ha marker aggiuntivo Z/GD) ----
    # Lamiere pre-zincate (DIN EN 10346: DX51D+Z, DX52D+Z, DX53D+Z, DX54D+Z)
    if _re.search(r'\bDX5[1-6]D?\s*\+?\s*Z', s):
        return 'ZINCATO'
    # Acciai galvanizzati per profilazione (S220GD, S250GD, S320GD, S350GD)
    if _re.search(r'\bS[23]\d{2}GD\b', s):
        return 'ZINCATO'
    # S235JR + Z275 / +Z100 (rivestimento zinco su acciaio strutturale)
    if _re.search(r'\+\s*Z\d{2,4}\b', s):
        return 'ZINCATO'
    if 'ZINCAT' in s or 'GALVAN' in s or 'SENDZIMIR' in s or 'ZINCK' in s:
        return 'ZINCATO'

    # ---- OTTONE ----
    if 'OTTONE' in s or 'BRASS' in s or 'MESSING' in s or _re.search(r'\bCUZN\d', s):
        return 'OTTONE'
    # Codici commerciali ottone (MS58, MS63, MS72, CW508L, CW614N)
    if _re.match(r'^MS\d{2}', s) or _re.match(r'^CW\d{3}[A-Z]?', s):
        return 'OTTONE'

    # ---- INOX 316 (numerazione DIN 1.4401/1.4404) ----
    if '316' in s or '1.4401' in s or '1.4404' in s or 'X2CRNIMO' in s:
        return 'INOX_304'  # mappato a 304 (no 316 in laser_config attuale)

    # ---- INOX 304 (numerazione DIN 1.4301 / nome X5CrNi) ----
    if '304' in s or '1.4301' in s or 'X5CRNI' in s or 'INOX' in s or 'AISI' in s or 'STAINLESS' in s:
        return 'INOX_304'
    if _re.search(r'\bX\d+CRNI\b', s):
        return 'INOX_304'

    # ---- Alluminio (tutte le leghe → ALU nel laser_config) ----
    if 'ALLUM' in s or s.startswith('ALU') or 'ALUMIN' in s or s == 'AL':
        return 'ALU'
    if _re.search(r'\b5\d{3}\b', s):  # 5052, 5083, 5754, ecc.
        return 'ALU'
    if _re.search(r'\b(6060|6061|6082|7075|3003|1050)\b', s):
        return 'ALU'
    if _re.search(r'\bENAW\b', s) or _re.search(r'\bAW-?\d{4}\b', s):
        return 'ALU'

    # ---- S235 aggregato (tutti gli acciai al carbonio strutturali) ----
    if 'S235' in s or '1.0037' in s or 'ST37' in s or 'FE 37' in s or 'FE37' in s:
        return 'S235'
    if 'S275' in s or '1.0044' in s:
        return 'S235'
    if 'S355' in s or '1.0577' in s or 'ST52' in s:
        return 'S235'
    if 'S460' in s or 'S500' in s or 'S550' in s:
        return 'S235'  # HSLA aggregati
    # Acciai al carbonio per molle/lamine (C45, C50, C60, C75, C45E, C60E)
    if _re.search(r'\bC\s*\d{2,3}[A-Z]?\b', s):
        return 'S235'
    # Lamiere a freddo per imbutitura (DIN EN 10130: DC01..DC06)
    if _re.match(r'^DC0?\d', s) or _re.match(r'^DD1\d', s):
        return 'S235'
    # Acciai E335/E355/E360 (DIN EN 10025)
    if _re.search(r'\bE3[3-9]\d\b', s):
        return 'S235'
    # Nomi generici acciaio
    if 'ACCI' in s or 'STEEL' in s or 'FERRO' in s or 'STAHL' in s:
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
        # LAST RESORT: se abbiamo trovato una stringa candidata ma la tabella
        # non la riconosce, chiediamo a Gemini (se configurato)
        return _try_llm_fallback(testi, label_pos=None)

    # Trova il testo più vicino spazialmente che sia un materiale valido
    import math as _math
    best = None
    best_dist = float('inf')
    best_unmapped_raw = None  # candidato raw ma non normalizzato dalla tabella
    best_unmapped_dist = float('inf')
    lx, ly = label_pos
    for x, y, t in testi:
        if (x, y) == label_pos and t.lower().startswith('material'):
            continue
        d = _math.hypot(x - lx, y - ly)
        mat = _normalize_materiale_cartiglio(t)
        if mat:
            if d < best_dist:
                best_dist = d
                best = (mat, t, d)
        elif len(t) >= 3 and any(c.isalpha() for c in t) and d < best_unmapped_dist:
            # Candidato non mappato dalla tabella: potrebbe essere un codice
            # sconosciuto (es. cartiglio custom). Salviamo per fallback LLM.
            best_unmapped_dist = d
            best_unmapped_raw = t
    if best:
        # confidence proporzionale alla distanza (più vicino = più alta)
        # entro 50 unità DXF: 1.0, oltre 500: 0.3
        conf = max(0.3, min(1.0, 1.0 - (best[2] / 500.0)))
        return {'materiale': best[0], 'materiale_raw': best[1], 'confidence': round(conf, 2)}

    # Fallback LLM: la tabella non ha riconosciuto ma abbiamo un candidato raw
    if best_unmapped_raw:
        llm_result = _try_llm_normalize(best_unmapped_raw)
        if llm_result:
            return llm_result

    return {'materiale': '', 'materiale_raw': best_unmapped_raw or '', 'confidence': 0.0}


def _somma_perim_fori_da_circle(path: str, min_r_mm: float = 1.0,
                                  max_r_mm: float = 25.0,
                                  dedup_tol_mm: float = 0.5) -> tuple[float, int]:
    """Somma il perimetro dei CIRCLE nel DXF che sono verosimili "fori di taglio".

    Politica:
    - Include solo CIRCLE con raggio ∈ [min_r_mm, max_r_mm] (esclude marker
      minuscoli e cerchi enormi tipo bordi decorativi).
    - Cerchi concentrici (stesso center entro dedup_tol) sono trattati come
      un solo foro con svasatura: si prende SOLO il raggio minimo (foro
      passante = quello che il laser deve tagliare). La svasatura è
      lavorazione post-taglio, non contribuisce al perimetro di taglio.

    Returns:
        (perimetro_totale_mm, n_fori)
    """
    import ezdxf
    import math
    try:
        doc = ezdxf.readfile(path)
    except Exception:
        return (0.0, 0)
    circles_by_center: dict = {}
    for e in doc.modelspace():
        if e.dxftype() != 'CIRCLE':
            continue
        try:
            cx = float(e.dxf.center.x)
            cy = float(e.dxf.center.y)
            r = float(e.dxf.radius)
        except Exception:
            continue
        if r < min_r_mm or r > max_r_mm:
            continue
        # Chiave di clustering: centro arrotondato a dedup_tol
        key = (round(cx / dedup_tol_mm), round(cy / dedup_tol_mm))
        # Tieni solo il raggio più piccolo per cluster (passante)
        if key not in circles_by_center or r < circles_by_center[key]:
            circles_by_center[key] = r
    perim_tot = sum(2 * math.pi * r for r in circles_by_center.values())
    return (perim_tot, len(circles_by_center))


def estrai_dimensioni_da_descrizione_cartiglio(path: str) -> dict:
    """Fallback per DXF dove il detector non riesce a chiudere il contorno:
    cerca nel cartiglio una descrizione tipo "Lama di contenimento 45x12 sp.3"
    o "Piastra 100x50 sp.4" e ne ricava area/perimetro/spessore rettangolari.

    Perimetro di taglio: outer_rettangolo + perimetro dei fori interni
    (rilevati come CIRCLE con raggio commerciale plausibile).

    Usato per pezzi rettangolari semplici dove il DXF ha contorno rotto ma il
    testo del cartiglio è esplicito.

    Returns:
        {area_dm2, perimetro_taglio_m, spessore_mm, dim_x_mm, dim_y_mm,
         raw_text, confidence, n_forature, source='cartiglio_descrizione'}
        Oppure {area_dm2: None} se non trovato.
    """
    import re
    testi = _raccogli_testi_dxf(path)
    if not testi:
        return {'area_dm2': None, 'source': 'none'}

    # Pattern noti nelle descrizioni Lantek/cliente:
    # "45x12 sp.3", "100x50 sp 4mm", "45x12x3", "Ø10 sp.2" (circolare)
    RX_RECT_SP = re.compile(
        r'\b(\d{1,4})\s*[xX×]\s*(\d{1,4})\s+(?:sp\.?\s*)?(\d+[.,]?\d*)\s*(?:mm)?\b',
        re.IGNORECASE,
    )
    RX_RECT_ONLY = re.compile(
        r'\b(\d{1,4})\s*[xX×]\s*(\d{1,4})\s*(?:mm)?\b'
    )
    RX_INTERNAL_SP = re.compile(
        r'\bsp\.?\s*(\d+[.,]?\d*)\s*(?:mm)?\b', re.IGNORECASE
    )

    for x, y, t in testi:
        # Skip cartigli standard che potrebbero avere numeri incoerenti
        if len(t) > 200:
            continue
        m = RX_RECT_SP.search(t)
        if m:
            try:
                dx = float(m.group(1))
                dy = float(m.group(2))
                sp = float(m.group(3).replace(',', '.'))
                # Sanity: pezzo lamiera plausibile
                if 5 <= dx <= 3000 and 5 <= dy <= 3000 and 0.5 <= sp <= 30:
                    area_dm2 = (dx * dy) / 10000.0
                    perim_outer_mm = 2 * (dx + dy)
                    # Aggiungi perimetro dei fori interni (CIRCLE clusterizzati)
                    perim_fori_mm, n_fori = _somma_perim_fori_da_circle(path)
                    perim_totale_m = (perim_outer_mm + perim_fori_mm) / 1000.0
                    return {
                        'area_dm2': round(area_dm2, 4),
                        'perimetro_taglio_m': round(perim_totale_m, 4),
                        'spessore_mm': sp,
                        'dim_x_mm': dx, 'dim_y_mm': dy,
                        'raw_text': t,
                        'confidence': 0.85,
                        'n_forature': n_fori + 1,  # +1 per contorno esterno (1 pierce)
                        'source': 'cartiglio_descrizione',
                    }
            except (ValueError, AttributeError):
                continue

    # Secondo tentativo: dimensioni rettangolari separate dallo spessore
    # (es. "Piastra 100x50" in un TEXT + "Sp.: 3" in un altro)
    best_rect = None
    best_sp = None
    for x, y, t in testi:
        if len(t) > 200:
            continue
        m = RX_RECT_ONLY.search(t)
        if m and not best_rect:
            try:
                dx = float(m.group(1))
                dy = float(m.group(2))
                if 5 <= dx <= 3000 and 5 <= dy <= 3000:
                    best_rect = (dx, dy, t)
            except ValueError:
                continue
        m2 = RX_INTERNAL_SP.search(t)
        if m2 and not best_sp:
            try:
                sp = float(m2.group(1).replace(',', '.'))
                if 0.5 <= sp <= 30:
                    best_sp = sp
            except ValueError:
                continue
    if best_rect and best_sp:
        dx, dy, raw_t = best_rect
        area_dm2 = (dx * dy) / 10000.0
        perim_outer_mm = 2 * (dx + dy)
        perim_fori_mm, n_fori = _somma_perim_fori_da_circle(path)
        perim_totale_m = (perim_outer_mm + perim_fori_mm) / 1000.0
        return {
            'area_dm2': round(area_dm2, 4),
            'perimetro_taglio_m': round(perim_totale_m, 4),
            'spessore_mm': best_sp,
            'dim_x_mm': dx, 'dim_y_mm': dy,
            'raw_text': raw_t,
            'confidence': 0.65,
            'n_forature': n_fori + 1,
            'source': 'cartiglio_descrizione',
        }

    # Terzo tentativo: cartiglio "tabellare" con label separate spazialmente
    # (es. label "Lunghezza:" @ pos_A, valore numerico "280" @ pos_B).
    # Pattern usato dai cartigli Lantek/UNI standardizzati.
    result = _estrai_da_cartiglio_tabellare(testi, path)
    if result:
        return result

    return {'area_dm2': None, 'source': 'none'}


def _estrai_da_cartiglio_tabellare(testi: list, path: str) -> dict | None:
    """Cartiglio standardizzato: label 'Lunghezza:' 'Larghezza:' 'Sp./⌀:' con
    valore numerico nel TEXT più vicino. Il valore va cercato in un raggio
    di alcuni cm dalla label (non tutto il cartiglio).

    Guardrail:
    - Escludo revisioni (numeri a 2 cifre "00", "01" ecc. sono spesso rev.)
    - Range Lunghezza/Larghezza: 5-3000mm
    - Range Spessore: 0.5-30mm
    - Sanity check finale: se peso disponibile → verifica peso ≈ V × densità
    """
    import re
    import math

    def _num(s: str) -> float | None:
        m = re.match(r'^\s*(\d+[.,]?\d*)\s*(?:mm)?\s*$', s.strip())
        if not m:
            return None
        try:
            return float(m.group(1).replace(',', '.'))
        except ValueError:
            return None

    def _find_value(label_key: str, min_v: float, max_v: float,
                     max_dist_mm: float = 100.0) -> tuple[float, float] | None:
        """Trova il valore numerico più vicino alla label che è nel range plausibile."""
        label_pos = None
        for x, y, t in testi:
            if t.strip().lower().startswith(label_key):
                label_pos = (x, y)
                break
        if not label_pos:
            return None
        lx, ly = label_pos
        best = None
        best_dist = float('inf')
        for x, y, t in testi:
            if (x, y) == label_pos:
                continue
            v = _num(t)
            if v is None:
                continue
            if v < min_v or v > max_v:
                continue
            d = math.hypot(x - lx, y - ly)
            if d > max_dist_mm:
                continue
            if d < best_dist:
                best_dist = d
                best = (v, d)
        return best

    # Cerco valori con range di plausibilità stringenti (escludono revisioni,
    # anno, protocol number, ecc.)
    lunghezza = _find_value('lunghezza', min_v=5, max_v=3000)
    larghezza = _find_value('larghezza', min_v=5, max_v=3000)
    spessore = _find_value('sp.', min_v=0.5, max_v=30)  # 'sp./⌀:', 'sp.', 'sp:'
    if not spessore:
        spessore = _find_value('spessore', min_v=0.5, max_v=30)

    if not (lunghezza and larghezza and spessore):
        return None

    dx = lunghezza[0]
    dy = larghezza[0]
    sp = spessore[0]
    # Sanity semantico: per una lamiera, il rapporto lato-min/spessore
    # deve essere >= 3 (altrimenti sarebbe una barra/tondino, non lamiera).
    # Blocca match spuri tipo L=8mm W=8mm sp=2mm (ratio 4) che sembrano
    # cifre da campi vuoti (00, 8, 7...) invece che vere dimensioni.
    lato_min = min(dx, dy)
    if lato_min / sp < 3:
        return None
    area_dm2 = (dx * dy) / 10000.0
    perim_outer_mm = 2 * (dx + dy)
    perim_fori_mm, n_fori = _somma_perim_fori_da_circle(path)
    perim_totale_m = (perim_outer_mm + perim_fori_mm) / 1000.0

    # Confidence: dipende da distanza label→valore. Se distanza > 50mm,
    # confidence media (potrebbe essere fluke). Altrimenti alta.
    max_dist = max(lunghezza[1], larghezza[1], spessore[1])
    if max_dist < 30:
        conf = 0.80
    elif max_dist < 80:
        conf = 0.65
    else:
        conf = 0.50

    return {
        'area_dm2': round(area_dm2, 4),
        'perimetro_taglio_m': round(perim_totale_m, 4),
        'spessore_mm': sp,
        'dim_x_mm': dx, 'dim_y_mm': dy,
        'raw_text': f'Cartiglio tabellare: L={dx} W={dy} sp={sp}',
        'confidence': conf,
        'n_forature': n_fori + 1,
        'source': 'cartiglio_tabellare',
    }


def _try_llm_normalize(raw: str) -> dict | None:
    """Tenta normalizzazione via LLM. Se successo, ritorna dict compat.
    Se LLM non disponibile o fallisce, ritorna None."""
    try:
        from . import llm_material_normalizer
        if not llm_material_normalizer.is_available():
            return None
        mat = llm_material_normalizer.normalize_via_llm(raw)
        if mat:
            return {
                'materiale': mat,
                'materiale_raw': raw,
                'confidence': 0.75,  # confidence media: LLM ha risposto ma non è deterministico
                '_source': 'llm',
            }
    except Exception as e:
        logger.warning('LLM material fallback fallito: %s', e)
    return None


def _try_llm_fallback(testi: list, label_pos=None) -> dict:
    """Fallback quando non troviamo etichetta 'Materiale': chiediamo a LLM
    di analizzare tutti i TEXT ragionevoli. Usato solo se rules-based fallisce."""
    # Per ora restituiamo empty result — implementazione full richiede prompt
    # multi-text che è overhead senza copertura reale nei DXF cliente attuali
    return {'materiale': '', 'materiale_raw': '', 'confidence': 0.0}


def _raccogli_testi_dxf(path: str) -> list[tuple[float, float, str]]:
    """Raccoglie TEXT/MTEXT dal DXF con pulizia codici e coordinate.

    Returns lista di (x, y, testo_pulito).
    """
    import re
    try:
        doc = ezdxf.readfile(path)
    except Exception:
        return []
    testi = []
    for e in doc.modelspace():
        if e.dxftype() not in ('MTEXT', 'TEXT'):
            continue
        try:
            t = (e.dxf.text or '').strip()
            if not t:
                continue
            t_clean = re.sub(r'\\[A-Za-z][^;]*;', '', t)
            t_clean = re.sub(r'\{|\}', '', t_clean)
            t_clean = re.sub(r'\\U\+([0-9A-Fa-f]{4})', '', t_clean).strip()
            if not t_clean:
                continue
            x = float(e.dxf.insert.x)
            y = float(e.dxf.insert.y)
            testi.append((x, y, t_clean))
        except Exception:
            continue
    return testi


def estrai_peso_da_cartiglio(path: str) -> dict:
    """Estrae il peso in kg dal cartiglio del DXF.

    Pattern univoco "Peso kg", "Peso (kg)", "Weight kg", "Peso:" seguito
    da un numero (o numero vicino spazialmente se in TEXT separato).

    Returns:
        {peso_kg: float|None, peso_raw: str, confidence: 0..1,
         source: 'inline'|'label'|'none'}
    """
    import re
    import math as _math

    testi = _raccogli_testi_dxf(path)
    if not testi:
        return {'peso_kg': None, 'peso_raw': '', 'confidence': 0.0, 'source': 'none'}

    def _parse_num(s: str) -> float | None:
        s = s.strip().replace(',', '.')
        try:
            v = float(s)
            # Peso pezzo plausibile: 0.001 kg (1g) - 2000 kg
            if 0.001 <= v <= 2000.0:
                return v
        except ValueError:
            pass
        return None

    # --- 1. INLINE: "Peso Kg 0.34", "Peso: 0.34 kg", "Weight 12.5" ---
    RX_INLINE = re.compile(
        r'\b(?:peso|weight)\b\s*(?:\(?\s*kg\s*\)?)?\s*[:=]?\s*(\d+[.,]?\d*)\s*(?:kg)?\b',
        re.IGNORECASE,
    )
    for x, y, t in testi:
        m = RX_INLINE.search(t)
        if m:
            v = _parse_num(m.group(1))
            if v is not None:
                return {'peso_kg': v, 'peso_raw': t, 'confidence': 0.95, 'source': 'inline'}

    # --- 2. LABEL + numero vicino ---
    # Cerca TEXT che sia solo la label "Peso kg" / "Peso" / "Weight"
    LABEL_RX = re.compile(r'^\s*(?:peso|weight)\b\s*(?:\(?\s*kg\s*\)?)?[:=]?\s*$',
                          re.IGNORECASE)
    label_pos = None
    for x, y, t in testi:
        if LABEL_RX.match(t):
            label_pos = (x, y)
            break
    if label_pos:
        lx, ly = label_pos
        best = None
        best_dist = float('inf')
        NUM_ONLY_RX = re.compile(r'^\s*(\d+[.,]?\d*)\s*(?:kg)?\s*$', re.IGNORECASE)
        for x, y, t in testi:
            if (x, y) == label_pos:
                continue
            m = NUM_ONLY_RX.match(t)
            if not m:
                continue
            v = _parse_num(m.group(1))
            if v is None:
                continue
            d = _math.hypot(x - lx, y - ly)
            if d < best_dist:
                best_dist = d
                best = (v, t, d)
        if best:
            # Peso in cartiglio raramente lontano dalla label. Se dist > 50 unità
            # DXF, la confidence cala.
            conf = max(0.5, min(0.95, 1.0 - (best[2] / 200.0)))
            return {'peso_kg': best[0], 'peso_raw': best[1],
                    'confidence': round(conf, 2), 'source': 'label'}

    return {'peso_kg': None, 'peso_raw': '', 'confidence': 0.0, 'source': 'none'}


# Densità standard (kg/dm3) usate per stima spessore da peso+area.
# Aligned con laser_cost_estimator.DEFAULT_LASER_CONFIG['materiali'].
_DENSITA_STD = {
    'S235': 7.85, 'ZINCATO': 7.85, 'INOX_304': 8.00, 'INOX_316': 8.00,
    'ALU': 2.70, 'ALU_5754': 2.70, 'ALU_5083': 2.66, 'OTTONE': 8.50,
}


STD_SPESSORI_MM = [
    0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0,
    6.0, 8.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0
]


def stima_spessore_da_peso(peso_kg: float, area_dm2: float,
                            materiale: str) -> dict:
    """Calcola spessore da peso × area × densità del materiale.

    Formula: spessore_mm = peso_kg / (area_dm2 * densita_kg_dm3) * 100
    (area in dm², spessore in dm = mm/100)

    Include physics sanity check + warnings strutturati:
    - Verifica materiale coerente con densità (cross-material check)
    - Arrotondamento a valore commerciale standard più vicino
    - Warnings esposti in `warnings` per UI traffic-light

    Returns:
        {spessore_mm, confidence, source, peso_kg, area_dm2, densita,
         errore_std_pct, warnings, possibili_materiali}
        oppure risultato "none" se input non plausibili.
    """
    if not peso_kg or peso_kg <= 0 or not area_dm2 or area_dm2 <= 0:
        return {'spessore_mm': None, 'confidence': 0.0, 'source': 'none',
                'warnings': ['peso o area non validi']}
    mat_key = (materiale or '').strip().upper()
    densita = _DENSITA_STD.get(mat_key)
    if not densita:
        return {'spessore_mm': None, 'confidence': 0.0, 'source': 'none',
                'warnings': [f'materiale {materiale!r} non in tabella densità']}
    # spessore in dm = peso / (area * densita); convert to mm
    sp = (peso_kg / (area_dm2 * densita)) * 100.0
    warnings = []
    if sp <= 0 or sp > 60.0:
        # Physics sanity: spessore fuori range plausibile → materiale probabilmente
        # sbagliato. Provo con altri materiali per suggerire il corretto.
        suggested = _cross_material_suggest(peso_kg, area_dm2)
        return {
            'spessore_mm': None, 'confidence': 0.0, 'source': 'none',
            'warnings': [
                f'spessore calcolato {sp:.1f}mm fuori range plausibile (0.5-30mm)',
                *([f'materiale probabilmente {suggested}, non {mat_key}'] if suggested else []),
            ],
            'possibili_materiali': suggested,
        }
    # Arrotonda ai valori commerciali standard più vicini
    nearest = min(STD_SPESSORI_MM, key=lambda s: abs(s - sp))
    err_pct = abs(nearest - sp) / nearest * 100
    # Confidence in base a errore vs valore commerciale
    if err_pct < 5:
        conf = 0.95
    elif err_pct < 15:
        conf = 0.80
        warnings.append(f'spessore calcolato {sp:.2f}mm → arrotondato a {nearest}mm (err {err_pct:.0f}%)')
    else:
        conf = 0.55
        warnings.append(
            f'spessore calcolato {sp:.2f}mm dista {err_pct:.0f}% dal valore commerciale {nearest}mm — verificare materiale o peso'
        )
        # Cross-material check: c'è un altro materiale che spiega meglio il peso?
        suggested = _cross_material_suggest(peso_kg, area_dm2, exclude=mat_key)
        if suggested:
            warnings.append(f'materiale potrebbe essere {suggested} invece di {mat_key}')

    return {
        'spessore_mm': round(nearest, 2),
        'spessore_calc_raw': round(sp, 3),
        'confidence': conf,
        'source': 'peso_area',
        'peso_kg': peso_kg,
        'area_dm2': area_dm2,
        'densita': densita,
        'errore_std_pct': round(err_pct, 1),
        'warnings': warnings,
    }


def _cross_material_suggest(peso_kg: float, area_dm2: float,
                             exclude: str = '') -> str | None:
    """Physics sanity: quale materiale (tra i 5 noti) spiega meglio il peso
    dato, assumendo che lo spessore sia un valore commerciale standard?

    Uso: se il calcolo con materiale scelto dà spessore assurdo, controllo
    se un altro materiale porta a uno spessore commerciale plausibile.
    Restituisce il codice del miglior candidato oppure None.
    """
    if not peso_kg or peso_kg <= 0 or not area_dm2 or area_dm2 <= 0:
        return None
    exclude_upper = (exclude or '').upper()
    best_score = float('inf')
    best_mat = None
    for mat, densita in _DENSITA_STD.items():
        if mat == exclude_upper:
            continue
        sp = (peso_kg / (area_dm2 * densita)) * 100.0
        if sp <= 0 or sp > 30.0:
            continue
        nearest = min(STD_SPESSORI_MM, key=lambda s: abs(s - sp))
        err = abs(nearest - sp) / nearest * 100.0
        # Score = err% (più basso = migliore match con valore commerciale)
        if err < best_score and err < 10.0:  # solo se plausibile
            best_score = err
            best_mat = mat
    return best_mat


def estrai_spessore_da_cartiglio(path: str, area_dm2: float | None = None,
                                  materiale: str | None = None) -> dict:
    """Estrae/calcola lo spessore lamiera con la migliore strategia disponibile.

    Priorità:
    1. PESO + AREA + MATERIALE → calcolo fisico (più affidabile).
       Il peso si estrae dal cartiglio con pattern univoco "Peso kg".
    2. Fallback: nome file (`_sp3`, `_10mm`).

    Non usa più la ricerca "Sp." nel testo perché è troppo ambigua
    (matcha smussi, tolleranze, quote): dava risultati sbagliati sui 7 DXF
    del cliente.

    Returns:
        {spessore_mm: float|None, confidence: 0..1,
         source: 'peso_area'|'filename'|'none',
         details: dict con peso_kg, densita, errore_std_pct, ecc. per debug UI}
    """
    peso_info = estrai_peso_da_cartiglio(path)
    peso = peso_info.get('peso_kg')

    if peso and area_dm2 and materiale:
        sp_info = stima_spessore_da_peso(peso, area_dm2, materiale)
        if sp_info.get('spessore_mm'):
            # Confidence finale = min(peso, calc) — se peso incerto abbassa
            conf = min(peso_info['confidence'], sp_info['confidence'])
            return {
                'spessore_mm': sp_info['spessore_mm'],
                'confidence': round(conf, 2),
                'source': 'peso_area',
                'warnings': sp_info.get('warnings', []),  # esposto per UI traffic-light
                'details': {
                    'peso_kg': peso,
                    'peso_source': peso_info['source'],
                    'peso_raw': peso_info['peso_raw'],
                    'area_dm2': area_dm2,
                    'materiale': materiale,
                    'densita_kg_dm3': sp_info['densita'],
                    'spessore_calc_raw': sp_info['spessore_calc_raw'],
                    'errore_std_pct': sp_info['errore_std_pct'],
                },
            }
        # Se stima non è riuscita, propago i warning (es. cross-material suggest)
        if sp_info.get('warnings'):
            return {
                'spessore_mm': None, 'confidence': 0.0, 'source': 'none',
                'warnings': sp_info['warnings'],
                'details': {
                    'peso_kg': peso, 'area_dm2': area_dm2, 'materiale': materiale,
                    'possibili_materiali': sp_info.get('possibili_materiali'),
                },
            }

    # Fallback su filename
    return _spessore_from_filename(path)


def _spessore_from_filename(path: str) -> dict:
    """Cerca spessore nel nome file: '_sp3', '_10mm', 'sp.3', 'sp3.0'."""
    import re
    import os
    name = os.path.basename(path)
    patterns = [
        re.compile(r'[_\-\s]sp\.?[_\-\s]?(\d+[.,]?\d*)\s*(?:mm)?', re.IGNORECASE),
        re.compile(r'[_\-\s](\d+[.,]?\d*)\s*mm(?=[_\-\.]|$)', re.IGNORECASE),
    ]
    for rx in patterns:
        m = rx.search(name)
        if m:
            try:
                v = float(m.group(1).replace(',', '.'))
                if 0.3 <= v <= 30.0:
                    return {'spessore_mm': v, 'confidence': 0.75,
                            'source': 'filename', 'details': {'raw': m.group(0)}}
            except ValueError:
                pass
    return {'spessore_mm': None, 'confidence': 0.0,
            'source': 'none', 'details': {}}


def dxf_to_svg_string(path: str) -> str:
    """Converte un DXF in stringa SVG ad alta fedeltà via ezdxf SVGBackend.

    Rendering completo: colori, spessori, archi, spline, polyline complesse —
    qualunque entità DXF supportata dal `Frontend` di ezdxf viene riprodotta
    fedelmente. Usato dalla preview interattiva in `preview-dxf.html`.

    Il viewBox del SVG risultante è impostato a partire dal bbox reale del DXF,
    così che il frontend possa fare screen→DXF con una semplice trasformazione
    affine (viewBox coord = mm DXF, a meno del flip Y-up→Y-down).
    """
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.svg import SVGBackend
    from ezdxf.addons.drawing import layout
    from ezdxf.bbox import extents

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    backend = SVGBackend()
    ctx = RenderContext(doc)
    frontend = Frontend(ctx, backend)
    frontend.draw_layout(msp)

    # Passiamo dimensioni pagina esatte in mm (senza margini) così il viewBox
    # SVG mappa 1:1 alla bbox DXF. Se il bbox non è disponibile (DXF vuoto),
    # fallback a layout auto (Page(0,0)).
    try:
        bb = extents(msp)
        if bb.has_data:
            w_mm = float(bb.extmax.x - bb.extmin.x)
            h_mm = float(bb.extmax.y - bb.extmin.y)
            if w_mm > 0 and h_mm > 0:
                page = layout.Page(
                    w_mm, h_mm,
                    units=layout.Units.mm,
                    margins=layout.Margins.all(0),
                )
                return backend.get_string(page)
    except Exception:
        pass
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
