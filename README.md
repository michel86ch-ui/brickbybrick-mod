# Brick by Brick – Zusatzgebäude (Mod)

Mod für *Brick by Brick: Tidy Up the Small Town!* (Steam). Sie baut zusätzliche Gebäude aus einem Bauplan ins Spiel –
mit echten Steinplätzen, Hologrammen, Bauabschnitten, Bauplan-Tafel, Abschlussmeldung und Baurückblick, genau wie bei
den Original-Gebäuden. Erstes Gebäude ist eine **Test-Garage mit 191 Steinen**. Ziel ist eine vereinfachte
**Notre-Dame mit rund 25'000 Steinen**.

> Inoffizielle Fan-Mod, nicht von den Entwicklern des Spiels. Das Repository enthält keine Spieldateien.

![Garage im Bau neben der Bäckerei](docs/modmapBrickByBrick.png)

![Bauarbeiten abgeschlossen: Garage mit Baurückblick](docs/modmapBrickByBrick2.png)

## Stand (2026-10-21)

| Funktion | Stand |
|---|---|
| Steinplätze, Hologramme, Einrasten | im Spiel bestätigt |
| Fortschritt pro Abschnitt, Bauplan-Tafel rechnet mit | im Spiel bestätigt |
| Abschnitte fertig (Endnetze), Meldung „Bauarbeiten abgeschlossen“, Baurückblick | im Spiel bestätigt |
| Sockel aus Spielsteinen, eigenes 3D-Modell auf der Bauplan-Tafel (0.2.0) | gebaut, noch nicht im Spiel geprüft |
| Speichern und Neuladen der Mod-Welt | noch nicht geprüft |
| Menüknopf „Mod-Map“ mit Neustart | geplant |
| Notre-Dame | geplant |

## Mod-Map: eigene Welt statt Hauptwelt

Ein zusätzliches Gebäude verändert die Gebäudeliste eines Spielstands; das Spiel wertet den Lauf dieser Welt dann nicht
mehr für die Rangliste. Deshalb baut die Mod nur in einer eigenen Welt, der **Mod-Map** (Standard: Welt-Slot 4).

Das Spiel lädt die Stadt-Szene einmal pro Spielstart und öffnet die Welten darin. Der Modus gilt deshalb für die ganze
Spielsitzung:

| Modus | Verhalten |
|---|---|
| normal (Standard) | Mod tut nichts. Die Mod-Welt ist gesperrt, weil das Spiel ohne Mod beim Laden die Steine der Zusatzgebäude verwerfen würde. |
| Mod-Map | Zusatzgebäude werden eingehängt, jede Weltwahl im Menü öffnet die Mod-Welt, oben links steht „MOD-MAP“. |

## Installation

1. [BepInEx 5.4.23.5 x64](https://github.com/BepInEx/BepInEx/releases/tag/v5.4.23.5) ins Spielverzeichnis entpacken.
2. Mod bauen (siehe unten) – `ExtraBuildings.dll` und `blueprints\garage.json` landen in `BepInEx\plugins\ExtraBuildings\`.
3. Spiel einmal starten, beenden. In `BepInEx\config\michel.brickbybrick.extrabuildings.cfg` setzen: `Mod-Map aktiv = true`.
4. Spiel starten, beliebige Welt wählen -> Mod-Welt. Die Garage steht auf der Wiese östlich vom Spawn.

Entfernen: `winhttp.dll`, `doorstop_config.ini`, `.doorstop_version`, `changelog.txt` und den Ordner `BepInEx` im
Spielordner löschen. Das Spiel selbst wird nicht verändert.

## Bauen

```
cd mods\ExtraBuildings
dotnet build -c Release -p:DeployToGame=true     (kopiert DLL + blueprints\*.json ins Spiel)
py tools\gen_garage.py                            (Bauplan neu erzeugen)
```

Das Projekt referenziert die DLLs direkt aus dem Spielordner (`GameDir` in der `.csproj` anpassen, falls das Spiel
woanders liegt).

| Ordner | Inhalt |
|---|---|
| [mods/ExtraBuildings](mods/ExtraBuildings/) | Die Mod (C#, BepInEx 5 / HarmonyX) |
| [tools](tools/) | Bauplan-Generatoren (Python) |
| [blueprints](blueprints/) | Erzeugte Baupläne (JSON) |
| [docs](docs/) | Screenshots |

## Wie das Spiel Gebäude aufbaut

Gemessen im Spielcode (Unity 6000.3.6, Mono) und in den Szenendaten:

- Gebäude stehen **nicht im Code**, sondern in der Szene: 7 `ConstructionSite` mit zusammen 18'485 Steinplätzen.
- Lose Steine: ein `BrickWorldCatalog` mit genau 18'485 Steinen, GPU-instanziert über `BrickWorldSource`.
- Szenenstart (`GameSceneInstaller.OnSceneEnterAsync`): Steinplätze anmelden -> Steinkatalog registrieren ->
  Spielstand anwenden. Danach initialisiert je Gebäude ein `ConstructionSceneInstaller` seine Baustelle.
- Ein Steinplatz ist ein GameObject mit `PlacementSlot` + `ConstructionSlot` und Kind `Hologram`. Slot-ID und Stein-ID
  sind `uint`. Drehpunkt eines Steins = Mitte, Raster 0.21 m.
- `PlacementSlot.placeTrigger` ist der Baustellenbereich des Gebäudes: Setzen geht nur, wenn man darin steht.
- Jede Baustelle hat eine gebackene Topologie (`bakedSpecs`), die `GetBakedSpecs()` streng gegen die Slots prüft.
- Ist ein Abschnitt fertig, zeigt das Spiel ein zusammengefasstes Netz (`finalVisualRoot`) statt der Einzelsteine.
- Die Bauplan-Tafel zeigt ein einzelnes vorgefertigtes Netz (`ConstructionBlueprintPreview.modelPrefab`).
- Fehlende Steine oder Steinplätze brechen das Laden nicht ab: Steine aus entfernten Plätzen gehen an ihren
  Startplatz, unbekannte Steine werden verworfen.
- Spielstände sind JSON (EasySave3), die Abschnitte darin Base64-JSON.
