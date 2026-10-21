"""Simplified Notre-Dame de Paris from Brick by Brick bricks (preview + future blueprint).

Grid: 1 cell = 0.21 m in x, y, z (the game's brick unit). Walls are one cell thick, laid in running bond with
2x1 blocks. Roof tiles lie flat in rows that step in by one cell per layer (45 degrees, like the game's own roofs,
chamfered side towards the eave). Doors and windows are framed like the game's house: upright "2x1x2 Blocks" as
jambs, the same block lying flat as lintel, "2x2 Window" pieces as sill or drip cap; the portals are open passages.
A drum of curved wedge blocks (the library's round-tower pieces) carries the spire at the crossing. A walkable
scaffold (visuals + colliders only, no bricks) leads from the ground up a stair tower, over a bridge to a spiral
around drum and spire, and from the spiral over a bridge to both bell towers.

Axes (game/Unity coordinates): x = width (centered), y = up (0 = top of the plinth), z = length (0 = west facade).
Yaw convention (Unity): yaw t maps local +x to (cos t, 0, -sin t) and local +z to (sin t, 0, cos t).

Usage:  py gen_notredame.py [scale]   ->  ../blueprints/notredame_preview.json
"""
import json
import math
import os
import sys

S = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
CELL = 0.21


def c(v):
    return int(round(v * S))


def c2(v):
    """Even number of cells, so 2x2 roof tiles cover the span exactly."""
    return 2 * int(round(v * S / 2))


# ---- Dimensions (cells at scale 1, about 1:4 of the real building) ----
TW = c2(18)          # tower width and depth
FC = c2(14)          # facade center width (= nave width)
FD = c2(6)           # facade center depth in front of the nave
HALF_F = TW + FC // 2
HALF_B = c2(28)      # half body width (nave + double aisles)
HALF_N = c2(8)       # half nave width (clerestory walls)
HALF_T = c2(32)      # half transept width
Z_NAVE0 = TW
Z_TR0 = c2(88)
Z_TR1 = Z_TR0 + 2 * HALF_N          # transept as wide as the nave -> same ridge height
Z_CH = c2(124)
H_A = c(14)          # aisle wall height
H_N = c(39)          # clerestory height
H_F = c(52)          # facade center (gallery)
H_T = c(82)          # towers
H_S = c(114)         # spire top
Z_X = (Z_TR0 + Z_TR1) // 2
H_R = H_N + HALF_N - 2              # ridge of 45-degree roofs (rows step one cell in per layer)
AISLE_RISE = (HALF_B - HALF_N) // 2  # aisle roofs: rows step two cells in per layer
WIN = 4                              # window width (cells), even -> two sills


def in_solid(x, y, z):
    if y < 0:
        return True
    px, pz = x + 0.5, z + 0.5
    ax = abs(px)
    if HALF_F - TW <= ax < HALF_F and 0 <= pz < TW and y < H_T:
        return True
    if ax < FC / 2 and 0 <= pz < FD + TW and y < H_F:
        return True
    if ax < HALF_B and Z_NAVE0 <= pz < Z_CH and y < H_A:
        return True
    if ax < HALF_N and FD <= pz < Z_CH and y < H_N:
        return True
    if ax < HALF_T and Z_TR0 <= pz < Z_TR1 and y < H_N:
        return True
    if pz >= Z_CH:
        r = math.hypot(px, pz - Z_CH)
        if r < HALF_B and y < H_A:
            return True
        if r < HALF_N and y < H_N:
            return True
    return False


def keeps_flat_top(x, z):
    ax, pz = abs(x + 0.5), z + 0.5
    return (pz < TW and ax < HALF_F) or (ax < FC / 2 and pz < FD + TW)


