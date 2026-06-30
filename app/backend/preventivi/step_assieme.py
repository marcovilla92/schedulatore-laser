"""STEP file assembly analysis.

Analyzes STEP assemblies for weld estimation and instance counting.
Supports both multi-body parts and assemblies with NAUO + RRWT + IDT transforms.
"""

import logging
import math
import re

import numpy as np

logger = logging.getLogger(__name__)


def analizza_step_assieme(step_path: str) -> dict:
    """Analizza file STEP 3D di un assieme per stimare i ml di saldatura.

    Supporta sia corpi sovrapposti (multi-body part) sia assiemi con
    trasformazioni (NAUO + RRWT + IDT). Filtra bordi interni (solo
    perimetro esterno) per stime realistiche.

    Args:
        step_path: Path al file STEP.

    Returns:
        dict: {"saldatura_mm": float, "n_corpi": int, "errore": str|None}
    """
    try:
        with open(step_path, 'r', errors='replace') as f:
            content = f.read()
    except (IOError, OSError) as e:
        return {"saldatura_mm": 0.0, "n_corpi": 0, "errore": str(e)}

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

    def _build_a2p3d(eid):
        val = entities.get(eid, '')
        refs = _refs(val)
        if len(refs) < 2:
            return np.eye(4)
        origin = np.array(_coords(entities.get(refs[0], '')) or (0,0,0))
        z_dir = np.array(_coords(entities.get(refs[1], '')) or (0,0,1))
        x_dir = np.array(_coords(entities.get(refs[2], '')) or (1,0,0)) if len(refs) >= 3 else np.array([1,0,0])
        z_dir = z_dir / max(np.linalg.norm(z_dir), 1e-12)
        x_dir = x_dir - np.dot(x_dir, z_dir) * z_dir
        xn = np.linalg.norm(x_dir)
        if xn < 1e-12:
            x_dir = np.array([1,0,0]) if abs(z_dir[0]) < 0.9 else np.array([0,1,0])
            x_dir = x_dir - np.dot(x_dir, z_dir) * z_dir
            xn = np.linalg.norm(x_dir)
        x_dir = x_dir / max(xn, 1e-12)
        y_dir = np.cross(z_dir, x_dir)
        T = np.eye(4)
        T[:3, 0] = x_dir; T[:3, 1] = y_dir; T[:3, 2] = z_dir; T[:3, 3] = origin
        return T

    def _tp(T, p):
        return tuple((T @ np.array([p[0], p[1], p[2], 1.0]))[:3])
    def _td(T, d):
        return tuple(T[:3, :3] @ np.array(d))

    def _get_face_refs(bid):
        val = entities.get(bid, '')
        et = _etype(val)
        refs_list = _refs(val)
        if not refs_list:
            return []
        if et == 'MANIFOLD_SOLID_BREP':
            return _refs(entities.get(refs_list[-1], ''))
        elif et in ('CLOSED_SHELL', 'OPEN_SHELL'):
            return refs_list
        elif et == 'SHELL_BASED_SURFACE_MODEL':
            faces = []
            for sr in refs_list:
                sv = entities.get(sr, '')
                if _etype(sv) in ('CLOSED_SHELL', 'OPEN_SHELL'):
                    faces.extend(_refs(sv))
            return faces
        else:
            return _refs(entities.get(refs_list[-1], ''))

    def _get_edges(face_refs):
        edges = []; seen = set()
        for fref in face_refs:
            fval = entities.get(fref, '')
            if _etype(fval) != 'ADVANCED_FACE': continue
            for bref in _refs(fval):
                bval = entities.get(bref, '')
                if _etype(bval) not in ('FACE_OUTER_BOUND', 'FACE_BOUND'): continue
                el_ref = _refs(bval)[0]
                el_val = entities.get(el_ref, '')
                if _etype(el_val) != 'EDGE_LOOP': continue
                for oe_ref in _refs(el_val):
                    oe_val = entities.get(oe_ref, '')
                    if _etype(oe_val) != 'ORIENTED_EDGE': continue
                    oe_refs = _refs(oe_val)
                    if not oe_refs: continue
                    ec_ref = oe_refs[-1]
                    if ec_ref in seen: continue
                    ec_val = entities.get(ec_ref, '')
                    if _etype(ec_val) != 'EDGE_CURVE': continue
                    refs2 = _refs(ec_val)
                    if len(refs2) < 3: continue
                    ct = _etype(entities.get(refs2[2], ''))
                    v1r = _refs(entities.get(refs2[0], ''))
                    v2r = _refs(entities.get(refs2[1], ''))
                    p1 = _coords(entities.get(v1r[0], '')) if v1r else None
                    p2 = _coords(entities.get(v2r[0], '')) if v2r else None
                    if p1 and p2:
                        seen.add(ec_ref)
                        edges.append((ec_ref, p1, p2, ct))
        return edges

    def _get_planes(face_refs):
        planes = []
        for fref in face_refs:
            fval = entities.get(fref, '')
            if _etype(fval) != 'ADVANCED_FACE': continue
            for sr in _refs(fval):
                sv = entities.get(sr, '')
                if _etype(sv) != 'PLANE': continue
                ax = _refs(sv)[0]
                axr = _refs(entities.get(ax, ''))
                if len(axr) >= 2:
                    o = _coords(entities.get(axr[0], ''))
                    n = _coords(entities.get(axr[1], ''))
                    if o and n: planes.append((o, n))
        return planes

    # --- Check if this is an ASSEMBLY (has RRWT transforms) ---
    raw_rrwts = []
    for eid, val in entities.items():
        if 'REPRESENTATION_RELATIONSHIP' in val and 'TRANSFORMATION' in val:
            refs = _refs(val)
            if len(refs) >= 3:
                raw_rrwts.append({'eid': eid, 'sr_a': refs[0], 'sr_b': refs[1], 'idt': refs[2]})

    # Determine which SR is assembly (shared by all) vs component (varies)
    rrwts = []
    if raw_rrwts:
        from collections import Counter
        sr_a_counts = Counter(r['sr_a'] for r in raw_rrwts)
        sr_b_counts = Counter(r['sr_b'] for r in raw_rrwts)
        # The assembly SR appears in ALL rrwts on one side; component SR varies
        max_a = max(sr_a_counts.values())
        max_b = max(sr_b_counts.values())
        _sr_order_flipped = False
        if max_b >= max_a:
            # refs[1] is assembly (repeated), refs[0] is component — FLIPPED
            _sr_order_flipped = True
            for r in raw_rrwts:
                rrwts.append({'assembly_sr': r['sr_b'], 'child_sr': r['sr_a'], 'idt': r['idt']})
        else:
            # refs[0] is assembly (repeated), refs[1] is component — STANDARD
            for r in raw_rrwts:
                rrwts.append({'assembly_sr': r['sr_a'], 'child_sr': r['sr_b'], 'idt': r['idt']})

    if rrwts:
        # === ASSEMBLY MODE: apply transforms ===
        srr_map = {}
        for eid, val in entities.items():
            if _etype(val) == 'SHAPE_REPRESENTATION_RELATIONSHIP':
                refs = _refs(val)
                if len(refs) >= 2:
                    srr_map[refs[0]] = refs[1]
                    srr_map[refs[1]] = refs[0]

        # Build context → ABSR bodies map (for STEP files where SR and ABSR share context)
        _ctx_to_bodies = {}
        for eid, val in entities.items():
            if _etype(val) == 'ADVANCED_BREP_SHAPE_REPRESENTATION':
                refs = _refs(val)
                if refs:
                    ctx = refs[-1]
                    for r in refs[:-1]:
                        if _etype(entities.get(r, '')) in ('MANIFOLD_SOLID_BREP', 'CLOSED_SHELL'):
                            _ctx_to_bodies.setdefault(ctx, []).append(r)

        def _find_bodies(sr_id, visited=None):
            if visited is None: visited = set()
            if sr_id in visited: return []
            visited.add(sr_id)
            val = entities.get(sr_id, '')
            bodies = [r for r in _refs(val) if _etype(entities.get(r, '')) in
                      ('MANIFOLD_SOLID_BREP', 'CLOSED_SHELL', 'SHELL_BASED_SURFACE_MODEL',
                       'ADVANCED_BREP_SHAPE_REPRESENTATION')]
            # Resolve ADVANCED_BREP_SHAPE_REPRESENTATION → extract actual bodies inside
            resolved = []
            for b in bodies:
                bt = _etype(entities.get(b, ''))
                if bt == 'ADVANCED_BREP_SHAPE_REPRESENTATION':
                    inner = [r for r in _refs(entities.get(b, '')) if _etype(entities.get(r, '')) in
                             ('MANIFOLD_SOLID_BREP', 'CLOSED_SHELL', 'SHELL_BASED_SURFACE_MODEL')]
                    resolved.extend(inner)
                else:
                    resolved.append(b)
            if resolved:
                return resolved
            # Try context-based lookup: SR shares context with ABSR
            sr_refs = _refs(val)
            if sr_refs:
                ctx = sr_refs[-1]
                if ctx in _ctx_to_bodies:
                    return list(_ctx_to_bodies[ctx])
            if sr_id in srr_map:
                return _find_bodies(srr_map[sr_id], visited)
            return []

        def _get_transform(idt_id):
            val = entities.get(idt_id, '')
            refs = _refs(val)
            if len(refs) >= 2:
                if _sr_order_flipped:
                    # Flipped format: swap IDT direction too
                    return _build_a2p3d(refs[1]) @ np.linalg.inv(_build_a2p3d(refs[0]))
                else:
                    # Standard: item_1 = assembly placement, item_2 = component origin
                    return _build_a2p3d(refs[0]) @ np.linalg.inv(_build_a2p3d(refs[1]))
            return np.eye(4)

        # Build transformed instances with bbox dimensions
        raw_instances = []
        for rrwt in rrwts:
            T = _get_transform(rrwt['idt'])
            bodies = _find_bodies(rrwt['child_sr'])
            all_edges, all_planes, all_pts = [], [], []
            n_cylinders = 0
            for bid in bodies:
                faces = _get_face_refs(bid)
                for ec, p1, p2, ct in _get_edges(faces):
                    tp1, tp2 = _tp(T, p1), _tp(T, p2)
                    all_edges.append((ec, tp1, tp2, ct))
                    all_pts.extend([tp1, tp2])
                for o, n in _get_planes(faces):
                    all_planes.append((_tp(T, o), _td(T, n)))
                # Count cylindrical surfaces (CHS vs RHS distinction)
                for fref in faces:
                    fval = entities.get(fref, '')
                    if _etype(fval) != 'ADVANCED_FACE':
                        continue
                    for sr in _refs(fval):
                        sv = entities.get(sr, '')
                        if _etype(sv) == 'CYLINDRICAL_SURFACE':
                            n_cylinders += 1
            if all_pts:
                pts_arr = np.array(all_pts)
                bbox_min = tuple(pts_arr.min(axis=0))
                bbox_max = tuple(pts_arr.max(axis=0))
                dims = sorted([bbox_max[k] - bbox_min[k] for k in range(3)])
            else:
                bbox_min = bbox_max = (0, 0, 0)
                dims = [0, 0, 0]
            raw_instances.append({
                'edges': all_edges, 'planes': all_planes,
                'bbox_min': bbox_min, 'bbox_max': bbox_max,
                'dims': dims,  # [min, mid, max] sorted
                'child_sr': rrwt['child_sr'],
                'n_cylinders': n_cylinders
            })

        # --- Multi-body merge: same SR + >90% bbox overlap = same part ---
        merged_out = set()
        for i in range(len(raw_instances)):
            if i in merged_out:
                continue
            for j in range(i + 1, len(raw_instances)):
                if j in merged_out:
                    continue
                if raw_instances[i]['child_sr'] != raw_instances[j]['child_sr']:
                    continue
                vol_overlap = 1.0
                min_vol = 1.0
                for k in range(3):
                    ov = max(0, min(raw_instances[i]['bbox_max'][k],
                                   raw_instances[j]['bbox_max'][k])
                               - max(raw_instances[i]['bbox_min'][k],
                                     raw_instances[j]['bbox_min'][k]))
                    da = raw_instances[i]['bbox_max'][k] - raw_instances[i]['bbox_min'][k]
                    db = raw_instances[j]['bbox_max'][k] - raw_instances[j]['bbox_min'][k]
                    vol_overlap *= ov
                    min_vol *= min(max(da, 0.01), max(db, 0.01))
                if min_vol > 0 and vol_overlap / min_vol > 0.90:
                    raw_instances[i]['planes'].extend(raw_instances[j]['planes'])
                    merged_out.add(j)

        instances = [inst for idx, inst in enumerate(raw_instances)
                     if idx not in merged_out]
        n_corpi = len(instances)

        # --- Weld detection: bbox adjacency + cross-section perimeter ---
        CONTACT_TOL = 2.0  # mm tolerance for bbox adjacency

        def _cross_perimeter(inst):
            a, b = inst['dims'][0], inst['dims'][1]
            if a < 1 or b < 1:
                return 0
            return 2 * (a + b)

        total_weld = 0.0
        for i in range(len(instances)):
            for j in range(i + 1, len(instances)):
                a, b = instances[i], instances[j]
                adjacent = True
                for k in range(3):
                    if (a['bbox_min'][k] > b['bbox_max'][k] + CONTACT_TOL or
                            b['bbox_min'][k] > a['bbox_max'][k] + CONTACT_TOL):
                        adjacent = False
                        break
                if not adjacent:
                    continue
                perim_a = _cross_perimeter(a)
                perim_b = _cross_perimeter(b)
                joint_weld = (min(perim_a, perim_b)
                              if perim_a > 0 and perim_b > 0
                              else max(perim_a, perim_b))
                if joint_weld > 0:
                    total_weld += joint_weld

    else:
        # === MULTI-BODY MODE (no assembly transforms) ===
        body_ids = [eid for eid, val in entities.items()
                    if _etype(val) == 'MANIFOLD_SOLID_BREP']
        msb_child_shells = set()
        for bid in body_ids:
            for r in _refs(entities.get(bid, '')):
                msb_child_shells.add(r)
        for eid, val in entities.items():
            if _etype(val) == 'CLOSED_SHELL' and eid not in msb_child_shells:
                body_ids.append(eid)
        for eid, val in entities.items():
            if _etype(val) == 'SHELL_BASED_SURFACE_MODEL':
                body_ids.append(eid)

        if len(body_ids) < 2:
            return {"saldatura_mm": 0.0, "n_corpi": len(body_ids),
                    "errore": "Meno di 2 corpi" if len(body_ids) < 2 else None}

        body_data = {}
        for bid in body_ids:
            faces = _get_face_refs(bid)
            edges = _get_edges(faces)
            planes = _get_planes(faces)
            total_len = sum(math.sqrt(sum((a-b)**2 for a,b in zip(p1,p2))) for _, p1, p2, _ in edges)
            all_pts = [p for _, p1, p2, _ in edges for p in (p1, p2)]
            bbox_min = tuple(min(p[k] for p in all_pts) for k in range(3)) if all_pts else (0,0,0)
            bbox_max = tuple(max(p[k] for p in all_pts) for k in range(3)) if all_pts else (0,0,0)
            body_data[bid] = {'edges': edges, 'planes': planes,
                              'total_len': total_len, 'bbox_min': bbox_min, 'bbox_max': bbox_max}

        BB_TOL = 2.0
        merged_groups = []
        assigned = set()
        for bid in body_ids:
            if bid in assigned: continue
            group = [bid]; assigned.add(bid)
            for bid2 in body_ids:
                if bid2 not in assigned:
                    mn1, mx1 = body_data[bid]['bbox_min'], body_data[bid]['bbox_max']
                    mn2, mx2 = body_data[bid2]['bbox_min'], body_data[bid2]['bbox_max']
                    if all(abs(a-b) < BB_TOL for a,b in zip(mn1,mn2)) and \
                       all(abs(a-b) < BB_TOL for a,b in zip(mx1,mx2)):
                        group.append(bid2); assigned.add(bid2)
            merged_groups.append(group)

        n_corpi = len(merged_groups)
        TOL = 0.8; MIN_WELD = 5.0
        def _on_plane(pt, o, n):
            return abs(sum((p-oo)*nn for p,oo,nn in zip(pt, o, n))) < TOL

        total_weld = 0.0
        seen = set()
        for i, g1 in enumerate(merged_groups):
            for g2 in merged_groups[i+1:]:
                e1, p1_list = [], []
                for bid in g1:
                    e1.extend(body_data[bid]['edges']); p1_list.extend(body_data[bid]['planes'])
                e2, p2_list = [], []
                for bid in g2:
                    e2.extend(body_data[bid]['edges']); p2_list.extend(body_data[bid]['planes'])
                for check_e, check_p in [(e1, p2_list), (e2, p1_list)]:
                    for ec, pa, pb, ct in check_e:
                        if ec in seen or ct != 'LINE': continue
                        el = math.sqrt(sum((a-b)**2 for a,b in zip(pa,pb)))
                        if el < MIN_WELD: continue
                        for o, n in check_p:
                            if _on_plane(pa, o, n) and _on_plane(pb, o, n):
                                seen.add(ec); total_weld += el; break

    return {
        "saldatura_mm": round(total_weld, 1),
        "n_corpi": n_corpi,
        "errore": None
    }


