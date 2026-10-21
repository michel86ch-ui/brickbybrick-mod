# ExtraBuildings 0.2.0

Zusätzliche Baustellen aus einem Bauplan (JSON). Aktiv nur in einer **Mod-Map-Sitzung**
(`Mod-Map aktiv = true`); dann öffnet jede Weltwahl die Mod-Welt (Standard `singleplayer-4`).
In einer normalen Sitzung tut die Mod nichts und sperrt die Mod-Welt.

## Ablauf

1. Prefix auf `GameSceneInstaller.OnSceneEnterAsync` (vor dem Anmelden der Steinplätze), nur in einer Mod-Map-Sitzung.
2. Klon der Vorlage `house` in einem inaktiven Halter: ohne `ConstructionSceneInstaller` (sitzt auf der House-Wurzel),
   ohne `CompletionObjects`, `Supply`, `House`. Behalten: Bauplan-Tafel, Fortschrittsanzeige, Zeitraffer, Effekt.
3. Abschnitte aus dem Bauplan, je ein eigenes Endnetz (zusammengefasst aus den Katalog-Optiken).
4. Steinplätze = Klone eines Original-Slots derselben Steindefinition, Slot-ID 900000001+,
   `placeTrigger` = Baustellenbereich der neuen Baustelle.
5. Sockel aus Spielsteinen (nur Optik, ein Netz) + begehbare Kollider; 3D-Modell für die Bauplan-Tafel.
6. Topologie backen, `ValidateAuthoredReferences` + `GetBakedSpecs` des Spiels prüfen.
7. Neuer Steinkatalog = Original + Material des Bauplans (Stein-IDs 900000001+), Vorrat neben dem Bauplatz.
8. Erst dann: Katalog tauschen, Slots und Baustelle an die Listen des Spiels hängen. Bei einem Fehler lädt die Welt ohne.
9. `AppBootstrap.ConfigureHostSaveSlot`: Mod-Map-Sitzung -> jede Wahl wird zur Mod-Welt; normale Sitzung -> Mod-Welt gesperrt.

## Einstellungen (`BepInEx\config\michel.brickbybrick.extrabuildings.cfg`)

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| Allgemein / Mod-Map aktiv | false | true = Spielstart als Mod-Map (wirkt beim nächsten Start) |
| Allgemein / Welt | singleplayer-4 | Welt-Slot der Mod-Map |
| Allgemein / Bauplan | garage.json | Datei im Plugin-Ordner |
| Bauplatz / X, Z | 12, 42 | Grundriss-Mitte (Freifläche östlich vom Spawn) |
| Bauplatz / Drehung | 90 | Tor nach Westen |
| Bauplatz / Taste | F9 | Bauplatz 4 m vor dich setzen, Tor zu dir; wirkt nach dem nächsten Spielstart |

## Bauplan-Format (`blueprints\*.json`, erzeugt von `tools\gen_*.py`)

`siteId`, `displayName`, `templateSite`, `sections[]`, `blueprintStand [x, z, Grad]`,
`pile {x, z, gap, perRow, stack}`, `colliders[] {c, s}`, `decor[] {def, p, yaw}` (nur Optik),
`bricks[]` mit `def` (Asset-Name der Steindefinition), `p` (Steinmitte in m, lokal, y über Boden), `yaw`,
`s` (Abschnitt), `mode` (0 = alle Vorbedingungen, 1 = eine genügt), `req` (Indizes).

## Garage (garage.json)

8 x 12 Zellen à 0.42 m (3.36 x 5.04 m) auf einem 0.42 m hohen Sockel, 6 Wandschichten (2.52 m) + Flachdach,
Tor 2.52 x 2.10 m. 191 Steine: 91 x `Bakery_Brick_2D1CAFD3` (4x2x2 Block), 100 x `Factory_Brick_7CB4833B`
(2x2x2 Block). Abschnitte: Wände unten 46, Wände oben 49, Dach 96. Sockel: 226 Deko-Steine.

## Geprüft im Spiel (0.1.0, ohne Sockel)

Steinplätze, Hologramme, Einrasten, Fortschritt pro Abschnitt, Bauplan-Tafel rechnet mit, fertige Abschnitte bleiben
sichtbar, „Bauarbeiten abgeschlossen“, Baurückblick.

## Offen

- 0.2.0 im Spiel: Sockel, Tafelmodell, Tafel aufrecht.
- Speichern und Neuladen der Mod-Welt.
- Gibt die fertige Garage Fähigkeitspunkte (`construction-building` + Gebäude-ID)?
- Menüknopf „Mod-Map“ mit automatischem Neustart.
