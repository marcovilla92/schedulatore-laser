"""STEP file tubular structure analysis.

Detects CHS (Circular Hollow Sections), RHS (Rectangular Hollow Sections),
and SHS (Square Hollow Sections) from STEP geometry.
"""

import json
import logging
import math
import os
import re

logger = logging.getLogger(__name__)


def carica_profili_tubolari(base_dir: str) -> dict:
    """Carica database profili tubolari da profili_tubolari.json.

    Args:
        base_dir: Directory base dove cercare il file profili_tubolari.json.

    Returns:
        dict con chiavi 'CHS', 'SHS', 'RHS', ciascuna con lista di profili.
    """
    profili_path = os.path.join(base_dir, "profili_tubolari.json")
    try:
        with open(profili_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"CHS": [], "SHS": [], "RHS": []}


def match_profilo_chs(d_ext, spessore, profili_db) -> dict | None:
    """Trova il profilo CHS piu' vicino nel database. Tolleranza +/-1.5mm su diametro.

    Args:
        d_ext: Diametro esterno in mm.
        spessore: Spessore parete in mm.
        profili_db: Database profili (da carica_profili_tubolari).

    Returns:
        dict del profilo matchato o None.
    """
    best = None
    best_dist = 999
    for p in profili_db.get("CHS", []):
        dist_d = abs(p["d_ext"] - d_ext)
        dist_s = abs(p["spessore"] - spessore) if spessore else 0
        dist = dist_d + dist_s * 2
        if dist < best_dist and dist_d < 1.5:
            best_dist = dist
            best = p
    return best


def match_profilo_rhs(lato_a, lato_b, spessore, profili_db) -> dict | None:
    """Trova il profilo RHS/SHS piu' vicino. Tolleranza +/-2mm.

    Args:
        lato_a: Dimensione lato A in mm.
        lato_b: Dimensione lato B in mm.
        spessore: Spessore parete in mm.
        profili_db: Database profili (da carica_profili_tubolari).

    Returns:
        dict del profilo matchato o None.
    """
    a, b = max(lato_a, lato_b), min(lato_a, lato_b)
    best = None
    best_dist = 999
    search_types = ["SHS", "RHS"] if abs(a - b) < 2.0 else ["RHS", "SHS"]
    for tipo in search_types:
        for p in profili_db.get(tipo, []):
            pa, pb = max(p["lato_a"], p["lato_b"]), min(p["lato_a"], p["lato_b"])
            dist_a = abs(pa - a)
            dist_b = abs(pb - b)
            dist_s = abs(p["spessore"] - spessore) if spessore else 0
            dist = dist_a + dist_b + dist_s * 2
            if dist < best_dist and dist_a < 2.0 and dist_b < 2.0:
                best_dist = dist
                best = p
    return best


