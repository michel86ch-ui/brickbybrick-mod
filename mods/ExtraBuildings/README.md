# ExtraBuildings 1.1.1

Extra construction sites from a blueprint (JSON). Active only in a **mod-map session** (`ModMapEnabled = true`);
every world choice then opens the mod world (default `singleplayer-4`). In a normal session the mod does nothing and
locks the mod world. A button top left in the main menu switches the mode and restarts the game.

## How it works

1. Prefix on `GameSceneInstaller.OnSceneEnterAsync` (before the slots are registered), only in a mod-map session.
2. One clone of the template `house` per blueprint part, in an inactive holder: without `ConstructionSceneInstaller`
   (it sits on the House root), without `CompletionObjects`, `Supply`, `House`. Kept: blueprint board, progress
   display, timelapse, effect.
3. Every part becomes its own construction site. The game allows at most **8192 slots and 256 sections per site**
   (measured in `ConstructionStateNetworkSynchronizer`), so a large building is split into parts, like the town's own
   buildings. Prerequisites stay inside a part.
4. Sections from the blueprint, each with its own final mesh (combined from the catalog visuals).
5. Brick slots = clones of an original slot of the same brick definition, slot IDs 900000001+ over the whole
   blueprint, `placeTrigger` = site area of the part.
6. The first part carries the plinth (game bricks, visuals only, one mesh, plus walkable colliders) and the scaffold
   (see below). Every part gets its own 3D model on its blueprint board.
7. Bake the topology, check with the game's `ValidateAuthoredReferences` + `GetBakedSpecs`.
8. New brick catalog = original + the blueprint's material (brick IDs 900000001+), supply next to the site.
9. Only then: swap the catalog, append slots and sites to the game's lists. On any error the world loads without them.
   With `RemoveVanillaBuildings` the seven original sites are hidden and their slots, bricks and sites leave the
   game's lists; the catalog then holds only the blueprint's bricks.
10. `AppBootstrap.ConfigureHostSaveSlot`: mod-map session -> every choice becomes the building's world (Taj Mahal
    slot 3, Notre-Dame slot 4); a slot that holds a normal save is refused, every slot opened as mod map is remembered
    (`ModWorlds`). Normal session -> all remembered mod worlds are locked.
11. `ConstructionSceneInstaller.OnSceneEnterAsync`: installers left without a site are skipped (the game's
    `ConstructionStateNetworkSynchronizer` requires 1 to 32 sites).
12. `ConstructionSite.ObserveLocalPlayer`: the parts of a building share one area, so only the part whose bricks are
    nearest to the player shows its progress panel. Placing is not affected (`PlacementSlot.IsPlayerInside` checks
    the area collider itself).
13. Main-menu buttons, one per building ("Start Notre-Dame (world 4)", "Start Taj Mahal (world 3)"): set world,
    blueprint and site, save `ModMapEnabled`, start a hidden PowerShell that waits for the game to exit and then opens
    `steam://rungameid/5228920`, and quit the game. In a mod-map session one button leads back to the normal worlds.
14. `Showcase = true`: instead of construction sites the blueprint stands finished, one mesh with a walkable
    `MeshCollider` per section, on its plinth, without scaffold (ramps stay). The original sites are hidden and every installer is
    left empty, so the world keeps no building progress. For checking a design in the game.
15. Start skill points: a mod world whose shared progression was never changed (`ProgressionService.Revision` 0, saved
    with the world) gets `StartSkillPoints` through the game's own `GrantCurrencyForDevelopment` (host only). The
    grant raises the revision, so it happens once per world; existing worlds keep what they have.
16. Mobile scaffold: in the base game its skill node opens only when the town's house is finished (the only node of
    58 that a finished building opens), and the mod map has no house. With `UnlockScaffoldLift` the mod claims that
    completion reward (`construction-building` + `house`, with its 10 skill points) through the game's own
    `TryClaimCompletionReward` (host only), once per mod world.
