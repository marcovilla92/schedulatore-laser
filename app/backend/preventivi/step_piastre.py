"""STEP file plate (piastre) analysis.

Identifies flat bodies with two antiparallel PLANE faces (top/bottom),
calculates thickness, area and weight for each plate.
"""

import logging
import math
import re

logger = logging.getLogger(__name__)


def analizza_step_piastre(step_path: str, densita: float = 7.85) -> dict:
    """Analizza file STEP per rilevare piastre (corpi piatti in lamiera).

    Identifica corpi con 2 facce PLANE parallele opposte (top/bottom).
    Calcola spessore, area e peso per ogni piastra.

    Args:
        step_path: Path al file STEP.
        densita: Densita' materiale in kg/dm3 (default: 7.85 per acciaio).

    Returns:
        dict con 'piastre': lista, 'peso_totale_kg': float, 'errore': str|None
    """
    try:
        with open(step_path, 'r', errors='replace') as f:
            content = f.read()
    except (IOError, OSError) as e:
        return {'piastre': [], 'peso_totale_kg': 0, 'errore': str(e)}

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
        return {'piastre': [], 'peso_totale_kg': 0,
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
        """Per una ADVANCED_FACE, ritorna (tipo, dati)."""
        fval = entities.get(face_ref, '')
        if _etype(fval) != 'ADVANCED_FACE':
            return None, {}
        frefs = _refs(fval)
        if not frefs:
            return None, {}
        surf_ref = frefs[-1]
        surf_val = entities.get(surf_ref, '')
        surf_type = _etype(surf_val)

        # Controlla il sense flag dell'ADVANCED_FACE (.T. o .F.)
        # Il flag e' l'ultimo argomento: ADVANCED_FACE('',(...),#surf,.T./.F.)
        face_sense_fwd = '.F.' not in fval

        if surf_type == 'PLANE':
            srefs = _refs(surf_val)
            if srefs:
                ax_val = entities.get(srefs[0], '')
                ax_refs = _refs(ax_val)
                if len(ax_refs) >= 2:
                    origin = _coords(entities.get(ax_refs[0], ''))
                    normal = _coords(entities.get(ax_refs[1], ''))
                    if origin and normal:
                        n = _vec_norm(normal)
                        if not face_sense_fwd:
                            n = (-n[0], -n[1], -n[2])
                        return 'PLANE', {'origin': origin, 'normal': n}
            return 'PLANE', {}
        elif surf_type == 'CYLINDRICAL_SURFACE':
            nums = re.findall(r'([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)', surf_val)
            radius = float(nums[-1]) if nums else 0.0
            return 'CYL', {'raggio': radius}
        else:
            return surf_type, {}

    def _get_edge_points(face_ref):
        """Estrai tutti i punti vertice dagli edge loop di una faccia."""
        fval = entities.get(face_ref, '')
        if _etype(fval) != 'ADVANCED_FACE':
            return []
        pts = []
        for bref in _refs(fval):
            bval = entities.get(bref, '')
            if _etype(bval) not in ('FACE_OUTER_BOUND', 'FACE_BOUND'):
                continue
            brefs = _refs(bval)
            if not brefs:
                continue
            el_val = entities.get(brefs[0], '')
            if _etype(el_val) != 'EDGE_LOOP':
                continue
            for oe_ref in _refs(el_val):
                oe_val = entities.get(oe_ref, '')
                if _etype(oe_val) != 'ORIENTED_EDGE':
                    continue
                oe_refs = _refs(oe_val)
                if not oe_refs:
                    continue
                ec_val = entities.get(oe_refs[-1], '')
                if _etype(ec_val) != 'EDGE_CURVE':
                    continue
                ec_refs = _refs(ec_val)
                if len(ec_refs) < 2:
                    continue
                for vref in ec_refs[:2]:
                    vval = entities.get(vref, '')
                    if _etype(vval) == 'VERTEX_POINT':
                        vrefs = _refs(vval)
                        if vrefs:
                            pt = _coords(entities.get(vrefs[0], ''))
                            if pt:
                                pts.append(pt)
        return pts

    piastre_rilevate = []

    for bid in body_ids:
        face_refs = _get_face_refs(bid)
        if not face_refs:
            continue

        # Raccogli info superfici
        surfaces = []
        for fref in face_refs:
            stype, sdata = _get_surface_info(fref)
            if stype:
                surfaces.append((stype, sdata, fref))

        n_cyl = sum(1 for s in surfaces if s[0] == 'CYL')
        n_plane = sum(1 for s in surfaces if s[0] == 'PLANE')

        # Skip se sembra un tubo (molti cilindri grandi o >=6 piani in >=3 direzioni)
        big_cyl = [s for s in surfaces if s[0] == 'CYL' and s[1].get('raggio', 0) > 15.0]
        if len(big_cyl) >= 2:
            continue  # Probabilmente tubo tondo

        # Raccogli piani con dati completi
        planes = [(s[1]['origin'], s[1]['normal'], s[2])
                  for s in surfaces
                  if s[0] == 'PLANE' and 'origin' in s[1] and 'normal' in s[1]]

        if len(planes) < 2:
            continue

        # Controlla se e' un tubo quadro (>=6 piani in >=3 direzioni normali)
        normal_dirs = {}
        for o, n, fref in planes:
            matched = False
            for dk, dn_list in normal_dirs.items():
                if abs(_vec_dot(n, dn_list[0][1])) > 0.95:
                    normal_dirs[dk].append((o, n, fref))
                    matched = True
                    break
            if not matched:
                normal_dirs[len(normal_dirs)] = [(o, n, fref)]

        if len(normal_dirs) >= 3 and n_plane >= 6:
            # Verifica se 3 direzioni hanno ognuna >=2 piani -> tubo quadro
            dirs_with_pairs = sum(1 for d in normal_dirs.values() if len(d) >= 2)
            if dirs_with_pairs >= 3:
                # Ma potrebbe essere una piastra con fori/features
                # Controlla se 2 facce dominano in area (piastra) vs distribuite (tubo)
                face_areas = []
                for o, n, fref in planes:
                    pts = _get_edge_points(fref)
                    if len(pts) >= 3:
                        ndir = n
                        if abs(ndir[0]) < 0.9:
                            uu = (1, 0, 0)
                        else:
                            uu = (0, 1, 0)
                        duu = _vec_dot(uu, ndir)
                        uu = (uu[0]-duu*ndir[0], uu[1]-duu*ndir[1], uu[2]-duu*ndir[2])
                        ul = _vec_len(uu)
                        if ul > 1e-12:
                            uu = (uu[0]/ul, uu[1]/ul, uu[2]/ul)
                            vv = (ndir[1]*uu[2]-ndir[2]*uu[1], ndir[2]*uu[0]-ndir[0]*uu[2], ndir[0]*uu[1]-ndir[1]*uu[0])
                            us = [_vec_dot(p, uu) for p in pts]
                            vs = [_vec_dot(p, vv) for p in pts]
                            a = (max(us)-min(us)) * (max(vs)-min(vs))
                            face_areas.append(a)
                        else:
                            face_areas.append(0)
                    else:
                        face_areas.append(0)
                face_areas.sort(reverse=True)
                # Se le 2 facce piu' grandi sono >2.5x la terza -> piastra con features
                # (tubi quadri hanno ratio ~1.0, piastre con features >2.5)
                if len(face_areas) >= 3 and face_areas[2] > 0:
                    ratio = face_areas[1] / face_areas[2]
                    if ratio > 2.5:
                        pass  # Non skip, e' una piastra
                    else:
                        continue  # Tubo quadro
                else:
                    continue  # Tubo quadro

        # --- CERCA COPPIE DI PIANI PARALLELI OPPOSTI ---
        # Una piastra ha 2 facce grandi con normali antiparallele
        best_pair = None
        best_area = 0

        for i in range(len(planes)):
            for j in range(i + 1, len(planes)):
                o1, n1, fref1 = planes[i]
                o2, n2, fref2 = planes[j]

                # Normali antiparallele (dot ~ -1)
                dot = _vec_dot(n1, n2)
                if dot > -0.95:
                    continue

                # Calcola spessore = distanza tra i piani
                diff = (o2[0] - o1[0], o2[1] - o1[1], o2[2] - o1[2])
                spessore = abs(_vec_dot(diff, n1))

                # Spessore tipico lamiera: 0.5 - 30mm
                if spessore < 0.5 or spessore > 30.0:
                    continue

                # Calcola area dalla faccia: bounding box dei punti della faccia
                pts1 = _get_edge_points(fref1)
                pts2 = _get_edge_points(fref2)
                pts = pts1 if len(pts1) >= len(pts2) else pts2
                face_ref_used = fref1 if len(pts1) >= len(pts2) else fref2

                if len(pts) < 3:
                    continue

                # Proietta i punti su un piano 2D per calcolare il bounding box
                # Usa la normale del piano per definire assi locali
                n_dir = n1
                # Trova due assi perpendicolari alla normale
                if abs(n_dir[0]) < 0.9:
                    u = (1, 0, 0)
                else:
                    u = (0, 1, 0)
                # Gram-Schmidt
                dot_un = _vec_dot(u, n_dir)
                u = (u[0] - dot_un * n_dir[0], u[1] - dot_un * n_dir[1], u[2] - dot_un * n_dir[2])
                u_len = _vec_len(u)
                if u_len < 1e-12:
                    continue
                u = (u[0]/u_len, u[1]/u_len, u[2]/u_len)
                v = (n_dir[1]*u[2] - n_dir[2]*u[1],
                     n_dir[2]*u[0] - n_dir[0]*u[2],
                     n_dir[0]*u[1] - n_dir[1]*u[0])

                # Proietta punti su (u, v)
                us = [_vec_dot(p, u) for p in pts]
                vs = [_vec_dot(p, v) for p in pts]
                width = max(us) - min(us)
                height = max(vs) - min(vs)
                area_mm2 = width * height

                # Verifica che sia effettivamente piatto (area >> spessore^2)
                if area_mm2 < spessore * spessore * 4:
                    continue

                if area_mm2 > best_area:
                    best_area = area_mm2
                    best_pair = (spessore, area_mm2, width, height, fref1, fref2)

        if best_pair:
            spessore, area_mm2, width, height, fref1, fref2 = best_pair
            area_dm2 = round(area_mm2 / 10000.0, 3)  # mm2 -> dm2
            spessore_mm = round(spessore, 1)
            # peso = area_m2 x spessore_m x densita_kg/m3
            # area_m2 = area_mm2 / 1e6, spessore_m = spessore / 1000
            # densita_kg/m3 = densita_kg/dm3 x 1000
            peso_kg = round(area_mm2 / 1e6 * spessore / 1000.0 * densita * 1000, 2)

            # Bounding box 3D per il corpo (da tutti i punti delle facce)
            all_pts = []
            for fref in face_refs:
                all_pts.extend(_get_edge_points(fref))
            if all_pts:
                bbox_min = tuple(min(p[k] for p in all_pts) for k in range(3))
                bbox_max = tuple(max(p[k] for p in all_pts) for k in range(3))
            else:
                bbox_min = bbox_max = (0, 0, 0)

            piastre_rilevate.append({
                'spessore_mm': spessore_mm,
                'area_dm2': area_dm2,
                'larghezza_mm': round(width, 1),
                'altezza_mm': round(height, 1),
                'peso_kg': peso_kg,
                'body_id': bid,
                'bbox_min': bbox_min,
                'bbox_max': bbox_max,
            })

    peso_totale = round(sum(p['peso_kg'] for p in piastre_rilevate), 2)
    return {
        'piastre': piastre_rilevate,
        'peso_totale_kg': peso_totale,
        'errore': None if piastre_rilevate else 'Nessuna piastra rilevata'
    }


def calcola_costo_piastre(analisi: dict, config: dict, materiale: str = "acciaio") -> dict:
    """Calcola il costo delle piastre rilevate.

    Args:
        analisi: dict da analizza_step_piastre().
        config: dict di configurazione applicazione.
        materiale: 'acciaio', 'inox', 'alluminio'.

    Returns:
        dict con breakdown costi per piastra.
    """
    tabella = config.get('prezzo_dm2', {})
    prezzi_mat = tabella.get(materiale, tabella.get('acciaio', {}))

    # Converti chiavi stringa a float per matching
    spessori_disponibili = []
    for k, v in prezzi_mat.items():
        try:
            spessori_disponibili.append((float(k), v))
        except ValueError:
            continue
    spessori_disponibili.sort(key=lambda x: x[0])

    def _find_prezzo(spessore_mm):
        if not spessori_disponibili:
            return 0.0, 0.0
        # Trova lo spessore piu' vicino
        best = min(spessori_disponibili, key=lambda x: abs(x[0] - spessore_mm))
        return best[1], best[0]

    dettaglio = []
    totale = 0.0
    for piastra in analisi.get('piastre', []):
        prezzo_dm2, sp_match = _find_prezzo(piastra['spessore_mm'])
        costo = round(piastra['area_dm2'] * prezzo_dm2, 2)
        totale += costo
        dettaglio.append({
            'spessore_mm': piastra['spessore_mm'],
            'spessore_matchato': sp_match,
            'area_dm2': piastra['area_dm2'],
            'prezzo_dm2': prezzo_dm2,
            'costo': costo,
            'peso_kg': piastra['peso_kg'],
            'larghezza_mm': piastra.get('larghezza_mm', 0),
            'altezza_mm': piastra.get('altezza_mm', 0),
        })

    return {
        'dettaglio_piastre': dettaglio,
        'costo_materiale': round(totale, 2),
        'totale': round(totale, 2),
        'materiale': materiale,
    }
