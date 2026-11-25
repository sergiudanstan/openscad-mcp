"""Pure-Python mesh analysis for OpenSCAD exports (no third-party deps).

Units are whatever the model uses (OpenSCAD convention: millimetres).
"""

from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path

Vec = tuple[float, float, float]
Tri = tuple[Vec, Vec, Vec]

# Densities in g/cm^3 (typical values; filament datasheets vary by a few %).
MATERIAL_DENSITY = {
    "pla": 1.24,
    "petg": 1.27,
    "abs": 1.04,
    "asa": 1.07,
    "tpu": 1.21,
    "nylon": 1.14,
    "pc": 1.20,
    "resin": 1.15,
    "aluminium": 2.70,
    "aluminum": 2.70,
    "steel": 7.85,
    "stainless": 8.00,
    "brass": 8.50,
    "copper": 8.96,
    "titanium": 4.43,
    "wood": 0.70,
}


# ----------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------

def read_stl(path: str | Path) -> list[Tri]:
    """Read a binary or ASCII STL file into a list of triangles."""
    data = Path(path).read_bytes()
    if len(data) >= 84:
        (count,) = struct.unpack_from("<I", data, 80)
        if 84 + 50 * count == len(data):
            tris: list[Tri] = []
            for rec in struct.iter_unpack("<12fH", data[84:]):
                tris.append(((rec[3], rec[4], rec[5]), (rec[6], rec[7], rec[8]), (rec[9], rec[10], rec[11])))
            return tris
    text = data.decode("ascii", errors="replace")
    pts: list[Vec] = [
        (float(x), float(y), float(z))
        for x, y, z in re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", text)
    ]
    return [(pts[i], pts[i + 1], pts[i + 2]) for i in range(0, len(pts) - 2, 3)]