17. Prerequisites across construction sites (`xreq`): a building cut into storeys has bricks resting on bricks of the
    site below. Each site's state registers its slots when created; a postfix on `ConstructionSiteState.CanPlace`
    also requires those bricks, on the host and on clients alike.
18. Clear area (`clearArea`): in a mod-map session the town's fences and small props (material `M_Map_04` with a
    collider) inside the blueprint's rectangle are switched off, to make room for a large building.
19. Temporary scaffold (`tempScaffold`): stands while the building is built; a watcher checks twice a second whether
    every site of the building is complete (`ConstructionSite.State.IsComplete`) and then switches it off.

### Scaffold

Boxes from the blueprint in two meshes: planks with the game's `M_Scaffolding` material (a texture atlas of the
scaffold lift, so their UVs map onto a deck plate of it), uprights, rails and braces with a copy of it in plain
aluminium. Walkable boxes get a `BoxCollider` on the layer of the house foundation, rotated ones (ramps) with their
rotation. Uprights have no collider, so the mobile scaffold can drive through between them; braces are visuals only.

## Settings (`BepInEx\config\michel.brickbybrick.extrabuildings.cfg`)

| Key | Default | Meaning |
|---|---|---|
| General / ModMapEnabled | false | true = start the game as mod map (takes effect at the next start) |
| General / RemoveVanillaBuildings | true | Mod map only: remove the seven original buildings and their bricks |
| General / StartSkillPoints | 20 | Mod map only: skill points a new mod world starts with (0 = like the base game) |
| General / UnlockScaffoldLift | true | Mod map only: unlock the mobile scaffold (the game unlocks it with the town's house, which the mod map does not have) |
| General / Showcase | false | Mod map only: the blueprint as a finished building instead of construction sites (no building progress) |
| General / World | singleplayer-4 | World slot of the mod map (set by the menu buttons: Taj Mahal slot 3, Notre-Dame slot 4) |
| General / ModWorlds | singleplayer-4 | Slots opened as mod map so far (kept by the mod, locked in normal sessions) |
| General / Blueprint | garage.json | File in the plugin folder (`garage.json`, `roundtest.json`, `notredame.json`, `tajmahal.json`) |
| Site / X, Z | 0, 0 | Footprint center (town center); the Notre-Dame expects X 3.5, Z 0.4 |
| Site / Rotation | 0 | Rotation in degrees; the Notre-Dame expects 180 (west front towards the spawn) |
| Site / MoveKey | F9 | Move the site 4 m in front of you, door facing you; takes effect at the next game start |

## Blueprint format (`blueprints\*.json`, generated by `tools\gen_*.py`)

`siteId`, `displayName`, `templateSite`, `sections[]`, `blueprintStand [x, z, degrees]`,
`pile {x, z, gap, perRow, stack, maxHeight, areas}`, `colliders[] {c, s}`, `decor[] {def, p, yaw, pitch}` (visuals
only), `scaffold[]`, `parts[]`, and `bricks[]` with `def` (asset name of the brick definition), `p` (brick center in
m, local, y above ground), `yaw`, `pitch` (optional tilt around the brick's x axis, Unity Euler order pitch then yaw;
-90 lays a 2x1x2 block flat), `s` (section), `mode` (0 = all prerequisites, 1 = any one is enough), `req` (indices).

- `parts[] {siteId, displayName, sections[], blueprintStand}`: optional, one construction site per part; every
  section belongs to exactly one part. Without parts the whole blueprint is one site.
- `scaffold[]`: `[cx, cy, cz, sx, sy, sz]` = walkable box (a slim upright one gets no collider),
  `[cx, cy, cz, sx, sy, sz, pitch, yaw, roll]` = rotated box, visuals only; a tenth value 1 makes it walkable (ramps).
- `pile.areas`: local rectangles `[x0, z0, x1, z1]` filled one after the other; `pile.maxHeight` caps the stacks
  (meters). Without areas the supply grows in rows of `perRow` from `x, z`.

Positions and angles are free, the game does not need its grid: `ConstructionSiteState.CanPlace` checks only that the
slot is free, its section open and its prerequisites met, no geometry. Blocks may therefore stand at small angles
along a circle and overlap a little. Roof tiles in a ring are lifted 5 mm on every other tile, so overlapping tops
do not lie in one plane (z-fighting).

## Garage (garage.json)

8 x 12 cells of 0.42 m (3.36 x 5.04 m) on a 0.42 m high plinth, 6 wall layers (2.52 m) + flat roof,
door 2.52 x 2.10 m. 191 bricks: 91 x `Bakery_Brick_2D1CAFD3` (4x2x2 block), 100 x `Factory_Brick_7CB4833B`
(2x2x2 block). Sections: lower walls 46, upper walls 49, roof 96. Plinth: 226 decor bricks.

## Round test (roundtest.json)

Round tower on the same plinth as the garage: wall of 2x1 blocks along a circle of 1.575 m radius (8 rows, running
bond), a window framed like the game's house (upright 2x1x2 blocks as jambs, lying ones stepping into a point,
"2x2 Window" sill) and a 45 degree cone of roof-tile rings with a yellow block on top. 311 bricks in 3 sections;
prerequisites: any piece whose top carries the brick within 4 cm and 0.45 m.

