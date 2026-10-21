"""Generates the blueprint of the test garage for the ExtraBuildings mod.

Grid: 1 cell = 0.42 m (width of a 4x2x2 block). Footprint 8 x 12 cells (3.36 x 5.04 m),
6 wall layers (2.52 m) + flat roof. Door at the front (local -z), 6 cells wide, 5 layers high.
Blueprint coordinates: meters, relative to the footprint center at ground level, y = brick center.

Usage:  py gen_garage.py  ->  ../blueprints/garage.json
"""
import json
import os

U = 0.42
NX, NZ, LAYERS = 8, 12, 6
BASE_H = 0.42             # plinth height (like the original buildings: lowest brick center at 0.63 m)
STEP = "House_Brick_41DF8BC6"     # 2x1 block (0.21 x 0.21 x 0.42), long along local z
FLOOR = "Factory_Brick_1687C5FC"  # 2x1 block (0.42 x 0.21 x 0.21), long along local x: floor
DOOR_X = range(1, 7)      # door cells in the front wall (k = 0)
DOOR_LAYERS = 5           # door open in layers 0..4
BLOCK = "Bakery_Brick_2D1CAFD3"   # 4x2x2 block, long along local z
CUBE = "Factory_Brick_7CB4833B"   # 2x2x2 block (1 cell)

bricks = []  # {def, cells:[(i,k)], layer, yaw, section}


def section_of(layer):
    return 0 if layer < 3 else (1 if layer < LAYERS else 2)


def add(defn, cells, layer, yaw):
    bricks.append({"def": defn, "cells": cells, "layer": layer, "yaw": yaw, "s": section_of(layer)})


def run(cells, layer, along_x):
    """Fill a row of cells with 2-cell blocks, the remainder with a cube."""
    i = 0
    while i < len(cells):
        if i + 1 < len(cells):
            add(BLOCK, [cells[i], cells[i + 1]], layer, 90 if along_x else 0)
            i += 2
        else:
            add(CUBE, [cells[i]], layer, 0)
            i += 1


for L in range(LAYERS):
    door_open = L < DOOR_LAYERS
    even = L % 2 == 0
    # Long walls (x = 0 and x = NX-1): even layers own the corners
    kz = range(0, NZ) if even else range(1, NZ - 1)
    for x in (0, NX - 1):
        run([(x, k) for k in kz], L, along_x=False)
    # Back wall (k = NZ-1) and front wall (k = 0)
    ix = range(1, NX - 1) if even else range(0, NX)
    run([(i, NZ - 1) for i in ix], L, along_x=True)
    front = [(i, 0) for i in ix]
    if door_open:
        front = [c for c in front if c[0] not in DOOR_X]
        for c in front:          # remaining pieces next to the door, one by one
            add(CUBE, [c], L, 0)
    else:
        run(front, L, along_x=True)

# Flat roof: one layer of cubes over everything
for i in range(NX):
    for k in range(NZ):
        add(CUBE, [(i, k)], LAYERS, 0)

# Prerequisites: all bricks below that overlap the footprint (All);
# without support (middle of the lintel, inner roof): any neighbor in the same layer (Any).
cell_owner = {}
for idx, b in enumerate(bricks):
    for c in b["cells"]:
        key = (b["layer"], c)
        assert key not in cell_owner, f"Duplicate cell {key}"
        cell_owner[key] = idx

for idx, b in enumerate(bricks):
    L = b["layer"]
    if L == 0:
        b["mode"], b["req"] = 0, []
        continue
    below = sorted({cell_owner[(L - 1, c)] for c in b["cells"] if (L - 1, c) in cell_owner})
    if below:
        b["mode"], b["req"] = 0, below
        continue
    neigh = set()
    for (i, k) in b["cells"]:
        for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            o = cell_owner.get((L, (i + di, k + dk)))
            if o is not None and o != idx:
                neigh.add(o)
    b["mode"], b["req"] = 1, sorted(neigh)
    assert neigh, f"Brick {idx} has neither support nor neighbors"


def lx(i):
    return round((i - (NX - 1) / 2) * U, 4)


