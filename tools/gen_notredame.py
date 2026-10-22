"""Simplified Notre-Dame de Paris from Brick by Brick bricks (preview + future blueprint).

Grid: 1 cell = 0.21 m in x, y, z (the game's brick unit). Walls are one cell thick, laid in running bond with
2x1 blocks. Roof tiles lie flat in rows that step in by one cell per layer (45 degrees, like the game's own roofs,
chamfered side towards the eave). Doors and windows are framed like the game's house: upright "2x1x2 Blocks" as
jambs, the same block lying flat as lintel, "2x2 Window" pieces as sill or drip cap; the portals are open passages.
A drum of curved wedge blocks (the library's round-tower pieces) carries the spire at the crossing. Arcades of pointed
arches carry every wall that stands above an aisle or a hall. A walkable scaffold (visuals + colliders only, no bricks)
leads from the ground up a stair tower and over a bridge to a spiral around drum and spire; stair towers and lanes
around the bell towers end in a cross bridge between both tower tops.

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
    if ax < FC / 2 and 0 <= pz < TW and y < H_F:
        return True
    if ax < HALF_B and Z_NAVE0 <= pz < Z_CH and y < H_A:
        return True
    if ax < HALF_N and Z_NAVE0 <= pz < Z_CH and y < H_N:
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
    return pz < TW and ax < HALF_F


# ---- 1) Shell ----
# A cell is wall when one of its 8 neighbours in the layer is outside: inner corners, where two walls meet, get their
# corner cell, so the walls interlock there instead of touching edge to edge.
X0, X1 = -HALF_T - 6, HALF_T + 6
Z1 = Z_CH + HALF_B + 4
vox = {}
for x in range(X0, X1):
    for z in range(-2, Z1):
        for y in range(0, H_T):
            if not in_solid(x, y, z):
                continue
            side = any(not in_solid(x + dx, y, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if dx or dz)
            top = not in_solid(x, y + 1, z)
            if side or (top and keeps_flat_top(x, z)):
                vox[(x, y, z)] = "S"


# ---- 1b) Inner walls: nothing hangs in the air ----
# The shell alone leaves walls standing on nothing: the clerestory walls over the aisles, the transept walls over the
# aisles, the back walls of the towers over the aisles, the towers' inner walls and the back wall over the hall
# between the towers. Walls down to the plinth carry them; section 2 opens them into arcades of pointed arches.
def inner_wall(axis, fixed, u0, u1, y1):
    """Wall cells u0..u1 from the plinth up to row y1 - 1, along x at z = fixed (axis "x") or along z at x = fixed."""
    for u in range(u0, u1 + 1):
        for y in range(y1):
            vox.setdefault((u, y, fixed) if axis == "x" else (fixed, y, u), "S")


X_TW = HALF_F - TW                                     # inner wall of the right tower; the left one is -X_TW - 1
for xw in (HALF_N - 1, -HALF_N):                       # nave and choir arcades, ending in the crossing piers
    inner_wall("z", xw, Z_NAVE0, Z_TR0 + 1, H_A)       # (two cells deep, so they take 2x1 blocks, not 1x1)
    inner_wall("z", xw, Z_TR1 - 2, Z_CH - 1, H_A)
for zw in (Z_TR0, Z_TR1 - 1):                          # transept arcades over the aisles
    inner_wall("x", zw, HALF_N - 1, HALF_B - 1, H_A)
    inner_wall("x", zw, -HALF_B, -HALF_N, H_A)
inner_wall("x", TW - 1, -HALF_F + 1, HALF_F - 2, H_N)  # back of towers and hall, towards aisles and nave
for xw in (X_TW, -X_TW - 1):                           # towers against the hall between them
    inner_wall("z", xw, 1, TW - 2, H_F)


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
# Belfry openings on all four sides of both towers, with plum louvers inside and a sill
TL_Y, TL_H = c(56), c2(18)
for sx in (-1, 1):
    x_mid = sx * (HALF_F - TW // 2)
    sides = ((-HALF_F, -1), (-(HALF_F - TW) - 1, 1)) if sx < 0 else ((HALF_F - TW, -1), (HALF_F - 1, 1))
    for off in (-c(4), c(4)):
        for wall in (FACADE, Wall("x", TW - 1, 1)):
            frame(wall, x_mid + off - WIN // 2, WIN, TL_Y, TL_H, "window", "West front", fill="D")
        for x_wall, out in sides:
            frame(Wall("z", x_wall, out), TW // 2 + off - WIN // 2, WIN, TL_Y, TL_H, "window", "West front", fill="D")


# Arcades in the inner walls of section 1b: open pointed arches framed like the windows (no sill), between piers of
# two jambs; the apex stays at least two rows under the wall that rests on the arcade (top).
def arch(wall, lo, hi, top, part):
    """Open arch between the jamb columns lo and hi (the opening is the cells between)."""
    w = hi - lo - 1
    assert w >= 4 and w % 2 == 0, f"arch {lo}..{hi}: opening of {w} cells"
    frame(wall, lo + 1, w, 0, (top - 1 - w // 2) // 2 * 2, "window", part, sill=False)


def mirror(lo, hi):
    """The same arch on the left side (x -> -x - 1)."""
    return -hi - 1, -lo - 1


# The frames stick out into the nave and into the aisles beside the transept, which keeps the transept free for the
# scaffold's uprights (and the jambs of two arcades never meet in one cell at a crossing pier).
for bc in bays:                                        # one arch per bay, piers under the flying buttresses
    for x_wall, out in ((-HALF_N, 1), (HALF_N - 1, -1)):
        arch(Wall("z", x_wall, out), bc - BAY // 2, bc + BAY // 2 - 1, H_A, "Nave" if bc < Z_TR0 else "Choir")
choir_lo = min(bc for bc in bays if bc > Z_TR1) - BAY // 2
for x_wall, out in ((-HALF_N, 1), (HALF_N - 1, -1)):  # between the crossing pier and the first choir bay
    arch(Wall("z", x_wall, out), Z_TR1, choir_lo - 1, H_A, "Choir")
span = HALF_B - HALF_N                                 # transept arcades: two arches over the aisles; the outer one
for z_wall, out in ((Z_TR0, -1), (Z_TR1 - 1, 1)):      # stops a pier short of the aisle wall (its frame would cut it)
    for lo, hi in ((HALF_N, HALF_N + span // 2 - 1), (HALF_N + span // 2, HALF_B - 3)):
        for a, b in ((lo, hi), mirror(lo, hi)):
            arch(Wall("x", z_wall, out), a, b, H_A, "Transept")
BACK = Wall("x", TW - 1, -1)                           # jambs stick out into the towers and the hall
arch(BACK, -X_TW, X_TW - 1, H_N, "West front")         # hall -> nave
for a, b in ((HALF_N, HALF_F - 3), mirror(HALF_N, HALF_F - 3)):   # towers -> aisles
    arch(BACK, a, b, H_A, "West front")
for x_wall, out in ((X_TW, 1), (-X_TW - 1, -1)):      # hall -> towers, jambs right at the front and back wall
    arch(Wall("z", x_wall, out), 1, TW - 2, H_F // 2 + 1, "West front")   # (a one-cell stub there would be all 1x1)

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
    if pz < TW and ax < HALF_F:
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
    for zz in range(TW, Z_CH, 2):
        add_tile(-HALF_N + k, H_N + k, zz, 0, part_of(0, zz))           # left slope, +x towards the ridge
        add_tile(HALF_N - 2 - k, H_N + k, zz, 180, part_of(0, zz))
# Transept gables: the end walls stop at the eaves, so close the triangle under the roof, row by row between the slopes
for k in range(HALF_N - 1):
    for x_end in (-HALF_T, HALF_T - 1):
        for zz in range(Z_TR0 + k + 2, Z_TR1 - 2 - k):
            if (x_end, H_N + k, zz) not in tile_cells:
                vox.setdefault((x_end, H_N + k, zz), "S")
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


def ring_wall(r_cells, y0, y1, windows, part, sills=True):
    """Half ring wall of 2x1 blocks along the circle (running bond) with windows framed like the straight ones (or
    arches: sills=False). Positions along the ring are in cells of arc length u (0 at phi = 0); windows = [(phi_c, w,
    wy0, h)]."""
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
        if sills:
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
ring_wall(HALF_N - 0.5, 0, H_A, [(30 + 60 * j, 6, 0, (H_A - 4) // 2 * 2) for j in range(3)], "Choir", sills=False)
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
    for step in (8, 10, 12):                         # outside the scaffold ring around the drum
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
# and spire. The bell towers have their own scaffold (below) with a cross bridge between their tops.
# Walking surfaces are the tops of 6 cm planks; steps rise one cell (0.21 m) per 0.42 m. No two boxes share a face
# plane where they overlap (z-fighting): ledgers are 5 cm, rails and stringers 6 to 8 cm, uprights 12 cm.
scaffold = []   # (cx, cy, cz, sx, sy, sz) meters
BASE_H_SCAF = 0.42                                         # plinth height (= BASE_H of the mod blueprint)
W, PLANK, RAIL, POST = 1.3, 0.06, 1.0, 0.12   # walkways wider than the player (capsule radius 0.5 m, step offset 0.30 m)
STEP_RISE, STEP_RUN = CELL, 2 * CELL


def plank(x0, x1, z0, z1, walk):
    scaffold.append(((x0 + x1) / 2, walk - PLANK / 2, (z0 + z1) / 2, abs(x1 - x0), PLANK, abs(z1 - z0)))


def rail(x0, x1, z0, z1, y, t=0.06):
    scaffold.append(((x0 + x1) / 2, y, (z0 + z1) / 2, max(abs(x1 - x0), t), t, max(abs(z1 - z0), t)))


def deck(x0, x1, z0, z1, walk, ledgers=None):
    """Plank on two ledgers along its long edges (the ledgers run from upright to upright, or over ledgers = (a, b)
    along the long axis). The 5 cm ledgers sit 5 mm inside the plank edge, so their faces lie neither in the plank's
    edge nor in an upright's face."""
    plank(x0, x1, z0, z1, walk)
    y = walk - PLANK - 0.025
    if abs(x1 - x0) >= abs(z1 - z0):
        a, b = ledgers or (x0, x1)
        for zz in (min(z0, z1) + 0.03, max(z0, z1) - 0.03):
            rail(a, b, zz, zz, y, 0.05)
    else:
        a, b = ledgers or (z0, z1)
        for xx in (min(x0, x1) + 0.03, max(x0, x1) - 0.03):
            rail(xx, xx, a, b, y, 0.05)


