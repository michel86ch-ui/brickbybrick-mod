"""Generates a small round test tower for the ExtraBuildings mod (about 300 bricks).

It tries out in the game what the Notre-Dame needs for its round parts before 25,000 bricks depend on it:
- 2x1 blocks laid along a circle, each turned to the tangent, slightly overlapping (the game checks no geometry
  when a brick is set, ConstructionSiteState.CanPlace),
- a window framed like the game's house: upright "2x1x2 Blocks" as jambs, the same block lying flat (pitch -90)
  stepping into a point, a "2x2 Window" sill,
- a conical roof of flat 2x2 tiles in rings, every other tile 5 mm higher so overlapping tops do not flicker.

Grid: 1 cell = 0.21 m. Blueprint coordinates: meters, relative to the footprint center at ground level,
y = brick center. Angles phi run from +x towards +z; yaw t turns local +x to (cos t, 0, -sin t).

Usage:  py gen_roundtest.py  ->  ../blueprints/roundtest.json
"""
import json
import math
import os

CELL = 0.21
U = 0.42
BASE_H = 0.42                     # plinth height, like the garage
R_CELLS = 7.5                     # wall center radius in cells (1.575 m)
ROWS = 8                          # wall rows
WIN, WIN_Y, WIN_H = 4, 2, 2       # window: width (cells), first open row, straight rows
WIN_PHI = 270.0                   # window faces local -z (towards the blueprint board)
LIFT = 0.005
JAMB_OUT, SILL_OUT = 0.073, 0.173  # measured on the game's house

S2, S1 = "LibraryNew_Brick_FEB8053A", "LibraryNew_Brick_D800AC09"      # beige 2x1 (long along local z), 1x1
JAMB = "Bakery_Brick_4018D562"    # grey 2x1x2 block (0.42 deep along x, 0.42 high, 0.21 along z)
SILL = "Bakery_Brick_402F42D4"    # grey "2x2 Window", sloped, local -x outwards
TILE = "Bakery_Brick_6ED2F14B"    # anthracite 2x2 roof tile, local +x up the slope
GOLD = "Bakery_Brick_EBE67C24"    # yellow 1x1
BLOCK, CUBE, FLOOR = "Bakery_Brick_2D1CAFD3", "Factory_Brick_7CB4833B", "Factory_Brick_1687C5FC"
HEIGHT = {S2: 0.21, S1: 0.21, JAMB: 0.42, SILL: 0.22, TILE: 0.22, GOLD: 0.21}

pieces = []   # (def, x, y, z, yaw, pitch, section)
r = R_CELLS * CELL
circ = 2 * math.pi * r / CELL                    # circumference in cells
phi0 = WIN_PHI - 180.0                           # arc length u = 0 lies opposite the window


def put(defn, u, y_cells, out_off, yaw_of, pitch, sec):
    phi = phi0 + math.degrees(u * CELL / r)
    a = math.radians(phi)
    rr = r + out_off
    pieces.append((defn, rr * math.cos(a), BASE_H + y_cells * CELL, rr * math.sin(a), yaw_of(phi), pitch, sec))


radial = lambda phi: -phi          # local x along the radius, local z along the tangent
inwards = lambda phi: 180 - phi    # local +x towards the center
sec_of = lambda y: 0 if y < 4 else 1

# ---- Window frame ----
uc = circ / 2
blocked = {}


def block(y, a, b):
    blocked.setdefault(y, []).append((a, b))


