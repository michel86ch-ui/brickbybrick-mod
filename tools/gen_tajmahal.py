"""Taj Mahal from Brick by Brick bricks: preview data for the 3D page (the mod blueprint follows once the design stands).

Usage:  py gen_tajmahal.py [scale]      (default 1.35)  ->  ../blueprints/tajmahal_preview.json
        py build_preview.py taj         ->  ../docs/taj-mahal/index.html

Coordinates: cells of 0.21 m (the game's grid), x to the right, z away from the front (the main entrance faces -z),
y up from the ground; the center of the platform is the origin. Straight walls are cells packed into 2x1 blocks
(running bond); round parts (hall, drum, domes, minarets, chhatris) are rings of blocks at small angles, which the
game allows (it checks no geometry when a brick is set, see gen_notredame.py 4b).
"""
import collections
import json
import math
import os
import sys

S = float(sys.argv[1]) if len(sys.argv) > 1 else 1.35
CELL = 0.21
HERE = os.path.dirname(os.path.abspath(__file__))


def c(v):
    return int(round(v * S))


def c2(v):
    return 2 * int(round(v * S / 2))


# ---- Dimensions (cells at scale 1, about 1:4 of the real building) ----
PL = c2(57)          # half side of the platform
PH = c2(8)           # platform height (top of the deck)
M = c2(34)           # half side of the mausoleum
CH = c(9)            # chamfer: the corners are cut by this many cells
HM = c(38)           # wall height above the platform
PW = c2(12)          # main arch (pishtaq) opening width
PHA = c(26)          # main arch: height up to where the point starts
PD = c(6)            # depth of the main recess (iwan)
PF = c(4)            # frame around the main arch on the face
PUP = c(6)           # the pishtaq frame rises this far above the roof
RH = c(11)           # radius of the central hall and the drum (cells)
DH = c(10)           # drum height
DOME_H = c(30)       # onion dome height
RM0, RM1 = 4.6 * S, 3.9 * S   # minaret radius at the foot and at the top gallery (cells)
MIN_H = c(54)        # minaret height up to the top gallery
MO = c(8)            # minaret center: this far in from the platform edge
Y0 = PH              # floor of the mausoleum (top of the platform)
Y_ROOF = Y0 + HM     # roof slab: one row of 2x1 blocks (the 4x2x2 blocks are for the platform)
ROOF_TOP = Y_ROOF + 1

vox = {}             # (x, y, z) -> material of a cell
pieces = []          # (key, x, y, z, yaw, pitch, part) in meters / degrees: blocks not on the grid
scaffold = []        # (cx, cy, cz, sx, sy, sz[, pitch, yaw, roll, walkable]) meters, kept when the building is finished
temp_scaffold = []   # the same, but removed by the mod once every site of the building is complete
part_cells = {}      # (x, y, z) -> part


def setc(x, y, z, mat, part):
    vox[(x, y, z)] = mat
    part_cells[(x, y, z)] = part


def clear(x, y, z):
    vox.pop((x, y, z), None)
    part_cells.pop((x, y, z), None)


# ---- 1) Platform: grey 4x2x2 blocks, a terracotta base course, the deck on top ----
for y in range(PH):
    for x in range(-PL, PL):
        for z in range(-PL, PL):
            edge = x < -PL + 2 or x >= PL - 2 or z < -PL + 2 or z >= PL - 2
            if y >= PH - 2 or edge:
                setc(x, y, z, "R" if y < 2 else "Q", "Platform")


# ---- 2) Mausoleum: octagon (square with cut corners), walls one cell thick ----
def nearest(x, z):
    """Distance (cells) from the vertical axis to the nearest point of cell (x, z)."""
    px = 0.0 if x <= 0 <= x + 1 else min(abs(x), abs(x + 1))
    pz = 0.0 if z <= 0 <= z + 1 else min(abs(z), abs(z + 1))
    return math.hypot(px, pz)


def farthest(x, z):
    """Distance (cells) from the vertical axis to the farthest corner of cell (x, z)."""
    return max(math.hypot(px, pz) for px in (x, x + 1) for pz in (z, z + 1))


def face_frame(f, half=None):
    """Face f (0 front -z, 1 right +x, 2 back +z, 3 left -x) of a square of half side `half` (default: the
    mausoleum): maps (u along the face, d into the building) to cells. u runs from -half to half - 1 left to right as
    seen from outside; d = 0 is the wall itself."""
    h = M if half is None else half
    if f == 0:
        return lambda u, d: (u, -h + d)
    if f == 1:
        return lambda u, d: (h - 1 - d, u)
    if f == 2:
        return lambda u, d: (-1 - u, h - 1 - d)
    return lambda u, d: (-h + d, -1 - u)


RESERVED = set()     # (x, z) columns inside recesses: the floor between the storeys leaves them free
# Slabs end before the chamfer walls: the walls' centre line runs at |x| + |z| = 2M - CH - 1 (cell centres) and is half a
# cell thick across; a cell reaches 1 further in |x| + |z| than its centre. A small gap stays, no block inside a wall.
CHAMFER_SLAB = 2 * M - CH - 1 - 0.5 * math.sqrt(2) - 1.0


U_FACE = M - CH                      # the straight part of a face: u in [-U_FACE, U_FACE)


