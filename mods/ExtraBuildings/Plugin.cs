using System.IO;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;

namespace ExtraBuildings
{
    /// <summary>
    /// Zusaetzliche Baustellen aus einem Bauplan (JSON). Aktiv nur im konfigurierten Welt-Slot,
    /// alle anderen Welten bleiben unveraendert.
    /// </summary>
    [BepInPlugin(Guid, "ExtraBuildings", Version)]
    public sealed class Plugin : BaseUnityPlugin
    {
        public const string Guid = "michel.brickbybrick.extrabuildings";
        public const string Version = "0.2.0";

        internal static ManualLogSource Log;
        internal static string PluginDir;
        /// <summary>Modus dieser Spielsitzung, beim Start festgelegt (die Spielszene wird nur einmal geladen).</summary>
        internal static bool ModMapSession;
        internal static ConfigEntry<bool> ModMapActive;
        internal static ConfigEntry<string> TargetSlot;
        internal static ConfigEntry<string> BlueprintFile;
        internal static ConfigEntry<float> OriginX;
        internal static ConfigEntry<float> OriginZ;
        internal static ConfigEntry<float> Yaw;
        internal static ConfigEntry<KeyboardShortcut> MoveKey;

        private static string toast;
        private static float toastUntil;

        private void Awake()
        {
            Log = Logger;
            PluginDir = Path.GetDirectoryName(Info.Location);
            ModMapActive = Config.Bind("Allgemein", "Mod-Map aktiv", false,
                "true = Spiel startet als Mod-Map: Zusatzbau wird eingehaengt, jede Weltwahl oeffnet die Mod-Welt. " +
                "false = Mod inaktiv, die Mod-Welt ist gesperrt. Wirkt beim naechsten Spielstart.");
            TargetSlot = Config.Bind("Allgemein", "Welt", "singleplayer-4",
                "Welt-Slot der Mod-Map (singleplayer-1 bis singleplayer-4). Andere Welten bleiben unveraendert.");
            ModMapSession = ModMapActive.Value;
            BlueprintFile = Config.Bind("Allgemein", "Bauplan", "garage.json", "Bauplan-Datei im Plugin-Ordner.");
            OriginX = Config.Bind("Bauplatz", "X", 12f, "Weltkoordinate X der Grundriss-Mitte.");
            OriginZ = Config.Bind("Bauplatz", "Z", 42f, "Weltkoordinate Z der Grundriss-Mitte.");
            Yaw = Config.Bind("Bauplatz", "Drehung", 90f, "Drehung in Grad. Bei 90 zeigt das Tor nach Westen (Richtung Spawn).");
            MoveKey = Config.Bind("Bauplatz", "Taste", new KeyboardShortcut(KeyCode.F9),
                "Setzt den Bauplatz 4 m vor dich, Tor zu dir gedreht. Wirkt nach dem naechsten Spielstart.");
            new Harmony(Guid).PatchAll(typeof(Plugin).Assembly);
            Log.LogInfo(ModMapSession
                ? $"ExtraBuildings {Version}: MOD-MAP-Sitzung, Welt '{TargetSlot.Value}', Bauplan '{BlueprintFile.Value}'."
                : $"ExtraBuildings {Version}: normale Sitzung, Mod inaktiv, Welt '{TargetSlot.Value}' gesperrt.");
        }

        private void Update()
        {
            if (!MoveKey.Value.IsDown())
            {
                return;
            }
            Camera cam = Camera.main;
            if (cam == null)
            {
                return;
            }
            Vector3 forward = cam.transform.forward;
            forward.y = 0f;
            if (forward.sqrMagnitude < 0.01f)
            {
                return;
            }
            forward.Normalize();
            float yaw = Mathf.Repeat(Mathf.Round(Mathf.Atan2(forward.x, forward.z) * Mathf.Rad2Deg / 90f) * 90f, 360f);
            Vector3 center = cam.transform.position + forward * 4f;
            OriginX.Value = Mathf.Round(center.x * 100f) / 100f;
            OriginZ.Value = Mathf.Round(center.z * 100f) / 100f;
            Yaw.Value = yaw;
            Config.Save();
            Toast($"Bauplatz gesetzt: X {OriginX.Value:0.0}, Z {OriginZ.Value:0.0}, Drehung {yaw:0}. Wirkt nach Spielneustart.");
            Log.LogInfo($"Bauplatz per Taste gesetzt: X {OriginX.Value}, Z {OriginZ.Value}, Drehung {yaw}");
        }

        internal static void Toast(string text, float seconds = 6f)
        {
            toast = text;
            toastUntil = Time.unscaledTime + seconds;
        }

        private void OnGUI()
        {
            if (ModMapSession)
            {
                var badge = new GUIStyle(GUI.skin.box) { fontSize = 16, alignment = TextAnchor.MiddleCenter };
                GUI.Box(new Rect(12f, 12f, 150f, 30f), "MOD-MAP", badge);
            }
            if (toast == null || Time.unscaledTime > toastUntil)
            {
                return;
            }
            var style = new GUIStyle(GUI.skin.box) { fontSize = 22, alignment = TextAnchor.MiddleCenter, wordWrap = true };
            GUI.Box(new Rect(Screen.width / 2f - 420f, 60f, 840f, 70f), toast, style);
        }
    }
}