_SVG_PATH = re.compile(r'<path[^>]*\sd="([^"]*)"', re.S)
_SVG_NUM = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def read_svg_contours(path: str | Path) -> list[list[tuple[float, float]]]:
    """Read the polygon contours of an OpenSCAD SVG export (M/L/z paths only).

    OpenSCAD flips Y when writing SVG; it is flipped back here.
    """
    text = Path(path).read_text(errors="replace")
    contours: list[list[tuple[float, float]]] = []
    for d in _SVG_PATH.findall(text):
        for sub in re.split(r"[Mm]", d):
            nums = [float(n) for n in _SVG_NUM.findall(sub)]
            pts = [(nums[i], -nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
            if len(pts) >= 3:
                contours.append(pts)
    return contours


# ----------------------------------------------------------------------
# Vector helpers
# ----------------------------------------------------------------------

def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _r(x: float, nd: int = 6) -> float:
    """Round for reporting, avoiding -0.0."""
    v = round(x, nd)
    return 0.0 if v == 0 else v


def _sig(x: float, digits: int = 9) -> float:
    """Round to significant digits (for values spanning many magnitudes)."""
    if x == 0 or not math.isfinite(x):
        return 0.0 if x == 0 else x
    v = float(f"{x:.{digits}g}")
    return 0.0 if v == 0 else v


# ----------------------------------------------------------------------
# Mesh metrics
# ----------------------------------------------------------------------

@dataclass
class MeshStats:
    triangles: int
    vertices: int
    bbox_min: Vec
    bbox_max: Vec
    area: float
    volume: float
    centroid: Vec | None
    boundary_edges: int
    nonmanifold_edges: int
    misoriented_edges: int
    bodies: int

    @property
    def watertight(self) -> bool:
        return self.triangles > 0 and self.boundary_edges == 0 and self.nonmanifold_edges == 0

    def to_dict(self) -> dict:
        size = tuple(self.bbox_max[i] - self.bbox_min[i] for i in range(3))
        return {
            "triangles": self.triangles,
            "vertices": self.vertices,
            "bbox": {
                "min": [_r(v) for v in self.bbox_min],
                "max": [_r(v) for v in self.bbox_max],
                "size": [_r(v) for v in size],
                "center": [_r((self.bbox_min[i] + self.bbox_max[i]) / 2) for i in range(3)],
            },
            "volume": _r(self.volume, 4),
            "surface_area": _r(self.area, 4),
            "centroid": [_r(v) for v in self.centroid] if self.centroid else None,
            "watertight": self.watertight,
            "bodies": self.bodies,
            "mesh_health": {
                "boundary_edges": self.boundary_edges,
                "nonmanifold_edges": self.nonmanifold_edges,
                "misoriented_edges": self.misoriented_edges,
            },
        }


def mesh_stats(tris: list[Tri]) -> MeshStats:
    """Compute bbox, area, signed volume, centroid, edge health and body count."""
    if not tris:
        zero = (0.0, 0.0, 0.0)
        return MeshStats(0, 0, zero, zero, 0.0, 0.0, None, 0, 0, 0, 0)

    index: dict[Vec, int] = {}
    faces: list[tuple[int, int, int]] = []
    area = 0.0
    vol6 = 0.0
    cx = cy = cz = 0.0
    for a, b, c in tris:
        ia = index.setdefault(a, len(index))
        ib = index.setdefault(b, len(index))
        ic = index.setdefault(c, len(index))
        faces.append((ia, ib, ic))
        cr = _cross(_sub(b, a), _sub(c, a))
        area += math.sqrt(_dot(cr, cr)) / 2
        d = _dot(a, _cross(b, c))
        vol6 += d
        cx += d * (a[0] + b[0] + c[0])
        cy += d * (a[1] + b[1] + c[1])
        cz += d * (a[2] + b[2] + c[2])

    verts = list(index)
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]

    # Edge health: undirected use count and directed duplicates.
    undirected: dict[tuple[int, int], int] = {}
    directed: dict[tuple[int, int], int] = {}
    for f in faces:
        for u, v in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            if u == v:
                continue
            key = (u, v) if u < v else (v, u)
            undirected[key] = undirected.get(key, 0) + 1
            directed[(u, v)] = directed.get((u, v), 0) + 1
    boundary = sum(1 for n in undirected.values() if n == 1)
    nonmanifold = sum(1 for n in undirected.values() if n > 2)
    misoriented = sum(1 for n in directed.values() if n > 1)

    # Bodies: connected components over shared vertices.
    parent = list(range(len(verts)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for f in faces:
        ra, rb, rc = find(f[0]), find(f[1]), find(f[2])
        parent[rb] = ra
        parent[find(rc)] = ra
    used = {i for f in faces for i in f}
    bodies = len({find(i) for i in used})

    volume = vol6 / 6
    centroid = (cx / (4 * vol6), cy / (4 * vol6), cz / (4 * vol6)) if abs(vol6) > 1e-12 else None
    return MeshStats(
        triangles=len(tris),
        vertices=len(verts),
        bbox_min=(min(xs), min(ys), min(zs)),
        bbox_max=(max(xs), max(ys), max(zs)),
        area=area,
        volume=volume,
        centroid=centroid,
        boundary_edges=boundary,
        nonmanifold_edges=nonmanifold,
        misoriented_edges=misoriented,
        bodies=bodies,
    )


def mass_properties(tris: list[Tri], density_g_cm3: float) -> dict:
    """Mass (g), centre of mass (mm) and inertia tensor about the COM (g*mm^2).

    Uses exact polyhedral integrals over signed tetrahedra (origin, a, b, c):
    integral of x x^T over a tetra = det/120 * (sum v v^T + s s^T), s = a+b+c.
    """
    vol6 = 0.0
    m1 = [0.0, 0.0, 0.0]
    m2 = [[0.0] * 3 for _ in range(3)]
    for a, b, c in tris:
        d = _dot(a, _cross(b, c))
        vol6 += d
        s = (a[0] + b[0] + c[0], a[1] + b[1] + c[1], a[2] + b[2] + c[2])
        for i in range(3):
            m1[i] += d * s[i]
            for j in range(3):
                m2[i][j] += d * (a[i] * a[j] + b[i] * b[j] + c[i] * c[j] + s[i] * s[j])
    volume = vol6 / 6
    if abs(volume) < 1e-12:
        return {"error": "Mesh encloses no volume (open, empty or 2D)."}
    com = [m1[i] / 24 / volume for i in range(3)]
    cov = [[m2[i][j] / 120 - volume * com[i] * com[j] for j in range(3)] for i in range(3)]
    rho = density_g_cm3 / 1000.0  # g/mm^3
    mass = rho * volume
    tr = cov[0][0] + cov[1][1] + cov[2][2]
    inertia = [[rho * ((tr if i == j else 0.0) - cov[i][j]) for j in range(3)] for i in range(3)]
    return {
        "volume_mm3": _r(volume, 4),
        "density_g_cm3": density_g_cm3,
        "mass_g": _sig(mass),
        "center_of_mass": [_r(v) for v in com],
        "inertia_about_com_g_mm2": [[_sig(v) if abs(v) > 1e-9 * abs(tr * rho) else 0.0 for v in row] for row in inertia],
        "principal_moments_g_mm2": [_sig(v) for v in _sym_eigenvalues(inertia)],
    }


def _sym_eigenvalues(m: list[list[float]]) -> list[float]:
    """Eigenvalues of a symmetric 3x3 matrix (closed form), ascending."""
    a, b, c = m[0][0], m[1][1], m[2][2]
    d, e, f = m[0][1], m[1][2], m[0][2]
    p1 = d * d + e * e + f * f
    if p1 <= 1e-18 * max(1.0, a * a + b * b + c * c):
        return sorted([a, b, c])
    q = (a + b + c) / 3
    p2 = (a - q) ** 2 + (b - q) ** 2 + (c - q) ** 2 + 2 * p1
    p = math.sqrt(p2 / 6)
    bm = [[(m[i][j] - (q if i == j else 0)) / p for j in range(3)] for i in range(3)]
    det = (bm[0][0] * (bm[1][1] * bm[2][2] - bm[1][2] * bm[2][1])
           - bm[0][1] * (bm[1][0] * bm[2][2] - bm[1][2] * bm[2][0])
           + bm[0][2] * (bm[1][0] * bm[2][1] - bm[1][1] * bm[2][0]))
    r = max(-1.0, min(1.0, det / 2))
    phi = math.acos(r) / 3
    e1 = q + 2 * p * math.cos(phi)
    e3 = q + 2 * p * math.cos(phi + 2 * math.pi / 3)
    return sorted([e1, 3 * q - e1 - e3, e3])


def print_report(
    tris: list[Tri],
    overhang_deg: float = 45.0,
    build_volume: tuple[float, float, float] = (256.0, 256.0, 256.0),
) -> dict:
    """FDM printability digest for the mesh as oriented (Z up, bed at min Z).

    overhang_deg is measured from vertical: a ceiling is 90 deg, a wall 0 deg.
    """
    st = mesh_stats(tris)
    if not st.triangles:
        return {"error": "Empty mesh."}
    zmin = st.bbox_min[2]
    tol = 1e-3
    # 0.01 deg of slack: float32 vertices put faces drawn exactly at the threshold
    # (e.g. a 45 deg chamfer) a hair either side of it.
    limit = math.sin(math.radians(min(90.0, overhang_deg + 0.01)))
    overhang_area = bed_area = 0.0
    overhang_facets = 0
    lowest_overhang: float | None = None
    for a, b, c in tris:
        cr = _cross(_sub(b, a), _sub(c, a))
        n = math.sqrt(_dot(cr, cr))
        if n == 0:
            continue
        nz = cr[2] / n
        tri_area = n / 2
        on_bed = max(a[2], b[2], c[2]) - zmin < tol
        if nz < -0.999 and on_bed:
            bed_area += tri_area
        elif -nz > limit and not on_bed:
            overhang_area += tri_area
            overhang_facets += 1
            z = min(a[2], b[2], c[2])
            lowest_overhang = z if lowest_overhang is None else min(lowest_overhang, z)
    size = [st.bbox_max[i] - st.bbox_min[i] for i in range(3)]
    fits = all(size[i] <= build_volume[i] + 1e-9 for i in range(3))
    issues = []
    if not st.watertight:
        issues.append("Mesh is not watertight; slicers may fill or drop regions.")
    if st.bodies > 1:
        issues.append(f"{st.bodies} separate bodies; check they are meant to print apart.")
    if bed_area <= 0:
        issues.append("No flat face on the bed; the part needs supports or a raft to start.")
    if overhang_area > 0:
        issues.append(f"{overhang_facets} facets overhang more than {overhang_deg} deg from vertical; supports likely needed.")
    if not fits:
        issues.append(f"Size {['%.1f' % s for s in size]} exceeds build volume {list(build_volume)}.")
    return {
        "overhang_threshold_deg": overhang_deg,
        "overhang_area_mm2": _r(overhang_area, 3),
        "overhang_fraction_of_surface": _r(overhang_area / st.area, 4) if st.area else 0.0,
        "lowest_overhang_z": _r(lowest_overhang) if lowest_overhang is not None else None,
        "bed_contact_area_mm2": _r(bed_area, 3),
        "size": [_r(s) for s in size],
        "build_volume": list(build_volume),
        "fits_build_volume": fits,
        "watertight": st.watertight,
        "bodies": st.bodies,
        "issues": issues,
    }


# Plane coordinates of a cut (u, v), right-handed with the normal along +axis,
# as OpenSCAD's projection(cut=true) lays them out after the tool's rotation:
# z-cut -> (x, y); y-cut -> (x, -z); x-cut -> (-z, y).
_SECTION_AXES = {
    "z": (2, lambda p: (p[0], p[1])),
    "y": (1, lambda p: (p[0], -p[2])),
    "x": (0, lambda p: (-p[2], p[1])),
}


def _cut_segments(tris: list[Tri], k: int, offset: float, to2d, on_plane_below: bool) -> list:
    """One directed segment (entry edge, exit edge, entry point, exit point) per
    triangle straddling the plane. Walking a triangle a->b->c, the cut face's
    boundary runs from where the walk enters the kept side (below the plane) to
    where it leaves it, which makes outer loops counter-clockwise and holes
    clockwise in (u, v) for an outward-oriented mesh."""
    segs = []
    for tri in tris:
        d = (tri[0][k] - offset, tri[1][k] - offset, tri[2][k] - offset)
        below = tuple((x <= 0) if on_plane_below else (x < 0) for x in d)
        if below[0] == below[1] == below[2]:
            continue
        entry = leave = None
        for i in range(3):
            j = (i + 1) % 3
            if below[i] == below[j]:
                continue
            p, q, dp, dq = tri[i], tri[j], d[i], d[j]
            # Canonical endpoint order, so both triangles sharing the edge compute
            # the same point and the loop telescopes exactly.
            lo, hi, dlo, dhi = (p, q, dp, dq) if p < q else (q, p, dq, dp)
            t = dlo / (dlo - dhi) if dlo != dhi else 0.0
            pt = to2d((lo[0] + t * (hi[0] - lo[0]), lo[1] + t * (hi[1] - lo[1]), lo[2] + t * (hi[2] - lo[2])))
            if below[j]:
                entry = ((lo, hi), pt)
            else:
                leave = ((lo, hi), pt)
        if entry is not None and leave is not None:
            segs.append((entry[0], leave[0], entry[1], leave[1]))
    return segs


def section(tris: list[Tri], axis: str, offset: float) -> dict | None:
    """Cross-section of a mesh with the plane <axis> = offset, or None if the
    plane does not cut it.

    Area is the shoelace sum over all segments (holes subtract; it does not
    depend on how segments are chained). Segments are chained into loops by
    the mesh edge they cross, never by comparing coordinates; `regions` counts
    the counter-clockwise (outer) loops. A plane lying exactly on a face cuts
    just below it, or just above it when nothing lies below (a bottom face), so
    the face itself is reported either way.
    """
    k, to2d = _SECTION_AXES[axis]
    on_face = any(t[0][k] == offset and t[1][k] == offset and t[2][k] == offset for t in tris)
    segs = _cut_segments(tris, k, offset, to2d, on_plane_below=False)
    if not segs:
        segs = _cut_segments(tris, k, offset, to2d, on_plane_below=True)
    if not segs:
        return None
    area2 = 0.0
    us: list[float] = []
    vs: list[float] = []
    for _, _, (u0, v0), (u1, v1) in segs:
        area2 += u0 * v1 - u1 * v0
        us += (u0, u1)
        vs += (v0, v1)
    scale = max(max(us) - min(us), max(vs) - min(vs))
    if abs(area2) / 2 <= 1e-12 * scale * scale:
        return None

    by_entry: dict = {}
    for idx, seg in enumerate(segs):
        by_entry.setdefault(seg[0], []).append(idx)
    used = [False] * len(segs)
    loops: list[list[tuple[float, float]]] = []
    regions = open_chains = 0
    for start in range(len(segs)):
        if used[start]:
            continue
        pts: list[tuple[float, float]] = []
        cur = start
        while True:
            used[cur] = True
            pts.append(segs[cur][2])
            cands = by_entry.get(segs[cur][1], ())
            nxt = next((c for c in cands if not used[c]), None)
            if nxt is None:
                closed = start in cands
                break
            cur = nxt
        if not closed:
            pts.append(segs[cur][3])
            open_chains += 1
        elif len(pts) >= 3:
            loop2 = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                        for i in range(len(pts)))
            if loop2 / 2 > 1e-12 * scale * scale:
                regions += 1
        loops.append(pts)
    return {
        "area": abs(area2) / 2,
        "bbox_2d": {
            "min": [_r(min(us)), _r(min(vs))],
            "max": [_r(max(us)), _r(max(vs))],
            "size": [_r(max(us) - min(us)), _r(max(vs) - min(vs))],
        },
        "regions": regions,
        "open_chains": open_chains,
        "on_face": on_face,
        "loops": loops,
    }


# Rays sit at an irrational fraction of each grid cell, so they never run
# exactly along an edge shared by two triangles of an axis-aligned CAD face.
_RAY_OX = 0.5 + 0.0137 * math.sqrt(2)
_RAY_OY = 0.5 + 0.0171 * math.sqrt(3)


def _ray_crossings(tris: list[Tri], x0: float, y0: float, hx: float, hy: float, nx: int, ny: int) -> list:
    """cols[j * nx + i] = z values where the vertical ray of cell (i, j) crosses the mesh."""
    cols: list = [None] * (nx * ny)
    xmax, ymax = x0 + nx * hx, y0 + ny * hy
    for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in tris:
        lx, ux = min(ax, bx, cx), max(ax, bx, cx)
        ly, uy = min(ay, by, cy), max(ay, by, cy)
        if ux < x0 or lx > xmax or uy < y0 or ly > ymax:
            continue
        e1x, e1y, e2x, e2y = bx - ax, by - ay, cx - ax, cy - ay
        det = e1x * e2y - e2x * e1y
        if det == 0.0:
            continue  # vertical facet: rays only graze it
        i0 = max(0, math.ceil((lx - x0) / hx - _RAY_OX))
        i1 = min(nx - 1, math.floor((ux - x0) / hx - _RAY_OX))
        j0 = max(0, math.ceil((ly - y0) / hy - _RAY_OY))
        j1 = min(ny - 1, math.floor((uy - y0) / hy - _RAY_OY))
        if i0 > i1 or j0 > j1:
            continue
        inv = 1.0 / det
        for j in range(j0, j1 + 1):
            py = y0 + (j + _RAY_OY) * hy - ay
            row = j * nx
            for i in range(i0, i1 + 1):
                px = x0 + (i + _RAY_OX) * hx - ax
                u = px * e2y - py * e2x
                v = e1x * py - e1y * px
                if det > 0:
                    if u < 0.0 or v < 0.0 or u + v > det:
                        continue
                elif u > 0.0 or v > 0.0 or u + v < det:
                    continue
                z = az + (u * (bz - az) + v * (cz - az)) * inv
                col = cols[row + i]
                if col is None:
                    cols[row + i] = [z]
                else:
                    col.append(z)
    return cols


def ray_overlap(tris_a: list[Tri], tris_b: list[Tri], bbox_a: tuple[Vec, Vec], bbox_b: tuple[Vec, Vec],
                n: int = 64) -> dict:
    """Estimate the overlap volume of two meshes by casting vertical rays on an
    n-cell grid over the overlap of their bounding boxes: along each ray a mesh
    is solid between pairs of sorted crossings. It needs no CGAL, so it works
    on meshes CGAL refuses (non-manifold). Rays crossing a mesh an odd number of
    times (an open mesh) are dropped and counted in `invalid_rays`.

    error_bound is a conservative bound on the volume error from sampling.
    """
    lo = [max(bbox_a[0][i], bbox_b[0][i]) for i in range(3)]
    hi = [min(bbox_a[1][i], bbox_b[1][i]) for i in range(3)]
    extent = [hi[i] - lo[i] for i in range(3)]
    if min(extent) <= 0:
        status = "clear" if min(extent) < 0 else "touching_or_near"
        return {"status": status, "volume": 0.0, "error_bound": 0.0, "cell": [0.0, 0.0], "invalid_rays": 0}
    h = max(extent[0], extent[1]) / n
    nx, ny = max(1, round(extent[0] / h)), max(1, round(extent[1] / h))
    hx, hy = extent[0] / nx, extent[1] / ny
    ca = _ray_crossings(tris_a, lo[0], lo[1], hx, hy, nx, ny)
    cb = _ray_crossings(tris_b, lo[0], lo[1], hx, hy, nx, ny)

    def solid(col: list | None) -> list | None:
        if col is None:
            return []
        if len(col) % 2:
            return None
        col.sort()
        return [(col[k], col[k + 1]) for k in range(0, len(col), 2)]

    lengths = [0.0] * (nx * ny)
    total = mx = my = mz = 0.0
    zlo, zhi = math.inf, -math.inf
    invalid = 0
    for k in range(nx * ny):
        if ca[k] is None or cb[k] is None:
            continue
        ia, ib = solid(ca[k]), solid(cb[k])
        if ia is None or ib is None:
            invalid += 1
            continue
        length = zsum = 0.0
        for a0, a1 in ia:
            for b0, b1 in ib:
                s0, s1 = max(a0, b0), min(a1, b1)
                if s1 > s0:
                    length += s1 - s0
                    zsum += (s1 - s0) * (s0 + s1) / 2
                    zlo, zhi = min(zlo, s0), max(zhi, s1)
        if length:
            lengths[k] = length
            total += length
            mx += length * (lo[0] + (k % nx + 0.5) * hx)
            my += length * (lo[1] + (k // nx + 0.5) * hy)
            mz += zsum
    cell = hx * hy
    # Every cell next to a change in overlap length may be mis-sampled by at most
    # that change: half the sum of neighbour jumps bounds the error.
    jump = 0.0
    for j in range(ny):
        for i in range(nx):
            v = lengths[j * nx + i]
            right = lengths[j * nx + i + 1] if i + 1 < nx else 0.0
            up = lengths[(j + 1) * nx + i] if j + 1 < ny else 0.0
            jump += abs(v - right) + abs(v - up) + (v if i == 0 else 0.0) + (v if j == 0 else 0.0)
    out: dict = {"volume": total * cell, "error_bound": jump * cell / 2, "cell": [hx, hy], "invalid_rays": invalid}
    if total > 0:
        cols = [k for k in range(nx * ny) if lengths[k]]
        ii = [k % nx for k in cols]
        jj = [k // nx for k in cols]
        out.update({
            "status": "interference",
            "centroid": (mx / total, my / total, mz / total),
            "bbox_min": (lo[0] + min(ii) * hx, lo[1] + min(jj) * hy, zlo),
            "bbox_max": (lo[0] + (max(ii) + 1) * hx, lo[1] + (max(jj) + 1) * hy, zhi),
        })
    else:
        out["status"] = "indeterminate" if invalid else "touching_or_near"
    return out


def contours_stats(contours: list[list[tuple[float, float]]]) -> dict:
    """Area, perimeter and bbox of 2D contours (holes have opposite winding)."""
    if not contours:
        return {"contours": 0, "area": 0.0, "perimeter": 0.0, "bbox": None}
    signed = 0.0
    perim = 0.0
    xs: list[float] = []
    ys: list[float] = []
    for pts in contours:
        s = 0.0
        for i, (x0, y0) in enumerate(pts):
            x1, y1 = pts[(i + 1) % len(pts)]
            s += x0 * y1 - x1 * y0
            perim += math.hypot(x1 - x0, y1 - y0)
        signed += s / 2
        xs += [p[0] for p in pts]
        ys += [p[1] for p in pts]
    return {
        "contours": len(contours),
        "area": _r(abs(signed), 4),
        "perimeter": _r(perim, 4),
        "bbox": {
            "min": [_r(min(xs)), _r(min(ys))],
            "max": [_r(max(xs)), _r(max(ys))],
            "size": [_r(max(xs) - min(xs)), _r(max(ys) - min(ys))],
        },
    }