def pointed(w, h):
    """Open cells of a pointed opening: rows y (from 0) -> half widths; the point closes one cell per row."""
    rows = {}
    for y in range(h):
        rows[y] = w // 2
    for k in range(1, w // 2 + 1):
        rows[h - 1 + k] = w // 2 - k
    return rows


def is_open(rows, u, y):
    hw = rows.get(y)
    return hw is not None and hw > 0 and -hw <= u < hw


def recess(f, uc, w, y0, h, depth, part, door=None, base=None):
    """Arched recess (iwan or niche) in face f: opening in the wall, back wall at depth, side walls, and a vault
    shell one cell thick along the arch line. door = (w, h) opening in the back wall. The back and side walls start
    at base (default: the floor of the opening) and run up to the point, so a recess higher up stands on walls down
    to the platform; a recess above the platform gets a floor."""
    if base is None:
        base = y0
    cell = face_frame(f)
    for u in range(-w // 2 - 1, w // 2 + 1):
        for d in range(0, depth + 1):
            RESERVED.add(cell(uc + u, d))
    rows = pointed(w, h)
    top = max(rows) + 1
    for (yy, hw) in rows.items():
        for u in range(-hw, hw):
            clear(*xz(cell(uc + u, 0), y0 + yy))
    drows = pointed(*door) if door else {}
    for u in range(-w // 2 - 1, w // 2 + 1):
        # arch line: first row above the opening at this u
        yy = 0
        while is_open(rows, u, yy):
            yy += 1
        for d in range(1, depth):
            if -w // 2 <= u < w // 2:
                setc(*xz(cell(uc + u, d), y0 + yy), "S", part)            # vault shell
                if y0 > Y0:
                    setc(*xz(cell(uc + u, d), y0 - 1), "S", part)        # floor
            else:
                for y in range(base, y0 + top):
                    setc(*xz(cell(uc + u, d), y), "S", part)             # side walls
        for y in range(base, y0 + yy + 1):
            if not is_open(drows, u, y - y0):
                setc(*xz(cell(uc + u, depth), y), "S", part)             # back wall


def xz(p, y):
    return (p[0], y, p[1])


for f in range(4):
    cell = face_frame(f)
    for u in range(-U_FACE, U_FACE):
        for y in range(Y0, Y_ROOF):
            if y % 2 and u in (-U_FACE, U_FACE - 1):
                continue                     # odd rows: the chamfer wall takes the end cell (corner bonded like an L)
            setc(*xz(cell(u, 0), y), "S", "Walls")

# Main arch (pishtaq) with its recess, a door and a lattice window above it
for f in range(4):
    recess(f, 0, PW, Y0, PHA, PD, "Walls", door=(c2(6), c(12)))
    cell = face_frame(f)
    jy0 = Y0 + c(12) + c2(6) // 2 + 3
    for u in range(-c2(6) // 2, c2(6) // 2):
        for y in range(jy0, jy0 + c(6)):
            if u % 2 == 0 and (y - jy0) % 2 == 0:
                clear(*xz(cell(u, PD), y))                                # jali: openings between bars

# Two storeys of smaller niches on each side of the main arch
L_SIDE = U_FACE - (PW // 2 + PF)
NW = 2 * ((L_SIDE - 4) // 2)
NUC = PW // 2 + PF + L_SIDE // 2
NH = (HM - 6) // 2 - NW // 2
for f in range(4):
    for s in (-1, 1):
        for storey in (0, 1):
            recess(f, s * NUC, NW, Y0 + 2 + storey * (HM // 2), NH, c(3), "Walls", base=Y0)

# Inlays on the faces: a plum band round each arch and the pishtaq frame (calligraphy), dots of colour in the
# spandrels (pietra dura)
for f in range(4):
    cell = face_frame(f)
    rows = pointed(PW, PHA)
    band = set()
    for (yy, hw) in rows.items():                 # two beige cells between the opening and the band
        for u in (-hw - 3, hw + 2):
            band.add((u, yy))
    apex = max(rows) + 1
    for u in range(-3, 3):
        band.add((u, apex + 2))
    fx = PW // 2 + PF - 2
    for y in range(0, HM + PUP - 2):
        band.add((-fx - 1, y))
        band.add((fx, y))
    for u in range(-fx - 1, fx + 1):
        band.add((u, HM + PUP - 2))
    for (u, yy) in band:
        p = xz(cell(u, 0), Y0 + yy)
        if p in vox:
            vox[p] = "D"
    for u in range(-fx, fx):
        for yy in range(apex + 2, HM + PUP - 3):
            p = xz(cell(u, 0), Y0 + yy)
            if p in vox and vox[p] == "S" and (u + yy) % 4 == 0 and (u - yy) % 4 == 0:
                vox[p] = "U" if (u // 4 + yy // 4) % 2 else "G"
    for s in (-1, 1):
        for storey in (0, 1):
            nrows = pointed(NW, NH)
            for (yy, hw) in nrows.items():
                for u in (-hw - 3, hw + 2):
                    p = xz(cell(s * NUC + u, 0), Y0 + 2 + storey * (HM // 2) + yy)
                    if p in vox:
                        vox[p] = "D"

# Pishtaq frame above the roof, with a row of merlons
for f in range(4):
    cell = face_frame(f)
    fx = PW // 2 + PF
    for u in range(-fx, fx):
        for y in range(Y_ROOF, ROOF_TOP + PUP):
            setc(*xz(cell(u, 0), y), "S", "Roof")
        if u % 2 == 0:
            setc(*xz(cell(u, 0), ROOF_TOP + PUP), "S", "Roof")

# Inside: two storeys round the central hall, as in the original. A square ring of arcades (pointed arches on piers)
# halfway between the hall and the outer walls carries the floor between the storeys, and a second ring above it the
# roof; the floor lies at the level of the upper niches' floors and leaves the hall and the recesses free.
Y_MID = Y0 + HM // 2 + 1
A_HALF = 2 * ((RH + M - PD) // 4)
ARCH_CENTERS = [10 * k for k in range(-((A_HALF - 7) // 10), (A_HALF - 7) // 10 + 1)]  # symmetric, one on the axis;
# piers of four cells between the arches, so their rows alternate (2+2, 1+2+1)
for (ya, yb) in ((Y0, Y_MID), (Y_MID + 1, Y_ROOF)):
    arch_rows = pointed(c2(4.5), (yb - ya) - 5)
    for f in range(4):
        cell = face_frame(f, A_HALF)
        for u in range(-A_HALF, A_HALF):
            for y in range(ya, yb):
                if any(is_open(arch_rows, u - uc, y - ya) for uc in ARCH_CENTERS):
                    continue
                setc(*xz(cell(u, 0), y), "S", "Arcades")
for x in range(-M + 1, M - 1):
    for z in range(-M + 1, M - 1):
        cx, cz = x + 0.5, z + 0.5
        if abs(cx) + abs(cz) > CHAMFER_SLAB or nearest(x, z) < RH + 0.9 or (x, z) in RESERVED:
            continue
        if (x, Y_MID, z) not in vox:
            setc(x, Y_MID, z, "S", "Floor")

# Roof slab (one row of 2x1 blocks), open over the central hall, and a parapet with merlons on the straight faces
for x in range(-M, M):
    for z in range(-M, M):
        cx, cz = x + 0.5, z + 0.5
        if abs(cx) + abs(cz) > CHAMFER_SLAB:
            continue
        if nearest(x, z) < RH + 0.9:                  # up to the drum; rings on top cover the stepped edge
            continue
        setc(x, Y_ROOF, z, "S", "Roof")
for f in range(4):
    cell = face_frame(f)
    for u in range(-U_FACE, U_FACE):
        if abs(u + 0.5) < PW // 2 + PF or (ROOF_TOP % 2 and u in (-U_FACE, U_FACE - 1)):
            continue
        setc(*xz(cell(u, 0), ROOF_TOP), "S", "Roof")
        if u % 2 == 0:
            setc(*xz(cell(u, 0), ROOF_TOP + 1), "S", "Roof")


# ---- 3) Pieces off the grid: chamfer walls, rings, domes ----
def yaw_along(dx, dz, key):
    """Yaw that turns a block's long axis along (dx, dz). S2, D2, U2 are long along z; G2, T2, gold2 along x."""
    a = math.degrees(math.atan2(dx, dz))
    return a - 90 if key in ("G2", "T2", "gold2") else a


def line_wall(p0, p1, y0, y1, part, color=None, lead_half=None):
    """Straight wall of 2x1 blocks from p0 to p1 (centre line, meters) in running bond, rows y0..y1 (cells).
    color(u, y) -> key or None picks inlay blocks by position along the wall (u in cells). lead_half: start every row
    with a 1x1 (True), never (False), or in odd rows (None, running bond)."""
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dz)
    ux, uz = dx / length, dz / length
    n_cells = length / CELL
    for y in range(y0, y1):
        lead = (y % 2 == 1) if lead_half is None else lead_half
        sizes = ([1] if lead else []) + [2] * int((n_cells - (1 if lead else 0)) // 2)
        rest = n_cells - sum(sizes)
        if rest >= 0.5:
            sizes.append(1 if rest < 1.5 else 2)
        f = n_cells / sum(sizes)
        u = 0.0
        for s in sizes:
            mid = u + s * f / 2
            key = "S2" if s == 2 else "S1"
            if color:
                k2 = color(mid, y)
                if k2:
                    key = {"D": "D2", "G": "G2", "U": "U2"}[k2] if s == 2 else {"D": "D1", "G": "G1", "U": "U1"}[k2]
            pieces.append((key, p0[0] + ux * mid * CELL, (y + 0.5) * CELL, p0[1] + uz * mid * CELL,
                           yaw_along(ux, uz, key), 0, part))
            u += s * f


# Chamfer walls: from the end of one face to the start of the next, with two blind niches outlined in plum
CHAMFER_MIDS = []
for k in range(4):
    a0 = face_frame(k)(U_FACE - 1, 0)
    a1 = face_frame((k + 1) % 4)(-U_FACE, 0)
    p0 = ((a0[0] + 0.5) * CELL, (a0[1] + 0.5) * CELL)
    p1 = ((a1[0] + 0.5) * CELL, (a1[1] + 0.5) * CELL)
    sx, sz = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(sx, sz)
    # start and end half a cell further, so the corners close
    q0 = (p0[0] + sx / ln * 0.5 * CELL, p0[1] + sz / ln * 0.5 * CELL)
    q1 = (p1[0] - sx / ln * 0.5 * CELL, p1[1] - sz / ln * 0.5 * CELL)
    L = math.hypot(q1[0] - q0[0], q1[1] - q0[1]) / CELL
    nw = 2 * int((L - 4) // 2)
    nrows = pointed(nw, NH)

    def chamfer_color(u, y, L=L, nrows=nrows, nw=nw):
        for storey in (0, 1):
            yy = y - (Y0 + 2 + storey * (HM // 2))
            uu = u - L / 2
            hw = nrows.get(yy)
            if hw is not None and abs(abs(uu) - (hw + 0.5)) < 0.6:
                return "D"
            if hw is not None and abs(uu) < hw and (int(uu + 50) + yy) % 3 == 0:
                return "G" if yy % 2 else "U"
        return None
    # Bonded with the faces: even rows run between the faces' end cells, odd rows one cell further at both ends (where
    # the faces stop a cell short) and start with a 2x1 across the corner, so no joint runs through from bottom to top
    r0 = (p0[0] - sx / ln * 0.5 * CELL, p0[1] - sz / ln * 0.5 * CELL)
    r1 = (p1[0] + sx / ln * 0.5 * CELL, p1[1] + sz / ln * 0.5 * CELL)
    for y in range(Y0, ROOF_TOP + 1):
        wall = y < ROOF_TOP
        colour = (chamfer_color if y % 2 == 0 else (lambda u, yy, f=chamfer_color: f(u - 1.0, yy))) if wall else None
        line_wall(q0 if y % 2 == 0 else r0, q1 if y % 2 == 0 else r1, y, y + 1, "Walls" if wall else "Roof", colour,
                  lead_half=False)
    CHAMFER_MIDS.append(((q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2))


def ring(r, y, part, key2="S2", key1="S1", offset=0.5, gaps=(), lift=0.0):
    """Full ring of 2x1 blocks along a circle of radius r (meters), one row at cell height y; offset shifts every
    other row by half a block (running bond). gaps = [(phi_center_deg, half_width_m)] left open; lift raises the row
    a little (meters), so its top does not lie in the plane of blocks it overlaps (flickering)."""
    small = r < 0.45                      # a 2x1 is too long for such a ring: 1x1 blocks, which only touch
    n = max(4, int(round(2 * math.pi * r / ((1 if small else 2) * CELL))))
    if small:
        key2 = key1
    for i in range(n):
        phi = (i + (offset if y % 2 else 0)) * 360.0 / n
        a = math.radians(phi)
        skip = False
        for (pc, hw) in gaps:
            d = math.radians((phi - pc + 180) % 360 - 180) * r
            if abs(d) < hw:
                skip = True
        if skip:
            continue
        x, z = r * math.cos(a), r * math.sin(a)
        pieces.append((key2, x, (y + 0.5) * CELL + lift, z, yaw_along(-math.sin(a), math.cos(a), key2), 0, part))


def sizes_for(length):
    n2 = int(length // 2)
    rest = length - 2 * n2
    return [2] * n2 + ([2] if rest >= 1.5 else [1] if rest >= 0.5 else [])


def ring_row(r, y, part, gaps, key2="S2", key1="S1"):
    """One row of a ring wall with openings (gaps = [(phi_center_deg, half_width_m)]): every free arc is laid in
    running bond, with a 1x1 at both ends in every other row, so the jambs of the openings are straight."""
    U = 2 * math.pi * r / CELL
    spans = sorted(((math.radians(pc) * r / CELL - hw / CELL) % U, 2 * hw / CELL) for (pc, hw) in gaps)
    for k, (start, width) in enumerate(spans):
        a = start + width
        b = spans[(k + 1) % len(spans)][0] + (U if k + 1 == len(spans) else 0)
        length = b - a
        if length <= 0.3:
            continue
        sizes = [1] + sizes_for(length - 2) + [1] if y % 2 and length >= 3 else sizes_for(length)
        if not sizes:
            continue
        f = length / sum(sizes)
        u = a
        for s in sizes:
            ang = (u + s * f / 2) * CELL / r
            key = key2 if s == 2 else key1
            pieces.append((key, r * math.cos(ang), (y + 0.5) * CELL, r * math.sin(ang),
                           yaw_along(-math.sin(ang), math.cos(ang), key), 0, part))
            u += s * f


def ring_at(cx, cz, r, y, part, key2="S2", gaps=()):
    before = len(pieces)
    ring(r, y, part, key2=key2, gaps=gaps)
    for i in range(before, len(pieces)):
        k, x, yy, z, yaw, pitch, p = pieces[i]
        pieces[i] = (k, x + cx, yy, z + cz, yaw, pitch, p)


def dome(cx, cz, y0, r0, profile, part, layers, solid_top=True):
    """Dome of rings: radius r0 * profile(t) for t from 0 (bottom) to 1 (top); where a row steps in by more than a
    block, extra inner rings fill the row below so every block rests on one below."""
    def snap(r):                              # near the tip: whole cells (0.42, 0.21, 0), so the last rings and the
        return r if r >= 0.53 else round(r / CELL) * CELL      # centre block touch without overlapping
    radii = [snap(r0 * profile(i / max(1, layers - 1))) for i in range(layers)]
    for i, r in enumerate(radii):
        if r < 0.11:
            pieces.append(("S1", cx, (y0 + i + 0.5) * CELL, cz, 0, 0, part))
            return y0 + i + 1
        ring_at(cx, cz, r, y0 + i, part)
        nxt = radii[i + 1] if i + 1 < len(radii) else 0.0
        rr = r
        while rr - nxt > 0.11:                    # the next row needs a ring within half a block below it
            rr -= CELL
            if rr < 0.11:
                if solid_top:                     # a 1x1 closes the middle; a ring of 1x1 at one cell's distance
                    if rr + CELL > 0.23:          # bridges to the dome's smallest ring, all only touching
                        ring_at(cx, cz, CELL, y0 + i, part)
                    pieces.append(("S1", cx, (y0 + i + 0.5) * CELL, cz, 0, 0, part))
                break
            ring_at(cx, cz, rr, y0 + i, part)
    return y0 + len(radii)


def onion(t):
    """Onion profile: bulges out over the drum, then draws in to a slender tip."""
    pts = [(0.0, 1.0), (0.1, 1.08), (0.22, 1.13), (0.36, 1.1), (0.5, 0.98), (0.62, 0.8), (0.74, 0.58),
           (0.84, 0.38), (0.92, 0.22), (0.97, 0.11), (1.0, 0.04)]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return pts[-1][1]


def finial(cx, cz, y0, h, part):
    """Brass finial (yellow): a slim shaft with bulbs (two rows each, so they read as bulbs, not as a cross bar)
    and, on the tall ones, a crescent of two horns on top."""
    tall = h >= 8
    shaft = h - 2 if tall else h
    for k in range(shaft):
        pieces.append(("gold1", cx, (y0 + k + 0.5) * CELL, cz, 0, 0, part))
    for k in ((h // 5, h // 2 - 1) if tall else ()):
        for kk in (k, k + 1):
            for dx, dz in ((CELL, 0), (-CELL, 0), (0, CELL), (0, -CELL)):
                pieces.append(("gold1", cx + dx, (y0 + kk + 0.5) * CELL, cz + dz, 0, 0, part))
    if tall:
        for kk in (shaft - 1, shaft):
            for dx in (-CELL, CELL):
                pieces.append(("gold1", cx + dx, (y0 + kk + 0.5) * CELL, cz, 0, 0, part))


def pinnacle(x, z, y0, h, part):
    """Slim pinnacle (guldasta): a column of 1x1 blocks with a yellow tip."""
    for k in range(h):
        pieces.append(("S1", x, (y0 + k + 0.5) * CELL, z, 0, 0, part))
    pieces.append(("gold1", x, (y0 + h + 0.5) * CELL, z, 0, 0, part))


# Central hall: ring wall from the floor to the roof, on each storey four pointed arches towards the main recesses;
# each arch closes a row of wall below the next floor
r_hall = (RH + 0.5) * CELL
W_ARCH = c2(7) * CELL
H_ARCH = {Y0: (Y_MID - Y0) - int(W_ARCH / 2 / CELL) - 2, Y_MID + 1: (Y_ROOF - Y_MID - 1) - int(W_ARCH / 2 / CELL) - 2}
for y in range(Y0, Y_ROOF):
    storey = Y0 if y < Y_MID else Y_MID + 1
    yy, h_arch = y - storey, H_ARCH[storey]
    hw = W_ARCH / 2 if yy < h_arch else W_ARCH / 2 - (yy - h_arch + 1) * CELL
    if y != Y_MID and yy >= 0 and hw > 0.05:
        ring_row(r_hall, y, "Hall", [(phi, hw) for phi in (0, 90, 180, 270)])
    else:
        ring(r_hall, y, "Hall")
# Drum above the roof (the hall ring continues), with a plum band near its top
Y_DRUM = ROOF_TOP
for y in range(Y_ROOF, Y_DRUM + DH):
    ring(r_hall, y, "Dome", key2="D2" if y in (Y_DRUM + DH - 3, Y_DRUM + DH - 2) else "S2")
# Two rings lie on the floor round the hall wall and on the roof round the drum: they cover the stepped edge of the slab
# from above. Nothing lies in the slab's own row, so no block hides another (with "all blocks below" as prerequisite
# the rings come after the slab under them)
for k in (1, 2):
    ring(r_hall + k * CELL, Y_MID + 1, "Floor")
for k in (1, 2):
    ring(r_hall + k * CELL, ROOF_TOP, "Roof")
# Inner dome over the hall, below the outer one
Y_INNER = Y_MID + 1 + H_ARCH[Y_MID + 1] + int(W_ARCH / 2 / CELL) + 1    # above the upper arches
dome(0.0, 0.0, Y_INNER, r_hall - CELL, lambda t: math.cos(t * math.pi / 2) ** 0.8, "Hall", c(14))   # with the hall
# Outer onion dome on the drum, and the finial
y_top = dome(0.0, 0.0, Y_DRUM + DH, r_hall, onion, "Dome", DOME_H)
finial(0.0, 0.0, y_top, c(10), "Dome")
DOME_TOP = y_top + c(10)


# Chhatris on the roof: eight slim columns, a ring beam, a small onion dome
def chhatri(cx, cz, y0, rc, hc, part):
    ring_at(cx, cz, rc, y0, part)                                # base: the columns stand on the inner ring
    ring_at(cx, cz, rc + CELL, y0, part)
    for k in range(8):
        a = math.radians(22.5 + 45 * k)
        for y in range(y0 + 1, y0 + 1 + hc):
            pieces.append(("S1", cx + rc * math.cos(a), (y + 0.5) * CELL, cz + rc * math.sin(a), 0, 0, part))
    yb = y0 + 1 + hc
    ring_at(cx, cz, rc, yb, part)                                # ring beam
    ring_at(cx, cz, rc + CELL, yb + 1, part, key2="D2")         # eave
    yt = dome(cx, cz, yb + 2, rc, onion, part, int(round(rc / CELL * 1.7)) + 2)
    finial(cx, cz, yt, c(3), part)
    return yt + c(3)


# Pinnacles: at the top corners of every pishtaq frame and in the middle of every chamfer
for f in range(4):
    cell = face_frame(f)
    fx = PW // 2 + PF
    for u in (-fx, fx - 1):
        px, pz = cell(u, 0)
        clear(px, ROOF_TOP + PUP, pz)
        pinnacle((px + 0.5) * CELL, (pz + 0.5) * CELL, ROOF_TOP + PUP, c(6), "Roof")
for (mx, mz) in CHAMFER_MIDS:
    pinnacle(mx, mz, ROOF_TOP + 1, c(7), "Roof")

RC_ROOF = c(5) * CELL
# as far out as the cut corner allows: the outer base ring keeps a block's width from the chamfer parapet
CHHATRI_D = ((2 * M - CH) * CELL - 2 * CELL - (RC_ROOF + 1.5 * CELL) * math.sqrt(2)) / 2
for sx in (-1, 1):
    for sz in (-1, 1):
        chhatri(sx * CHHATRI_D, sz * CHHATRI_D, ROOF_TOP, RC_ROOF, c(9), "Roof")


# Minarets at the platform corners: tapered rings, three balconies, a chhatri on top
def minaret(cx, cz, part):
    for k in range(MIN_H):
        t = k / MIN_H
        r = (RM0 + (RM1 - RM0) * t) * CELL
        y = Y0 + k
        balcony = k in (MIN_H // 3, 2 * MIN_H // 3, MIN_H - 1)
        ring_at(cx, cz, r, y, part, key2="D2" if k in (MIN_H // 3 - 1, 2 * MIN_H // 3 - 1, MIN_H - 2) else "S2")
        if balcony:
            ring_at(cx, cz, r + CELL, y, part)
            ring_at(cx, cz, r + 2 * CELL, y, part)
            n = int(round(2 * math.pi * (r + 2 * CELL) / (2 * CELL)))
            for i in range(n):
                a = math.radians(i * 360.0 / n)
                pieces.append(("S1", cx + (r + 2 * CELL) * math.cos(a), (y + 1.5) * CELL,
                               cz + (r + 2 * CELL) * math.sin(a), 0, 0, part))
    return chhatri(cx, cz, Y0 + MIN_H, RM1 * CELL - 0.5 * CELL, c(6), part)


MIN_C = (PL - MO) * CELL
minaret_top = 0
for sx in (-1, 1):
    for sz in (-1, 1):
        minaret_top = minaret(sx * MIN_C, sz * MIN_C, "Minarets " + ("front" if sz < 0 else "back"))

# Ramp for the game's mobile scaffold and for walking up: 15 degrees from the ground to the deck, in front
RAMP_DEG, RAMP_W, RAMP_T = 15.0, 4.0, 0.08
ramp_h = PH * CELL
ramp_len = ramp_h / math.sin(math.radians(RAMP_DEG))
ramp_run = ramp_h / math.tan(math.radians(RAMP_DEG))
z_edge = -PL * CELL
scaffold.append((0.0, ramp_h / 2 - RAMP_T / 2, z_edge - ramp_run / 2, RAMP_W, RAMP_T, ramp_len + 0.1, -RAMP_DEG, 0.0, 0.0, 1.0))

# Scaffold (visuals and colliders of the mod, no bricks), built like the Notre-Dame's: walking surfaces are the tops of
# 6 cm planks on 5 cm ledgers, steps rise one cell (0.21 m) per 0.42 m, uprights 12 cm (no collider), and no two boxes
# share a face plane where they overlap (z-fighting). Placing reaches 5 m from the player (game code; counted from the
# feet here). The mobile scaffold reaches the outer walls, the minarets and the roof's chhatris from the platform.
# Only the ramp stays (the way up onto the platform); the scaffold goes once every site of the building is complete:
# outside, a stair tower behind the building from the platform up onto the roof (a bridge over the parapet), and a
# stair round drum and dome from the roof up to a platform from which the finial is within reach; inside, narrow, a
# stair tower in the hall up to the inner dome, turned by 45 degrees so its corners face the hall's four arches, and
# walkways round the hall on both storeys in both corridors, joined by bridges through the arches. The upper storey is
# reached only through the hall: its niches outside are blind.
PLANK, RAIL, POST = 0.06, 1.0, 0.12
STEP_RISE, STEP_RUN = CELL, 2 * CELL
W_OUT, W_IN = 1.3, 1.0        # walkway widths: outside wider than the player (capsule radius 0.5 m), inside narrow
NO_TURN = (0.0, 0.0, 0.0)


def world(tf, lx, lz):
    """Local frame tf = (cx, cz, yaw) -> world (x, z), turned like Unity: local x -> (cos, -sin), local z -> (sin, cos)."""
    cx, cz, yaw = tf
    a = math.radians(yaw)
    return cx + lx * math.cos(a) + lz * math.sin(a), cz - lx * math.sin(a) + lz * math.cos(a)


def box(out, tf, lx, y, lz, sx, sy, sz, walk=True):
    """Box in the local frame; turned boxes carry their Euler angles and whether they get a collider."""
    x, z = world(tf, lx, lz)
    if tf[2] % 360 == 0:
        out.append((x, y, z, sx, sy, sz))
    else:
        out.append((x, y, z, sx, sy, sz, 0.0, tf[2], 0.0, 1.0 if walk else 0.0))


def plank(out, tf, x0, x1, z0, z1, walk):
    box(out, tf, (x0 + x1) / 2, walk - PLANK / 2, (z0 + z1) / 2, abs(x1 - x0), PLANK, abs(z1 - z0))


def tube(out, tf, x0, x1, z0, z1, y, t=0.06, walk=True):
    box(out, tf, (x0 + x1) / 2, y, (z0 + z1) / 2, max(abs(x1 - x0), t), t, max(abs(z1 - z0), t), walk)


def deck(out, tf, x0, x1, z0, z1, walk, ledgers=None):
    """Plank on two ledgers along its long edges, 3 cm inside them (or along ledgers = (a, b) of the long axis)."""
    plank(out, tf, x0, x1, z0, z1, walk)
    y = walk - PLANK - 0.025
    if abs(x1 - x0) >= abs(z1 - z0):
        a, b = ledgers or (x0, x1)
        for zz in (min(z0, z1) + 0.03, max(z0, z1) - 0.03):
            tube(out, tf, a, b, zz, zz, y, 0.05, False)
    else:
        a, b = ledgers or (z0, z1)
        for xx in (min(x0, x1) + 0.03, max(x0, x1) - 0.03):
            tube(out, tf, xx, xx, a, b, y, 0.05, False)


uprights = {}       # (list, x mm, z mm) -> index


def post(out, x, z, y0, y1):
    """Upright (never turned); two on the same spot, or overlapping each other, become one where their heights meet
    (one storey's uprights stand on the floor above the other's)."""
    near_ = [k for k, i in uprights.items() if k[0] == id(out) and abs(out[i][0] - x) < POST and abs(out[i][2] - z) < POST
             and out[i][1] - out[i][4] / 2 <= y1 + 0.01 and out[i][1] + out[i][4] / 2 >= y0 - 0.01]
    if near_:
        key = near_[0]
        bx, cy, bz, _, sy, _ = out[uprights[key]]
        y0, y1 = min(y0, cy - sy / 2), max(y1, cy + sy / 2)
        x, z = bx, bz
    else:
        key = (id(out), len(uprights))
        uprights[key] = len(out)
        out.append(None)
    out[uprights[key]] = (x, (y0 + y1) / 2, z, POST, y1 - y0, POST)


def brace(out, p0, p1, t=0.06):
    """Tube from p0 to p1 (x, y, z), visuals only: the Euler angles turn its local y onto the line."""
    (x0, y0, z0), (x1, y1, z1) = p0, p1
    out.append(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2, t, math.dist(p0, p1), t,
                math.degrees(math.atan2(math.hypot(x1 - x0, z1 - z0), y1 - y0)), math.degrees(math.atan2(x1 - x0, z1 - z0)),
                0.0, 0.0))


def braces(out, a, b, y0, y1, band=2.4):
    """Zigzag of braces between the uprights at a and b (x, z), from y0 to y1."""
    n_b = max(1, int(round((y1 - y0) / band)))
    for k in range(n_b):
        ya, yb = y0 + (y1 - y0) * k / n_b, y0 + (y1 - y0) * (k + 1) / n_b
        p, q = (a, b) if k % 2 == 0 else (b, a)
        brace(out, (p[0], ya, p[1]), (q[0], yb, q[1]))


def stair_geometry(mid, w):
    k = int((2 * mid - w + 1e-9) // STEP_RUN)              # steps per side
    return k, (2 * mid - w) / k


def corner_square(out, tf, mid, w, corner, walk):
    """Landing on two ledgers along its outer edges, which meet at the tower's corner upright."""
    kx, kz = corner[0] * mid, corner[1] * mid
    plank(out, tf, kx - w / 2, kx + w / 2, kz - w / 2, kz + w / 2, walk)
    ex, ez = kx + corner[0] * (w / 2 - 0.03), kz + corner[1] * (w / 2 - 0.03)
    tube(out, tf, ex, ex, kz - w / 2, kz + w / 2, walk - PLANK - 0.025, 0.05, False)
    xa, xb = (kx - w / 2, ex - 0.025) if corner[0] > 0 else (ex + 0.025, kx + w / 2)   # butting, not crossing
    tube(out, tf, xa, xb, ez, ez, walk - PLANK - 0.025, 0.05, False)


def stair(out, tf, mid, w, corners, c_top, u_top, u0):
    """Stair tower round the local origin like a scaffold stair tower: a square ring (corner centres at +-mid, walked in
    `corners` order), a w x w landing at every corner and straight flights between them, as many 21 cm risers as fit
    on a side. From the floor at u0 cells (the first flight cut to the height left over) up to a landing at corner
    c_top, u_top cells high; a stringer under both edges of every flight. Returns [(corner, u)] of its landings."""
    k, t = stair_geometry(mid, w)
    per = k + 1                                            # cells per side: k steps + the riser onto the landing
    runs, levels = [], []

    def flight(a, u, m):
        """m steps on side a (corner a to corner a + 1), on the places next to corner a + 1, from u cells."""
        (ax0, az0), (ax1, az1) = corners[a % 4], corners[(a + 1) % 4]
        dx, dz = (ax1 - ax0) // 2, (az1 - az0) // 2
        run = []
        for i in range(m):
            d = w / 2 + (k - m + i + 0.5) * t
            px, pz = ax0 * mid + dx * d, az0 * mid + dz * d
            walk = (u + 1 + i) * STEP_RISE
            if dx:
                plank(out, tf, px - t / 2 - 0.015, px + t / 2 + 0.015, pz - w / 2, pz + w / 2, walk)
            else:
                plank(out, tf, px - w / 2, px + w / 2, pz - t / 2 - 0.015, pz + t / 2 + 0.015, walk)
            run.append((px, pz, walk))
        runs.append((run, dx, dz))

    n_full = (u_top - u0 - 1) // per
    r = u_top - u0 - n_full * per                          # 1 .. per: the first landing
    c, u = (c_top - n_full) % 4, u0 + r
    flight(c - 1, u0, r - 1)
    corner_square(out, tf, mid, w, corners[c], u * STEP_RISE)
    levels.append((c, u))
    while u < u_top:
        flight(c, u, k)
        c, u = (c + 1) % 4, u + per
        corner_square(out, tf, mid, w, corners[c], u * STEP_RISE)
        levels.append((c, u))
    for run, dx, dz in runs:
        if len(run) < 2:
            continue
        (xa, za, wa), (xb, zb, wb) = run[0], run[-1]
        for off in (-(w / 2 - 0.06), w / 2 - 0.06):
            ox, oz = (0, off) if dx else (off, 0)
            pa = world(tf, xa - dx * t / 2 + ox, za - dz * t / 2 + oz)
            pb = world(tf, xb + dx * t / 2 + ox, zb + dz * t / 2 + oz)
            brace(out, (pa[0], wa - PLANK - 0.05, pa[1]), (pb[0], wb - PLANK - 0.05, pb[1]), 0.08)
    return levels


def tower_frame(out, tf, mid, w, y0, top, braced_sides=()):
    """Uprights at the inner and the outer corner of every corner landing, braces on the named outer faces."""
    for (ax, az) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        for m in (mid - w / 2, mid + w / 2):
            post(out, *world(tf, ax * m, az * m), y0, top)
    o = mid + w / 2 + 0.06
    faces = {"-z": ((-1, -1), (1, -1)), "+x": ((1, -1), (1, 1)), "+z": ((1, 1), (-1, 1)), "-x": ((-1, 1), (-1, -1))}
    for side in braced_sides:
        c0, c1 = faces[side]
        braces(out, world(tf, c0[0] * o, c0[1] * o), world(tf, c1[0] * o, c1[1] * o), y0 + 0.3, top - RAIL - 0.3)


# -- Outside: stair tower behind the building, in front of the right-hand niches of the back face. Its top landing lies
# next to the wall between the pishtaq frame and the chhatri; a bridge crosses the parapet above the merlons, two solid
# steps lead down onto the roof. The mobile scaffold still passes between the tower and the minaret.
Y_DECK = Y0 * CELL
C_WALL = 0.45                                              # clearance to the walls
MID_T = 1.72                                               # 5 steps per side, 1.26 m per side
X_BRIDGE = 4.0                                             # middle of the bridge onto the roof
U_OVER = ROOF_TOP + 3                                      # the bridge's ledgers clear the merlons (row ROOF_TOP + 1)
z_wall = M * CELL
tf_t = (X_BRIDGE + MID_T, z_wall + C_WALL + MID_T + W_OUT / 2, 0.0)
T_CORNERS = [(-1, -1), (-1, 1), (1, 1), (1, -1)]           # corner 0: next to the wall, towards the middle
stair(temp_scaffold, tf_t, MID_T, W_OUT, T_CORNERS, 0, U_OVER, Y0)
y_over = U_OVER * STEP_RISE
tower_frame(temp_scaffold, tf_t, MID_T, W_OUT, Y_DECK, y_over + RAIL, ("-x", "+x", "+z"))
lx0 = tf_t[0] - MID_T - W_OUT / 2                          # rail on the top landing's open side
tube(temp_scaffold, NO_TURN, lx0, lx0, tf_t[1] - MID_T - W_OUT / 2, tf_t[1] - MID_T + W_OUT / 2, y_over + RAIL)
deck(temp_scaffold, NO_TURN, X_BRIDGE - W_OUT / 2, X_BRIDGE + W_OUT / 2, z_wall - CELL - 0.05, z_wall + C_WALL, y_over)
y_roof = ROOF_TOP * CELL
for j in (1, 2):                                           # 13.44 m and 13.23 m, standing on the roof slab
    top_j = (U_OVER - j) * STEP_RISE
    z1 = z_wall - CELL - 0.05 - (j - 1) * STEP_RUN
    box(temp_scaffold, NO_TURN, X_BRIDGE, (y_roof + 0.01 + top_j) / 2, z1 - STEP_RUN / 2, W_OUT, top_j - y_roof - 0.01, STEP_RUN)

# -- Outside: stair round drum and dome, standing on the roof. Its inner edge keeps 0.3 m from the dome's widest ring
# (and clears the chhatris outside its corners); the first flight starts on the roof behind the drum, the top platform
# covers three corners and three sides (not the last flight), and a bridge reaches in over the narrowing dome towards
# the finial, whose tip is then within 4.4 m.
R_DOME = max(math.hypot(math.hypot(pc[1], pc[3]) + CELL / 2, CELL) for pc in pieces if pc[6] == "Dome")
A_IN = R_DOME + 0.3
MID_D = A_IN + W_OUT / 2
B_OUT = MID_D + W_OUT / 2
D_CORNERS = [(1, 1), (-1, 1), (-1, -1), (1, -1)]           # first flight behind the drum (towards -x), top at the front right
U_TOP_D = int(math.ceil((DOME_TOP * CELL - 4.0) / CELL))
stair(temp_scaffold, NO_TURN, MID_D, W_OUT, D_CORNERS, 3, U_TOP_D, ROOF_TOP)
y_top_d = U_TOP_D * STEP_RISE
for j in (1, 2):                                           # the platform's other corners
    corner_square(temp_scaffold, NO_TURN, MID_D, W_OUT, D_CORNERS[(3 + j) % 4], y_top_d)
for s_idx in (3, 0, 1):                                    # its sides (not the last flight's)
    (ax0, az0), (ax1, az1) = D_CORNERS[s_idx], D_CORNERS[(s_idx + 1) % 4]
    xm, zm = (ax0 + ax1) / 2 * MID_D, (az0 + az1) / 2 * MID_D
    if ax0 != ax1:
        plank(temp_scaffold, NO_TURN, xm - MID_D + W_OUT / 2, xm + MID_D - W_OUT / 2, zm - W_OUT / 2, zm + W_OUT / 2, y_top_d)
    else:
        plank(temp_scaffold, NO_TURN, xm - W_OUT / 2, xm + W_OUT / 2, zm - MID_D + W_OUT / 2, zm + MID_D - W_OUT / 2, y_top_d)
tube(temp_scaffold, NO_TURN, -B_OUT, B_OUT, -B_OUT, -B_OUT, y_top_d + RAIL)
tube(temp_scaffold, NO_TURN, -B_OUT, B_OUT, B_OUT, B_OUT, y_top_d + RAIL)
tube(temp_scaffold, NO_TURN, -B_OUT, -B_OUT, -B_OUT + 0.03, B_OUT - 0.03, y_top_d + RAIL)   # butting, not crossing
tube(temp_scaffold, NO_TURN, B_OUT, B_OUT, -B_OUT + 0.03, B_OUT - 0.03, y_top_d + RAIL)
# bridge in from the right-hand side: its tip 0.3 m from the dome rings at its height, on two struts from uprights
# standing on the roof beside the drum
r_tip = max([math.hypot(math.hypot(pc[1], pc[3]) + CELL / 2, CELL) for pc in pieces
             if pc[6] == "Dome" and abs(pc[2] - (y_top_d - PLANK / 2)) < CELL / 2 + 0.2] + [0.0]) + 0.3
deck(temp_scaffold, NO_TURN, r_tip, A_IN, -W_OUT / 2, W_OUT / 2, y_top_d)
for zz in (-W_OUT / 2 + 0.09, W_OUT / 2 - 0.09):
    post(temp_scaffold, A_IN + 0.06, zz, y_roof, y_top_d - PLANK - 0.05)
    brace(temp_scaffold, (A_IN + 0.06, y_top_d - 1.8, zz), (r_tip + 0.15, y_top_d - PLANK - 0.05, zz))
tower_frame(temp_scaffold, NO_TURN, MID_D, W_OUT, y_roof, y_top_d + RAIL, ("-x", "+x", "-z"))

# -- Inside: stair tower in the hall, from its floor up to a platform under the inner dome. Its
# corners face the arches, and its landings line up with the walkways: the ground floor's (2.52 m above the floor,
# headroom below), the upper floor itself (on the two rings round the hall) and the upper floor's (1.68 m above the
# rings, so the upper hall arch leaves headroom). Bridges at -z lead to the ground floor's walkways and onto the upper
# floor, one at +z to the upper floor's walkways; the entrance (-z) passes below them.
TF_HALL = (0.0, 0.0, 45.0)
MID_H = 1.25                                               # 3 steps per side: 0.84 m per side, 3.36 m per turn
H_CORNERS = [(-1, -1), (1, -1), (1, 1), (-1, 1)]           # turned by 45 degrees: -x, -z, +x, +z
AXIS = {(-1, -1): (-1, 0), (1, -1): (0, -1), (1, 1): (1, 0), (-1, 1): (0, 1)}
U_RING_G = Y0 + 12
U_UPPER = Y_MID + 2
U_RING_U = U_UPPER + 8
U_TOP_H = int(math.ceil((Y_INNER + c(14) - 1) - 4.5 / CELL))   # the inner dome's top row within reach
k_h, _ = stair_geometry(MID_H, W_IN)
per_h = k_h + 1
U_TOP_H += (U_TOP_H - U_RING_G) % per_h and per_h - (U_TOP_H - U_RING_G) % per_h
n_h = (U_TOP_H - Y0 - 1) // per_h
u_first = U_TOP_H - n_h * per_h


def hall_corner(c_top, u):
    return H_CORNERS[(c_top - n_h + (u - u_first) // per_h) % 4]


c_top_h = next(cc for cc in range(4) if AXIS[hall_corner(cc, U_RING_G)] == (0, -1))
for u_ in (U_RING_G, U_UPPER, U_RING_U):
    assert (u_ - u_first) % per_h == 0, f"no hall landing at {u_}"
assert AXIS[hall_corner(c_top_h, U_UPPER)] == (0, -1) and AXIS[hall_corner(c_top_h, U_RING_U)] == (0, 1)
stair(temp_scaffold, TF_HALL, MID_H, W_IN, H_CORNERS, c_top_h, U_TOP_H, Y0)
y_top_h = U_TOP_H * STEP_RISE
for j in (1, 2):
    corner_square(temp_scaffold, TF_HALL, MID_H, W_IN, H_CORNERS[(c_top_h + j) % 4], y_top_h)
for s_idx in (c_top_h, c_top_h + 1, c_top_h + 2):
    (ax0, az0), (ax1, az1) = H_CORNERS[s_idx % 4], H_CORNERS[(s_idx + 1) % 4]
    xm, zm = (ax0 + ax1) / 2 * MID_H, (az0 + az1) / 2 * MID_H
    if ax0 != ax1:
        plank(temp_scaffold, TF_HALL, xm - MID_H + W_IN / 2, xm + MID_H - W_IN / 2, zm - W_IN / 2, zm + W_IN / 2, y_top_h)
    else:
        plank(temp_scaffold, TF_HALL, xm - W_IN / 2, xm + W_IN / 2, zm - MID_H + W_IN / 2, zm + MID_H - W_IN / 2, y_top_h)
plank(temp_scaffold, TF_HALL, -MID_H + W_IN / 2, MID_H - W_IN / 2, -MID_H + W_IN / 2, MID_H - W_IN / 2, y_top_h)  # the well
bh = MID_H + W_IN / 2
last_side = {H_CORNERS[(c_top_h - 1) % 4], H_CORNERS[c_top_h]}
for (c0, c1) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
    if {c0, c1} == last_side:
        continue                                           # over the last flight: the rail would be at head height
    if c0[0] != c1[0]:
        tube(temp_scaffold, TF_HALL, -bh, bh, c0[1] * bh, c0[1] * bh, y_top_h + RAIL)
    else:
        tube(temp_scaffold, TF_HALL, c0[0] * bh, c0[0] * bh, -bh + 0.03, bh - 0.03, y_top_h + RAIL)
for corner in H_CORNERS:                                   # uprights; none at the tips where the bridges leave
    post(temp_scaffold, *world(TF_HALL, corner[0] * (MID_H - W_IN / 2), corner[1] * (MID_H - W_IN / 2)), Y_DECK, y_top_h + RAIL)
    if AXIS[corner][1] == 0:
        post(temp_scaffold, *world(TF_HALL, corner[0] * bh, corner[1] * bh), Y_DECK, y_top_h + RAIL)

# -- Inside: walkways round the hall, square rings 0.3 m clear of the hall wall and the arcades, on both storeys:
# one in the inner corridor (hall to arcades), one in the outer corridor (arcades to the outer walls); uprights at the
# corners and beside the arches (no collider: the doorways below stay passable)
R_HALL_OUT = r_hall + CELL / 2
ARC_IN, ARC_OUT = (A_HALF - 1) * CELL, A_HALF * CELL
RINGS = [(ARC_IN - 0.3 - W_IN, ARC_IN - 0.3, (1.05, 3.2)),        # inner corridor
         (ARC_OUT + 0.3, ARC_OUT + 0.3 + W_IN, (1.05, 3.6, 5.2))]  # outer corridor
assert RINGS[0][0] - R_HALL_OUT > 0.3


def ring_walk(a, b, walk, mids, foot):
    for s in (-1, 1):
        deck(temp_scaffold, NO_TURN, -b, b, s * a, s * b, walk)                 # along x, full length
        deck(temp_scaffold, NO_TURN, s * a, s * b, -a, a, walk)                 # along z, butting
    top = walk - PLANK - 0.05
    for sx in (-1, 1):
        for sz in (-1, 1):
            for e in (a + 0.06, b - 0.06):
                post(temp_scaffold, sx * e, sz * e, foot, top)
            for u_ in mids:
                for e in (a + 0.06, b - 0.06):
                    post(temp_scaffold, sx * u_, sz * e, foot, top)         # sides along x
                    post(temp_scaffold, sx * e, sz * u_, foot, top)         # sides along z


for walk_u, foot in ((U_RING_G, Y_DECK), (U_RING_U, (Y_MID + 1) * CELL)):
    for a, b, mids in RINGS:
        ring_walk(a, b, walk_u * STEP_RISE, mids, foot)

# -- Bridges: from the hall tower's corner landings through the hall arches, and from ring to ring through the arcade
# arch on the same axis; 1 cm below the landing they leave (no shared face plane), level with the rings they reach
tip_h = MID_H * math.sqrt(2)                               # corner landing centre from the hall axis


def axis_deck(sign_z, r0, r1, walk, ledger_from=None):
    """Deck along the z axis (x = -W_IN/2 .. W_IN/2) from r0 to r1 on the side sign_z."""
    deck(temp_scaffold, NO_TURN, -W_IN / 2, W_IN / 2, sign_z * r0, sign_z * r1, walk,
         ledgers=None if ledger_from is None else tuple(sorted((sign_z * ledger_from, sign_z * r1))))


axis_deck(-1, tip_h, RINGS[0][0], U_RING_G * STEP_RISE - 0.01, ledger_from=tip_h + W_IN / math.sqrt(2))
axis_deck(-1, RINGS[0][1], RINGS[1][0], U_RING_G * STEP_RISE)
# onto the upper floor: 7 cm short of the floor rings, whose straight blocks reach in a little beside the axis
axis_deck(-1, tip_h, R_HALL_OUT - 0.07, U_UPPER * STEP_RISE - 0.01, ledger_from=tip_h + W_IN / math.sqrt(2))
axis_deck(1, tip_h, RINGS[0][0], U_RING_U * STEP_RISE - 0.01, ledger_from=tip_h + W_IN / math.sqrt(2))
axis_deck(1, RINGS[0][1], RINGS[1][0], U_RING_U * STEP_RISE)


# ---- 4) Packing cells into blocks ----
SMALL = {"S": ("S2", "S1", "z"), "D": ("D2", "D1", "z"), "G": ("G2", "G1", "x"), "U": ("U2", "U1", "z")}
packed = []          # (key, x, y, z, yaw, pitch, part)


def put_cells(key, cells, yaw, part):
    xs = [c_[0] for c_ in cells]; ys = [c_[1] for c_ in cells]; zs = [c_[2] for c_ in cells]
    packed.append((key, (min(xs) + max(xs) + 1) / 2 * CELL, (min(ys) + max(ys) + 1) / 2 * CELL,
                   (min(zs) + max(zs) + 1) / 2 * CELL, yaw, 0, part))


by_layer = collections.defaultdict(set)
for (x, y, z), mat in vox.items():
    by_layer[(y, mat)].add((x, z))

# Small blocks, laid row by row from the bottom: first the bond over the whole wall regardless of colour, then each
# block takes the colour of its cells (inlay bands follow the bond, as in real brickwork). A corner cell belongs to the
# wall along x in even rows and to the wall along z in odd rows, so the 2x1 at a corner reaches into one wall and, one
# row up, into the other. Every run along a wall is split into 2x1 and 1x1 by the cheapest choice: a joint standing on
# a joint of the row below costs 3, a 1x1 costs 1 (3 more on a 1x1 below or at a corner), a joint in line with one in
# the neighbouring run of the same row (slabs) costs 1.
COLOUR_RANK = {"S": 0, "U": 1, "G": 2, "D": 3}
brick_at = {}        # cell -> brick id
bricks_small = []    # [cells, axis]


def run_cost_split(cells, below_joint, below_single, side_joint, corner_ends):
    """cells in order; returns a list of groups (1 or 2 cells) with the lowest cost."""
    n = len(cells)
    INF = float("inf")
    best = [INF] * (n + 1)
    choice = [None] * (n + 1)
    best[0] = 0.0

    def joint_cost(i):                 # joint between cells i - 1 and i
        if i <= 0 or i >= n:
            return 0.0
        return 3.0 * below_joint(cells[i - 1], cells[i]) + 1.0 * side_joint(cells[i - 1], cells[i])
    for i in range(n):
        if best[i] == INF:
            continue
        jc = joint_cost(i)
        c1 = best[i] + jc + 1.0 + 3.0 * below_single(cells[i]) + (3.0 if i in corner_ends else 0.0)
        if c1 < best[i + 1]:
            best[i + 1], choice[i + 1] = c1, 1
        if i + 1 < n:
            c2 = best[i] + jc
            if c2 < best[i + 2]:
                best[i + 2], choice[i + 2] = c2, 2
    groups, i = [], n
    while i > 0:
        k = choice[i]
        groups.append(cells[i - k:i])
        i -= k
    return groups[::-1]


layers = collections.defaultdict(set)
for (x, y, z), mat in vox.items():
    if mat in SMALL:
        layers[y].add((x, z))
for y in sorted(layers):
    cells = layers[y]
    axis = {}
    for (x, z) in cells:
        nx = (x + 1, z) in cells or (x - 1, z) in cells
        nz = (x, z + 1) in cells or (x, z - 1) in cells
        axis[(x, z)] = ("x" if y % 2 == 0 else "z") if nx and nz else "x" if nx else "z" if nz else None

    def below_joint(a, b):
        ba, bb = brick_at.get((a[0], y - 1, a[1])), brick_at.get((b[0], y - 1, b[1]))
        return ba is not None and bb is not None and ba != bb

    def below_single(a):
        b = brick_at.get((a[0], y - 1, a[1]))
        return b is not None and len(bricks_small[b][0]) == 1

    def side_joint_for(ax):
        def f(a, b):
            if ax == "x":
                na, nb = (a[0], y, a[1] - 1), (b[0], y, b[1] - 1)
            else:
                na, nb = (a[0] - 1, y, a[1]), (b[0] - 1, y, b[1])
            ba, bb = brick_at.get(na), brick_at.get(nb)
            return ba is not None and bb is not None and ba != bb
        return f
    for ax in ("x", "z"):
        lines = collections.defaultdict(list)
        for (x, z), a in axis.items():
            if a == ax:
                lines[z if ax == "x" else x].append(x if ax == "x" else z)
        for fixed in sorted(lines):
            coords = sorted(lines[fixed])
            runs, cur = [], [coords[0]]
            for v in coords[1:]:
                if v == cur[-1] + 1:
                    cur.append(v)
                else:
                    runs.append(cur)
                    cur = [v]
            runs.append(cur)
            for run in runs:
                cl = [((v, fixed) if ax == "x" else (fixed, v)) for v in run]
                ends = set()
                for idx in (0, len(cl) - 1):
                    x, z = cl[idx]
                    perp = (((x, z + 1) in cells) + ((x, z - 1) in cells)) if ax == "x" else (((x + 1, z) in cells) + ((x - 1, z) in cells))
                    if perp == 1:
                        ends.add(idx)
                for grp in run_cost_split(cl, below_joint, below_single, side_joint_for(ax), ends):
                    bid = len(bricks_small)
                    bricks_small.append([[(c_[0], y, c_[1]) for c_ in grp], ax])
                    for c_ in grp:
                        brick_at[(c_[0], y, c_[1])] = bid
    for (x, z), a in axis.items():
        if a is None:
            bid = len(bricks_small)
            bricks_small.append([[(x, y, z)], None])
            brick_at[(x, y, z)] = bid
for cells_, ax in bricks_small:
    mat = max((vox[c_] for c_ in cells_), key=lambda m: COLOUR_RANK[m])
    key2, key1, longax = SMALL[mat]
    if len(cells_) == 2:
        put_cells(key2, cells_, 0 if longax == ax else 90, part_cells[cells_[0]])
    else:
        put_cells(key1, cells_, 0, part_cells[cells_[0]])

# Big blocks (grey Q, terracotta R): two rows high; 4x2 footprints along the long side, offset by two cells every
# other course, 2x2 where a 4 does not fit; single cells left over become two stacked 1x1 (beige)
BIG = {"Q": ("Q4", "Q2", "z"), "R": ("T4", "T8", "x")}
for (y, mat), cellmap in sorted(by_layer.items()):
    if mat not in BIG or y % 2:
        continue
    key4, key2, longax = BIG[mat]
    upper = set(by_layer[(y + 1, mat)])
    cells = {p for p in cellmap if p in upper}
    used = set()
    course = y // 2
    for (x, z) in sorted(cells):
        if (x, z) in used:
            continue
        placed = False
        for ax in (("x", "z") if course % 2 == 0 else ("z", "x")):
            if ax == "x":
                if (x - course * 2) % 4 != 0 and (x - 1, z) in cells and (x - 1, z) not in used:
                    continue
                block = [(x + i, z + j) for i in range(4) for j in range(2)]
            else:
                if (z - course * 2) % 4 != 0 and (x, z - 1) in cells and (x, z - 1) not in used:
                    continue
                block = [(x + i, z + j) for i in range(2) for j in range(4)]
            if all(b in cells and b not in used for b in block):
                used |= set(block)
                put_cells(key4, [(bx, y, bz) for bx, bz in block] + [(bx, y + 1, bz) for bx, bz in block],
                          (0 if longax == ax else 90), part_cells[(x, y, z)])
                placed = True
                break
        if placed:
            continue
        block = [(x + i, z + j) for i in range(2) for j in range(2)]
        if all(b in cells and b not in used for b in block):
            used |= set(block)
            put_cells(key2, [(bx, y, bz) for bx, bz in block] + [(bx, y + 1, bz) for bx, bz in block], 0,
                      part_cells[(x, y, z)])
    for (x, z) in sorted(cells - used):
        for yy in (y, y + 1):
            put_cells("S1", [(x, yy, z)], 0, part_cells[(x, y, z)])
    for (x, z) in sorted(set(cellmap) - cells):
        put_cells("S1", [(x, y, z)], 0, part_cells[(x, y, z)])
for (y, mat), cellmap in by_layer.items():
    if mat in BIG and y % 2 and not any((y - 1, mat) == k for k in by_layer):
        for (x, z) in cellmap:
            put_cells("S1", [(x, y, z)], 0, part_cells[(x, y, z)])

items = packed + pieces

# ---- 5) Types, sections, output ----
TYPES = {
    "S2": ("2×1 Block", "Beige", "library.beige", "LibraryNew_Brick_FEB8053A", "#e2ce9d", "z"),
    "S1": ("1×1 Block", "Beige", "library.beige", "LibraryNew_Brick_D800AC09", "#e2ce9d", None),
    "D2": ("2×1 Block", "Plum", "tavern.plum", "Tavern_Brick_9DEF6649", "#673e5c", "z"),
    "D1": ("1×1 Block", "Plum", "tavern.plum", "Tavern_Brick_CCE9C299", "#673e5c", None),
    "G2": ("2×1 Block", "Blue", "pharmacy.blue", "Pharmacy_Brick_06A152F5", "#5e8bb0", "x"),
    "G1": ("1×1 Block", "Blue", "pharmacy.blue", "Pharmacy_Brick_169A37B3", "#5e8bb0", None),
    "U2": ("2×1 Block", "Turquoise", "house.turquoise", "House_Brick_41DF8BC6", "#6fb4a2", "z"),
    "U1": ("1×1 Block", "Turquoise", "house.turquoise", "House_Brick_49D2AD69", "#6fb4a2", None),
    "Q4": ("4×2×2 Block", "Grey", "bakery.grey", "Bakery_Brick_2D1CAFD3", "#c9d4d4", "z"),
    "Q2": ("2×2×2 Block", "Grey", "pharmacy.grey", "Pharmacy_Brick_272A63CE", "#c9d4d4", None),
    "T4": ("4×2×2 Block", "Terracotta", "factory.terracotta", "Factory_Brick_DB127285", "#9f4d49", "x"),
    "T8": ("2×2×2 Block", "Terracotta", "factory.terracotta", "Factory_Brick_7CB4833B", "#9f4d49", None),
    "gold1": ("1×1 Block", "Yellow", "bakery.yellow", "Bakery_Brick_EBE67C24", "#cf9c61", None),
}
type_keys = list(TYPES)

# Construction sites: the game takes at most 8192 brick slots and 256 sections per site, so the building is cut like
# its storeys; the platform is a finished mesh (decor), not bricks to build.
PARTS = [
    ("tajmahal-ground-walls", "Taj Mahal: Ground floor walls", "Ground floor walls"),
    ("tajmahal-ground-inside", "Taj Mahal: Ground floor inside", "Ground floor inside"),
    ("tajmahal-upper-walls", "Taj Mahal: Upper floor walls", "Upper floor walls"),
    ("tajmahal-upper-inside", "Taj Mahal: Upper floor inside", "Upper floor inside"),
    ("tajmahal-roof", "Taj Mahal: Roof", "Roof"),
    ("tajmahal-dome", "Taj Mahal: Dome", "Dome"),
    ("tajmahal-minarets", "Taj Mahal: Minarets", "Minarets"),
]


def final_part(tag, y):
    row = int(y / CELL)
    if tag == "Walls":
        return 0 if row <= Y_MID else 2
    if tag in ("Arcades", "Hall", "Floor"):
        return 1 if row <= Y_MID + 1 else 3
    return {"Roof": 4, "Dome": 5, "Minarets front": 6, "Minarets back": 6}[tag]


decor_items = [it for it in items if it[6] == "Platform"]
build = [(it[0], it[1], it[2], it[3], it[4], it[5], final_part(it[6], it[2])) for it in items if it[6] != "Platform"]
PER_SECTION = 64
sections, ordered, section_part = [], [], []
for pi, (_, _, short) in enumerate(PARTS):
    bands = collections.defaultdict(list)
    for it in build:
        if it[6] == pi:
            bands[int(it[2] / (4 * CELL))].append(it)
    for b in sorted(bands):
        group = sorted(bands[b], key=lambda it: (round(it[2], 3), math.atan2(it[3], it[1])))
        if len(group) < PER_SECTION // 2 and section_part and section_part[-1] == pi:
            ordered += [(it, len(sections) - 1) for it in group]       # a small top band joins the section below
            continue
        n = max(1, round(len(group) / PER_SECTION))
        for k in range(n):
            chunk = group[k * len(group) // n:(k + 1) * len(group) // n]
            if not chunk:
                continue
            sections.append(f"{short} {b * 4 * CELL:.1f} m" + (f" · {k + 1}/{n}" if n > 1 else ""))
            section_part.append(pi)
            ordered += [(it, len(sections) - 1) for it in chunk]

# ---- 6) Prerequisites: a block needs every block of its site it rests on ----
# Geometry from the game's meshes (brick_meshes_taj.json): a block rests on another when that one's top meets its
# bottom (2 cm) and their footprints overlap. Blocks of other sites it rests on go to "xreq" (the mod checks them
# across sites). A block resting on nothing (a slab row, a lintel) needs a neighbour in its row that is itself held,
# like the Notre-Dame; one on the platform or the ground needs nothing.
MESH = json.load(open(os.path.join(HERE, "brick_meshes_taj.json"), encoding="utf-8"))
geo = []
for (it, s) in ordered:
    key, x, y, z, yaw, pitch, pi = it
    bnd = MESH[key]["bounds"]
    hx, hy, hz = (bnd[1] - bnd[0]) / 2, (bnd[3] - bnd[2]) / 2, (bnd[5] - bnd[4]) / 2
    a = math.radians(yaw)
    geo.append((x, y, z, hx, hy, hz, (math.cos(a), -math.sin(a)), (math.sin(a), math.cos(a)), pi))


def corners(i):
    x, y, z, hx, hy, hz, ax, az, _ = geo[i]
    return [(x + sx * hx * ax[0] + sz * hz * az[0], z + sx * hx * ax[1] + sz * hz * az[1]) for sx in (-1, 1) for sz in (-1, 1)]


def overlap(i, j, shrink=0.01):
    for (o, other) in ((i, j), (j, i)):
        x, y, z, hx, hy, hz, ax, az, _ = geo[o]
        for axis, h in ((ax, hx), (az, hz)):
            proj = [(cx - x) * axis[0] + (cz - z) * axis[1] for cx, cz in corners(other)]
            if min(proj) >= h - shrink or max(proj) <= -h + shrink:
                return False
    return True


hgrid = collections.defaultdict(list)
for i, gi in enumerate(geo):
    hgrid[(int(math.floor(gi[0] / 0.5)), int(math.floor(gi[2] / 0.5)))].append(i)


def near(i):
    gx, gz = int(math.floor(geo[i][0] / 0.5)), int(math.floor(geo[i][2] / 0.5))
    for dx in (-2, -1, 0, 1, 2):
        for dz in (-2, -1, 0, 1, 2):
            yield from hgrid.get((gx + dx, gz + dz), ())


DECK = PH * CELL
req, xreq, mode, held = [[] for _ in geo], [[] for _ in geo], [0] * len(geo), set()
for i, gi in enumerate(geo):
    bottom = gi[1] - gi[4]
    if bottom < 0.02 or abs(bottom - DECK) < 0.02:
        held.add(i)
        continue
    below = [j for j in near(i) if j != i and abs(geo[j][1] + geo[j][4] - bottom) < 0.02 and overlap(i, j)]
    req[i] = sorted(j for j in below if geo[j][8] == gi[8])
    xreq[i] = sorted(j for j in below if geo[j][8] != gi[8])
    if below:
        held.add(i)
side = {}
for i, gi in enumerate(geo):
    if i in held:
        continue
    bottom = gi[1] - gi[4]
    side[i] = [j for j in near(i) if j != i and geo[j][8] == gi[8] and abs(geo[j][1] - geo[j][4] - bottom) < 0.02
               and overlap(i, j, shrink=-0.02)]
changed = True
while changed:
    changed = False
    for i, nb in side.items():
        if i not in held and any(j in held for j in nb):
            req[i] = sorted(j for j in nb if j in held)
            mode[i] = 1
            held.add(i)
            changed = True
free = [i for i in range(len(geo)) if i not in held]

# ---- 6b) Scaffold clearance: no scaffold part may reach into a block (or the platform) ----
def euler_axes(pitch, yaw, roll):
    """Unity: R = Ry(yaw) Rx(pitch) Rz(roll); returns the box's local x, y, z axes in world coordinates."""
    p, y_, r = math.radians(pitch), math.radians(yaw), math.radians(roll)
    def ry(v): return (v[0] * math.cos(y_) + v[2] * math.sin(y_), v[1], -v[0] * math.sin(y_) + v[2] * math.cos(y_))
    def rx(v): return (v[0], v[1] * math.cos(p) - v[2] * math.sin(p), v[1] * math.sin(p) + v[2] * math.cos(p))
    def rz(v): return (v[0] * math.cos(r) - v[1] * math.sin(r), v[0] * math.sin(r) + v[1] * math.cos(r), v[2])
    return [ry(rx(rz(v))) for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]


def obb_hit(c1, h1, a1, c2, h2, a2, tol=0.005):
    d = [c2[k] - c1[k] for k in range(3)]
    axes = list(a1) + list(a2)
    for u in a1:
        for v in a2:
            w = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            if math.hypot(*w) > 1e-6:
                axes.append(w)
    for ax in axes:
        n = math.hypot(*ax)
        ax = (ax[0] / n, ax[1] / n, ax[2] / n)
        r1 = sum(h1[k] * abs(sum(a1[k][j] * ax[j] for j in range(3))) for k in range(3))
        r2 = sum(h2[k] * abs(sum(a2[k][j] * ax[j] for j in range(3))) for k in range(3))
        if abs(sum(d[j] * ax[j] for j in range(3))) >= r1 + r2 - tol:
            return False
    return True


solids = []
for (key, x, y, z, yaw, pitch, _) in [it for it, s in ordered] + decor_items:
    bnd = MESH[key]["bounds"]
    solids.append(((x, y, z), ((bnd[1] - bnd[0]) / 2, (bnd[3] - bnd[2]) / 2, (bnd[5] - bnd[4]) / 2), euler_axes(0.0, yaw, 0.0)))
sgrid = collections.defaultdict(list)
for i, (cs, hs, _) in enumerate(solids):
    rr = math.hypot(hs[0], hs[2])
    for gx in range(int(math.floor((cs[0] - rr) / 0.5)), int(math.floor((cs[0] + rr) / 0.5)) + 1):
        for gz in range(int(math.floor((cs[2] - rr) / 0.5)), int(math.floor((cs[2] + rr) / 0.5)) + 1):
            sgrid[(gx, gz)].append(i)
clashes = []
for name, lst in (("scaffold", scaffold), ("tempScaffold", temp_scaffold)):
    for bi, sb in enumerate(lst):
        if len(sb) > 9 and sb[9] and sb[6]:
            continue                                       # the ramp: its top end tucks into the platform's edge
        ax3 = euler_axes(*sb[6:9]) if len(sb) > 6 else euler_axes(0.0, 0.0, 0.0)
        hs = (sb[3] / 2, sb[4] / 2, sb[5] / 2)
        ext = [sum(hs[k] * abs(ax3[k][j]) for k in range(3)) for j in range(3)]
        cand = set()
        for gx in range(int(math.floor((sb[0] - ext[0]) / 0.5)), int(math.floor((sb[0] + ext[0]) / 0.5)) + 1):
            for gz in range(int(math.floor((sb[2] - ext[2]) / 0.5)), int(math.floor((sb[2] + ext[2]) / 0.5)) + 1):
                cand.update(sgrid.get((gx, gz), ()))
        for i in cand:
            cs, hb, ab = solids[i]
            if abs(cs[1] - sb[1]) < hb[1] + ext[1] and obb_hit(sb[:3], hs, ax3, cs, hb, ab):
                clashes.append((name, bi, sb[:6], i))
                break
print(f"scaffold: {len(scaffold)} parts kept (ramp), {len(temp_scaffold)} removed when finished, "
      f"{len(clashes)} reaching into blocks; roof tower to {y_over:.2f} m, dome stair {y_roof:.2f} to {y_top_d:.2f} m "
      f"(ring {A_IN:.2f}..{B_OUT:.2f} m, bridge tip {r_tip:.2f} m, finial tip {DOME_TOP * CELL:.2f} m), hall tower to "
      f"{y_top_h:.2f} m (inner dome top {(Y_INNER + c(14)) * CELL:.2f} m), walkways {U_RING_G * CELL:.2f} / "
      f"{U_RING_U * CELL:.2f} m, upper floor {U_UPPER * CELL:.2f} m")
for cl in clashes[:12]:
    print("  ", cl[0], cl[1], [round(v, 2) for v in cl[2]], "block", cl[3], solids[cl[3]][0])

# ---- 7) Output: preview data and the mod blueprint ----
counts = collections.Counter(it[0] for it, s in ordered)
per_part = {PARTS[pi][2]: sum(1 for it, s in ordered if it[6] == pi) for pi in range(len(PARTS))}
stats = {
    "total": len(ordered),
    "platform_m": round(2 * PL * CELL, 1),
    "platform_h_m": round(PH * CELL, 1),
    "building_m": round(2 * M * CELL, 1),
    "roof_m": round(ROOF_TOP * CELL, 1),
    "dome_m": round(DOME_TOP * CELL, 1),
    "minaret_m": round((Y0 + MIN_H) * CELL + 2.5, 1),
    "scaffold_top_m": round(max(s[1] + s[4] / 2 for s in scaffold + temp_scaffold), 1),
    "scaffold_parts": len(scaffold) + len(temp_scaffold),
    "parts": per_part,
}


def prow(key, x, y, z, yaw, pitch, s):
    row = [type_keys.index(key), round(x * 100, 1), round(y * 100, 1), round(z * 100, 1), round(yaw, 2) % 360, s]
    if pitch:
        row.append(pitch)
    return row


data = {
    "scale": S, "cell": CELL,
    "types": [{"name": TYPES[k][0], "color": TYPES[k][1], "group": TYPES[k][2], "asset": TYPES[k][3], "hex": TYPES[k][4],
               **({"long": TYPES[k][5]} if TYPES[k][5] else {}), "key": k} for k in type_keys],
    "sections": sections,
    "bricks": [prow(it[0], it[1], it[2], it[3], it[4], it[5], s) for it, s in ordered],
    "decor": [prow(it[0], it[1], it[2], it[3], it[4], it[5], 0)[:5] for it in decor_items],
    "scaffold": [[round(v * 100, 1) for v in s[:6]] + [round(v, 2) for v in s[6:9]] for s in scaffold],
    "tempScaffold": [[round(v * 100, 1) for v in s[:6]] + [round(v, 2) for v in s[6:9]] for s in temp_scaffold],
    "stats": stats,
}
dst = os.path.normpath(os.path.join(HERE, "..", "blueprints", "tajmahal_preview.json"))
with open(dst, "w", encoding="utf-8") as f:
    json.dump(data, f, separators=(",", ":"), ensure_ascii=False)

# Mod blueprint (ExtraBuildings). Local meters around the platform centre, y above the ground; meant for the site at
# X 1.5, Z 2.0, rotation 180 (front and ramp towards the spawn), with the town's fences gone.
z_front = -PL * CELL


def scaffold_row(sb):
    """[cx, cy, cz, sx, sy, sz] or, turned, [..., pitch, yaw, roll] plus 1 when it is walkable (gets a collider)."""
    row = [round(v, 4) for v in sb[:6]]
    if len(sb) > 6:
        row += [round(v, 2) for v in sb[6:9]] + ([1.0] if len(sb) > 9 and sb[9] else [])
    return row


STAND_X = (-14.0, -11.2, -8.4, -5.6, 5.6, 8.4, 11.2)
EDGE = round(PL * CELL + 0.6, 2)
blueprint_mod = {
    "siteId": "tajmahal",
    "displayName": "Taj Mahal",
    "templateSite": "house",
    "sections": sections,
    "blueprintStand": [STAND_X[0], round(z_front - 1.6, 3), 0],
    "parts": [{"siteId": sid, "displayName": name, "sections": [k for k, pk in enumerate(section_part) if pk == pi],
               "blueprintStand": [STAND_X[pi], round(z_front - 1.6, 3), 0]} for pi, (sid, name, _) in enumerate(PARTS)],
    # supply behind the platform and along both sides; the front stays free for the ramp and the mobile scaffold
    "pile": {"x": -20.0, "z": EDGE, "gap": 0.06, "perRow": 10, "stack": 14, "maxHeight": 3.0,
             "areas": [[-20.0, EDGE, 20.0, 29.5], [EDGE, -14.0, 24.0, 16.0], [-24.0, -14.0, -EDGE, 16.0]]},
    # the town's fences and small props in this rectangle go (platform, supply, ramp and boards need the room)
    "clearArea": [-26.0, -25.0, 26.0, 31.0],
    "colliders": [{"c": [0.0, round(PH * CELL / 2, 4), 0.0],
                   "s": [round(2 * PL * CELL, 4), round(PH * CELL, 4), round(2 * PL * CELL, 4)]}],
    "decor": [{"def": TYPES[it[0]][3], "p": [round(it[1], 4), round(it[2], 4), round(it[3], 4)], "yaw": round(it[4], 2) % 360}
              for it in decor_items],
    "scaffold": [scaffold_row(sb) for sb in scaffold],
    # removed by the mod once every site is complete
    "tempScaffold": [scaffold_row(sb) for sb in temp_scaffold],
    "bricks": [{"def": TYPES[it[0]][3], "p": [round(it[1], 4), round(it[2], 4), round(it[3], 4)], "yaw": round(it[4], 2) % 360,
                **({"pitch": it[5]} if it[5] else {}), "s": s, "mode": mode[i], "req": req[i],
                **({"xreq": xreq[i]} if xreq[i] else {})}
               for i, (it, s) in enumerate(ordered)],
}
dst_mod = os.path.normpath(os.path.join(HERE, "..", "blueprints", "tajmahal.json"))
with open(dst_mod, "w", encoding="utf-8") as f:
    json.dump(blueprint_mod, f, separators=(",", ":"))
sizes = sorted(collections.Counter(s for _, s in ordered).values())
print(f"scale {S}: {len(ordered)} bricks to build + {len(decor_items)} platform blocks as decor, {len(sections)} sections "
      f"(per section min {sizes[0]}, median {sizes[len(sizes) // 2]}, max {sizes[-1]}); platform {stats['platform_m']} m, "
      f"building {stats['building_m']} m, roof {stats['roof_m']} m, dome {stats['dome_m']} m, minarets {stats['minaret_m']} m")
print("sites (bricks, sections):", [(PARTS[pi][2], per_part[PARTS[pi][2]], section_part.count(pi)) for pi in range(len(PARTS))])
print(f"prerequisites: all blocks below {sum(1 for i in range(len(geo)) if mode[i] == 0 and req[i])}, "
      f"row neighbour {sum(1 for m in mode if m == 1)}, "
      f"only on other sites, platform or ground {sum(1 for i in range(len(geo)) if not req[i] and i not in free)}, "
      f"with cross-site blocks below {sum(1 for x in xreq if x)}, free without support {len(free)}")
for k in type_keys:
    if counts.get(k):
        print(f"  {counts[k]:6d}  {TYPES[k][0]} {TYPES[k][1]}")
print(f"-> {dst}\n-> {dst_mod} ({os.path.getsize(dst_mod) / 1e6:.1f} MB)")