def lz(k):
    return round((k - (NZ - 1) / 2) * U, 4)


out = []
for b in bricks:
    ci = sum(c[0] for c in b["cells"]) / len(b["cells"])
    ck = sum(c[1] for c in b["cells"]) / len(b["cells"])
    out.append({
        "def": b["def"],
        "p": [lx(ci), round(BASE_H + (b["layer"] + 0.5) * U, 4), lz(ck)],
        "yaw": b["yaw"], "s": b["s"], "mode": b["mode"], "req": b["req"],
    })

# Plinth (visuals + colliders only, no slots): ring of 4x2x2 blocks one cell around the footprint,
# floor inside, step in front of the door.
decor = []
ring_x = [(i, k) for k in (-1, NZ) for i in range(-1, NX + 1)]          # front/back, incl. corners
ring_z = [(i, k) for i in (-1, NX) for k in range(0, NZ)]               # left/right
for line, along_x in ((ring_x[:NX + 2], True), (ring_x[NX + 2:], True), (ring_z[:NZ], False), (ring_z[NZ:], False)):
    for j in range(0, len(line) - 1, 2):
        a, c = line[j], line[j + 1]
        decor.append({"def": BLOCK, "p": [lx((a[0] + c[0]) / 2), round(BASE_H / 2, 4), lz((a[1] + c[1]) / 2)], "yaw": 90 if along_x else 0})
    if len(line) % 2:
        a = line[-1]
        decor.append({"def": CUBE, "p": [lx(a[0]), round(BASE_H / 2, 4), lz(a[1])], "yaw": 0})
for i in DOOR_X:                    # step: two 2x1 blocks side by side per door cell (0.21 wide, 0.42 deep)
    for half in (-0.25, 0.25):
        decor.append({"def": STEP, "p": [round(lx(i) + half * U, 4), 0.105, lz(-2)], "yaw": 0})
for i in range(NX):                 # floor: two flat 2x1 blocks per cell, top = plinth height
    for k in range(NZ):
        for half in (-0.25, 0.25):
            decor.append({"def": FLOOR, "p": [lx(i), round(BASE_H - 0.105, 4), round(lz(k) + half * U, 4)], "yaw": 0})
door_c = sum(DOOR_X) / len(DOOR_X)

blueprint_base = {
    "colliders": [
        {"c": [0.0, round(BASE_H / 2, 4), 0.0], "s": [round((NX + 2) * U, 4), BASE_H, round((NZ + 2) * U, 4)]},
        {"c": [lx(door_c), 0.105, lz(-2)], "s": [round(len(DOOR_X) * U, 4), 0.21, U]},
    ],
    "decor": decor,
}

blueprint = {
    "siteId": "garage",
    "displayName": "Garage",
    "templateSite": "house",
    "sections": ["Lower walls", "Upper walls", "Roof"],
    # Blueprint board relative to the footprint center: x, z, rotation (degrees)
    "blueprintStand": [-(NX / 2) * U - 1.6, -(NZ / 2) * U - 1.2, 0],
    # Brick supply, local: start corner x, z, gap between bricks, bricks per row, stack height
    "pile": {"x": (NX / 2) * U + 1.5, "z": -(NZ / 2) * U, "gap": 0.06, "perRow": 10, "stack": 2},
    **blueprint_base,
    "bricks": out,
}

here = os.path.dirname(os.path.abspath(__file__))
dst = os.path.join(here, "..", "blueprints", "garage.json")
os.makedirs(os.path.dirname(dst), exist_ok=True)
with open(dst, "w", encoding="utf-8") as f:
    json.dump(blueprint, f, indent=1)
count = {}
for b in out:
    count[b["def"]] = count.get(b["def"], 0) + 1
per_sec = [sum(1 for b in out if b["s"] == s) for s in range(3)]
print(f"{len(out)} bricks {count}, sections {per_sec}, Any bricks {sum(1 for b in out if b['mode'] == 1)}, "
      f"plinth {len(decor)} decor bricks -> {os.path.normpath(dst)}")
