# Brick by Brick – Extra Buildings (Mod)

A mod for *Brick by Brick: Tidy Up the Small Town!* (Steam). It adds extra buildings to the game from a blueprint –
with real brick slots, holograms, construction sections, a blueprint board, a completion message and a build replay,
just like the original buildings. The first building is a **test garage with 191 bricks**. The goal is a simplified
**Notre-Dame with roughly 25,000 bricks**.

> Unofficial fan mod, not made by the game's developers. This repository contains no game files.

![Garage under construction next to the bakery](docs/modmapBrickByBrick.png)

![Construction complete: garage with build replay](docs/modmapBrickByBrick2.png)

## Status (2026-10-21)

| Feature | Status |
|---|---|
| Brick slots, holograms, snapping into place | confirmed in game |
| Progress per section, blueprint board counts along | confirmed in game |
| Finished sections (final meshes), "Construction complete" message, build replay | confirmed in game |
| Plinth made of game bricks, own 3D model on the blueprint board (0.2.0) | confirmed in game |
| Mod map without the seven original buildings and their 18,485 bricks, garage in the town center (0.3.0) | confirmed in game |
| "Start Mod Map" / "Back to normal worlds" menu button with automatic restart (0.3.0) | confirmed in game |
| Saving and reloading the mod world | confirmed in game (an older test world reopened with its finished garage) |
| Notre-Dame | planned |

## Mod map: a separate world instead of the main world

An extra building changes the building list of a save; the game then no longer counts that world's run for the
leaderboard. That is why the mod only builds in a world of its own, the **mod map** (default: world slot 4).

The game loads the town scene once per game start and opens the worlds inside it. The mode therefore applies to the
whole game session:

| Mode | Behavior |
|---|---|
| normal (default) | The mod does nothing. The mod world is locked, because without the mod the game would drop the extra buildings' bricks when loading it. |
| mod map | The seven original buildings and their bricks are removed, the extra buildings are injected, every world choice in the menu opens the mod world, "MOD-MAP" is shown top left. |

The main menu has a button top left: **Start Mod Map** in a normal session, **Back to normal worlds** in a mod-map
session. It saves the mode and restarts the game through Steam.

Placed bricks are saved with their world position. Do not move a site (`F9` or `X`/`Z` in the config) in a mod world
that already has bricks on it: they would stay behind at the old place. Delete the mod world first.

## Installation

1. Unpack [BepInEx 5.4.23.5 x64](https://github.com/BepInEx/BepInEx/releases/tag/v5.4.23.5) into the game folder.
2. Build the mod (see below) – `ExtraBuildings.dll` and `blueprints\garage.json` end up in `BepInEx\plugins\ExtraBuildings\`.
3. Start the game and click **Start Mod Map** top left in the main menu; the game restarts as mod map.
4. Choose any world -> mod world (world slot 4). The town is empty, the garage stands in its center.

Uninstall: delete `winhttp.dll`, `doorstop_config.ini`, `.doorstop_version`, `changelog.txt` and the `BepInEx` folder
in the game folder. The game itself is not modified.

## Building

```
cd mods\ExtraBuildings
dotnet build -c Release -p:DeployToGame=true     (copies the DLL + blueprints\*.json into the game)
py tools\gen_garage.py                            (regenerate the blueprint)
```

The project references the DLLs directly from the game folder (adjust `GameDir` in the `.csproj` if the game is
installed elsewhere).

| Folder | Content |
|---|---|
| [mods/ExtraBuildings](mods/ExtraBuildings/) | The mod (C#, BepInEx 5 / HarmonyX) |
| [tools](tools/) | Blueprint generators (Python) |
| [blueprints](blueprints/) | Generated blueprints (JSON) |
| [docs](docs/) | Screenshots |

## How the game builds its buildings

Measured in the game code (Unity 6000.3.6, Mono) and in the scene data:

- Buildings are **not in the code** but in the scene: 7 `ConstructionSite`s with 18,485 brick slots in total.
- Loose bricks: one `BrickWorldCatalog` with exactly 18,485 bricks, GPU-instanced through `BrickWorldSource`.
- Scene start (`GameSceneInstaller.OnSceneEnterAsync`): register the slots -> register the brick catalog ->
  apply the save. After that, one `ConstructionSceneInstaller` per building initializes its site.
- A brick slot is a GameObject with `PlacementSlot` + `ConstructionSlot` and a `Hologram` child. Slot ID and brick ID
  are `uint`. A brick's pivot is its center, the grid is 0.21 m.
- `PlacementSlot.placeTrigger` is the building's site area: a brick can only be placed while standing inside it.
- Every site has a baked topology (`bakedSpecs`) that `GetBakedSpecs()` checks strictly against the slots.
- Once a section is complete, the game shows a combined mesh (`finalVisualRoot`) instead of the single bricks.
- The blueprint board shows a single pre-made mesh (`ConstructionBlueprintPreview.modelPrefab`).
- Missing bricks or slots do not break loading: bricks from removed slots return to their start position,
  unknown bricks are dropped.
- Saves are JSON (EasySave3), their sections Base64-encoded JSON.