block(WIN_Y - 1, uc - WIN / 2 - 1, uc + WIN / 2 + 1)
for k in range(WIN // 2 + 1):
    put(SILL, uc - WIN / 2 + 2 * k, WIN_Y - 0.5, SILL_OUT, inwards, 0, sec_of(WIN_Y - 1))
for y in range(WIN_Y, WIN_Y + WIN_H):
    block(y, uc - WIN / 2 - 1, uc + WIN / 2 + 1)
for y in range(WIN_Y, WIN_Y + WIN_H, 2):
    for uj in (uc - WIN / 2 - 0.5, uc + WIN / 2 + 0.5):
        put(JAMB, uj, y + 1, JAMB_OUT, radial, 0, sec_of(y))
for k in range(1, WIN // 2 + 1):
    y, half = WIN_Y + WIN_H - 1 + k, WIN // 2 - k
    block(y, uc - half - 2, uc + half + 2)
    for ul in ((uc - half - 1, uc + half + 1) if half else (uc - 1, uc + 1)):
        put(JAMB, ul, y + 0.5, JAMB_OUT, radial, -90, sec_of(y))


# ---- Ring wall: running bond, the rest spread over all joints ----
def sizes_for(length):
    n2 = int(length // 2)
    rem = length - 2 * n2
    return [2] * n2 + ([2] if rem >= 1.5 else [1] if rem >= 0.5 else [])


for y in range(ROWS):
    arcs, pos = [], 0.0
    for a, b in sorted(blocked.get(y, [])):
        if a > pos:
            arcs.append((pos, a))
        pos = max(pos, b)
    if pos < circ:
        arcs.append((pos, circ))
    shift = 1.0 if y % 2 and not blocked.get(y) else 0.0      # closed rows: running bond by turning the start
    for a, b in arcs:
        length = b - a
        sizes = [1] + sizes_for(length - 2) + [1] if y % 2 and blocked.get(y) and length >= 3 else sizes_for(length)
        f = length / sum(sizes) if sizes else 1
        u = a + shift
        for s in sizes:
            put(S2 if s == 2 else S1, u + s * f / 2, y + 0.5, 0.0, radial, 0, sec_of(y))
            u += s * f

# ---- Conical roof: rings of flat tiles stepping in one cell per row (45 degrees) ----
for k in range(int(R_CELLS - 0.5)):
    rr = (R_CELLS - 0.5 - k) * CELL
    n = max(3, int(math.ceil(2 * math.pi * (rr + CELL) / U)))
    for i in range(n):
        phi = (i + 0.5 * (k % 2)) * 360.0 / n
        a = math.radians(phi)
        lift = LIFT * (2 if n % 2 and i == n - 1 else i % 2)
        pieces.append((TILE, rr * math.cos(a), BASE_H + (ROWS + k + 0.5) * CELL + lift, rr * math.sin(a), 180 - phi, 0, 2))
top_y = BASE_H + (ROWS + int(R_CELLS - 0.5)) * CELL
pieces.append((GOLD, 0.0, top_y + 0.105, 0.0, 0, 0, 2))

# ---- Prerequisites: any piece whose top carries this piece's bottom (within 4 cm) and lies within 0.45 m ----
out = []
for i, (d, x, y, z, yaw, pitch, s) in enumerate(pieces):
    h = HEIGHT[d] if not (d == JAMB and pitch) else 0.21
    bottom = y - h / 2
    req = []
    if bottom > BASE_H + 0.05:
        for j, (d2, x2, y2, z2, _, p2, _) in enumerate(pieces):
            h2 = HEIGHT[d2] if not (d2 == JAMB and p2) else 0.21
            if j != i and abs(y2 + h2 / 2 - bottom) < 0.04 and math.hypot(x - x2, z - z2) < 0.45:
                req.append(j)
        if not req:
            raise SystemExit(f"piece {i} ({d}) at y {y:.3f} has no support")
    out.append({"def": d, "p": [round(x, 4), round(y, 4), round(z, 4)], "yaw": round(yaw, 2), "pitch": pitch,
                "s": s, "mode": 1 if req else 0, "req": req})

# ---- Plinth (visuals + colliders only): ring of 4x2x2 blocks around a floor of flat 2x1 blocks ----
N = 8                                              # floor cells of 0.42 m per side (3.36 m)
lc = lambda i: round((i - (N - 1) / 2) * U, 4)
decor = []
for k in (-1, N):
    for i in range(-1, N + 1, 2):
        decor.append({"def": BLOCK, "p": [lc(i + 0.5), BASE_H / 2, lc(k)], "yaw": 90})
for i in (-1, N):
    for k in range(0, N, 2):
        decor.append({"def": BLOCK, "p": [lc(i), BASE_H / 2, lc(k + 0.5)], "yaw": 0})
for i in range(N):
    for k in range(N):
        for half in (-0.25, 0.25):
            decor.append({"def": FLOOR, "p": [lc(i), round(BASE_H - 0.105, 4), round(lc(k) + half * U, 4)], "yaw": 0})

blueprint = {
    "siteId": "roundtest",
    "displayName": "Round Test",
    "templateSite": "house",
    "sections": ["Round wall", "Window and upper wall", "Round roof"],
    "blueprintStand": [-(N / 2) * U - 1.6, -(N / 2) * U - 1.2, 0],
    "pile": {"x": (N / 2) * U + 1.5, "z": -(N / 2) * U, "gap": 0.06, "perRow": 10, "stack": 2},
    "colliders": [{"c": [0.0, BASE_H / 2, 0.0], "s": [round((N + 2) * U, 4), BASE_H, round((N + 2) * U, 4)]}],
    "decor": decor,
    "bricks": out,
}
here = os.path.dirname(os.path.abspath(__file__))
dst = os.path.join(here, "..", "blueprints", "roundtest.json")
with open(dst, "w", encoding="utf-8") as f:
    json.dump(blueprint, f, indent=1)
count = {}
for b in out:
    count[b["def"]] = count.get(b["def"], 0) + 1
print(f"{len(out)} bricks {count}, sections {[sum(1 for b in out if b['s'] == s) for s in range(3)]}, "
      f"plinth {len(decor)} decor bricks -> {os.path.normpath(dst)}")