def analizza_step_tubolari(step_path: str, profili_db: dict, debug: bool = False) -> dict:
    """Analizza file STEP per rilevare strutture tubolari (CHS, RHS, SHS).

    Per ogni CLOSED_SHELL/MANIFOLD_SOLID_BREP analizza i tipi di superficie:
    - CYLINDRICAL_SURFACE -> possibile CHS
    - PLANE -> possibile RHS/SHS o tappo estremita'

    Args:
        step_path: Path al file STEP.
        profili_db: Database profili tubolari (da carica_profili_tubolari).
        debug: Se True, logga dettagli diagnostici su classificazione candidati.

    Returns:
        dict con 'tubi', 'peso_totale_kg', 'n_tagli_dritti/obliqui/sagomati', 'errore'
    """
    try:
        with open(step_path, 'r', errors='replace') as f:
            content = f.read()
    except (IOError, OSError) as e:
        return {'tubi': [], 'peso_totale_kg': 0, 'n_tagli_dritti': 0,
                'n_tagli_obliqui': 0, 'n_tagli_sagomati': 0, 'errore': str(e)}

    entities = {}
    for m in re.finditer(r'#(\d+)\s*=\s*(.+?)\s*;', content, re.DOTALL):
        entities[int(m.group(1))] = m.group(2).strip()

    def _etype(val):
        m2 = re.match(r'(\w+)', val)
        return m2.group(1) if m2 else ''

    def _refs(val):
        return [int(x) for x in re.findall(r'#(\d+)', val)]

    def _coords(val):
        nums = re.findall(r'([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)', val)
        floats = [float(x) for x in nums]
        return tuple(floats[-3:]) if len(floats) >= 3 else None

    def _vec_dot(a, b):
        return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

    def _vec_len(a):
        return math.sqrt(a[0]**2 + a[1]**2 + a[2]**2)

    def _vec_norm(a):
        ln = _vec_len(a)
        return (a[0]/ln, a[1]/ln, a[2]/ln) if ln > 1e-12 else (0, 0, 0)

    def _last_float(val):
        nums = re.findall(r'([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)', val)
        return float(nums[-1]) if nums else 0.0

    # --- Trova tutti i body ---
    body_ids = [eid for eid, val in entities.items()
                if _etype(val) == 'MANIFOLD_SOLID_BREP']
    msb_child_shells = set()
    for bid in body_ids:
        for r in _refs(entities.get(bid, '')):
            msb_child_shells.add(r)
    for eid, val in entities.items():
        if _etype(val) == 'CLOSED_SHELL' and eid not in msb_child_shells:
            body_ids.append(eid)

    if not body_ids:
        return {'tubi': [], 'peso_totale_kg': 0, 'n_tagli_dritti': 0,
                'n_tagli_obliqui': 0, 'n_tagli_sagomati': 0,
                'errore': 'Nessun corpo solido trovato'}

    def _get_face_refs(bid):
        val = entities.get(bid, '')
        etype = _etype(val)
        refs_list = _refs(val)
        if not refs_list:
            return []
        if etype == 'MANIFOLD_SOLID_BREP':
            return _refs(entities.get(refs_list[-1], ''))
        elif etype in ('CLOSED_SHELL', 'OPEN_SHELL'):
            return refs_list
        else:
            return _refs(entities.get(refs_list[-1], ''))

    def _get_surface_info(face_ref):
        fval = entities.get(face_ref, '')
        if _etype(fval) != 'ADVANCED_FACE':
            return None, {}
        frefs = _refs(fval)
        if not frefs:
            return None, {}
        surf_ref = frefs[-1]
        surf_val = entities.get(surf_ref, '')
        surf_type = _etype(surf_val)

        if surf_type == 'CYLINDRICAL_SURFACE':
            radius = _last_float(surf_val)
            srefs = _refs(surf_val)
            axis_data = {}
            if srefs:
                ax_val = entities.get(srefs[0], '')
                ax_refs = _refs(ax_val)
                if len(ax_refs) >= 2:
                    origin = _coords(entities.get(ax_refs[0], ''))
                    axis_dir = _coords(entities.get(ax_refs[1], ''))
                    if origin and axis_dir:
                        axis_data = {'origin': origin, 'axis': axis_dir}
            return 'CYL', {'raggio': radius, **axis_data}

        elif surf_type == 'PLANE':
            srefs = _refs(surf_val)
            if srefs:
                ax_val = entities.get(srefs[0], '')
                ax_refs = _refs(ax_val)
                if len(ax_refs) >= 2:
                    origin = _coords(entities.get(ax_refs[0], ''))
                    normal = _coords(entities.get(ax_refs[1], ''))
                    if origin and normal:
                        return 'PLANE', {'origin': origin, 'normal': normal}
            return 'PLANE', {}

        elif surf_type == 'CONICAL_SURFACE':
            return 'CONE', {}
        elif surf_type == 'TOROIDAL_SURFACE':
            return 'TORUS', {}
        elif surf_type == 'B_SPLINE_SURFACE_WITH_KNOTS':
            return 'BSPLINE', {}
        else:
            return surf_type, {}

    def _collect_body_vertices(face_refs):
        """Raccoglie i vertici cartesiani veri del body (via FACE→LOOP→EDGE→VERTEX)."""
        verts = []
        seen_pts = set()
        for fref in face_refs:
            fval = entities.get(fref, '')
            if _etype(fval) != 'ADVANCED_FACE':
                continue
            for bref in _refs(fval):
                bval = entities.get(bref, '')
                if _etype(bval) not in ('FACE_OUTER_BOUND', 'FACE_BOUND'):
                    continue
                el_refs = _refs(bval)
                if not el_refs:
                    continue
                el_val = entities.get(el_refs[0], '')
                if _etype(el_val) != 'EDGE_LOOP':
                    continue
                for oe_ref in _refs(el_val):
                    oe_val = entities.get(oe_ref, '')
                    if _etype(oe_val) != 'ORIENTED_EDGE':
                        continue
                    ec_refs = _refs(oe_val)
                    if not ec_refs:
                        continue
                    ec_val = entities.get(ec_refs[-1], '')
                    if _etype(ec_val) != 'EDGE_CURVE':
                        continue
                    for vref in _refs(ec_val)[:2]:
                        vval = entities.get(vref, '')
                        if _etype(vval) != 'VERTEX_POINT':
                            continue
                        vrefs = _refs(vval)
                        if not vrefs:
                            continue
                        pt = _coords(entities.get(vrefs[0], ''))
                        if pt and pt not in seen_pts:
                            seen_pts.add(pt)
                            verts.append(pt)
        return verts

    # --- Analizza ogni body ---
    tubi_rilevati = []

    for bid in body_ids:
        face_refs = _get_face_refs(bid)
        if not face_refs:
            continue

        surfaces = []
        for fref in face_refs:
            stype, sdata = _get_surface_info(fref)
            if stype:
                surfaces.append((stype, sdata, fref))

        n_cyl = sum(1 for s in surfaces if s[0] == 'CYL')
        n_plane = sum(1 for s in surfaces if s[0] == 'PLANE')
        n_total = len(surfaces)

        if n_total == 0:
            continue

        # Raccogli raggi cilindri
        cyl_radii = {}
        for s in surfaces:
            if s[0] == 'CYL':
                r = round(s[1].get('raggio', 0), 2)
                if r > 0:
                    cyl_radii.setdefault(r, []).append(s)

        # Raccogli piani con normali
        planes_with_data = [(s[1]['origin'], _vec_norm(s[1]['normal']))
                            for s in surfaces
                            if s[0] == 'PLANE' and 'origin' in s[1] and 'normal' in s[1]]

        # === RHS/SHS: >=6 piani + opzionali cilindri piccoli (raccordi) ===
        # Soglia big_cyl alzata da 15 a 30mm: alcuni tubolari RHS hanno raccordi
        # interni con raggio 15-25mm (es. curve fresate), prima venivano esclusi
        # erroneamente dal ramo RHS perché considerati "big_cyl".
        detected_rhs = False
        if n_plane >= 6:
            big_cyl = [r for r in cyl_radii.keys() if r > 30.0]
            if not big_cyl and planes_with_data and len(planes_with_data) >= 6:
                # Step 1: raggruppo TUTTI i piani per normali parallele per trovare
                # l'asse principale (dimensione massima → asse tubo)
                normal_groups = {}
                for origin, normal in planes_with_data:
                    matched = False
                    for gk, gplanes in normal_groups.items():
                        ref_n = gplanes[0][1]
                        dot = abs(_vec_dot(normal, ref_n))
                        if dot > 0.95:
                            normal_groups[gk].append((origin, normal))
                            matched = True
                            break
                    if not matched:
                        normal_groups[len(normal_groups)] = [(origin, normal)]

                if len(normal_groups) >= 3:
                    # FIX Bug A+D: trova l'asse tubo come direzione con la MASSIMA
                    # extent di TUTTI i piani (non solo quelli paralleli tra loro).
                    # Risolve i tubi con tagli obliqui: in quel caso non esiste un
                    # gruppo di 2 piani paralleli lungo l'asse (un tappo è dritto,
                    # l'altro obliquo, o entrambi obliqui) — quindi la vecchia logica
                    # sceglieva erroneamente un lato della sezione come "asse".
                    #
                    # Candidates: (1) normali dei gruppi con >= 2 piani (evita che
                    # una singola smussa obliqua spuria venga scelta come asse);
                    # (2) i 3 assi cardinali come fallback (copre il caso in cui
                    # entrambe le testate sono oblique → nessun gruppo assiale dritto,
                    # ma il tubo è comunque allineato a X/Y/Z nel frame STEP).
                    candidate_normals = []
                    seen_dirs = []
                    for gk, gplanes in normal_groups.items():
                        if len(gplanes) < 2:
                            continue
                        nref = _vec_norm(gplanes[0][1])
                        candidate_normals.append(nref)
                        seen_dirs.append(nref)
                    for cardinal in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
                        # Aggiungo solo se non già presente (quasi parallelo a uno dei gruppi)
                        already = any(abs(_vec_dot(cardinal, d)) > 0.98 for d in seen_dirs)
                        if not already:
                            candidate_normals.append(cardinal)
                            seen_dirs.append(cardinal)

                    # Fix v14: calcolo extent dai VERTICI veri del body, non dalle
                    # AXIS2_PLACEMENT_3D.location dei piani. Le location STEP sono
                    # frame origin arbitrari (non centroidi/punti del piano), e per
                    # tubi modellati via CSG/Boolean possono cadere ovunque nello
                    # spazio. Risultato: su spezzoni corti l'extent calcolato dalle
                    # location era patologico (es. 1819mm su un tubo 40x40x140mm),
                    # facendo scegliere come asse una direzione laterale invece
                    # della lunghezza vera.
                    body_verts = _collect_body_vertices(face_refs)
                    candidates = []
                    for ref_normal in candidate_normals:
                        if body_verts:
                            projs = [_vec_dot(v, ref_normal) for v in body_verts]
                        else:
                            projs = [_vec_dot(origin, ref_normal)
                                     for origin, _ in planes_with_data]
                        extent = max(projs) - min(projs)
                        candidates.append((extent, ref_normal, None))

                    # Calcolo group_dims (dim del gruppo stesso) per compatibilità
                    # con logica downstream (side calculations, debug old vs new)
                    group_dims = []
                    for gk, gplanes in normal_groups.items():
                        if len(gplanes) < 2:
                            continue
                        ref_normal = _vec_norm(gplanes[0][1])
                        projs = [_vec_dot(p[0], ref_normal) for p in gplanes]
                        dim = max(projs) - min(projs)
                        group_dims.append((dim, ref_normal, gk))

                    if candidates and len(group_dims) >= 2:
                        candidates.sort(key=lambda x: x[0], reverse=True)
                        group_dims.sort(key=lambda x: x[0], reverse=True)
                        # Asse = direzione con extent totale max
                        lunghezza_mm = candidates[0][0]
                        axis_normal = candidates[0][1]

                        # Fix v14b: per tubi obliqui (cap planes inclinati di 8-30°
                        # rispetto al perpendicolare-asse), il candidate con extent
                        # max e' la cardinale dominante (X o Y), NON l'asse vero del
                        # tubo. L'asse vero e' perpendicolare ai 2 side groups con
                        # >=4 piani (i 2 lati chiusi della sezione). Se questi 2
                        # side groups esistono e sono quasi-ortogonali, calcolo
                        # l'asse come cross product delle loro normali.
                        side_normals_4 = [
                            _vec_norm(gplanes[0][1])
                            for gplanes in normal_groups.values()
                            if len(gplanes) >= 4
                        ]
                        if len(side_normals_4) >= 2:
                            n1, n2 = side_normals_4[0], side_normals_4[1]
                            if abs(_vec_dot(n1, n2)) < 0.2:
                                # cross product
                                cross = (
                                    n1[1] * n2[2] - n1[2] * n2[1],
                                    n1[2] * n2[0] - n1[0] * n2[2],
                                    n1[0] * n2[1] - n1[1] * n2[0],
                                )
                                cross_n = _vec_norm(cross)
                                if body_verts:
                                    projs_a = [_vec_dot(v, cross_n) for v in body_verts]
                                    new_len = max(projs_a) - min(projs_a)
                                    if new_len > 50:
                                        axis_normal = cross_n
                                        lunghezza_mm = new_len


                        # Step 2: separo i piani in axis-aligned (cap, paralleli all'asse tubo)
                        # vs side (perpendicolari, definiscono la sezione) vs obliqui (smussi/tagli).
                        # Soglie:
                        # - axis (dritto): dot > 0.995 (< 5.7° dall'asse)
                        # - side (sezione): dot < 0.5 (> 60° dall'asse) — più permissivo
                        #   per catturare side con leggera imperfezione. Serve a
                        #   non perdere tubi 60x60/100x60 quando la sezione ha
                        #   minimo di inclinazione.
                        # - oblique (taglio a gradi): 0.5 <= dot <= 0.995
                        axis_planes = []
                        side_planes = []
                        oblique_planes = []
                        for origin, normal in planes_with_data:
                            dot_axis = abs(_vec_dot(_vec_norm(normal), axis_normal))
                            if dot_axis > 0.995:
                                axis_planes.append((origin, normal, dot_axis))
                            elif dot_axis < 0.5:
                                side_planes.append((origin, normal))
                            else:
                                oblique_planes.append((origin, normal, dot_axis))

                        # Step 3: ricalcolo dim_a, dim_b usando SOLO i side planes
                        side_groups = {}
                        for origin, normal in side_planes:
                            matched = False
                            for gk, gplanes in side_groups.items():
                                ref_n = gplanes[0][1]
                                if abs(_vec_dot(_vec_norm(normal), _vec_norm(ref_n))) > 0.95:
                                    side_groups[gk].append((origin, normal))
                                    matched = True
                                    break
                            if not matched:
                                side_groups[len(side_groups)] = [(origin, normal)]
                        side_dims = []
                        for gk, gplanes in side_groups.items():
                            if len(gplanes) < 2:
                                continue
                            ref_normal = _vec_norm(gplanes[0][1])
                            projs = [_vec_dot(p[0], ref_normal) for p in gplanes]
                            side_dims.append(max(projs) - min(projs))
                        side_dims.sort(reverse=True)
                        if len(side_dims) >= 2:
                            dim_a = side_dims[0]
                            dim_b = side_dims[1]
                        else:
                            # Fallback se i side planes non sono sufficienti
                            dim_a = group_dims[1][0] if len(group_dims) >= 2 else 0
                            dim_b = group_dims[2][0] if len(group_dims) >= 3 else 0

                        # FIX lunghezza dai soli piani di testa del tubo (v12).
                        # Prima: lunghezza = extent di TUTTI i piani lungo l'asse.
                        # Problema: se il CAD fonde tubo + piastra di tappo saldata in
                        # un singolo solido, l'extent include la piastra → lunghezza
                        # sovrastimata di 20-60mm.
                        #
                        # Ora: lunghezza = extent SOLO dei piani di testa (axis + oblique
                        # con correzione geometrica). Per un obliquo, il centroide del
                        # piano è al centro del taglio; l'estensione assiale del piano
                        # è L/2·tan(α), da aggiungere ai 2 estremi del centroide.
                        if axis_planes or oblique_planes:
                            max_sec = max(dim_a, dim_b) if max(dim_a, dim_b) > 0 else 1.0
                            terminal_projs = []
                            for origin, normal, dot_a in axis_planes:
                                p = _vec_dot(origin, axis_normal)
                                terminal_projs.append(p)
                            for origin, normal, dot_a in oblique_planes:
                                p = _vec_dot(origin, axis_normal)
                                cos_a = abs(dot_a)
                                if cos_a > 1e-6:
                                    sin_a = math.sqrt(max(0.0, 1.0 - cos_a * cos_a))
                                    tan_a = sin_a / cos_a
                                    ext = max_sec * 0.5 * tan_a
                                else:
                                    ext = 0.0
                                terminal_projs.append(p - ext)
                                terminal_projs.append(p + ext)
                            if terminal_projs:
                                lunghezza_tubo_mm = max(terminal_projs) - min(terminal_projs)
                                # Usa questa come lunghezza ufficiale (prima era extent globale)
                                lunghezza_mm = lunghezza_tubo_mm

                        if debug:
                            old_a = group_dims[1][0] if len(group_dims) >= 2 else -1
                            old_b = group_dims[2][0] if len(group_dims) >= 3 else -1
                            logger.info(
                                "[TUBE bid=%s] n_planes=%d axis=%d side=%d oblique=%d | "
                                "len=%.1f dim_a=%.1f dim_b=%.1f (old: %.1f/%.1f)",
                                bid, len(planes_with_data), len(axis_planes),
                                len(side_planes), len(oblique_planes),
                                lunghezza_mm, dim_a, dim_b, old_a, old_b,
                            )

                        # Filtro: la lunghezza deve essere almeno 3x la sezione per
                        # distinguere tubi da piastre/gusset. Per spezzoni corti che
                        # matchano un profilo standard nel DB, accettiamo anche
                        # elongation >= 1.2 (tubo tagliato a misura breve).
                        elongation = lunghezza_mm / max(dim_a, dim_b, 1.0)
                        # Pre-check: il profilo matcha il database? (guardia contro
                        # piastre/gusset che hanno sezione non-standard)
                        _pre_lato_a = round(dim_a, 1)
                        _pre_lato_b = round(dim_b, 1)
                        _profilo_match = match_profilo_rhs(_pre_lato_a, _pre_lato_b, 2.0, profili_db)
                        _min_elongation = 1.2 if _profilo_match else 3.0

                        # Fix Bug E: rifiuto sezioni sospette che non matchano DB.
                        # Il match DB ha già tolleranza ±2mm su ciascun lato, quindi
                        # è affidabile. Se la sezione calcolata NON corrisponde a
                        # nessun profilo del database, è molto probabile che si
                        # tratti di una piastra/lamiera/gusset, non un tubo.
                        # Esempi falsi positivi bloccati: 140x40, 110x40, 100x25,
                        # 50x50, 70x60, 54x10 (ciascuno era presente nel log v6).
                        if not _profilo_match:
                            if debug:
                                logger.info(
                                    "[TUBE bid=%s] SKIP no match DB: %sx%s (possibile piastra/lamiera)",
                                    bid, _pre_lato_a, _pre_lato_b,
                                )
                            continue

                        # Fix Bug falsi positivi v12: verifica topologia da tubo cavo CHIUSO.
                        # Un tubo cavo rettangolare chiuso su 4 lati deve avere:
                        #   (a) almeno 2 piani di testa (axis o oblique) — piastre e
                        #       profili aperti (L, C, U) ne hanno 0-1
                        #   (b) ALMENO 2 side_groups, CIASCUNO con >= 4 piani (4
                        #       paralleli = 2 esterni + 2 interni, lato chiuso).
                        #       Una lamiera piegata a U ha solo 1 gruppo con 4 piani;
                        #       il fondo ha solo 2 piani (esterno+interno singolo).
                        cap_count = len(axis_planes) + len(oblique_planes)
                        closed_side_groups = [
                            g for g in side_groups.values() if len(g) >= 4
                        ]
                        if cap_count < 2:
                            if debug:
                                logger.info(
                                    "[TUBE bid=%s] SKIP topologia: cap_count=%d<2 "
                                    "(profilo aperto L/C/U o piastra)",
                                    bid, cap_count,
                                )
                            continue
                        if len(closed_side_groups) < 2:
                            if debug:
                                side_sizes = [len(g) for g in side_groups.values()]
                                logger.info(
                                    "[TUBE bid=%s] SKIP topologia: side_groups_sizes=%s "
                                    "(lamiera piegata U/C o profilo non chiuso)",
                                    bid, sorted(side_sizes, reverse=True),
                                )
                            continue

                        if lunghezza_mm >= 50 and dim_a >= 10 and dim_b >= 10 and elongation >= _min_elongation:
                            ratio_sezione = max(dim_a, dim_b) / max(min(dim_a, dim_b), 0.1)
                            if ratio_sezione <= 5.0:
                                # v14: spessore calcolato dai gap consecutivi tra
                                # proiezioni dei VERTICI body sulla normale del lato.
                                # I gap tra le AXIS2_PLACEMENT_3D.location dei piani
                                # erano falsati dai frame-origin arbitrari (stesso
                                # bug del calcolo asse). Per un tubo 40x40 sp.2 i
                                # vertici proiettati sulla normale di un lato cadono
                                # in 4 cluster (-20/-18/+18/+20), gap 2mm = spessore.
                                spessore = None
                                all_small_gaps = []
                                for gk, gplanes in side_groups.items():
                                    if len(gplanes) >= 4:
                                        ref_normal = _vec_norm(gplanes[0][1])
                                        if body_verts:
                                            vp = sorted({round(_vec_dot(v, ref_normal), 2)
                                                         for v in body_verts})
                                        else:
                                            vp = sorted([_vec_dot(p[0], ref_normal)
                                                         for p in gplanes])
                                        gaps = [vp[i+1] - vp[i] for i in range(len(vp)-1)]
                                        group_gaps = [g for g in gaps if 1.5 < g < 10.0]
                                        all_small_gaps.extend(group_gaps)
                                if all_small_gaps:
                                    all_small_gaps.sort()
                                    # Mediana
                                    mid = len(all_small_gaps) // 2
                                    spessore = round(all_small_gaps[mid], 1)

                                lunghezza_m = round(lunghezza_mm / 1000.0, 3)
                                lato_a = round(dim_a, 1)
                                lato_b = round(dim_b, 1)

                                # Step 4: classifica i tagli.
                                # Logica semplice: se ci sono oblique_planes, almeno un taglio è
                                # obliquo. Assegno l'obliquo a taglio_1 o taglio_2 in base alla
                                # proiezione lungo l'asse (metà bassa o metà alta del tubo).
                                taglio_1, taglio_2 = "dritto", "dritto"
                                # v16: angolo numerico in gradi (inclinazione cap rispetto
                                # al perpendicolare-asse). 0° = dritto, N° = obliquo di N°.
                                angolo_taglio_1, angolo_taglio_2 = 0.0, 0.0

                                # Midpoint per assegnare ogni piano cap a testata 1 o 2
                                all_cap_projs = []
                                for origin, _, _ in axis_planes:
                                    all_cap_projs.append(_vec_dot(origin, axis_normal))
                                for origin, _, _ in oblique_planes:
                                    all_cap_projs.append(_vec_dot(origin, axis_normal))
                                axis_mid = (min(all_cap_projs) + max(all_cap_projs)) / 2.0 if all_cap_projs else 0.0

                                # Calcola angolo per ogni cap: angolo = acos(|dot(normal, axis)|)
                                # Per axis_planes (dot > 0.995) angolo ~ 0°, per oblique progressivo.
                                def _cap_angle_deg(normal):
                                    d = abs(_vec_dot(_vec_norm(normal), axis_normal))
                                    d = max(-1.0, min(1.0, d))
                                    return round(math.degrees(math.acos(d)), 1)

                                ang_side1, ang_side2 = [], []
                                for origin, normal, _ in axis_planes + oblique_planes:
                                    proj = _vec_dot(origin, axis_normal)
                                    a = _cap_angle_deg(normal)
                                    if proj < axis_mid:
                                        ang_side1.append(a)
                                    else:
                                        ang_side2.append(a)
                                # Per ogni testata, prendo l'angolo MAX dei piani cap (cap dominante)
                                if ang_side1:
                                    angolo_taglio_1 = max(ang_side1)
                                    if angolo_taglio_1 > 2.0:
                                        taglio_1 = "obliquo"
                                if ang_side2:
                                    angolo_taglio_2 = max(ang_side2)
                                    if angolo_taglio_2 > 2.0:
                                        taglio_2 = "obliquo"

                                profilo = match_profilo_rhs(lato_a, lato_b, spessore or 2.0, profili_db)
                                if profilo:
                                    nome_profilo = profilo["nome"]
                                    peso_kg_m = profilo["peso_kg_m"]
                                    tipo = "SHS" if "Quadro" in profilo["nome"] else "RHS"
                                else:
                                    tipo = "SHS" if abs(lato_a - lato_b) < 2.0 else "RHS"
                                    tipo_label = "Quadro" if tipo == "SHS" else "Rett."
                                    nome_profilo = f"{tipo_label} {lato_a}x{lato_b} sp.{spessore or '?'}mm"
                                    peso_kg_m = 0.0

                                peso_kg = round(peso_kg_m * lunghezza_m, 2)

                                # v15: centroide = bbox center dei vertici body veri.
                                # Prima era la media delle AXIS2_PLACEMENT_3D.location
                                # dei piani (frame-origin arbitrari, non centroidi
                                # geometrici), che produceva centroidi sballati e
                                # quindi matching mesh<->tubo sbagliato lato JS.
                                if body_verts:
                                    centroide = [
                                        (max(v[0] for v in body_verts) + min(v[0] for v in body_verts)) / 2,
                                        (max(v[1] for v in body_verts) + min(v[1] for v in body_verts)) / 2,
                                        (max(v[2] for v in body_verts) + min(v[2] for v in body_verts)) / 2,
                                    ]
                                else:
                                    all_origins = [o for o, _ in side_planes]
                                    all_origins += [o for o, _, _ in axis_planes]
                                    all_origins += [o for o, _, _ in oblique_planes]
                                    if all_origins:
                                        n_o = len(all_origins)
                                        centroide = [
                                            sum(o[0] for o in all_origins) / n_o,
                                            sum(o[1] for o in all_origins) / n_o,
                                            sum(o[2] for o in all_origins) / n_o,
                                        ]
                                    else:
                                        centroide = None

                                if debug:
                                    logger.info(
                                        "[TUBE bid=%s] MATCHED profilo=%s lato=%sx%s sp=%s "
                                        "len=%.3fm taglio=%s/%s centroide=%s",
                                        bid, nome_profilo, lato_a, lato_b, spessore,
                                        lunghezza_m, taglio_1, taglio_2,
                                        [round(c, 1) for c in centroide] if centroide else None,
                                    )

                                tubi_rilevati.append({
                                    "tipo": tipo,
                                    "profilo": nome_profilo,
                                    "lato_a": lato_a,
                                    "lato_b": lato_b,
                                    "spessore": spessore,
                                    "lunghezza_m": lunghezza_m,
                                    "peso_kg": peso_kg,
                                    "peso_kg_m": peso_kg_m,
                                    "taglio_1": taglio_1,
                                    "taglio_2": taglio_2,
                                    "angolo_taglio_1": angolo_taglio_1,
                                    "angolo_taglio_2": angolo_taglio_2,
                                    "centroide": centroide,
                                    "body_id": bid
                                })
                                detected_rhs = True
                            else:
                                if debug:
                                    logger.info(
                                        "[TUBE bid=%s] SKIP ratio_sezione=%.2f > 5.0 "
                                        "(len=%.1f dim_a=%.1f dim_b=%.1f)",
                                        bid, ratio_sezione, lunghezza_mm, dim_a, dim_b,
                                    )
                        else:
                            if debug:
                                logger.info(
                                    "[TUBE bid=%s] SKIP filter: len=%.1f dim_a=%.1f dim_b=%.1f "
                                    "elongation=%.2f (need len>=50, dims>=10, elong>=3.0)",
                                    bid, lunghezza_mm, dim_a, dim_b, elongation,
                                )

        if detected_rhs:
            continue

        # === CHS: >=1 cilindro + pochi piani (tappi, max 4) ===
        # Fix Bug B: soglia cilindro abbassata da r>10 a r>5 per includere tondi
        # piccoli come D.27 (r=13.5mm passa già, ma D.12/D.10 ora rilevabili).
        if debug:
            logger.info(
                "[CHS bid=%s] candidato: n_cyl=%d n_plane=%d cyl_radii=%s",
                bid, n_cyl, n_plane, sorted(cyl_radii.keys()),
            )
        if n_cyl >= 1 and n_plane <= 4:
            big_cyl_radii = {r: surfs for r, surfs in cyl_radii.items() if r > 5.0}
            if not big_cyl_radii:
                if debug:
                    logger.info("[CHS bid=%s] SKIP: nessun cilindro r>5mm", bid)
                continue

            radii_sorted = sorted(big_cyl_radii.keys(), reverse=True)
            r_ext = radii_sorted[0]
            r_int = radii_sorted[1] if len(radii_sorted) > 1 else None
            d_ext = round(r_ext * 2, 1)
            spessore = round(r_ext - r_int, 1) if r_int and (r_ext - r_int) > 0.5 else None

            cyl_axis = None
            for s in big_cyl_radii[r_ext]:
                if 'axis' in s[1]:
                    cyl_axis = _vec_norm(s[1]['axis'])
                    break

            lunghezza_mm = 0
            taglio_1 = "dritto"
            taglio_2 = "dritto"
            angolo_taglio_1 = 0.0
            angolo_taglio_2 = 0.0
            chs_verts = None

            if cyl_axis and planes_with_data:
                # cap_planes serve solo per classificare taglio dritto/obliquo
                # ai due estremi del tondo. La lunghezza vera viene invece
                # calcolata sui vertici del body (vedi sotto), perché le
                # AXIS2_PLACEMENT_3D.location dei piani cap STEP non sono
                # punti del piano ma frame-origin arbitrari → producevano
                # +40mm sistematici sui tondi (es. D27 600→640).
                cap_planes = []
                for origin, normal in planes_with_data:
                    dot = abs(_vec_dot(normal, cyl_axis))
                    if dot > 0.95:
                        cap_planes.append((origin, normal, dot))

                # v14: lunghezza dai vertici body proiettati sull'asse del
                # cilindro (criterio robusto, indipendente dalle location piani).
                chs_verts = _collect_body_vertices(face_refs)
                if chs_verts:
                    projs_v = [_vec_dot(v, cyl_axis) for v in chs_verts]
                    lunghezza_mm = max(projs_v) - min(projs_v)
                elif len(cap_planes) >= 2:
                    projs_p = [_vec_dot(p[0], cyl_axis) for p in cap_planes]
                    lunghezza_mm = max(projs_p) - min(projs_p)

                # Classificazione taglio agli estremi: usa cap_planes
                if len(cap_planes) >= 2:
                    cps = sorted(cap_planes, key=lambda p: _vec_dot(p[0], cyl_axis))
                    p_min, p_max = cps[0], cps[-1]
                    taglio_1 = "dritto" if p_min[2] > 0.98 else "obliquo"
                    taglio_2 = "dritto" if p_max[2] > 0.98 else "obliquo"
                    # v16: angolo numerico in gradi (inclinazione cap rispetto al
                    # perpendicolare-asse). p[2] = |dot(normal, axis)|.
                    d1 = max(-1.0, min(1.0, p_min[2]))
                    d2 = max(-1.0, min(1.0, p_max[2]))
                    angolo_taglio_1 = round(math.degrees(math.acos(d1)), 1)
                    angolo_taglio_2 = round(math.degrees(math.acos(d2)), 1)

            if lunghezza_mm < 10:
                all_origins = [s[1]['origin'] for s in surfaces
                               if s[0] == 'CYL' and 'origin' in s[1]]
                if len(all_origins) >= 2:
                    xs = [p[0] for p in all_origins]
                    ys = [p[1] for p in all_origins]
                    zs = [p[2] for p in all_origins]
                    lunghezza_mm = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))

            lunghezza_m = round(lunghezza_mm / 1000.0, 3)

            profilo = match_profilo_chs(d_ext, spessore or 2.0, profili_db)
            nome_profilo = profilo["nome"] if profilo else f"Tondo \u00d8{d_ext} sp.{spessore or '?'}mm"
            peso_kg_m = profilo["peso_kg_m"] if profilo else 0.0
            peso_kg = round(peso_kg_m * lunghezza_m, 2)
            # v14: snap d_ext e spessore al nominale del profilo DB se matched.
            # Il valore geometrico (es. sp 2.3 da r_ext-r_int) e' lo spessore
            # reale del CAD ma puo' divergere dalla nomenclatura commerciale
            # ("Tondo 27x2"). Per coerenza con la distinta usiamo il nominale.
            if profilo:
                d_ext = profilo.get("d_ext", d_ext)
                spessore = profilo.get("spessore", spessore)

            # v15: centroide CHS = bbox center dei vertici body veri.
            if not chs_verts:
                chs_verts = _collect_body_vertices(face_refs)
            if chs_verts:
                centroide = [
                    (max(v[0] for v in chs_verts) + min(v[0] for v in chs_verts)) / 2,
                    (max(v[1] for v in chs_verts) + min(v[1] for v in chs_verts)) / 2,
                    (max(v[2] for v in chs_verts) + min(v[2] for v in chs_verts)) / 2,
                ]
            else:
                chs_origins = [s[1]['origin'] for s in surfaces
                               if s[0] in ('PLANE', 'CYL') and 'origin' in s[1]]
                if chs_origins:
                    n_o = len(chs_origins)
                    centroide = [
                        sum(o[0] for o in chs_origins) / n_o,
                        sum(o[1] for o in chs_origins) / n_o,
                        sum(o[2] for o in chs_origins) / n_o,
                    ]
                else:
                    centroide = None

            if debug:
                logger.info(
                    "[CHS bid=%s] MATCHED profilo=%s d=%s sp=%s len=%.3fm taglio=%s/%s",
                    bid, nome_profilo, d_ext, spessore, lunghezza_m, taglio_1, taglio_2,
                )

            tubi_rilevati.append({
                "tipo": "CHS",
                "profilo": nome_profilo,
                "d_ext": d_ext,
                "spessore": spessore,
                "lunghezza_m": lunghezza_m,
                "peso_kg": peso_kg,
                "peso_kg_m": peso_kg_m,
                "taglio_1": taglio_1,
                "taglio_2": taglio_2,
                "angolo_taglio_1": angolo_taglio_1,
                "angolo_taglio_2": angolo_taglio_2,
                "centroide": centroide,
                "body_id": bid
            })
            continue

    # --- Caso speciale: corpo unico fuso con molti cilindri ---
    if not tubi_rilevati and body_ids:
        for bid in body_ids:
            face_refs = _get_face_refs(bid)
            surfaces = []
            for fref in face_refs:
                stype, sdata = _get_surface_info(fref)
                if stype:
                    surfaces.append((stype, sdata))

            cyl_by_radius = {}
            for s in surfaces:
                if s[0] == 'CYL':
                    r = round(s[1].get('raggio', 0), 1)
                    if r > 5.0:
                        cyl_by_radius.setdefault(r, []).append(s)

            if not cyl_by_radius:
                continue

            for r, cyl_list in sorted(cyl_by_radius.items(), key=lambda x: len(x[1]), reverse=True):
                n_cyl_same = len(cyl_list)
                if n_cyl_same < 3:
                    continue

                d_ext = round(r * 2, 1)
                origins = [s[1]['origin'] for s in cyl_list if 'origin' in s[1]]
                axes = [_vec_norm(s[1]['axis']) for s in cyl_list if 'axis' in s[1]]

                axis_groups = {}
                for i_ax, (orig, ax) in enumerate(zip(origins, axes)):
                    matched = False
                    for gk in axis_groups:
                        ref_ax = axis_groups[gk][0][1]
                        if abs(_vec_dot(ax, ref_ax)) > 0.95:
                            axis_groups[gk].append((orig, ax))
                            matched = True
                            break
                    if not matched:
                        axis_groups[len(axis_groups)] = [(orig, ax)]

                profilo = match_profilo_chs(d_ext, 2.0, profili_db)
                nome_profilo = profilo["nome"] if profilo else f"Tondo \u00d8{d_ext}mm"
                peso_kg_m = profilo["peso_kg_m"] if profilo else 0.0

                for gk, group in axis_groups.items():
                    if len(group) < 1:
                        continue
                    ref_ax = _vec_norm(group[0][1])
                    projs = [_vec_dot(o, ref_ax) for o, a in group]
                    if len(projs) >= 2:
                        lunghezza_mm = max(projs) - min(projs)
                    else:
                        lunghezza_mm = 500

                    if lunghezza_mm < 20:
                        lunghezza_mm = 500

                    lunghezza_m = round(lunghezza_mm / 1000.0, 3)
                    peso_kg = round(peso_kg_m * lunghezza_m, 2)

                    tubi_rilevati.append({
                        "tipo": "CHS",
                        "profilo": nome_profilo,
                        "d_ext": d_ext,
                        "spessore": profilo["spessore"] if profilo else None,
                        "lunghezza_m": lunghezza_m,
                        "peso_kg": peso_kg,
                        "peso_kg_m": peso_kg_m,
                        "taglio_1": "dritto",
                        "taglio_2": "dritto",
                        "body_id": bid,
                        "stimato": True
                    })

    # --- Riepilogo ---
    peso_totale = round(sum(t["peso_kg"] for t in tubi_rilevati), 2)
    n_dritti = sum(1 for t in tubi_rilevati
                   for tag in [t["taglio_1"], t["taglio_2"]] if tag == "dritto")
    n_obliqui = sum(1 for t in tubi_rilevati
                    for tag in [t["taglio_1"], t["taglio_2"]] if tag == "obliquo")
    n_sagomati = sum(1 for t in tubi_rilevati
                     for tag in [t["taglio_1"], t["taglio_2"]] if tag == "sagomato")

    return {
        'tubi': tubi_rilevati,
        'peso_totale_kg': peso_totale,
        'n_tagli_dritti': n_dritti,
        'n_tagli_obliqui': n_obliqui,
        'n_tagli_sagomati': n_sagomati,
        'errore': None if tubi_rilevati else 'Nessun tubo rilevato nel file STEP'
    }