# Stairs like a scaffold stair tower: a square ring (corner centers at cx +- mid, cz +- mid, walked in `corners` order),
# a square landing W x W at every corner and straight flights between them, as many 21 cm risers as fit on a side
# (treads of at least 42 cm). Nothing climbs on a landing, and lanes and bridges leave from landings, so a stair never
# turns on its steps.
flights = []        # every stair's steps (with their tread), for the stringers added once brace() exists


def ax_of(corners):
    return [corners[k][0] != corners[(k + 1) % 4][0] for k in range(4)]     # side k runs along x?


def stair_geometry(mid):
    k = int((2 * mid - W + 1e-9) // STEP_RUN)              # steps per side
    return k, (2 * mid - W) / k


def flight(cx, cz, mid, corners, a, u, m, out):
    """m steps on side a (from corner a to corner a + 1), on the places next to corner a + 1; the first one climbs
    from u units (cells) of height."""
    k, t = stair_geometry(mid)
    (ax0, az0), (ax1, az1) = corners[a % 4], corners[(a + 1) % 4]
    dx, dz = (ax1 - ax0) / 2, (az1 - az0) / 2
    for i in range(m):
        d = W / 2 + (k - m + i + 0.5) * t                  # from the corner a center along the side
        px, pz = cx + ax0 * mid + dx * d, cz + az0 * mid + dz * d
        walk = (u + 1 + i) * STEP_RISE
        if dx:
            plank(px - t / 2 - 0.015, px + t / 2 + 0.015, pz - W / 2, pz + W / 2, walk)
        else:
            plank(px - W / 2, px + W / 2, pz - t / 2 - 0.015, pz + t / 2 + 0.015, walk)
        out.append((px, pz, walk, a % 4))


def corner_square(cx, cz, mid, corner, walk):
    kx, kz = cx + corner[0] * mid, cz + corner[1] * mid
    plank(kx - W / 2, kx + W / 2, kz - W / 2, kz + W / 2, walk)


def stair(cx, cz, mid, corners, c_top, u_top, c_start=None, u_start=0):
    """Stair up to a landing at corner c_top, u_top cells high: from the plinth (the first flight is cut to the height
    left over), or from a landing at corner c_start, u_start cells high. Returns [(corner, height)] of its landings."""
    k, t = stair_geometry(mid)
    per = k + 1                                            # cells per side: k steps + the riser onto the landing
    out, levels = [], []
    if c_start is None:
        n_full = (u_top - 1) // per
        r = u_top - n_full * per                           # 1 .. per: the first landing
        c, u = (c_top - n_full) % 4, r
        flight(cx, cz, mid, corners, c - 1, 0, r - 1, out)
    else:
        assert (u_top - u_start) % per == 0 and (c_start + (u_top - u_start) // per) % 4 == c_top % 4, "stair does not fit"
        c, u = c_start % 4, u_start
    corner_square(cx, cz, mid, corners[c], u * STEP_RISE)
    levels.append((c, u * STEP_RISE))
    while u < u_top:
        flight(cx, cz, mid, corners, c, u, k, out)
        c, u = (c + 1) % 4, u + per
        corner_square(cx, cz, mid, corners[c], u * STEP_RISE)
        levels.append((c, u * STEP_RISE))
    flights.append((out, ax_of(corners), t))
    return levels


# Stair around drum and spire: from a landing one cell above the ridge (bridge 1 arrives there from the stair tower,
# the apostles stand outside the ring) up to a top platform, from which the spire tip is within reach. The platform
# covers three corners and two sides plus the side above the flight before the last; the last flight and the landing
# below the platform stay open (headroom).
MID = max(RING_R + 0.27, r0 + 0.215) + 0.05 + W / 2      # inner edge clear of drum and spire base
A_IN, B_OUT = MID - W / 2, MID + W / 2
DRUM_CORNERS = [(-1, -1), (1, -1), (1, 1), (-1, 1)]       # side 0 = west side, walked towards +x
BASE_CELLS = DRUM_Y0 + 1
y_base = BASE_CELLS * CELL
DECK = H_T * CELL                                          # tower platforms
k_d, _ = stair_geometry(MID)
y_top_target = (spire_top + 1) * CELL - 4.5                # spire tip within 5 m reach from the top platform
n_d = int(math.ceil((y_top_target - y_base) / ((k_d + 1) * STEP_RISE)))
c_end = n_d % 4
drum_levels = stair(cxm, czm, MID, DRUM_CORNERS, c_end, BASE_CELLS + n_d * (k_d + 1), c_start=0, u_start=BASE_CELLS)
y_top = drum_levels[-1][1]
for j in (1, 2):                                           # the platform's other corners
    corner_square(cxm, czm, MID, DRUM_CORNERS[(c_end + j) % 4], y_top)
for s_idx in (c_end, c_end + 1, c_end + 2):                # its sides (not the last flight's)
    (ax0, az0), (ax1, az1) = DRUM_CORNERS[s_idx % 4], DRUM_CORNERS[(s_idx + 1) % 4]
    xm, zm = cxm + (ax0 + ax1) / 2 * MID, czm + (az0 + az1) / 2 * MID
    if ax0 != ax1:
        plank(xm - MID + W / 2, xm + MID - W / 2, zm - W / 2, zm + W / 2, y_top)
    else:
        plank(xm - W / 2, xm + W / 2, zm - MID + W / 2, zm + MID - W / 2, y_top)
rail(cxm - B_OUT, cxm + B_OUT, czm - B_OUT, czm - B_OUT, y_top + RAIL)
rail(cxm - B_OUT, cxm + B_OUT, czm + B_OUT, czm + B_OUT, y_top + RAIL)
rail(cxm - B_OUT, cxm - B_OUT, czm - B_OUT + 0.03, czm + B_OUT - 0.03, y_top + RAIL)    # butting, not crossing
rail(cxm + B_OUT, cxm + B_OUT, czm - B_OUT + 0.03, czm + B_OUT - 0.03, y_top + RAIL)

# Stair tower from the ground; its top landing lies on the line of the drum ring's west side, at bridge height
MID_T = 1.72                                               # 5 steps per side: 5.04 m per turn, as many turns as before
T_CORNERS = [(-1, 1), (1, 1), (1, -1), (-1, -1)]
cz_t = czm - MID - MID_T
cx_t = -(HALF_T * CELL + 0.3 + MID_T + W / 2)
stair(cx_t, cz_t, MID_T, T_CORNERS, 1, BASE_CELLS)

# Bridge 1 (ridge height): from the stair tower's top landing to the drum stair's first landing
z_b1 = czm - MID
deck(cx_t + MID_T + W / 2, cxm - B_OUT, z_b1 - W / 2, z_b1 + W / 2, y_base)
for zz in (z_b1 - W / 2, z_b1 + W / 2):
    rail(cx_t + MID_T + W / 2, cxm - B_OUT, zz, zz, y_base + RAIL)
# Cross bridge between the bell towers (tower height)
z_cross = TW * CELL / 2
x_tw = (HALF_F - TW) * CELL                                # inner faces of the towers
deck(-x_tw, x_tw, z_cross - W / 2, z_cross + W / 2, DECK)
for zz in (z_cross - W / 2, z_cross + W / 2):
    rail(-x_tw, x_tw, zz, zz, DECK + RAIL)
for zc in range(int(math.floor((z_cross - W / 2) / CELL)), int(math.ceil((z_cross + W / 2) / CELL))):
    for xc in (-(HALF_F - TW) - 1, HALF_F - TW):           # parapet gaps where the cross bridge lands
        for y in (H_T, H_T + 1):
            vox.pop((xc, y, zc), None)

# Bell towers: a facade scaffold in front of the west front and around both towers. A stair tower at each tower's
# outer face climbs from the ground to the tower platform (parapet gap). Where its flights pass the corner at the
# facade lane or at the outer lane, level platforms branch off: the facade lane (between the towers too, once above
# the gallery) and the back lane behind the tower (once above the aisle roof). One turn = 4.8 m between levels.
C_TW = 0.45                                                # clearance to the walls (sills stick out 0.39 m)
X_OUT, X_IN, TWM = HALF_F * CELL, (HALF_F - TW) * CELL, TW * CELL
front_z, back_z = -C_TW - W / 2, TWM + C_TW + W / 2
lane_x = X_OUT + C_TW + W / 2                              # outer lane = inner side of the stair tower
zs_tw = front_z + MID_T                                    # stair tower: its front side lies on the facade lane
GALLERY_TOP = (H_F + 2) * CELL                             # balustrade between the towers
front_lv, back_lv = [], []
tw_stairs = []
for sx in (1, -1):
    corners = [(-1, -1), (-1, 1), (1, 1), (1, -1)] if sx > 0 else [(1, -1), (1, 1), (-1, 1), (-1, -1)]
    cx_s = sx * (X_OUT + C_TW + MID_T + W / 2)
    levels = stair(cx_s, zs_tw, MID_T, corners, 1, H_T)   # top landing at corner 1, next to the tower, at DECK
    tw_stairs.append((cx_s, corners))
    front_lv = sorted({round(y, 3) for c, y in levels if c == 0})        # landings at the facade lane
    back_lv = sorted({round(y, 3) for c, y in levels if c == 1})         # landings at the outer lane
front_lv = [h for h in front_lv if 3.0 <= h <= DECK - 2.2]
back_lv = [h for h in back_lv if h >= (H_A + AISLE_RISE + 2) * CELL]
assert back_lv and abs(back_lv[-1] - DECK) < 0.01, "tower stair does not end at the platform"
print(f"tower scaffold levels: facade {front_lv}, back {back_lv}")
for h in front_lv:
    deck(-(X_OUT + C_TW), X_OUT + C_TW, front_z - W / 2, front_z + W / 2, h)
    rail(-(X_OUT + C_TW), X_OUT + C_TW, front_z - W / 2, front_z - W / 2, h + RAIL)
    if GALLERY_TOP + 0.15 < h <= DECK - 2.2:                # between the towers, above the gallery
        deck(-(X_IN - C_TW), X_IN - C_TW, front_z + W / 2, TWM + C_TW, h)
for sx in (1, -1):
    for h in back_lv:
        x_min = 0.0 if h > GALLERY_TOP + 0.15 else (HALF_N + 1) * CELL     # low lanes stay clear of the nave
        z_from = zs_tw + MID_T + W / 2
        deck(sx * (lane_x - W / 2), sx * (lane_x + W / 2), z_from, back_z + W / 2, h)       # outer lane
        deck(sx * x_min, sx * (lane_x - W / 2), back_z - W / 2, back_z + W / 2, h)        # back lane
        rail(sx * x_min, sx * (lane_x + W / 2), back_z + W / 2, back_z + W / 2, h + RAIL)
        rail(sx * (lane_x + W / 2), sx * (lane_x + W / 2), z_from, back_z + W / 2 - 0.03, h + RAIL)
    plank(sx * X_OUT, sx * (X_OUT + C_TW), TWM / 2 - W / 2, TWM / 2 + W / 2, DECK)          # onto the platform
    xc = HALF_F - 1 if sx > 0 else -HALF_F
    for zc in range(int(math.floor((TWM / 2 - W / 2) / CELL)), int(math.ceil((TWM / 2 + W / 2) / CELL))):
        for y in (H_T, H_T + 1):
            vox.pop((xc, y, zc), None)

# Posts down to whatever is below (roof, wall top or ground)
col_ys = {}
for (x, y, z) in list(vox) + list(tile_cells) + [cl for p in pieces for cl in p[7]] + [(a[1], a[2], a[3]) for a in accents]:
    col_ys.setdefault((x, z), []).append(y)


tile_set = set(tile_cells)
piece_set = {cl for pc in pieces for cl in pc[7]}


def pierceable(cl):
    """Roof tiles and flat slabs may be pierced by an upright (like scaffold poles through a roof); walls may not."""
    if cl in tile_set:
        return True
    if cl in piece_set or cl not in vox:
        return False
    x, y, z = cl
    return all(in_solid(x + dx, y, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def post_cells(x, z):
    return {(int(math.floor((x + dx) / CELL)), int(math.floor((z + dz) / CELL))) for dx in (-POST / 2, POST / 2) for dz in (-POST / 2, POST / 2)}


uprights = {}       # (x, z) in mm -> index in scaffold


def upright(x, z, y0, y1):
    """Two uprights on the same spot become one (the faces of two would flicker)."""
    key = (round(x * 1000), round(z * 1000))
    if key in uprights:
        _, cy, _, _, sy, _ = scaffold[uprights[key]]
        y0, y1 = min(y0, cy - sy / 2), max(y1, cy + sy / 2)
    else:
        uprights[key] = len(scaffold)
        scaffold.append(None)
    scaffold[uprights[key]] = (x, (y0 + y1) / 2, z, POST, y1 - y0, POST)


def post(x, z, top):
    """Upright standing on the plinth up to top, through roofs and slabs; it moves up to 0.3 m sideways to miss walls,
    and only where that fails it stands on the building. Returns (surface, x, z): the height of the building surface
    below top (braces start above it) and where the upright stands."""
    ys = [y for cl in post_cells(x, z) for y in col_ys.get(cl, []) if (y + 1) * CELL <= top]
    surface = (max(ys) + 1) * CELL if ys else 0.0
    for ox, oz in ((0, 0), (0.15, 0), (-0.15, 0), (0, 0.15), (0, -0.15), (0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3)):
        if all(pierceable((cx, y, cz)) for (cx, cz) in post_cells(x + ox, z + oz) for y in col_ys.get((cx, cz), []) if (y + 1) * CELL <= top):
            upright(x + ox, z + oz, 0.0, top)
            return surface, x + ox, z + oz
    upright(x, z, surface, top)
    return surface, x, z


def brace(p0, p1, t=0.06):
    """Diagonal tube from p0 to p1 (x, y, z), usually in a vertical plane x = const or z = const. Visuals only (no
    collider): rotated entries carry Unity Euler angles (pitch, yaw, roll)."""
    (x0, y0, z0), (x1, y1, z1) = p0, p1
    length = math.dist(p0, p1)
    c = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    if abs(z1 - z0) < 1e-6:
        scaffold.append((*c, t, length, t, 0.0, 0.0, math.degrees(math.atan2(-(x1 - x0), y1 - y0))))
    elif abs(x1 - x0) < 1e-6:
        scaffold.append((*c, t, length, t, math.degrees(math.atan2(z1 - z0, y1 - y0)), 0.0, 0.0))
    else:   # skewed (an upright moved aside to miss a wall): local y -> (sin p sin yaw, cos p, sin p cos yaw)
        scaffold.append((*c, t, length, t, math.degrees(math.atan2(math.hypot(x1 - x0, z1 - z0), y1 - y0)),
                         math.degrees(math.atan2(x1 - x0, z1 - z0)), 0.0))


def braces(a, b, y0, y1, band=2.4):
    """Zigzag of braces between the uprights at a and b (x, z), from y0 to y1."""
    n_b = max(1, int(round((y1 - y0) / band)))
    for k in range(n_b):
        ya, yb = y0 + (y1 - y0) * k / n_b, y0 + (y1 - y0) * (k + 1) / n_b
        p, q = (a, b) if k % 2 == 0 else (b, a)
        brace((p[0], ya, p[1]), (q[0], yb, q[1]))


def row_posts(x0, x1, z, top, step=2.4):
    """Uprights along x at depth z, at most step apart; returns [(foot, x, z)]."""
    n_p = max(1, int(math.ceil(abs(x1 - x0) / step)))
    return [post(x0 + (x1 - x0) * k / n_p, z, top) for k in range(n_p + 1)]


def tower_frame(cx, cz, mid, top, skip_sides=()):
    """Uprights at the four corners of every corner landing of a square stair tower or ring, braces on its outer faces."""
    feet = {}
    for (ax, az) in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
        for a, b in ((mid - W / 2, mid - W / 2), (mid + W / 2, mid - W / 2), (mid - W / 2, mid + W / 2)):
            post(cx + ax * a, cz + az * b, top)
        feet[(ax, az)] = post(cx + ax * (mid + W / 2), cz + az * (mid + W / 2), top)[0]
    o = mid + W / 2 + 0.06
    for side, (c0, c1) in {"-z": ((-1, -1), (1, -1)), "+x": ((1, -1), (1, 1)), "+z": ((1, 1), (-1, 1)), "-x": ((-1, 1), (-1, -1))}.items():
        if side in skip_sides:
            continue
        y0 = max(feet[c0], feet[c1]) + 0.3
        braces((cx + c0[0] * o, cz + c0[1] * o), (cx + c1[0] * o, cz + c1[1] * o), y0, top - RAIL - 0.3)


def bridge_trestle(pts_a, pts_b):
    """Braces between consecutive uprights along both edges of a bridge: pts = [(x, z, foot, top)]."""
    for pts in (pts_a, pts_b):
        for (xa, za, fa, ta), (xb, zb, fb, tb) in zip(pts, pts[1:]):
            y0 = max(fa, fb) + 0.3
            if ta - 0.3 - y0 > 0.8:
                brace((xa, y0, za), (xb, ta - 0.3, zb))


tower_frame(cxm, czm, MID, y_top + RAIL, skip_sides=("-x",))       # no braces where bridges and lanes pass a face
tower_frame(cx_t, cz_t, MID_T, y_base + RAIL, skip_sides=("+x",))
for (cx_s, _) in tw_stairs:                                        # facade lane in at corner 0, outer lane out at 1
    tower_frame(cx_s, zs_tw, MID_T, DECK + RAIL, skip_sides=("-x" if cx_s > 0 else "+x", "+z"))
x0_b1, x1_b1 = cx_t + MID_T + W / 2 + 0.3, cxm - B_OUT - 0.3
edges = []
for zz in (z_b1 - W / 2, z_b1 + W / 2):
    edges.append([(x, z, f, y_base + RAIL - 0.2) for (f, x, z) in row_posts(x0_b1, x1_b1, zz, y_base + RAIL)])
    post(cxm - B_OUT, zz, y_base + RAIL)                                  # where the rails end
bridge_trestle(*edges)
# Facade scaffold: uprights on both edges of the facade lane, braces in its outer plane between the levels
fz_out = front_z - W / 2
top_f = front_lv[-1] + RAIL
row_out = row_posts(-(X_OUT + C_TW), X_OUT + C_TW, fz_out, top_f)
row_posts(-(X_OUT + C_TW), X_OUT + C_TW, front_z + W / 2, top_f)
lv = [0.3] + front_lv + [top_f - 0.3]
for (_, xa, za), (_, xb, zb) in zip(row_out, row_out[1:]):
    for k, (ya, yb) in enumerate(zip(lv, lv[1:])):
        p, q = ((xa, za), (xb, zb)) if k % 2 == 0 else ((xb, zb), (xa, za))
        brace((p[0], ya, p[1] - 0.06), (q[0], yb, q[1] - 0.06))
# Stair flights: a block under a first step near the ground, a stringer under both edges of every flight
for st_steps, along_x, tread in flights:
    if not st_steps:
        continue
    x_f, z_f, w_f, side_f = st_steps[0]
    if w_f - PLANK < 0.5:
        lx, lz = (tread, W - 0.1) if along_x[side_f] else (W - 0.1, tread)
        scaffold.append((x_f, (w_f - PLANK) / 2, z_f, lx, w_f - PLANK, lz))
for st_steps, along_x, tread in flights:
    if not st_steps:
        continue
    run = [st_steps[0]]
    for stp in st_steps[1:] + [None]:
        if stp is not None and stp[3] == run[-1][3]:
            run.append(stp)
            continue
        if len(run) >= 2:
            (xa, za, wa, side), (xb, zb, wb, _) = run[0], run[-1]
            ux, uz = (1 if xb > xa else -1, 0) if along_x[side] else (0, 1 if zb > za else -1)
            for off in (-(W / 2 - 0.06), W / 2 - 0.06):
                ox, oz = (0, off) if along_x[side] else (off, 0)
                brace((xa - ux * tread / 2 + ox, wa - PLANK - 0.05, za - uz * tread / 2 + oz),
                      (xb + ux * tread / 2 + ox, wb - PLANK - 0.05, zb + uz * tread / 2 + oz), 0.08)
        if stp is not None:
            run = [stp]
# Uprights the decks were still missing: platform between the towers, cross bridge, inner edge of the back lanes
mid_lv = [h for h in front_lv if GALLERY_TOP + 0.15 < h <= DECK - 2.2]
if mid_lv:
    for xx in (-(X_IN - C_TW), X_IN - C_TW):
        for zz in (front_z + W / 2, TWM + C_TW):
            post(xx, zz, mid_lv[-1] + 0.1)
for xx in (-(x_tw - 0.15), x_tw - 0.15):                  # cross bridge, up to its rails
    for zz in (z_cross - W / 2, z_cross + W / 2):
        post(xx, zz, DECK + RAIL)
# Back lanes: uprights on both edges, through the aisle roof down to the plinth: where the low lanes start, at the
# corner with the outer lane and at its outer edge
x_low = (HALF_N + 1) * CELL
xs_back = [W / 2 + 0.35, x_low + 0.1, (x_low + 0.1 + lane_x - W / 2) / 2, lane_x - W / 2, lane_x + W / 2]
for sx in (1, -1):
    for xx in xs_back:
        post(sx * xx, back_z - W / 2, back_lv[-1] + 0.1)
    bz_out = back_z + W / 2
    row = [post(sx * xx, bz_out, back_lv[-1] + RAIL) for xx in xs_back]
    post(sx * (lane_x + W / 2), zs_tw + MID_T + W / 2, back_lv[-1] + RAIL)
    for (fa, xa, za), (fb, xb, zb) in zip(row, row[1:]):
        y0 = max(fa, fb) + 0.3
        braces((xa, za + 0.06), (xb, zb + 0.06), y0, back_lv[-1])

# Ramps for the game's mobile scaffold, which rolls on wheels of 9.8 cm radius over ground up to 45 degrees (measured)
# and so cannot climb the plinth's 21 cm steps: 15 degrees from the ground up to the plinth, on both long sides just
# behind the bell tower stairs, where the plinth is widened for it (PLINTH_SIDE). Entries with a tenth value 1 are
# rotated boxes that are walkable (the mod gives them a collider).
PLINTH_SIDE = 25 * 0.42                                    # long sides of the plinth (its 0.42 m cell grid)
RAMP_DEG, RAMP_W, RAMP_T, RAMP_Z = 15.0, 4.0, 0.08, 12.0   # slope, width, board, middle along z
ramp_run = BASE_H_SCAF / math.tan(math.radians(RAMP_DEG))
for sx in (1, -1):
    a = math.radians(RAMP_DEG)
    mx, my = sx * (PLINTH_SIDE + ramp_run / 2), -BASE_H_SCAF / 2      # middle of the top face (0 = plinth top)
    scaffold.append((mx - sx * math.sin(a) * RAMP_T / 2, my - math.cos(a) * RAMP_T / 2, RAMP_Z,
                     ramp_run / math.cos(a), RAMP_T, RAMP_W, 0.0, 0.0, -sx * RAMP_DEG, 1.0))

# ---- 7) Brick packing: 2x1 blocks in running bond with bonded corners ----
# Wanted pattern first: at a corner, a junction or inside a solid block (piers, pinnacles) the 2x1 block lies across
# the block below (first layer: even layers along x, odd along z), so corners interlock like real masonry. Straight
# runs continue from their corner; a run without a corner (between openings) follows the layer parity, so the joints
# shift by one cell from layer to layer. Then augmenting paths over neighbouring cells of the same material turn as many
# leftover 1x1 cells into 2x1 blocks as the shape allows, without turning the corner blocks of thin walls; a 1x1 stays
# at an open wall end (an opening). Every layer is laid forwards and backwards; the one with fewer 1x1, then fewer
# vertical joints right above a joint of the layer below wins (that makes the joints of piers alternate).


def pack_layer(cells, y, below, joints_below):
    layer = set(cells)
    first = "x" if y % 2 == 0 else "z"
    mate, locked = {}, set()
    reveal = set()                 # 1x1 at an open wall end (window, arch, door): it shifts the joints, keep it

    def same(a, w):
        return w in layer and vox[w] == vox[a]

    def free_same(a, w):
        return same(a, w) and w not in mate

    def match(a, b):
        mate[a] = b
        mate[b] = a

    def axes(a):
        x, _, z = a
        return (same(a, (x + 1, y, z)) + same(a, (x - 1, y, z)), same(a, (x, y, z + 1)) + same(a, (x, y, z - 1)))

    def wall_end(a, d):
        """The run along d really ends at a (window, arch, door): no wall goes on across it, unlike at a corner."""
        return axes(a)[1 if d == "x" else 0] == 0

    for cl in cells:                                           # 1) corners, junctions, solid blocks
        if cl in mate:
            continue
        x, _, z = cl
        nx = [(x + d, y, z) for d in (1, -1) if free_same(cl, (x + d, y, z))]
        nz = [(x, y, z + d) for d in (1, -1) if free_same(cl, (x, y, z + d))]
        if nx and nz:
            want = {"x": "z", "z": "x"}.get(below.get((x, z)), first)     # across the block below
            partner = (nx if want == "x" else nz)[0]
            match(cl, partner)
            px, pz = axes(partner)
            if axes(cl) == (1, 1) and ((pz == 0) if want == "x" else (px == 0)):
                locked.update((cl, partner))                   # corner of one-cell walls: keep it
    for cl in cells:                                           # 2) straight runs
        if cl in mate:
            continue
        x, _, z = cl
        m = vox[cl]
        if free_same(cl, (x + 1, y, z)) or free_same(cl, (x - 1, y, z)):
            d, sx_, sz_ = "x", 1, 0
        elif free_same(cl, (x, y, z + 1)) or free_same(cl, (x, y, z - 1)):
            d, sx_, sz_ = "z", 0, 1
        else:
            continue
        start = cl
        while free_same(start, (start[0] - sx_, y, start[2] - sz_)):
            start = (start[0] - sx_, y, start[2] - sz_)
        run = [start]
        while free_same(run[-1], (run[-1][0] + sx_, y, run[-1][2] + sz_)):
            run.append((run[-1][0] + sx_, y, run[-1][2] + sz_))
        before, after = (start[0] - sx_, y, start[2] - sz_), (run[-1][0] + sx_, y, run[-1][2] + sz_)
        wall_before = before in layer and vox[before] == m        # a corner block was laid there
        wall_after = after in layer and vox[after] == m
        lead = 0 if wall_before else (len(run) % 2 if wall_after else ((start[0] if d == "x" else start[2]) + y) % 2)
        if len(run) == 2 and not (wall_before or wall_after):
            lead = 0                                            # one block between two openings: no joint to shift
        rest = run[lead:]
        if lead and wall_end(run[0], d):
            reveal.add(run[0])
        if wall_before and wall_after and len(rest) % 2:
            # One 1x1 between two corners, pairs on both sides: it goes where the fewest joints come to lie on a joint
            # of the layer below (a fixed place would keep one side's joints stacked while the corners alternate).
            def stacked(k):
                paired = set(range(0, k, 2)) | set(range(k + 1, len(rest) - 1, 2))
                return sum(1 for i in range(len(rest) - 1) if i not in paired
                           and ((rest[i][0], rest[i][2]), (rest[i + 1][0], rest[i + 1][2])) in joints_below)
            k = min(range(0, len(rest), 2), key=lambda k: (stacked(k), abs(k - len(rest) // 2)))
            pairs = [(rest[j], rest[j + 1]) for j in range(0, k, 2)] + [(rest[j], rest[j + 1]) for j in range(k + 1, len(rest) - 1, 2)]
        else:
            pairs = [(rest[j], rest[j + 1]) for j in range(0, len(rest) - 1, 2)]
            if len(rest) % 2 and wall_end(rest[-1], d):
                reveal.add(rest[-1])
        for a, b in pairs:
            match(a, b)

    def neighbours(a):
        x, _, z = a
        return [w for w in ((x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)) if same(a, w) and w not in locked]

    for u in cells:                                            # 3) augmenting paths (never through a reveal 1x1)
        if u in mate or u in reveal:
            continue
        prev, queue, found = {u: None}, [u], None
        while queue and found is None:
            nxt = []
            for a in queue:
                for w in neighbours(a):
                    if w in prev or w in reveal:
                        continue
                    prev[w] = a
                    if w not in mate:
                        found = w
                        break
                    b = mate[w]
                    if b not in prev:
                        prev[b] = w
                        nxt.append(b)
                if found is not None:
                    break
            queue = nxt
        w = found
        while w is not None:
            a = prev[w]
            back = prev[a]
            match(w, a)
            w = back
    singles = sum(1 for cl in cells if cl not in mate)
    joints = layer_joints(cells, mate)
    return mate, (singles, len(joints & joints_below)), joints


def layer_joints(cells, mate):
    """Vertical joints of a layer: neighbouring cells of the same material in different blocks, as (x, z) pairs."""
    layer = set(cells)
    out = set()
    for cl in cells:
        x, y, z = cl
        for w in ((x + 1, y, z), (x, y, z + 1)):
            if w in layer and vox[w] == vox[cl] and mate.get(cl) != w:
                out.add(((x, z), (w[0], w[2])))
    return out


bricks = []
below = {}                                                     # (x, z) -> direction of the block one layer lower
joints_below = set()
for y in sorted({k[1] for k in vox}):
    cells = sorted((k for k in vox if k[1] == y), key=lambda k: (k[2], k[0]))
    mate, score, joints = pack_layer(cells, y, below, joints_below)
    mate_r, score_r, joints_r = pack_layer(cells[::-1], y, below, joints_below)
    if score_r < score:
        mate, joints = mate_r, joints_r
    joints_below = joints
    done = set()
    below = {}
    for cl in cells:
        if cl in done:
            continue
        if cl in mate:
            o = mate[cl]
            d = "x" if cl[2] == o[2] else "z"
            done.update((cl, o))
            bricks.append((vox[cl], 2, min(cl[0], o[0]), y, min(cl[2], o[2]), d))
            below[(cl[0], cl[2])] = below[(o[0], o[2])] = d
        else:
            done.add(cl)
            bricks.append((vox[cl], 1, cl[0], y, cl[2], "x"))


def corner_cell(c):
    x, y, z = c
    m = vox[c]
    return any((x + d, y, z) in vox and vox[(x + d, y, z)] == m for d in (1, -1)) and any((x, y, z + d) in vox and vox[(x, y, z + d)] == m for d in (1, -1))


_singles = [b for b in bricks if b[1] == 1]
def nb_kind(cl):
    x, y, z = cl
    m = vox[cl]
    ax = sum(1 for d in (1, -1) if (x + d, y, z) in vox and vox[(x + d, y, z)] == m)
    az = sum(1 for d in (1, -1) if (x, y, z + d) in vox and vox[(x, y, z + d)] == m)
    return "L corner" if ax == 1 and az == 1 else ("T" if ax + az == 3 and ax and az else ("inside" if ax == 2 and az == 2 else ("line" if not (ax and az) else "other")))


from collections import Counter as _C
_dir = {}
for _b in bricks:
    _m, _k, _x, _y, _z, _d = _b
    for _cl in ([(_x, _y, _z)] if _k == 1 else ([(_x, _y, _z), (_x + 1, _y, _z)] if _d == "x" else [(_x, _y, _z), (_x, _y, _z + 1)])):
        _dir[_cl] = _d if _k == 2 else "1"
_pairs = [(cl, (cl[0], cl[1] + 1, cl[2])) for cl in vox if nb_kind(cl) == "L corner" and (cl[0], cl[1] + 1, cl[2]) in vox and nb_kind((cl[0], cl[1] + 1, cl[2])) == "L corner"]
_cols = {}
for cl in vox:
    if nb_kind(cl) == "L corner":
        _cols.setdefault((cl[0], cl[2]), []).append(cl[1])
_alt = _tot = 0
for (cx, cz), ys in _cols.items():
    ys = sorted(ys)
    run = [ys[0]]
    for yy in ys[1:] + [None]:
        if yy is not None and yy == run[-1] + 1:
            run.append(yy)
            continue
        if len(run) >= 6:
            for y0, y1 in zip(run, run[1:]):
                da, db = _dir[(cx, y0, cz)], _dir[(cx, y1, cz)]
                _tot += 1
                _alt += da != db and "1" not in (da, db)
        if yy is not None:
            run = [yy]
print(f"corner bond on vertical corners (6+ layers): {_alt} of {_tot} layer steps alternate")
print(f"packing: {len(bricks)} blocks, {len(_singles)} of them 1x1:", dict(_C(nb_kind((b[2], b[3], b[4])) for b in _singles)))

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


def cm(v):
    """Meters -> centimeters with one decimal (keeps the 5 mm lift of ring tiles)."""
    return round(v * 1000) / 10


for (m, kind, x, y, z, d) in sorted(bricks, key=lambda b: (b[3], b[4], b[2])):
    key = f"{m}{kind}"
    long_axis = TYPES[key].get("long")
    sx, sz = (2, 1) if (kind == 2 and d == "x") else ((1, 2) if kind == 2 else (1, 1))
    yaw = 0 if (long_axis is None or long_axis == d) else 90
    occupy([(x + i, y, z + k) for i in range(sx) for k in range(sz)])
    rows.append([type_keys.index(key), cm((x + sx / 2) * CELL), cm((y + 0.5) * CELL),
                 cm((z + sz / 2) * CELL), yaw, section(f"{part_of(x, z)} · Level {y // BAND + 1}")])
for (x0, y, z0), (yaw, part) in sorted(tiles.items(), key=lambda t: (t[0][1], t[0][2], t[0][0])):
    occupy([(x0 + i, y, z0 + k) for i in (0, 1) for k in (0, 1)])
    rows.append([type_keys.index("R4"), cm((x0 + 1) * CELL), cm((y + 0.5) * CELL),
                 cm((z0 + 1) * CELL), round(yaw, 2), section("Spire" if part == "Spire" else "Roof · " + part)])
for (key, xm, ym, zm, yaw, part, pitch, cells) in pieces:
    occupy(cells)
    if key == "ARC" or part == "Spire" or part.startswith("Roof"):
        sec = section("Drum" if key == "ARC" else part)
    else:
        sec = section(f"{part} · Level {int(ym / CELL) // BAND + 1}")
    rows.append([type_keys.index(key), cm(xm), cm(ym), cm(zm), round(yaw, 2), sec] + ([pitch] if pitch else []))
for (key, x, y, z) in accents:
    occupy([(x, y, z)])
    rows.append([type_keys.index(key), cm((x + 0.5) * CELL), cm((y + 0.5) * CELL), cm((z + 0.5) * CELL), 0,
                 section("Spire")])
print(f"overlapping cells: {overlaps}")
hits = []
for (bx, by, bz, sx, sy, sz) in (b for b in scaffold if len(b) == 6):    # braces are visuals only
    rng = [range(int(math.floor((c0 - s / 2 + 0.005) / CELL)), int(math.floor((c0 + s / 2 - 0.005) / CELL)) + 1)
           for c0, s in ((bx, sx), (by, sy), (bz, sz))]
    hits += [(gx, gy, gz) for gx in rng[0] for gy in rng[1] for gz in rng[2] if (gx, gy, gz) in cells_used and not pierceable((gx, gy, gz))]
print(f"scaffold cells inside bricks: {len(hits)} {sorted(set(hits))[:12]}")


# ---- Construction sites and sections ----
# The game allows at most 8192 slots and 256 sections per construction site (ConstructionStateNetworkSynchronizer),
# so the cathedral is built as several sites, like the town's own buildings. Prerequisites stay inside a part.
PARTS = [("notredame-west", "Notre-Dame: West front", ("West front",)),
         ("notredame-towers", "Notre-Dame: Bell towers", ("Bell towers",)),
         ("notredame-nave", "Notre-Dame: Nave", ("Nave",)),
         ("notredame-choir", "Notre-Dame: Transept and choir", ("Transept", "Choir")),
         ("notredame-spire", "Notre-Dame: Drum and spire", ("Drum", "Spire"))]


def part_index(name):
    base = name[len("Roof · "):] if name.startswith("Roof · ") else name.split(" · ")[0]
    if base == "West front" and not (" · Level " in name and int(name.split(" · Level ")[1]) <= 4):
        base = "Bell towers"                                # upper west front: its own site (slot limit)
    return next(k for k, (_, _, keys) in enumerate(PARTS) if base in keys)


# Sections like the town's own buildings: about 64 bricks each (every finished section is worth a skill point), cut
# from thin height bands of 0.84 m and built from the bottom up, so a section can be finished at its own height.
FINE_BAND, TARGET, MIN_BAND = 4, 64, 16          # cells per band, bricks per section, smaller bands join the next one
part_of_row = [part_index(sections[r[5]]) for r in rows]
band_of_row = [int(r[2] / 100 / CELL) // FINE_BAND for r in rows]
fine = []                                         # (height, part, index, name, rows)
for pi, (_, pname, _) in enumerate(PARTS):
    short = pname.split(": ", 1)[1]
    by_band = {}
    for i in range(len(rows)):
        if part_of_row[i] == pi:
            by_band.setdefault(band_of_row[i], []).append(i)
    groups, cur, cur_band = [], [], None
    for b in sorted(by_band):
        if not cur:
            cur_band = b
        cur += by_band[b]
        if len(cur) >= MIN_BAND:
            groups.append((cur_band, cur))
            cur = []
    if cur:
        if groups:
            groups[-1][1].extend(cur)
        else:
            groups.append((cur_band, cur))
    for band, g in groups:
        k = max(1, round(len(g) / TARGET))
        gx = [rows[i][1] for i in g]
        gz = [rows[i][3] for i in g]
        along_x = max(gx) - min(gx) > max(gz) - min(gz)
        g.sort(key=lambda i: (rows[i][1], rows[i][3]) if along_x else (rows[i][3], rows[i][1]))
        h = band * FINE_BAND * CELL
        for j in range(k):
            name = f"{short} {h:.1f} m" + (f" · {j + 1}/{k}" if k > 1 else "")
            fine.append((h, pi, j, name, g[j * len(g) // k:(j + 1) * len(g) // k]))
fine.sort(key=lambda t: (t[0], t[1], t[2]))       # the whole cathedral rises from the bottom up
sections = [t[3] for t in fine]
part_of_section = [t[1] for t in fine]
for si, t in enumerate(fine):
    for i in t[4]:
        rows[i][5] = si

xs = [r[1] for r in rows]; zs = [r[3] for r in rows]; ys = [r[2] for r in rows]
data = {
    "scale": S,
    "cell": CELL,
    "types": [dict(TYPES[k], key=k) for k in type_keys],
    "sections": sections,
    "bricks": rows,
    "scaffold": [[cm(v) for v in b[:6]] + [round(a, 1) for a in b[6:]] for b in scaffold],   # cm; braces + Euler degrees
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

# ---- 9) Blueprint for the mod (ExtraBuildings): ../blueprints/notredame.json ----
# Local meters around the footprint center (x as above, z shifted), y above the ground. Everything stands on a
# 0.42 m plinth like the original buildings, with a 0.21 m step all around (the player climbs at most 0.30 m).
# Prerequisites: any piece whose top carries the brick's bottom (within 4 cm) and lies within 0.45 m (0.7 m if none).
# The brick supply and the board assume the site at X 3.5, Z 0.4, rotation 180 (west front towards the spawn).
BASE_H = 0.42
HEIGHT = {"R4": 0.22, "SILL": 0.22, "JAMB": 0.42}
PLINTH_PAIR, PLINTH_ONE, STEP_PIECE = "Bakery_Brick_2D1CAFD3", "Pharmacy_Brick_272A63CE", "Bakery_Brick_4018D562"
ZC = (min(r[3] for r in rows) + max(r[3] for r in rows)) / 200
items = []
for r in rows:
    key = type_keys[r[0]]
    pitch = r[6] if len(r) > 6 else 0
    h = 0.21 if (key == "JAMB" and pitch) else HEIGHT.get(key, 0.21)
    items.append((key, r[1] / 100, r[2] / 100 + BASE_H, r[3] / 100 - ZC, r[4], pitch, r[5], h))
tops = {}
for i, it in enumerate(items):
    tops.setdefault((int(math.floor((it[2] + it[7] / 2) / 0.04)), int(math.floor(it[1] / 0.5)), int(math.floor(it[3] / 0.5))), []).append(i)
reqs, floating = [], []
for i, it in enumerate(items):
    bottom = it[2] - it[7] / 2
    found = set()
    carried_elsewhere = False                  # resting on a brick of another part: placeable without prerequisite
    if bottom > BASE_H + 0.05:
        tb, gx, gz = int(math.floor(bottom / 0.04)), int(math.floor(it[1] / 0.5)), int(math.floor(it[3] / 0.5))
        for radius, reach in ((0.45, 1), (0.7, 2)):
            for b in (tb - 1, tb, tb + 1):
                for dx in range(-reach, reach + 1):
                    for dz in range(-reach, reach + 1):
                        for j in tops.get((b, gx + dx, gz + dz), ()):
                            o = items[j]
                            if j != i and abs(o[2] + o[7] / 2 - bottom) < 0.04 and math.hypot(o[1] - it[1], o[3] - it[3]) < radius:
                                if part_of_section[o[6]] == part_of_section[it[6]]:
                                    found.add(j)
                                else:
                                    carried_elsewhere = True
            if found:
                break
        if not found and not carried_elsewhere:
            floating.append(i)
    reqs.append(sorted(found))
# Bricks without support (slabs over hollow towers, lintels over openings, walls rising above the aisles) need a
# neighbor in the same layer instead; a layer then grows from its supported edge. Groups that never touch a supported
# brick stay free to place (no prerequisites).
bottoms = {}
for i, it in enumerate(items):
    bottoms.setdefault((int(math.floor((it[2] - it[7] / 2) / 0.02)), int(math.floor(it[1] / 0.5)), int(math.floor(it[3] / 0.5))), []).append(i)


def layer_neighbors(i):
    it = items[i]
    bottom = it[2] - it[7] / 2
    tb, gx, gz = int(math.floor(bottom / 0.02)), int(math.floor(it[1] / 0.5)), int(math.floor(it[3] / 0.5))
    return [j for b in (tb - 1, tb, tb + 1) for dx in (-1, 0, 1) for dz in (-1, 0, 1) for j in bottoms.get((b, gx + dx, gz + dz), ())
            if j != i and abs(items[j][2] - items[j][7] / 2 - bottom) < 0.02 and math.hypot(items[j][1] - it[1], items[j][3] - it[3]) < 0.45
            and part_of_section[items[j][6]] == part_of_section[it[6]]]


reached = set(range(len(items))) - set(floating)
neigh = {i: layer_neighbors(i) for i in floating}
queue = [i for i in floating if any(j in reached for j in neigh[i])]
while queue:
    nxt = []
    for i in queue:
        if i in reached:
            continue
        reached.add(i)
        nxt += [j for j in neigh[i] if j in neigh and j not in reached]
    queue = [j for j in nxt if any(k in reached for k in neigh[j])]
free = []
for i in floating:
    if i in reached:
        reqs[i] = sorted(j for j in neigh[i] if j in reached)
    else:
        free.append(i)
floating = free

# Plinth: 0.42 m cells marked from rectangles (building with facade scaffold, bell tower stairs, transept stair)
rects = [(-8.82, 8.82, -2.1, max(r[3] for r in rows) / 100 + 0.42),
         (-(lane_x + 2 * MID_T + W / 2 + 0.15), lane_x + 2 * MID_T + W / 2 + 0.15, -2.1, zs_tw + MID_T + W / 2 + 0.2),
         (cx_t - MID_T - W / 2 - 0.2, -8.82, cz_t - MID_T - W / 2 - 0.2, cz_t + MID_T + W / 2 + 0.2),
         (-PLINTH_SIDE, PLINTH_SIDE, 3.0, 29.0)]                  # room for the mobile scaffold along the long sides
U = 0.42
cells = set()
for (x0, x1, z0, z1) in rects:
    for i in range(int(math.floor(x0 / U)), int(math.ceil(x1 / U))):
        for k in range(int(math.floor(z0 / U)), int(math.ceil(z1 / U))):
            cells.add((i, k))
decor, done = [], set()
for (i, k) in sorted(cells):
    if (i, k) in done:
        continue
    if (i, k + 1) in cells and (i, k + 1) not in done:
        decor.append({"def": PLINTH_PAIR, "p": [round((i + 0.5) * U, 4), BASE_H / 2, round((k + 1) * U - ZC, 4)], "yaw": 0})
        done.update({(i, k), (i, k + 1)})
    else:
        decor.append({"def": PLINTH_ONE, "p": [round((i + 0.5) * U, 4), BASE_H / 2, round((k + 0.5) * U - ZC, 4)], "yaw": 0})
        done.add((i, k))
ring = {(i + di, k + dk) for (i, k) in cells for di in (-1, 0, 1) for dk in (-1, 0, 1)} - cells
for (i, k) in sorted(ring):
    decor.append({"def": STEP_PIECE, "p": [round((i + 0.5) * U, 4), 0.105, round((k + 0.5) * U - ZC, 4)], "yaw": 0, "pitch": -90})


def runs(cellset):
    """Rows of neighbouring cells along x -> (i0, i1, k)."""
    out = []
    for k in sorted({c[1] for c in cellset}):
        row = sorted(c[0] for c in cellset if c[1] == k)
        start = prev = row[0]
        for i in row[1:] + [None]:
            if i is not None and i == prev + 1:
                prev = i
                continue
            out.append((start, prev, k))
            if i is not None:
                start = prev = i
    return out


colliders = [{"c": [round((a + b + 1) / 2 * U, 4), BASE_H / 2, round((k + 0.5) * U - ZC, 4)], "s": [round((b - a + 1) * U, 4), BASE_H, U]}
             for (a, b, k) in runs(cells)]
colliders += [{"c": [round((a + b + 1) / 2 * U, 4), 0.105, round((k + 0.5) * U - ZC, 4)], "s": [round((b - a + 1) * U, 4), 0.21, U]}
              for (a, b, k) in runs(ring)]
z_front = min(k for (_, k) in ring) * U - ZC
blueprint_mod = {
    "siteId": "notredame",
    "displayName": "Notre-Dame",
    "templateSite": "house",
    "sections": sections,
    "blueprintStand": [-7.0, round(z_front - 1.2, 3), 0],
    "parts": [{"siteId": sid, "displayName": name, "sections": [k for k, pk in enumerate(part_of_section) if pk == pi],
               "blueprintStand": [(-8.4, -5.6, -2.8, 2.8, 5.6)[pi], round(z_front - 1.2, 3), 0]}
              for pi, (sid, name, _) in enumerate(PARTS)],
    # supply: west of the cathedral and south of the choir, for the site at X 3.5, Z 0.4, rotation 180
    "pile": {"x": 12.0, "z": -21.1, "gap": 0.06, "perRow": 10, "stack": 14, "maxHeight": 3.0,
             "areas": [[14.6, -21.1, 24.5, 15.4], [-10.5, 20.7, 9.5, 23.9], [-18.0, -20.6, -14.6, -15.2],
                       [-18.0, -15.2, -14.6, 0.0]]},            # 2.4 m left for the mobile scaffold to the ramps;
                                                                # the last area is the long one (room for more)
    "colliders": colliders,
    "decor": decor,
    "scaffold": [[round(b[0], 4), round(b[1] + BASE_H, 4), round(b[2] - ZC, 4)] + [round(v, 4) for v in b[3:6]] + [round(a, 2) for a in b[6:]]
                 for b in scaffold],
    "bricks": [{"def": TYPES[it[0]]["asset"], "p": [round(it[1], 4), round(it[2], 4), round(it[3], 4)], "yaw": it[4],
                **({"pitch": it[5]} if it[5] else {}), "s": it[6], "mode": 1 if reqs[i] else 0, "req": reqs[i]}
               for i, it in enumerate(items)],
}
dst_mod = os.path.join(here, "..", "blueprints", "notredame.json")
with open(dst_mod, "w", encoding="utf-8") as f:
    json.dump(blueprint_mod, f, separators=(",", ":"))
print("parts:", [(sid, sum(1 for it in items if part_of_section[it[6]] == pi), part_of_section.count(pi)) for pi, (sid, _, _) in enumerate(PARTS)])
sizes = sorted(len(t[4]) for t in fine)
print(f"sections: {len(sections)}, bricks per section min {sizes[0]}, median {sizes[len(sizes) // 2]}, max {sizes[-1]}")
print(f"mod blueprint: {len(items)} bricks, {len(floating)} free to place (no supported neighbor) "
      f"{[(items[i][0], round(items[i][1], 2), round(items[i][2], 2), round(items[i][3], 2)) for i in floating[:8]]}, "
      f"plinth {len(cells)} cells + {len(ring)} step cells, {len(decor)} decor, {len(colliders)} colliders, "
      f"{os.path.getsize(dst_mod) / 1e6:.1f} MB -> {os.path.normpath(dst_mod)}")