def conta_istanze_nauo(step_path: str) -> dict:
    """Conta quante volte ogni body STEP e' istanziato nell'assieme via NAUO.

    Mappa body_id -> numero di istanze nell'assieme.
    Se non e' un assieme (nessun NAUO), ritorna {} (ogni body conta 1).

    Args:
        step_path: Path al file STEP.

    Returns:
        dict: body_id -> instance count mapping.
    """
    try:
        with open(step_path, 'r', errors='replace') as f:
            content = f.read()
    except (IOError, OSError):
        return {}

    entities = {}
    for m in re.finditer(r'#(\d+)\s*=\s*(.+?)\s*;', content, re.DOTALL):
        entities[int(m.group(1))] = m.group(2).strip()

    def _etype(val):
        m2 = re.match(r'(\w+)', val)
        return m2.group(1) if m2 else ''

    def _refs(val):
        return [int(x) for x in re.findall(r'#(\d+)', val)]

    # Trova tutti i NAUO: NEXT_ASSEMBLY_USAGE_OCCURRENCE('','','',#parent_pd,#child_pd)
    nauo_ids = [eid for eid, val in entities.items()
                if _etype(val) == 'NEXT_ASSEMBLY_USAGE_OCCURRENCE']
    if not nauo_ids:
        return {}  # Non e' un assieme

    # Conta istanze per ogni ProductDefinition figlio
    pd_instance_count = {}  # product_definition_id -> count
    for nid in nauo_ids:
        refs = _refs(entities.get(nid, ''))
        if len(refs) >= 2:
            child_pd = refs[1]
            pd_instance_count[child_pd] = pd_instance_count.get(child_pd, 0) + 1

    # Mappa ProductDefinition -> SHAPE_DEFINITION_REPRESENTATION -> AdvBrepShapeRep -> body
    # PD -> SDR -> rep -> items -> MSB
    sdr_map = {}  # pd_id -> rep_id
    for eid, val in entities.items():
        if _etype(val) == 'SHAPE_DEFINITION_REPRESENTATION':
            refs = _refs(val)
            if len(refs) >= 2:
                # refs[0] = PRODUCT_DEFINITION_SHAPE, refs[1] = representation
                pds_ref = refs[0]
                pds_val = entities.get(pds_ref, '')
                if _etype(pds_val) == 'PRODUCT_DEFINITION_SHAPE':
                    pds_refs = _refs(pds_val)
                    if pds_refs:
                        pd_id = pds_refs[-1]  # product_definition
                        sdr_map[pd_id] = refs[1]

    # Strategia: SHAPE_REPRESENTATION e ADVANCED_BREP_SHAPE_REPRESENTATION
    # condividono lo stesso context (ultimo ref). Usiamo il context come chiave
    # per collegare PD -> SR -> context <- ABSR -> MSB body.

    # Mappa context_id -> body_ids (da ADVANCED_BREP_SHAPE_REPRESENTATION)
    context_to_bodies = {}  # context_ref -> [body_id, ...]
    for eid, val in entities.items():
        if _etype(val) == 'ADVANCED_BREP_SHAPE_REPRESENTATION':
            refs = _refs(val)
            if not refs:
                continue
            context_ref = refs[-1]
            for r in refs[:-1]:
                if _etype(entities.get(r, '')) == 'MANIFOLD_SOLID_BREP':
                    context_to_bodies.setdefault(context_ref, []).append(r)

    # Mappa PD -> SR -> context -> bodies
    body_instance_count = {}  # body_id -> instance count
    for pd_id, count in pd_instance_count.items():
        rep_id = sdr_map.get(pd_id)
        if not rep_id:
            continue
        rep_val = entities.get(rep_id, '')
        rep_refs = _refs(rep_val)
        if not rep_refs:
            continue
        # Il context e' l'ultimo ref della SHAPE_REPRESENTATION
        context_ref = rep_refs[-1]
        # Cerca bodies con lo stesso context
        for body_id in context_to_bodies.get(context_ref, []):
            body_instance_count[body_id] = count
        # Fallback diretto: cerca MSB tra i ref della rep
        for ref in rep_refs:
            ref_val = entities.get(ref, '')
            if _etype(ref_val) == 'MANIFOLD_SOLID_BREP':
                body_instance_count[ref] = count

    return body_instance_count