# ---- 1) Shell ----
X0, X1 = -HALF_T - 6, HALF_T + 6
Z1 = Z_CH + HALF_B + 4
vox = {}
for x in range(X0, X1):
    for z in range(-2, Z1):
        for y in range(0, H_T):
            if not in_solid(x, y, z):
                continue
            side = any(not in_solid(x + dx, y, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            top = not in_solid(x, y + 1, z)
            if side or (top and keeps_flat_top(x, z)):
                vox[(x, y, z)] = "S"


# Tower platforms: parapet + pierced layer, corner pinnacles; balustrade on the gallery between the towers
def balustrade(cells, y0):
    for (x, z) in cells:
        vox.setdefault((x, y0, z), "S")
        if (x + z) % 2 == 0:
            vox.setdefault((x, y0 + 1, z), "S")


for sx in (-1, 1):
    xs_t = range(HALF_F - TW, HALF_F) if sx > 0 else range(-HALF_F, -HALF_F + TW)
    x_lo, x_hi = min(xs_t), max(xs_t)
    balustrade([(x, z) for x in xs_t for z in range(0, TW) if x in (x_lo, x_hi) or z in (0, TW - 1)], H_T)
    for cx_, cz_ in ((x_lo, 0), (x_hi, 0), (x_lo, TW - 1), (x_hi, TW - 1)):
        ix = 1 if cx_ == x_lo else -1
        iz = 1 if cz_ == 0 else -1
        for y in range(H_T, H_T + 4):          # short pinnacles: tower tops must stay within reach of the lift (17.05 m + 5 m)
            for (px_, pz_) in ((cx_, cz_), (cx_ + ix, cz_), (cx_, cz_ + iz), (cx_ + ix, cz_ + iz)):
                vox[(px_, y, pz_)] = "S"
        vox[(cx_, H_T + 4, cz_)] = "S"
balustrade([(x, 0) for x in range(-FC // 2, FC // 2)], H_F)


def pointed(u, v, w, h):
    half = w / 2
    if abs(u) > half or v < 0 or v >= h:
        return False
    spring = h - half * 1.4
    if v < spring:
        return True
    t = (v - spring) / max(1e-6, h - spring)
    return abs(u) <= half * math.sqrt(max(0.0, 1 - t * t))


def rose(px, py, r_out):
    r = math.hypot(px, py)
    if r >= r_out:
        return None
    ang = math.degrees(math.atan2(py, px)) % 30
    return "S" if (r > r_out - 0.6 or abs(r - r_out / 2) < 0.6 or ang < 4 or r < 0.9) else "G"


# ---- 2) Openings ----
pieces = []   # (key, x_m, y_m, z_m, yaw_deg, part, pitch_deg, cells)   free pieces with explicit pose (frames, wedges)
for (x, y, z), m in list(vox.items()):
    px = x + 0.5
    if z == 0:
        if c(20) <= y < c(23) and abs(px) < HALF_F - 1 and (x % 2 == 0):
            vox[(x, y, z)] = "D"
        if abs(px) < HALF_F - 1 and c(44) <= y < c(50) and (x % 3 != 0):
            vox[(x, y, z)] = "D"
        if abs(px) < FC / 2:
            rv = rose(px, y + 0.5 - c(33), c(6.2))
            if rv:
                vox[(x, y, z)] = rv

BAY = c2(12)
AISLE_WIN_Y = c(3)
CLER_WIN_Y = H_A + AISLE_RISE + 2          # above the aisle roof
bays = []
zb = Z_NAVE0 + BAY // 2
while zb < Z_CH - 2:
    if not (Z_TR0 - 3 <= zb < Z_TR1 + 3):
        bays.append(zb)
    zb += BAY
for (x, y, z), m in list(vox.items()):
    px, pz = x + 0.5, z + 0.5
    if abs(abs(px) - (HALF_T - 0.5)) < 0.6 and Z_TR0 <= pz < Z_TR1:
        rv = rose(pz - Z_X, y + 0.5 - c(26), c(6.2))
        if rv:
            vox[(x, y, z)] = rv
for k in [k for k in vox if k[2] >= Z_CH]:      # the apse is laid in true rings (section 4b)
    del vox[k]

# Doors and windows framed like the game's house (measured there): jambs of upright "2x1x2 Blocks" (2 cells deep,
# 1 along the wall, 2 high; centers 0.073 m in front of the wall center), the same block lying flat (pitch -90) for
# horizontal parts, "2x2 Window" pieces as drip cap over doors (0.085 m out) or as sill under windows (0.173 m out;
# local -x points outwards). Windows close in a stepped point (one cell in per row) framed by lying blocks; portals
# are open passages with a flat lintel, a stepped plum tympanum and a stepped archivolt above.
JAMB_OUT, CAP_OUT, SILL_OUT = 0.073, 0.085, 0.173


class Wall:
    """A straight wall one cell thick: axis "x" runs along x at z = fixed, axis "z" runs along z at x = fixed."""

    def __init__(self, axis, fixed, out):
        self.axis, self.fixed, self.out = axis, fixed, out

    def cell(self, u, y, d=0):
        return (u, y, self.fixed + d * self.out) if self.axis == "x" else (self.fixed + d * self.out, y, u)

    def pos(self, u, y, out_off):
        depth = (self.fixed + 0.5) * CELL + self.out * out_off
        return (u * CELL, y * CELL, depth) if self.axis == "x" else (depth, y * CELL, u * CELL)

    def yaw_depth(self):
        """Puts a piece's local x (its depth) across the wall."""
        return 90 if self.axis == "x" else 0

    def yaw_out(self):
        """Turns a sloped piece's local -x outwards."""
        if self.axis == "z":
            return 0 if self.out < 0 else 180
        return -90 if self.out < 0 else 90


def frame(wall, u0, w, y0, h, kind, part, fill=None, sill=True):
    """Opening w cells wide (first cell u0 along the wall), h straight rows from y0, framed like the game's house.
    fill = material left in the opening (None = open)."""
    lo, hi, uc = u0 - 1, u0 + w, u0 + w // 2

    def take(u, y):
        vox.pop(wall.cell(u, y), None)
        return [wall.cell(u, y), wall.cell(u, y, 1)]          # wall cell + the cell the piece sticks out into

    def opening(u, y):
        cl = wall.cell(u, y)
        if fill is None:
            vox.pop(cl, None)
        elif cl in vox:
            vox[cl] = fill

    def lying(u, y):                                          # lying block over cells u, u + 1
        pieces.append(("JAMB", *wall.pos(u + 1, y + 0.5, JAMB_OUT), wall.yaw_depth(), part, -90, take(u, y) + take(u + 1, y)))

    def sloped(y, out_off):                                   # "2x2 Window" pieces over the width of the frame
        for u in range(lo, hi + 1, 2):
            pieces.append(("SILL", *wall.pos(u + 1, y + 0.5, out_off), wall.yaw_out(), part, 0, take(u, y) + take(u + 1, y)))

    for u in range(u0, u0 + w):
        for y in range(y0, y0 + h):
            opening(u, y)
    for u in (lo, hi):
        for y in range(y0, y0 + h, 2):
            pieces.append(("JAMB", *wall.pos(u + 0.5, y + 1, JAMB_OUT), wall.yaw_depth(), part, 0, take(u, y) + take(u, y + 1)))
    if kind == "window":
        if sill:
            sloped(y0 - 1, SILL_OUT)
        for k in range(1, w // 2):                            # stepped point: one cell in per row
            y, half = y0 + h - 1 + k, w // 2 - k
            for u in range(uc - half, uc + half):
                opening(u, y)
            lying(uc - half - 2, y)
            lying(uc + half, y)
        y_apex = y0 + h - 1 + w // 2
    else:
        for u in range(lo, hi + 1, 2):                        # flat lintel + drip cap, then the tympanum
            lying(u, y0 + h)
        sloped(y0 + h + 1, CAP_OUT)
        for k in range(w // 2):
            y = y0 + h + 2 + k
            for u in range(u0 + k, u0 + w - k):
                if wall.cell(u, y) in vox:
                    vox[wall.cell(u, y)] = "D"
            lying(lo - 1 + k, y)
            lying(hi - k, y)
        y_apex = y0 + h + 2 + w // 2
    lying(uc - 2, y_apex)
    lying(uc, y_apex)


FACADE = Wall("x", 0, -1)
frame(FACADE, -c2(6.5) // 2, c2(6.5), 0, c2(10), "door", "West front")                   # central portal
for sx in (-1, 1):
    frame(FACADE, sx * (HALF_F - TW // 2) - c2(5) // 2, c2(5), 0, c2(8.5), "door", "West front")
for x_wall, out in ((-HALF_T, -1), (HALF_T - 1, 1)):                                        # transept portals
    frame(Wall("z", x_wall, out), Z_X - c2(5) // 2, c2(5), 0, c2(8.5), "door", "Transept")
for bc in bays:
    part = "Nave" if bc < Z_TR0 else "Choir"
    for x_wall, out in ((-HALF_B, -1), (HALF_B - 1, 1)):
        frame(Wall("z", x_wall, out), bc - WIN // 2, WIN, AISLE_WIN_Y, c2(5), "window", part)
    for x_wall, out in ((-HALF_N, -1), (HALF_N - 1, 1)):
        frame(Wall("z", x_wall, out), bc - WIN // 2, WIN, CLER_WIN_Y, c2(8), "window", part)
# Belfry openings on all four sides of both towers, with plum louvers inside
TL_Y, TL_H = c(56), c2(18)
for sx in (-1, 1):
    x_mid = sx * (HALF_F - TW // 2)
    sides = ((-HALF_F, -1), (-(HALF_F - TW) - 1, 1)) if sx < 0 else ((HALF_F - TW, -1), (HALF_F - 1, 1))
    for off in (-c(4), c(4)):
        for wall in (FACADE, Wall("x", TW - 1, 1)):
            frame(wall, x_mid + off - WIN // 2, WIN, TL_Y, TL_H, "window", "West front", fill="D", sill=False)
        for x_wall, out in sides:
            frame(Wall("z", x_wall, out), TW // 2 + off - WIN // 2, WIN, TL_Y, TL_H, "window", "West front", fill="D", sill=False)

# ---- 3) Flying buttresses with pinnacles ----
z = Z_NAVE0 + BAY
while z < Z_CH - 2:
    if not (Z_TR0 - 3 <= z < Z_TR1 + 3):
        for sx in (-1, 1):
            for dz in (0, 1):
                for x in range(HALF_B + 1, HALF_B + 4):
                    for y in range(0, H_A + c(8)):
                        vox.setdefault((x if sx > 0 else -x - 1, y, z + dz), "S")
                xo = HALF_B + 3
                xo = xo if sx > 0 else -xo - 1
                for y in range(H_A + c(8), H_A + c(8) + c(3)):
                    vox.setdefault((xo, y, z + dz), "S")
                if dz == 0:
                    for y in range(H_A + c(8) + c(3), H_A + c(8) + c(3) + 2):
                        vox.setdefault((xo, y, z), "S")
                x_out, y_out = HALF_B + 2, H_A + c(8)
                x_in, y_in = HALF_N, H_N - c(8)
                steps = x_out - x_in
                for i in range(steps + 1):
                    xx = x_out - i
                    yy = int(round(y_out + (y_in - y_out) * i / steps))
                    for t in (0, 1):
                        vox.setdefault((xx if sx > 0 else -xx - 1, yy + t, z + dz), "S")
    z += BAY

# ---- 4) Roof tiles: flat 2x2 pieces, rows stepping in; local +x points up the slope (towards the ridge) ----
tiles = {}        # (x0, y, z0) -> (yaw, part)
tile_cells = set()


def add_tile(x0, y, z0, yaw, part):
    cells = [(x0 + i, y, z0 + k) for i in (0, 1) for k in (0, 1)]
    if any(cl in vox or cl in tile_cells for cl in cells):
        return False
    tiles[(x0, y, z0)] = (yaw, part)
    tile_cells.update(cells)
    return True


def part_of(x, z):
    ax, pz = abs(x + 0.5), z + 0.5
    if pz < TW + FD and ax < HALF_F:
        return "West front"
    if Z_TR0 <= pz < Z_TR1:
        return "Transept"
    if pz >= Z_TR1:
        return "Choir"
    return "Nave"


# Transept first (its ridge runs across the crossing), then nave + choir
for k in range(HALF_N - 1):
    for xx in range(-HALF_T, HALF_T, 2):
        add_tile(xx, H_N + k, Z_TR0 + k, -90, "Transept")             # +x -> +z (towards the ridge)
        add_tile(xx, H_N + k, Z_TR1 - 2 - k, 90, "Transept")
for k in range(HALF_N - 1):
    for zz in range(FD + TW, Z_CH, 2):
        add_tile(-HALF_N + k, H_N + k, zz, 0, part_of(0, zz))           # left slope, +x towards the ridge
        add_tile(HALF_N - 2 - k, H_N + k, zz, 180, part_of(0, zz))
# Aisles: lean-to, rows two cells apart, one layer up each (about 26 degrees)
for k in range(AISLE_RISE):
    for zz in range(Z_NAVE0, Z_CH, 2):
        if Z_TR0 <= zz < Z_TR1:
            continue
        add_tile(-HALF_B + 2 * k, H_A + k, zz, 0, part_of(0, zz))
        add_tile(HALF_B - 2 - 2 * k, H_A + k, zz, 180, part_of(0, zz))
# ---- 4b) Apse in true rings ----
# The game checks no geometry when a brick is set (ConstructionSiteState.CanPlace: slot free, section open,
# prerequisites met), so blocks may sit at small angles and overlap slightly: half rings of 2x1 blocks along the
# wall circles (running bond, half blocks at the ends) and half rings of flat roof tiles that continue the straight
# rows of nave and aisles. Angles phi are measured from +x towards +z around the apse center.
APSE_Z = Z_CH * CELL


def ring_pose(r, phi):
    a = math.radians(phi)
    return r * math.cos(a), APSE_Z + r * math.sin(a)


def ring_wall(r_cells, y0, y1, windows, part):
    """Half ring wall of 2x1 blocks along the circle (running bond) with windows framed like the straight ones.
    Positions along the ring are in cells of arc length u (0 at phi = 0); windows = [(phi_c, w, wy0, h)]."""
    r = r_cells * CELL
    U = math.pi * r / CELL
    blocked = {}

    def put(key, u, y, out_off, pitch, yaw_of):
        phi = math.degrees(u * CELL / r)
        x, z = ring_pose(r + out_off, phi)
        pieces.append((key, x, y * CELL, z, yaw_of(phi), part, pitch, []))

    def block(y, a, b):
        blocked.setdefault(y, []).append((a, b))

    radial = lambda phi: -phi           # local x (depth) along the radius
    inwards = lambda phi: 180 - phi     # sloped piece: local -x outwards
    for (phi_c, w, wy0, h) in windows:
        uc = math.radians(phi_c) * r / CELL
        block(wy0 - 1, uc - w / 2 - 1, uc + w / 2 + 1)
        for k in range(w // 2 + 1):
            put("SILL", uc - w / 2 + 2 * k, wy0 - 0.5, SILL_OUT, 0, inwards)
        for y in range(wy0, wy0 + h):
            block(y, uc - w / 2 - 1, uc + w / 2 + 1)
        for y in range(wy0, wy0 + h, 2):
            for uj in (uc - w / 2 - 0.5, uc + w / 2 + 0.5):
                put("JAMB", uj, y + 1, JAMB_OUT, 0, radial)
        for k in range(1, w // 2 + 1):
            y, half = wy0 + h - 1 + k, w // 2 - k
            block(y, uc - half - 2, uc + half + 2)
            for ul in ((uc - half - 1, uc + half + 1) if half else (uc - 1, uc + 1)):
                put("JAMB", ul, y + 0.5, JAMB_OUT, -90, radial)

    def sizes_for(length):
        n2 = int(length // 2)
        rem = length - 2 * n2
        return [2] * n2 + ([2] if rem >= 1.5 else [1] if rem >= 0.5 else [])

    for y in range(y0, y1):
        arcs, pos = [], 0.0
        for a, b in sorted(blocked.get(y, [])):
            if a > pos:
                arcs.append((pos, a))
            pos = max(pos, b)
        if pos < U:
            arcs.append((pos, U))
        for a, b in arcs:
            length = b - a
            sizes = [1] + sizes_for(length - 2) + [1] if (y - y0) % 2 and length >= 3 else sizes_for(length)
            if not sizes:
                continue
            f = length / sum(sizes)                 # spread the rest over all joints (slight gaps or overlaps)
            u = a
            for s in sizes:
                put("S2" if s == 2 else "S1", u + s * f / 2, y + 0.5, 0.0, 0, radial)
                u += s * f


LIFT = 0.005   # every other tile in a ring 5 mm higher: overlapping tops are not coplanar (no z-fighting)


def lift(i, n, closed):
    return LIFT * (2 if closed and n % 2 and i == n - 1 else i % 2)


def tile_ring(r, y, part):
    """Half ring of flat 2x2 tiles at center radius r; local +x points to the apse center (like the straight rows)."""
    n = int(math.ceil(math.pi * (r + CELL) / (2 * CELL)))
    for i in range(n):
        phi = (i + 0.5) * 180.0 / n
        x, z = ring_pose(r, phi)
        pieces.append(("R4", x, (y + 0.5) * CELL + lift(i, n, False), z, 180 - phi, part, 0, []))


ring_wall(HALF_B - 0.5, 0, H_A, [(11.25 + 22.5 * j, WIN, AISLE_WIN_Y, c2(5)) for j in range(8)], "Choir")
ring_wall(HALF_N - 0.5, H_A, H_N, [(30 + 60 * j, WIN, CLER_WIN_Y, c2(8)) for j in range(3)], "Choir")
for k in range(AISLE_RISE):
    tile_ring((HALF_B - 1 - 2 * k) * CELL, H_A + k, "Roof · Choir")
for k in range(HALF_N - 1):
    tile_ring((HALF_N - 1 - k) * CELL, H_N + k, "Roof · Choir")

# ---- 5) Drum of curved wedges at the crossing + round stepped spire ----
# Ring rule measured on the library's round tower: wedge centers on radius 1.392 m, ~20 degrees apart,
# ring center at local (-0.6, 0, 1.26) of every wedge -> yaw = 115.46 - (phi + 180) degrees.
RING_R = 1.392
DRUM_Y0 = H_R + 1                       # first ring layer (cells)
DRUM_LAYERS = c(10)
cxm, czm = 0.0, Z_X * CELL               # crossing center (m)
for layer in range(DRUM_LAYERS):
    off = 10 if layer % 2 else 0         # running bond between rings
    for i in range(18):
        phi = i * 20 + off
        px_m = cxm + RING_R * math.cos(math.radians(phi))
        pz_m = czm + RING_R * math.sin(math.radians(phi))
        yaw = 115.46 - (phi + 180)
        pieces.append(("ARC", px_m, (DRUM_Y0 + layer + 0.5) * CELL, pz_m, yaw, "Drum", 0, []))
# Solid base under the drum down to the roof (stone), so the drum does not float over the slopes
drum_cells_r = RING_R + 0.27
for x in range(-9, 9):
    for zz in range(Z_X - 9, Z_X + 9):
        if math.hypot((x + 0.5) * CELL - cxm, (zz + 0.5) * CELL - czm) > drum_cells_r:
            continue
        top = max([ty + 1 for (tx, ty, tz) in tiles if tx <= x < tx + 2 and tz <= zz < tz + 2] or [H_N])
        for y in range(top, DRUM_Y0):
            if (x, y, zz) not in tile_cells:
                vox.setdefault((x, y, zz), "S")
# Spire: full rings of flat tiles above the drum, radius shrinking with height (tiles overlap slightly, see 4b)
SPIRE_Y0 = DRUM_Y0 + DRUM_LAYERS
r0 = RING_R + 0.15
for y in range(SPIRE_Y0, H_S):
    t = (y - SPIRE_Y0) / max(1, H_S - SPIRE_Y0)
    r = max(0.12, r0 * (1 - t))
    n = max(3, int(math.ceil(2 * math.pi * (r + CELL) / (2 * CELL))))
    for i in range(n):
        phi = (i + 0.5 * (y % 2)) * 360.0 / n
        a = math.radians(phi)
        pieces.append(("R4", cxm + r * math.cos(a), (y + 0.5) * CELL + lift(i, n, True), czm + r * math.sin(a), 180 - phi, "Spire", 0, []))


def roof_top(x, z):
    top = None
    for (tx, ty, tz) in tiles:
        if tx <= x < tx + 2 and tz <= z < tz + 2:
            top = ty + 1 if top is None else max(top, ty + 1)
    return top


accents = []
for dx, dz in ((0, 1), (0, -1), (1, 0), (-1, 0)):     # twelve apostles on the four ridges around the drum
    for step in (3, 5, 7):
        d = int(round(drum_cells_r / CELL)) + step
        ax, az = (0, Z_X + dz * d) if dx == 0 else (dx * d, Z_X)
        top = roof_top(ax, az)
        if top is None:
            continue
        for dy in (0, 1):
            accents.append(("green1", ax, top + dy, az))
spire_top = H_S
accents.append(("gold1", 0, spire_top, Z_X))

# ---- 6) Scaffold (no bricks: plank boxes + colliders for the mod) ----
# Stair tower from the ground in front of the north transept -> bridge at ridge height -> square spiral around drum
# and spire -> at tower height a bridge west to a cross bridge between both bell towers (gaps in their parapets).
# Walking surfaces are the tops of 6 cm planks; steps rise one cell (0.21 m) per 0.42 m.
scaffold = []   # (cx, cy, cz, sx, sy, sz) meters
W, PLANK, RAIL, POST = 0.85, 0.06, 1.0, 0.12
STEP_RISE, STEP_RUN = CELL, 2 * CELL


def plank(x0, x1, z0, z1, walk):
    scaffold.append(((x0 + x1) / 2, walk - PLANK / 2, (z0 + z1) / 2, abs(x1 - x0), PLANK, abs(z1 - z0)))


def rail(x0, x1, z0, z1, y):
    scaffold.append(((x0 + x1) / 2, y, (z0 + z1) / 2, max(abs(x1 - x0), 0.06), 0.06, max(abs(z1 - z0), 0.06)))


def spiral(cx, cz, mid, corners, phase, y0, n):
    """n steps on a square ring (centerline half-size mid) around (cx, cz), walked in corner order; step i walks at
    y0 + i * STEP_RISE. Returns [(x, z, walk, side)] of the step centers."""
    side = 2 * mid
    out = []
    for i in range(n):
        along = (phase + i * STEP_RUN) % (4 * side)
        s_idx = int(along // side)
        f = (along - s_idx * side) / side
        (ax0, az0), (ax1, az1) = corners[s_idx], corners[(s_idx + 1) % 4]
        px_m = cx + (ax0 + (ax1 - ax0) * f) * mid
        pz_m = cz + (az0 + (az1 - az0) * f) * mid
        walk = y0 + i * STEP_RISE
        if ax0 != ax1:
            plank(px_m - STEP_RUN / 2 - 0.01, px_m + STEP_RUN / 2 + 0.01, pz_m - W / 2, pz_m + W / 2, walk)
        else:
            plank(px_m - W / 2, px_m + W / 2, pz_m - STEP_RUN / 2 - 0.01, pz_m + STEP_RUN / 2 + 0.01, walk)
        out.append((px_m, pz_m, walk, s_idx))
    return out


def side_of(phase, i, side):
    return int(((phase + i * STEP_RUN) % (4 * side)) // side)


# Spiral around drum and spire. Its first step lies three cells above the ridge (clear of the apostles), the step at
# tower height sits in the middle of the west side, and it ends at a corner so the top platform leaves the last
# flight open (headroom).
MID = RING_R + 0.925
A_IN, B_OUT = MID - W / 2, MID + W / 2
SIDE = 2 * MID
DRUM_CORNERS = [(-1, -1), (1, -1), (1, 1), (-1, 1)]       # side 0 = west side, walked towards +x
BASE_CELLS = DRUM_Y0 + 3
y_base = BASE_CELLS * CELL
DECK = H_T * CELL                                          # tower platforms
i_deck = H_T - BASE_CELLS
phase = (MID - i_deck * STEP_RUN) % (4 * SIDE)
y_top_target = (spire_top + 1) * CELL - 4.5                # spire tip within 5 m reach from the top platform
n = int(math.ceil((y_top_target - y_base) / STEP_RISE))
while side_of(phase, n, SIDE) == side_of(phase, n - 1, SIDE):
    n += 1
steps = spiral(cxm, czm, MID, DRUM_CORNERS, phase, y_base, n)
assert steps[0][3] == 0 and steps[i_deck][3] == 0 and abs(steps[i_deck][0] - cxm) < 0.01, "spiral junctions moved"
y_top = y_base + n * STEP_RISE
last_side = steps[-1][3]
for (ax, az) in DRUM_CORNERS:                              # top platform: corners + three sides
    plank(cxm + ax * MID - W / 2, cxm + ax * MID + W / 2, czm + az * MID - W / 2, czm + az * MID + W / 2, y_top)
for s_idx in range(4):
    if s_idx == last_side:
        continue
    (ax0, az0), (ax1, az1) = DRUM_CORNERS[s_idx], DRUM_CORNERS[(s_idx + 1) % 4]
    xm, zm = cxm + (ax0 + ax1) / 2 * MID, czm + (az0 + az1) / 2 * MID
    if ax0 != ax1:
        plank(xm - MID + W / 2, xm + MID - W / 2, zm - W / 2, zm + W / 2, y_top)
    else:
        plank(xm - W / 2, xm + W / 2, zm - MID + W / 2, zm + MID - W / 2, y_top)
rail(cxm - B_OUT, cxm + B_OUT, czm - B_OUT, czm - B_OUT, y_top + RAIL)
rail(cxm - B_OUT, cxm + B_OUT, czm + B_OUT, czm + B_OUT, y_top + RAIL)
rail(cxm - B_OUT, cxm - B_OUT, czm - B_OUT, czm + B_OUT, y_top + RAIL)
rail(cxm + B_OUT, cxm + B_OUT, czm - B_OUT, czm + B_OUT, y_top + RAIL)

# Stair tower from the ground; its last flight runs towards +x on the line of the drum ring's west side
MID_T = 1.2
SIDE_T = 2 * MID_T
T_CORNERS = [(-1, 1), (1, 1), (1, -1), (-1, -1)]
cz_t = czm - MID - MID_T
cx_t = -(HALF_T * CELL + 0.3 + MID_T + W / 2)
n_t = BASE_CELLS - 1                                       # walks 0.21 m ... one step below the bridge
phase_t = (SIDE_T - STEP_RUN / 2 - (n_t - 1) * STEP_RUN) % (4 * SIDE_T)
spiral(cx_t, cz_t, MID_T, T_CORNERS, phase_t, STEP_RISE, n_t)

# Bridge 1 (ridge height): stair tower -> first spiral step
z_b1 = czm - MID
plank(cx_t + MID_T, steps[0][0] - STEP_RUN / 2 - 0.01, z_b1 - W / 2, z_b1 + W / 2, y_base)
for zz in (z_b1 - W / 2, z_b1 + W / 2):
    rail(cx_t + MID_T + W / 2, cxm - B_OUT, zz, zz, y_base + RAIL)
# Bridge 2 (tower height): spiral -> cross bridge; bridge 3 between the bell towers
z_cross = TW * CELL / 2
x_tw = (HALF_F - TW) * CELL                                # inner faces of the towers
plank(cxm - W / 2, cxm + W / 2, z_cross + W / 2, czm - B_OUT, DECK)
plank(-x_tw, x_tw, z_cross - W / 2, z_cross + W / 2, DECK)
for xx in (cxm - W / 2, cxm + W / 2):
    rail(xx, xx, z_cross + W / 2, czm - B_OUT, DECK + RAIL)
rail(-x_tw, x_tw, z_cross - W / 2, z_cross - W / 2, DECK + RAIL)
rail(-x_tw, cxm - W / 2, z_cross + W / 2, z_cross + W / 2, DECK + RAIL)
rail(cxm + W / 2, x_tw, z_cross + W / 2, z_cross + W / 2, DECK + RAIL)
for zc in range(int(math.floor((z_cross - W / 2) / CELL)), int(math.ceil((z_cross + W / 2) / CELL))):
    for xc in (-(HALF_F - TW) - 1, HALF_F - TW):           # parapet gaps where the cross bridge lands
        for y in (H_T, H_T + 1):
            vox.pop((xc, y, zc), None)

# Posts down to whatever is below (roof, wall top or ground)
col_ys = {}
for (x, y, z) in list(vox) + list(tile_cells) + [cl for p in pieces for cl in p[7]] + [(a[1], a[2], a[3]) for a in accents]:
    col_ys.setdefault((x, z), []).append(y)


def post(x, z, top):
    cols = {(int(math.floor((x + dx) / CELL)), int(math.floor((z + dz) / CELL))) for dx in (-POST / 2, POST / 2) for dz in (-POST / 2, POST / 2)}
    ys = [y for cl in cols for y in col_ys.get(cl, []) if (y + 1) * CELL <= top]
    foot = (max(ys) + 1) * CELL if ys else 0.0
    scaffold.append((x, (foot + top) / 2, z, POST, top - foot, POST))


for (ax, az) in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
    for r in (A_IN, B_OUT):
        post(cxm + ax * r, czm + az * r, y_top + RAIL)
    for r in (MID_T - W / 2, MID_T + W / 2):
        post(cx_t + ax * r, cz_t + az * r, y_base + RAIL)
x0_b1, x1_b1 = cx_t + MID_T + W / 2 + 0.3, cxm - B_OUT - 0.3
for k in range(int((x1_b1 - x0_b1) // 2.4) + 2):
    xx = min(x0_b1 + k * 2.4, x1_b1)
    for zz in (z_b1 - W / 2, z_b1 + W / 2):
        post(xx, zz, y_base + RAIL)
z0_b2, z1_b2 = z_cross + W / 2 + 0.3, czm - B_OUT - 0.3
for k in range(int((z1_b2 - z0_b2) // 2.4) + 2):
    zz = min(z0_b2 + k * 2.4, z1_b2)
    for xx in (cxm - W / 2, cxm + W / 2):
        post(xx, zz, DECK + RAIL)

# ---- 7) Brick packing of the voxel walls: 2x1 in running bond, leftovers 1x1 ----
assigned = set()
bricks = []
for y in sorted({k[1] for k in vox}):
    layer = sorted((k for k in vox if k[1] == y), key=lambda k: (k[2], k[0]))
    for v in layer:
        if v in assigned:
            continue
        x, _, z = v
        m = vox[v]
        pref = (("z", 0, 1), ("x", 1, 0)) if y % 2 == 0 else (("x", 1, 0), ("z", 0, 1))
        for d, dx, dz in pref:
            if ((z if d == "z" else x) + y) % 2 != 0:
                continue
            w = (x + dx, y, z + dz)
            if w in vox and w not in assigned and vox[w] == m:
                assigned.update((v, w))
                bricks.append((m, 2, x, y, z, d))
                break
    for v in layer:
        if v in assigned:
            continue
        x, _, z = v
        m = vox[v]
        for d, dx, dz in (("z", 0, 1), ("x", 1, 0), ("z", 0, -1), ("x", -1, 0)):
            w = (x + dx, y, z + dz)
            if w in vox and w not in assigned and vox[w] == m:
                assigned.update((v, w))
                bricks.append((m, 2, min(x, w[0]), y, min(z, w[2]), d))
                break
        else:
            assigned.add(v)
            bricks.append((m, 1, x, y, z, "x"))

# ---- 8) Types, sections, output ----
TYPES = {
    "S2": {"name": "2×1 Block", "color": "Beige", "group": "library.beige", "asset": "LibraryNew_Brick_FEB8053A", "hex": "#e2ce9d", "long": "z"},
    "S1": {"name": "1×1 Block", "color": "Beige", "group": "library.beige", "asset": "LibraryNew_Brick_D800AC09", "hex": "#e2ce9d"},
    "G2": {"name": "2×1 Block", "color": "Blue", "group": "pharmacy.blue", "asset": "Pharmacy_Brick_06A152F5", "hex": "#5e8bb0", "long": "x"},
    "G1": {"name": "1×1 Block", "color": "Blue", "group": "pharmacy.blue", "asset": "Pharmacy_Brick_169A37B3", "hex": "#5e8bb0"},
    "D2": {"name": "2×1 Block", "color": "Plum", "group": "tavern.plum", "asset": "Tavern_Brick_9DEF6649", "hex": "#673e5c", "long": "z"},
    "D1": {"name": "1×1 Block", "color": "Plum", "group": "tavern.plum", "asset": "Tavern_Brick_CCE9C299", "hex": "#673e5c"},
    "R4": {"name": "2×2 Roof", "color": "Anthracite", "group": "bakery.anthracite", "asset": "Bakery_Brick_6ED2F14B", "hex": "#454a4f"},
    "SILL": {"name": "2×2 Window", "color": "Grey", "group": "bakery.grey", "asset": "Bakery_Brick_402F42D4", "hex": "#c9d4d4"},
    "JAMB": {"name": "2×1×2 Block", "color": "Grey", "group": "bakery.grey", "asset": "Bakery_Brick_4018D562", "hex": "#c9d4d4"},
    "ARC": {"name": "Long Block", "color": "Beige", "group": "library.beige", "asset": "LibraryNew_Brick_4B9D4C0B", "hex": "#e2ce9d"},
    "green1": {"name": "1×1 Block", "color": "Green", "group": "tower.green", "asset": "Tower_Brick_9AB8D122", "hex": "#5faf58"},
    "gold1": {"name": "1×1 Block", "color": "Yellow", "group": "bakery.yellow", "asset": "Bakery_Brick_EBE67C24", "hex": "#cf9c61"},
}
type_keys = list(TYPES)
BAND = c(12)
sections, sec_index = [], {}


def section(name):
    if name not in sec_index:
        sec_index[name] = len(sections)
        sections.append(name)
    return sec_index[name]


rows = []       # [type, x_cm, y_cm, z_cm, yaw_deg, section]
cells_used = {}
overlaps = 0


def occupy(cells):
    global overlaps
    for cl in cells:
        if cl in cells_used:
            overlaps += 1
        cells_used[cl] = True


for (m, kind, x, y, z, d) in sorted(bricks, key=lambda b: (b[3], b[4], b[2])):
    key = f"{m}{kind}"
    long_axis = TYPES[key].get("long")
    sx, sz = (2, 1) if (kind == 2 and d == "x") else ((1, 2) if kind == 2 else (1, 1))
    yaw = 0 if (long_axis is None or long_axis == d) else 90
    occupy([(x + i, y, z + k) for i in range(sx) for k in range(sz)])
    rows.append([type_keys.index(key), round((x + sx / 2) * CELL * 100), round((y + 0.5) * CELL * 100),
                 round((z + sz / 2) * CELL * 100), yaw, section(f"{part_of(x, z)} · Level {y // BAND + 1}")])
for (x0, y, z0), (yaw, part) in sorted(tiles.items(), key=lambda t: (t[0][1], t[0][2], t[0][0])):
    occupy([(x0 + i, y, z0 + k) for i in (0, 1) for k in (0, 1)])
    rows.append([type_keys.index("R4"), round((x0 + 1) * CELL * 100), round((y + 0.5) * CELL * 100),
                 round((z0 + 1) * CELL * 100), round(yaw), section("Spire" if part == "Spire" else "Roof · " + part)])
for (key, xm, ym, zm, yaw, part, pitch, cells) in pieces:
    occupy(cells)
    if key == "ARC" or part == "Spire" or part.startswith("Roof"):
        sec = section("Drum" if key == "ARC" else part)
    else:
        sec = section(f"{part} · Level {int(ym / CELL) // BAND + 1}")
    rows.append([type_keys.index(key), round(xm * 100), round(ym * 100), round(zm * 100), round(yaw), sec] + ([pitch] if pitch else []))
for (key, x, y, z) in accents:
    occupy([(x, y, z)])
    rows.append([type_keys.index(key), round((x + 0.5) * CELL * 100), round((y + 0.5) * CELL * 100), round((z + 0.5) * CELL * 100), 0,
                 section("Spire")])
print(f"overlapping cells: {overlaps}")
hits = []
for (bx, by, bz, sx, sy, sz) in scaffold:
    rng = [range(int(math.floor((c0 - s / 2 + 0.005) / CELL)), int(math.floor((c0 + s / 2 - 0.005) / CELL)) + 1)
           for c0, s in ((bx, sx), (by, sy), (bz, sz))]
    hits += [(gx, gy, gz) for gx in rng[0] for gy in rng[1] for gz in rng[2] if (gx, gy, gz) in cells_used]
print(f"scaffold cells inside bricks: {len(hits)} {sorted(set(hits))[:12]}")


def order_key(name):
    if name == "Spire":
        return (5, 0, 0)
    if name == "Drum":
        return (4, 0, 0)
    if name.startswith("Roof"):
        return (3, 0, name)
    part, lvl = name.split(" · Level ")
    return (0, int(lvl), ["West front", "Nave", "Transept", "Choir"].index(part))


order = sorted(range(len(sections)), key=lambda i: order_key(sections[i]))
remap = {old: new for new, old in enumerate(order)}
sections = [sections[i] for i in order]
for r in rows:
    r[5] = remap[r[5]]

xs = [r[1] for r in rows]; zs = [r[3] for r in rows]; ys = [r[2] for r in rows]
data = {
    "scale": S,
    "cell": CELL,
    "types": [dict(TYPES[k], key=k) for k in type_keys],
    "sections": sections,
    "bricks": rows,
    "scaffold": [[round(v * 100) for v in b] for b in scaffold],
    "stats": {
        "total": len(rows),
        "length_m": round((max(zs) - min(zs)) / 100 + 0.42, 1),
        "width_m": round((max(xs) - min(xs)) / 100 + 0.42, 1),
        "tower_m": round(H_T * CELL, 1),
        "spire_m": round(max(ys) / 100 + 0.1, 1),
        "nave_m": round(H_N * CELL, 1),
        "scaffold_top_m": round(y_top, 1),
    },
}
here = os.path.dirname(os.path.abspath(__file__))
dst = os.path.join(here, "..", "blueprints", "notredame_preview.json")
with open(dst, "w", encoding="utf-8") as f:
    json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
counts = {}
for r in rows:
    counts[r[0]] = counts.get(r[0], 0) + 1
print(f"scale {S}: {len(rows)} bricks, {len(sections)} sections, {data['stats']['length_m']} x {data['stats']['width_m']} m, "
      f"towers {data['stats']['tower_m']} m, spire {data['stats']['spire_m']} m, scaffold top {data['stats']['scaffold_top_m']} m, "
      f"{len(scaffold)} scaffold boxes")
for i, k in enumerate(type_keys):
    print(f"  {counts.get(i, 0):6d}  {TYPES[k]['name']} {TYPES[k]['color']}")
