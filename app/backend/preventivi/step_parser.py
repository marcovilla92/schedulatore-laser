"""STEP file geometry parser.

Extracts edge wireframes (LINE + CIRCLE interpolated) and face polygons
(from ADVANCED_FACE edge loops) for solid-like rendering.
"""

import logging
import math
import re

logger = logging.getLogger(__name__)


def parse_step_geometry(step_path: str) -> dict:
    """Parse STEP file and extract 3D geometry for visualization.

    Extracts edge wireframes (LINE + CIRCLE interpolated) and face polygons
    (from ADVANCED_FACE edge loops) for solid-like rendering.

    Args:
        step_path: Path to the STEP file.

    Returns:
        dict with keys:
            'bodies': list of dicts, each with:
                'segments': list of [(x,y,z), ...] polylines (edges)
                'faces': list of [(x,y,z), ...] polygon vertex lists
            'weld_edges': list of [(x,y,z), ...] polylines for contact edges
            'n_corpi': int
            'errore': str or None
    """
    try:
        with open(step_path, 'r', errors='replace') as f:
            content = f.read()
    except (IOError, OSError) as e:
        return {'bodies': [], 'weld_edges': [], 'n_corpi': 0, 'errore': str(e)}

    # Parse entities
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

    def _vec_sub(a, b):
        return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

    def _vec_dot(a, b):
        return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

    def _vec_cross(a, b):
        return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

    def _vec_norm(a):
        ln = math.sqrt(a[0]**2 + a[1]**2 + a[2]**2)
        return (a[0]/ln, a[1]/ln, a[2]/ln) if ln > 1e-12 else (0,0,0)

    def _interpolate_arc(center, axis_normal, radius, p1, p2, n_pts=24):
        """Interpolate circular arc from p1 to p2 around center.
        Returns list of 3D points on the arc."""
        ax = _vec_norm(axis_normal)
        # Build local coordinate system on the circle plane
        v1 = _vec_sub(p1, center)
        v1_len = math.sqrt(_vec_dot(v1, v1))
        if v1_len < 1e-12:
            return [p1, p2]
        u = _vec_norm(v1)
        v = _vec_cross(ax, u)
        v = _vec_norm(v)

        # Angles of p1 and p2 in local coords
        d2 = _vec_sub(p2, center)
        angle1 = 0.0  # p1 is at angle 0 by construction
        angle2 = math.atan2(_vec_dot(d2, v), _vec_dot(d2, u))
        if angle2 <= 1e-9:
            angle2 += 2 * math.pi  # Always go CCW

        points = []
        for i in range(n_pts + 1):
            t = angle1 + (angle2 - angle1) * i / n_pts
            cos_t = math.cos(t)
            sin_t = math.sin(t)
            px = center[0] + radius * (cos_t * u[0] + sin_t * v[0])
            py = center[1] + radius * (cos_t * u[1] + sin_t * v[1])
            pz = center[2] + radius * (cos_t * u[2] + sin_t * v[2])
            points.append((px, py, pz))
        return points

    # Find solid bodies (MANIFOLD_SOLID_BREP)
    body_ids = [eid for eid, val in entities.items()
                if _etype(val) == 'MANIFOLD_SOLID_BREP']

    # Also find CLOSED_SHELL not referenced by any MANIFOLD_SOLID_BREP
    # Some exporters (SolidWorks sheet metal) use CLOSED_SHELL directly
    msb_child_shells = set()
    for bid in body_ids:
        for r in _refs(entities.get(bid, '')):
            msb_child_shells.add(r)
    for eid, val in entities.items():
        if _etype(val) == 'CLOSED_SHELL' and eid not in msb_child_shells:
            body_ids.append(eid)
    # Also SHELL_BASED_SURFACE_MODEL (open shells used for thin bodies)
    for eid, val in entities.items():
        if _etype(val) == 'SHELL_BASED_SURFACE_MODEL':
            body_ids.append(eid)

    if not body_ids:
        return {'bodies': [], 'weld_edges': [], 'n_corpi': 0,
                'errore': 'Nessun corpo solido trovato'}

    def _get_face_refs(bid):
        """Get ADVANCED_FACE refs from a body, handling different entity types."""
        val = entities.get(bid, '')
        etype = _etype(val)
        refs_list = _refs(val)
        if not refs_list:
            return []
        if etype == 'MANIFOLD_SOLID_BREP':
            # MANIFOLD_SOLID_BREP -> CLOSED_SHELL -> faces
            cs_ref = refs_list[-1]
            cs_val = entities.get(cs_ref, '')
            return _refs(cs_val)
        elif etype in ('CLOSED_SHELL', 'OPEN_SHELL'):
            # Direct shell -> faces are direct children
            return refs_list
        elif etype == 'SHELL_BASED_SURFACE_MODEL':
            # SHELL_BASED_SURFACE_MODEL -> shells -> faces
            all_faces = []
            for sr in refs_list:
                sv = entities.get(sr, '')
                if _etype(sv) in ('CLOSED_SHELL', 'OPEN_SHELL'):
                    all_faces.extend(_refs(sv))
            return all_faces
        else:
            # Fallback: try child -> grandchild
            cs_ref = refs_list[-1]
            cs_val = entities.get(cs_ref, '')
            return _refs(cs_val)

    def _get_body_edges(bid):
        """Extract edges from a body, returning raw edge data with curve info."""
        face_refs = _get_face_refs(bid)
        edges = []
        seen_ec = set()
        for fref in face_refs:
            fval = entities.get(fref, '')
            if _etype(fval) != 'ADVANCED_FACE':
                continue
            for bref in _refs(fval):
                bval = entities.get(bref, '')
                bt = _etype(bval)
                if bt not in ('FACE_OUTER_BOUND', 'FACE_BOUND'):
                    continue
                el_ref = _refs(bval)[0]
                el_val = entities.get(el_ref, '')
                if _etype(el_val) != 'EDGE_LOOP':
                    continue
                for oe_ref in _refs(el_val):
                    oe_val = entities.get(oe_ref, '')
                    if _etype(oe_val) != 'ORIENTED_EDGE':
                        continue
                    oe_refs = _refs(oe_val)
                    if not oe_refs:
                        continue
                    ec_ref = oe_refs[-1]
                    if ec_ref in seen_ec:
                        continue
                    ec_val = entities.get(ec_ref, '')
                    if _etype(ec_val) != 'EDGE_CURVE':
                        continue
                    refs2 = _refs(ec_val)
                    if len(refs2) < 3:
                        continue
                    v1_refs = _refs(entities.get(refs2[0], ''))
                    v2_refs = _refs(entities.get(refs2[1], ''))
                    p1 = _coords(entities.get(v1_refs[0], '')) if v1_refs else None
                    p2 = _coords(entities.get(v2_refs[0], '')) if v2_refs else None
                    if p1 and p2:
                        seen_ec.add(ec_ref)
                        curve_ref = refs2[2]
                        curve_val = entities.get(curve_ref, '')
                        curve_type = _etype(curve_val)
                        edges.append((ec_ref, p1, p2, curve_type, curve_ref))
        return edges

    def _edge_to_polyline(ec_ref, p1, p2, curve_type, curve_ref):
        """Convert an edge to a polyline (list of 3D points)."""
        if curve_type == 'CIRCLE':
            # CIRCLE('name', #axis2_placement, radius)
            cval = entities.get(curve_ref, '')
            crefs = _refs(cval)
            # Extract radius
            rnums = re.findall(r'([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)', cval)
            radius = float(rnums[-1]) if rnums else 0
            if crefs and radius > 0:
                # Get axis placement -> origin + axis direction
                ax_val = entities.get(crefs[0], '')
                ax_refs = _refs(ax_val)
                if len(ax_refs) >= 2:
                    center = _coords(entities.get(ax_refs[0], ''))
                    axis_dir = _coords(entities.get(ax_refs[1], ''))
                    if center and axis_dir:
                        return _interpolate_arc(center, axis_dir, radius, p1, p2, n_pts=24)
        # Fallback: straight line
        return [p1, p2]

    def _get_body_planes(bid):
        face_refs = _get_face_refs(bid)
        planes = []
        for fref in face_refs:
            fval = entities.get(fref, '')
            if _etype(fval) != 'ADVANCED_FACE':
                continue
            for sr in _refs(fval):
                sv = entities.get(sr, '')
                if _etype(sv) != 'PLANE':
                    continue
                ax_ref = _refs(sv)[0]
                ax_refs = _refs(entities.get(ax_ref, ''))
                if len(ax_refs) >= 2:
                    origin = _coords(entities.get(ax_refs[0], ''))
                    normal = _coords(entities.get(ax_refs[1], ''))
                    if origin and normal:
                        planes.append((origin, normal))
        return planes

    def _get_body_face_planes(bid):
        """Get PLANE faces with their finite bounding boxes (from edge loop vertices)."""
        face_refs = _get_face_refs(bid)
        face_planes = []
        for fref in face_refs:
            fval = entities.get(fref, '')
            if _etype(fval) != 'ADVANCED_FACE':
                continue
            # Find PLANE surface
            plane_origin = plane_normal = None
            for sr in _refs(fval):
                sv = entities.get(sr, '')
                if _etype(sv) == 'PLANE':
                    ax_ref = _refs(sv)[0]
                    ax_refs = _refs(entities.get(ax_ref, ''))
                    if len(ax_refs) >= 2:
                        plane_origin = _coords(entities.get(ax_refs[0], ''))
                        plane_normal = _coords(entities.get(ax_refs[1], ''))
                    break
            if not plane_origin or not plane_normal:
                continue
            # Collect all vertex points from this face's edge loops
            face_pts = []
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
                    refs2 = _refs(ec_val)
                    if len(refs2) < 2:
                        continue
                    for vref_idx in (0, 1):
                        v_refs = _refs(entities.get(refs2[vref_idx], ''))
                        if v_refs:
                            pt = _coords(entities.get(v_refs[0], ''))
                            if pt:
                                face_pts.append(pt)
            if not face_pts:
                continue
            fmin = tuple(min(p[k] for p in face_pts) for k in range(3))
            fmax = tuple(max(p[k] for p in face_pts) for k in range(3))
            face_planes.append((plane_origin, plane_normal, fmin, fmax))
        return face_planes

    def _get_body_faces(bid):
        """Extract face polygons from a body for solid rendering.
        Returns list of vertex-lists (one per face outer boundary)."""
        face_refs = _get_face_refs(bid)
        faces = []
        for fref in face_refs:
            fval = entities.get(fref, '')
            if _etype(fval) != 'ADVANCED_FACE':
                continue
            # Get outer bound vertices (ordered loop)
            for bref in _refs(fval):
                bval = entities.get(bref, '')
                if _etype(bval) != 'FACE_OUTER_BOUND':
                    continue
                el_ref = _refs(bval)[0]
                el_val = entities.get(el_ref, '')
                if _etype(el_val) != 'EDGE_LOOP':
                    continue
                # Collect ordered polyline from edge loop
                face_pts = []
                for oe_ref in _refs(el_val):
                    oe_val = entities.get(oe_ref, '')
                    if _etype(oe_val) != 'ORIENTED_EDGE':
                        continue
                    oe_refs = _refs(oe_val)
                    if not oe_refs:
                        continue
                    ec_ref = oe_refs[-1]
                    ec_val = entities.get(ec_ref, '')
                    if _etype(ec_val) != 'EDGE_CURVE':
                        continue
                    refs2 = _refs(ec_val)
                    if len(refs2) < 3:
                        continue
                    v1_refs = _refs(entities.get(refs2[0], ''))
                    v2_refs = _refs(entities.get(refs2[1], ''))
                    p1 = _coords(entities.get(v1_refs[0], '')) if v1_refs else None
                    p2 = _coords(entities.get(v2_refs[0], '')) if v2_refs else None
                    if not p1 or not p2:
                        continue
                    curve_ref = refs2[2]
                    curve_val = entities.get(curve_ref, '')
                    curve_type = _etype(curve_val)
                    poly = _edge_to_polyline(ec_ref, p1, p2, curve_type, curve_ref)
                    # Check orientation flag (.T. or .F.)
                    orient_true = '.T.' in oe_val
                    if not orient_true:
                        poly = list(reversed(poly))
                    # Use geometric connectivity to ensure correct stitching
                    if face_pts and poly:
                        last_pt = face_pts[-1]
                        d_start = sum((a - b) ** 2 for a, b in zip(last_pt, poly[0]))
                        d_end = sum((a - b) ** 2 for a, b in zip(last_pt, poly[-1]))
                        if d_end < d_start:
                            poly = list(reversed(poly))
                        face_pts.extend(poly[1:])
                    else:
                        face_pts.extend(poly)
                if len(face_pts) >= 3:
                    faces.append(face_pts)
        return faces

    # Build body data with bounding box
    body_info = {}
    for bid in body_ids:
        raw_edges = _get_body_edges(bid)
        planes = _get_body_planes(bid)
        faces = _get_body_faces(bid)

        segments = []
        total_len = 0
        all_pts = []
        for ec_ref, p1, p2, ctype, cref in raw_edges:
            polyline = _edge_to_polyline(ec_ref, p1, p2, ctype, cref)
            segments.append(polyline)
            total_len += math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))
            all_pts.extend([p1, p2])

        # Bounding box
        if all_pts:
            bbox_min = (min(p[0] for p in all_pts), min(p[1] for p in all_pts), min(p[2] for p in all_pts))
            bbox_max = (max(p[0] for p in all_pts), max(p[1] for p in all_pts), max(p[2] for p in all_pts))
        else:
            bbox_min = bbox_max = (0, 0, 0)

        body_info[bid] = {
            'segments': segments, 'faces': faces, 'raw_edges': raw_edges,
            'planes': planes, 'total_len': total_len,
            'bbox_min': bbox_min, 'bbox_max': bbox_max
        }

    # --- Merge overlapping bodies (SolidWorks splits parts into sub-bodies) ---
    # Bodies with nearly identical bounding boxes are the same physical part.
    BB_TOL = 2.0  # mm tolerance for bbox overlap detection
    def _bbox_similar(b1, b2):
        mn1, mx1 = body_info[b1]['bbox_min'], body_info[b1]['bbox_max']
        mn2, mx2 = body_info[b2]['bbox_min'], body_info[b2]['bbox_max']
        return all(abs(a - b) < BB_TOL for a, b in zip(mn1, mn2)) and \
               all(abs(a - b) < BB_TOL for a, b in zip(mx1, mx2))

    # Group bodies into physical parts
    merged_groups = []  # Each group = list of body_ids
    assigned = set()
    for bid in body_ids:
        if bid in assigned:
            continue
        group = [bid]
        assigned.add(bid)
        for bid2 in body_ids:
            if bid2 not in assigned and _bbox_similar(bid, bid2):
                group.append(bid2)
                assigned.add(bid2)
        merged_groups.append(group)

    # Build visual bodies by merging segments and faces of overlapping bodies
    bodies = []
    merged_body_ids = []  # Representative ID per merged group
    for group in merged_groups:
        merged_segments = []
        merged_faces = []
        for bid in group:
            merged_segments.extend(body_info[bid]['segments'])
            merged_faces.extend(body_info[bid]['faces'])
        bodies.append({'segments': merged_segments, 'faces': merged_faces, 'id': group[0]})
        merged_body_ids.append(group[0])

    # --- Find weld (contact) edges between DISTINCT physical parts ---
    TOL = 0.5  # mm
    MIN_WELD_LEN = 5.0  # mm -- ignore very short contact edges (fillets, chamfers)
    PROX_TOL = 3.0  # mm -- proximity tolerance for bbox overlap check

    def _on_plane(point, origin, normal):
        d = sum((p - o) * n for p, o, n in zip(point, origin, normal))
        return abs(d) < TOL

    def _group_bbox(group):
        """Compute combined bounding box of a merged body group."""
        all_min = [float('inf')] * 3
        all_max = [float('-inf')] * 3
        for bid in group:
            bmin = body_info[bid]['bbox_min']
            bmax = body_info[bid]['bbox_max']
            for k in range(3):
                all_min[k] = min(all_min[k], bmin[k])
                all_max[k] = max(all_max[k], bmax[k])
        return tuple(all_min), tuple(all_max)

    def _bbox_overlap(min1, max1, min2, max2, tol):
        """Compute the overlap zone of two bounding boxes (expanded by tol).
        Returns (overlap_min, overlap_max) or None if no overlap."""
        o_min = [max(min1[k], min2[k]) - tol for k in range(3)]
        o_max = [min(max1[k], max2[k]) + tol for k in range(3)]
        if all(o_min[k] <= o_max[k] for k in range(3)):
            return tuple(o_min), tuple(o_max)
        return None

    def _edge_in_box(p1, p2, box_min, box_max):
        """Check if BOTH endpoints of an edge are within a bounding box."""
        for pt in (p1, p2):
            if not all(box_min[k] <= pt[k] <= box_max[k] for k in range(3)):
                return False
        return True

    def _edge_key(p1, p2, precision=1.0):
        """Create a position-based key for deduplication.
        Rounds coordinates to `precision` mm and sorts endpoints."""
        def _round(pt):
            return tuple(round(c / precision) for c in pt)
        a, b = _round(p1), _round(p2)
        return (min(a, b), max(a, b))

    weld_edges = []
    seen_positions = set()  # Deduplicate by position across ALL body pairs

    for i, group1 in enumerate(merged_groups):
        bbox1_min, bbox1_max = _group_bbox(group1)
        for group2 in merged_groups[i + 1:]:
            bbox2_min, bbox2_max = _group_bbox(group2)

            # Only check pairs whose bounding boxes overlap (proximity check)
            overlap = _bbox_overlap(bbox1_min, bbox1_max, bbox2_min, bbox2_max, PROX_TOL)
            if not overlap:
                continue
            overlap_min, overlap_max = overlap

            all_edges_1 = []
            for bid in group1:
                all_edges_1.extend(body_info[bid]['raw_edges'])

            all_edges_2 = []
            for bid in group2:
                all_edges_2.extend(body_info[bid]['raw_edges'])

            # Get face-bounded planes (with face bbox) for each group
            face_planes_1 = []
            for bid in group1:
                face_planes_1.extend(_get_body_face_planes(bid))
            face_planes_2 = []
            for bid in group2:
                face_planes_2.extend(_get_body_face_planes(bid))

            # Check BOTH directions: edges of A on faces of B, AND edges of B on faces of A
            FACE_TOL = 2.0  # mm tolerance for face bbox check
            check_pairs = [
                (all_edges_1, face_planes_2, bbox1_min, bbox1_max),
                (all_edges_2, face_planes_1, bbox2_min, bbox2_max),
            ]

            for small_edges, large_face_planes, src_bmin, src_bmax in check_pairs:
                seen_ec = set()
                for ec_ref, p1, p2, curve_type, cref in small_edges:
                    if curve_type != 'LINE':
                        continue
                    edge_len = math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))
                    if edge_len < MIN_WELD_LEN:
                        continue
                    # Edge must be within the overlap zone of the two bodies
                    if not _edge_in_box(p1, p2, overlap_min, overlap_max):
                        continue
                    # Filter INNER edges: at least one coordinate of each endpoint
                    # must be at the boundary of the SOURCE body's bbox.
                    # Inner edges (inside tube wall) are not weldable.
                    BOUNDARY_TOL = 1.0
                    is_boundary = False
                    for pt in (p1, p2):
                        for k in range(3):
                            if (abs(pt[k] - src_bmin[k]) < BOUNDARY_TOL or
                                    abs(pt[k] - src_bmax[k]) < BOUNDARY_TOL):
                                is_boundary = True
                                break
                        if is_boundary:
                            break
                    if not is_boundary:
                        continue
                    for origin, normal, fmin, fmax in large_face_planes:
                        if _on_plane(p1, origin, normal) and _on_plane(p2, origin, normal):
                            # BOTH endpoints must be within the FACE's bounding box
                            if (all(fmin[k] - FACE_TOL <= p1[k] <= fmax[k] + FACE_TOL
                                    for k in range(3)) and
                                all(fmin[k] - FACE_TOL <= p2[k] <= fmax[k] + FACE_TOL
                                    for k in range(3))):
                                if ec_ref not in seen_ec:
                                    seen_ec.add(ec_ref)
                                    ekey = _edge_key(p1, p2)
                                    if ekey not in seen_positions:
                                        seen_positions.add(ekey)
                                        weld_edges.append([p1, p2])
                            break

    return {
        'bodies': bodies,
        'weld_edges': weld_edges,
        'n_corpi': len(merged_groups),
        'errore': None
    }