## Notre-Dame (notredame.json, from `tools\gen_notredame.py 1.2`)

26,462 bricks in 413 sections and five construction sites: west front 4,870, bell towers 4,825, nave 7,439, transept
and choir 8,027, drum and spire 1,301. Sections are cut like the town's own buildings, about 64 bricks each (the game
pays one skill point per finished section, ten per finished building, plus milestones for placed bricks), from height
bands of 0.84 m built from the bottom up, so every section can be finished at its own height.

No wall stands on nothing: arcades of pointed arches (framed like the windows, two jambs per pier) carry the upper
walls of nave, choir and transept, a ring of three arches carries the upper wall of the round choir, and arches open
the bell towers to the aisles and to the hall between them, and that hall to the nave. Only the flat slabs (tower
platforms, the ceiling of the hall) and the flying buttresses span free. A wall cell is part of the shell when any of
its 8 neighbours in the layer is outside, so two walls meeting in an inner corner share their corner block.

Walls are laid in running bond with bonded corners: at every corner, junction and pier the 2x1 block lies across the
one below. A 1x1 block sits where a wall ends at an opening, in every other course, so the joints shift like half
bricks at a real reveal (also in piers between two windows), where a wall has an odd length, or where a cell has no
neighbour; arch jambs stand right against the next wall, so no one-cell stubs are left (2,148 of 18,453 wall blocks,
1,439 of them at openings, 7 at corners; 99.5 % of the corner layers alternate; 9.3 % of the vertical joints sit
on the joint below). Prerequisites: a brick needs a brick of its part that
carries it; a brick without one (slabs, lintels over openings) needs a neighbour in the same layer that is itself
connected to a carried brick, so layers grow from their supported edge like in the original buildings. No brick is
free to place.

Plinth 0.42 m with a 0.21 m step all around (the player climbs at most 0.30 m). Supply: four areas around the
cathedral, stacks up to 3 m, with a 2.4 m wide way left for the mobile scaffold to the ramps.

Scaffold: 863 parts in aluminium, walkways 1.3 m wide (the player is 1 m wide), 73 uprights, all on the plinth.

- Bell towers: a facade scaffold in front of the west front and a stair tower at each tower's outer face up to its
  platform, decks every 5 m, a back lane behind each tower and a cross bridge between the tower tops.
- Transept, drum and spire: a stair tower in front of the north transept, a bridge at ridge height and a stair round
  the drum up to a platform from which the spire tip is within reach.
- Clerestory lanes at 9.45 m along the upper walls of nave, transept and choir, reached by short stairs from the
  bell towers' back lanes. A brick is set from up to 5 m from the player (game code), so from a lane the upper wall
  and the roofs up to the ridge are within reach.
