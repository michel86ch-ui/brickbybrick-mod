using System.IO;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;

namespace ExtraBuildings
{
    /// <summary>
    /// Extra construction sites from a blueprint (JSON). Active only in a mod-map session in its own world slot;
    /// all other worlds stay unchanged.
    /// </summary>
    [BepInPlugin(Guid, "ExtraBuildings", Version)]
    public sealed class Plugin : BaseUnityPlugin
    {
        public const string Guid = "michel.brickbybrick.extrabuildings";
        public const string Version = "0.2.0";

        internal static ManualLogSource Log;
        internal static string PluginDir;
        /// <summary>Mode of this game session, fixed at startup (the gameplay scene is only loaded once).</summary>
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
            ModMapActive = Config.Bind("General", "ModMapEnabled", false,
                "true = the game starts as mod map: extra buildings are injected and every world choice opens the mod world. " +
                "false = mod inactive, the mod world is locked. Takes effect at the next game start.");
            TargetSlot = Config.Bind("General", "World", "singleplayer-4",
                "World slot of the mod map (singleplayer-1 to singleplayer-4). Other worlds stay unchanged.");
            ModMapSession = ModMapActive.Value;
            BlueprintFile = Config.Bind("General", "Blueprint", "garage.json", "Blueprint file in the plugin folder.");
            OriginX = Config.Bind("Site", "X", 12f, "World X coordinate of the footprint center.");
            OriginZ = Config.Bind("Site", "Z", 42f, "World Z coordinate of the footprint center.");
            Yaw = Config.Bind("Site", "Rotation", 90f, "Rotation in degrees. At 90 the door faces west (towards the spawn).");
            MoveKey = Config.Bind("Site", "MoveKey", new KeyboardShortcut(KeyCode.F9),
                "Moves the site 4 m in front of you, door facing you. Takes effect at the next game start.");
            new Harmony(Guid).PatchAll(typeof(Plugin).Assembly);
            Log.LogInfo(ModMapSession
                ? $"ExtraBuildings {Version}: MOD-MAP session, world '{TargetSlot.Value}', blueprint '{BlueprintFile.Value}'."
                : $"ExtraBuildings {Version}: normal session, mod inactive, world '{TargetSlot.Value}' locked.");
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
            Toast($"Site moved: X {OriginX.Value:0.0}, Z {OriginZ.Value:0.0}, rotation {yaw:0}. Takes effect after a game restart.");
            Log.LogInfo($"Site moved by key: X {OriginX.Value}, Z {OriginZ.Value}, rotation {yaw}");
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