def calcola_costo_tubolare(analisi: dict, config: dict, materiale: str = "acciaio") -> dict:
    """Calcola il costo di una struttura tubolare.

    Args:
        analisi: dict da analizza_step_tubolari().
        config: dict di configurazione applicazione.
        materiale: 'acciaio', 'inox', o 'alluminio'.

    Returns:
        dict con breakdown costi.
    """
    costi_mat = {
        "acciaio": float(config.get("costo_materiale_acciaio_kg", 1.20)),
        "inox": float(config.get("costo_materiale_inox_kg", 4.50)),
        "alluminio": float(config.get("costo_materiale_alluminio_kg", 3.50)),
    }
    costo_mat_kg = costi_mat.get(materiale, costi_mat["acciaio"])

    costo_ora_taglio = float(config.get("costo_orario_taglio_tubo", 40.0))
    tempo_dritto = float(config.get("tempo_taglio_dritto_min", 1.0))
    tempo_obliquo = float(config.get("tempo_taglio_obliquo_min", 2.5))
    tempo_sagomato = float(config.get("tempo_taglio_sagomato_min", 5.0))

    peso_kg = analisi.get('peso_totale_kg', 0)
    n_dritti = analisi.get('n_tagli_dritti', 0)
    n_obliqui = analisi.get('n_tagli_obliqui', 0)
    n_sagomati = analisi.get('n_tagli_sagomati', 0)

    costo_materiale = round(peso_kg * costo_mat_kg, 2)

    costo_taglio_dritto = round(n_dritti * tempo_dritto * costo_ora_taglio / 60, 2)
    costo_taglio_obliquo = round(n_obliqui * tempo_obliquo * costo_ora_taglio / 60, 2)
    costo_taglio_sagomato = round(n_sagomati * tempo_sagomato * costo_ora_taglio / 60, 2)
    costo_taglio_totale = costo_taglio_dritto + costo_taglio_obliquo + costo_taglio_sagomato

    totale = costo_materiale + costo_taglio_totale

    return {
        'costo_materiale': costo_materiale,
        'costo_taglio_dritto': costo_taglio_dritto,
        'costo_taglio_obliquo': costo_taglio_obliquo,
        'costo_taglio_sagomato': costo_taglio_sagomato,
        'costo_taglio_totale': costo_taglio_totale,
        'totale': round(totale, 2),
        'peso_kg': peso_kg,
        'materiale': materiale,
        'n_tagli_dritti': n_dritti,
        'n_tagli_obliqui': n_obliqui,
        'n_tagli_sagomati': n_sagomati,
    }