- Every stair turns on a square landing, never on its steps.
- Two 15 degree ramps on the long sides lead the game's mobile scaffold up onto the plinth (it cannot climb the
  0.21 m step).

Checked by script: every part touches a path down to the ground, no rail or ledger ends more than 0.4 m past its last
upright, no plank lies without support, and no two visible parts share a face plane where they overlap
(flickering).

## Tested in game

- 0.1.0: brick slots, holograms, snapping, progress per section, blueprint board counts along, finished sections stay
  visible, "Construction complete", build replay.
- 0.2.0: plinth made of game bricks, garage model on the blueprint board.
- 0.3.0: menu button restarts into the mod map and back; the original buildings and their bricks are gone, the
  garage stands in the town center; a new mod world can be created and an existing one reopened with its progress.
- 0.3.1: round test tower built to completion: angled, slightly overlapping blocks snap in, lying (pitch -90) frame
  blocks, ring roof (no flickering thanks to the 5 mm lift), final meshes and "Construction complete".
- 0.4.0: the Notre-Dame loads as five construction sites with plinth, brick supply, five blueprint boards and the
  scaffold. Seen: the scaffold showed the whole texture atlas, uprights stood on roofs not built yet, stair steps had
  nothing under them, and all five progress panels showed at once.
- 0.4.1: fixes for those four points (atlas UVs, uprights on the plinth, stringers and ledgers, one progress panel).
- 0.5.0 showcase, first build: the Notre-Dame stands finished and walkable; drum, spire roof and towers as intended.
  Seen: upper walls inside without anything under them, straight joints in inner corners, scaffold parts in the air,
  a flickering walkway where the bridge to the spire scaffold crossed the tower lanes. Fixed since (arcades, 8-neighbour
  shell, scaffold rework, that bridge removed, no scaffold in the showcase).
- 0.5.0 showcase after the rework: confirmed in game (screenshots of the west front, the choir side, the nave arcades
  and the crossing).
- 0.5.0 building in normal mode: bricks snap in, sections finish, a skill point is earned. Seen: a column of 1x1
  beside an arch jamb and stacked joints in the piers between the aisle windows.
- 0.6.0: those two fixed (packing above), start skill points (a new mod world starts with them). Seen: stacked
  joints where an odd wall between two corners had its 1x1 in the middle, the red scaffold too dominant, a gap in a
  tower lane, stairs turning on their steps, the mobile scaffold unable to climb the plinth. The skill tree data
  showed that the mobile scaffold opens only with the town's house, which the mod map does not have.
- 1.1.1: the Taj Mahal's ramp at 20°, its lower end 0.6 m in the ground: the mobile scaffold got stuck at its lower end,
  where the town's ground lies lower than at the site's centre.
- 1.1.0 (with the Taj Mahal 1.0, first as beta 0.5): Taj Mahal in slot 3 next to the Notre-Dame in slot 4, a menu
  button per building, prerequisites across sites, fences cleared, a scaffold that goes once the building is complete;
  Notre-Dame with a stair tower inside. Seen in the showcase: size and place fine, fences gone, ramp missing (fixed:
  ramps stay in the showcase). Building the Taj Mahal brick by brick: confirmed in game, released as 1.0 unchanged
  from the beta.
- 1.0.0: all of that fixed: the 1x1 goes where the joints shift, aluminium scaffold with landings at every stair
  corner, mobile scaffold unlocked, up the ramps onto the plinth and through the uprights (no colliders), clerestory
  lanes, higher brick stacks, 73 instead of 200 uprights.

## Open

- Building the Notre-Dame to the end: reach from the clerestory lanes to the upper walls and roofs, load and frame
  rate with 26,000 bricks, saving.
- Does a finished building grant skill points (`construction-building` + building ID)?
- The tutorial hints still run in the mod world (e.g. "open the skill tree").
- Moving a site in a world with placed bricks leaves those bricks behind (they are saved with their world
  position); the mod should refuse to move a site that has bricks on it.
