using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using HarmonyLib;
using Unity.Netcode;
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
        public const string Version = "1.2.0";
        private const string SteamAppId = "5228920";

        internal static ManualLogSource Log;
        internal static string PluginDir;
        /// <summary>Mode of this game session, fixed at startup (the gameplay scene is only loaded once).</summary>
        internal static bool ModMapSession;
        internal static ConfigEntry<bool> ModMapActive;
        internal static ConfigEntry<bool> RemoveVanilla;
        internal static ConfigEntry<bool> Showcase;
        internal static ConfigEntry<int> StartSkillPoints;
        internal static ConfigEntry<bool> UnlockScaffoldLift;
        private static Plugin instance;
        private static bool restarting;
        internal static ConfigEntry<string> TargetSlot;
        internal static ConfigEntry<string> BlueprintFile;
        internal static ConfigEntry<float> OriginX;
        internal static ConfigEntry<float> OriginZ;
        internal static ConfigEntry<float> Yaw;
        internal static ConfigEntry<KeyboardShortcut> MoveKey;
        internal static ConfigEntry<string> ModWorlds;
        internal static ConfigEntry<string> TajPlatform;

        /// <summary>The buildings the main menu offers: each in its own world, at its own place in the town.</summary>
        private static readonly (string Name, string World, string Blueprint, float X, float Z, float Rotation)[] Presets =
        {
            ("Notre-Dame", "singleplayer-4", "notredame.json", 3.5f, 0.4f, 180f),
            ("Taj Mahal", "singleplayer-3", "tajmahal.json", 1.5f, 2.0f, 180f),
        };

        private static string toast;
        private static float toastUntil;

        private void Awake()
        {
            Log = Logger;
            instance = this;
            PluginDir = Path.GetDirectoryName(Info.Location);
            RemoveVanilla = Config.Bind("General", "RemoveVanillaBuildings", true,
                "Mod map only: remove the seven original buildings and their bricks, so the town is free for the extra buildings.");
            Showcase = Config.Bind("General", "Showcase", false,
                "Mod map only: show the blueprint as a finished building (walkable, with plinth and ramps, without scaffold) instead of " +
                "construction sites, to check a design. The mod world keeps no building progress while this is on.");
            ModMapActive = Config.Bind("General", "ModMapEnabled", false,
                "true = the game starts as mod map: extra buildings are injected and every world choice opens the mod world. " +
                "false = mod inactive, the mod world is locked. Takes effect at the next game start.");
            StartSkillPoints = Config.Bind("General", "StartSkillPoints", 20,
                "Mod map only: skill points a new mod world starts with (0 = none, like the base game). Granted once, while " +
                "the world has no progress yet; existing worlds keep what they have.");
            UnlockScaffoldLift = Config.Bind("General", "UnlockScaffoldLift", true,
                "Mod map only: unlock the mobile scaffold in the mod world (with the 10 skill points of a finished building). " +
                "The game unlocks it only when the town's house is finished, and the mod map has no house.");
            TargetSlot = Config.Bind("General", "World", "singleplayer-4",
                "World slot of the mod map (singleplayer-1 to singleplayer-4). Other worlds stay unchanged. The main menu " +
                "buttons set it (Notre-Dame: singleplayer-4, Taj Mahal: singleplayer-3).");
            ModWorlds = Config.Bind("General", "ModWorlds", "singleplayer-4",
                "Worlds opened as mod map so far (kept by the mod). They are locked in normal sessions, because without the " +
                "mod the game would drop their extra buildings' bricks.");
            ModMapSession = ModMapActive.Value;
            BlueprintFile = Config.Bind("General", "Blueprint", "garage.json", "Blueprint file in the plugin folder.");
            OriginX = Config.Bind("Site", "X", 0f, "World X coordinate of the footprint center (0 = town center).");
            OriginZ = Config.Bind("Site", "Z", 0f, "World Z coordinate of the footprint center (0 = town center).");
            Yaw = Config.Bind("Site", "Rotation", 0f, "Rotation in degrees.");
            MoveKey = Config.Bind("Site", "MoveKey", KeyboardShortcut.Empty,
                "For designing only: moves the site 4 m in front of you, door facing you. Takes effect at the next game start. " +
                "Never in a world with bricks placed: they stay where they are. Unbound by default.");
            TajPlatform = Config.Bind("Taj Mahal", "Platform", "Terracotta", new ConfigDescription(
                "Colour of the platform's 4x2x2 blocks. Terracotta: the light placement holograms of the first bricks stand out. " +
                "Grey: the original look. Only the colour changes, worlds stay valid. Takes effect when the world is loaded.",
                new AcceptableValueList<string>("Terracotta", "Grey")));
            new Harmony(Guid).PatchAll(typeof(Plugin).Assembly);
            Log.LogInfo(ModMapSession
                ? $"ExtraBuildings {Version}: MOD-MAP session, world '{TargetSlot.Value}', blueprint '{BlueprintFile.Value}'."
                : $"ExtraBuildings {Version}: normal session, mod inactive, world '{TargetSlot.Value}' locked.");
        }

        private void Update()
        {
            ModWorldProgression.Tick();
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

        internal static bool IsModWorld(string slot) =>
            ModWorlds.Value.Split(new[] { ',', ';', ' ' }, StringSplitOptions.RemoveEmptyEntries).Contains(slot, StringComparer.Ordinal);

        internal static void RememberModWorld(string slot)
        {
            if (!IsModWorld(slot))
            {
                ModWorlds.Value = string.IsNullOrWhiteSpace(ModWorlds.Value) ? slot : ModWorlds.Value + "," + slot;
                instance.Config.Save();
                Log.LogInfo($"'{slot}' is now a mod-map world (locked in normal sessions).");
            }
        }

        /// <summary>Does the game have a save in this world slot? (SteamCloud\steam id\host-world_slot.es3, measured)</summary>
        internal static bool SaveExists(string slot)
        {
            try
            {
                string root = Path.Combine(Application.persistentDataPath, "SteamCloud");
                return Directory.Exists(root) && Directory.GetFiles(root, "host-world_" + slot + ".es3", SearchOption.AllDirectories).Length > 0;
            }
            catch (Exception e)
            {
                Log.LogWarning("Could not look for saves: " + e.Message);
                return false;
            }
        }

        private static string ActiveName =>
            Presets.FirstOrDefault(p => string.Equals(p.Blueprint, BlueprintFile.Value, StringComparison.OrdinalIgnoreCase)).Name
            ?? Path.GetFileNameWithoutExtension(BlueprintFile.Value);

        /// <summary>Main menu = no network session running (the town scene is loaded behind the menu).</summary>
        private static bool InMainMenu()
        {
            NetworkManager nm = NetworkManager.Singleton;
            return nm != null && !nm.IsListening && !nm.ShutdownInProgress;
        }

        /// <summary>Switch the mode (and the building) and restart the game through Steam (the town scene is only loaded
        /// once per game start).</summary>
        private static void RestartInto(bool modMap, int preset = -1)
        {
            if (restarting)
            {
                return;
            }
            restarting = true;
            ModMapActive.Value = modMap;
            if (preset >= 0)
            {
                var p = Presets[preset];
                TargetSlot.Value = p.World;
                BlueprintFile.Value = p.Blueprint;
                OriginX.Value = p.X;
                OriginZ.Value = p.Z;
                Yaw.Value = p.Rotation;
            }
            instance.Config.Save();
            int pid = Process.GetCurrentProcess().Id;
            string ps = $"Wait-Process -Id {pid} -Timeout 90 -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2; Start-Process 'steam://rungameid/{SteamAppId}'";
            try
            {
                Process.Start(new ProcessStartInfo("powershell.exe", $"-NoProfile -WindowStyle Hidden -Command \"{ps}\"")
                {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                });
                Log.LogInfo($"Restarting into {(modMap ? "mod map" : "normal worlds")}.");
                Toast(modMap ? $"Restarting as mod map: {ActiveName}..." : "Restarting with the normal worlds...", 10f);
                Application.Quit();
            }
            catch (Exception e)
            {
                restarting = false;
                Log.LogError("Restart failed: " + e);
                Toast("Restart failed. The mode switches at the next manual game start.", 10f);
            }
        }

        private void OnGUI()
        {
            if (InMainMenu())
            {
                var btn = new GUIStyle(GUI.skin.button) { fontSize = 17, alignment = TextAnchor.MiddleCenter };
                if (ModMapSession)
                {
                    if (GUI.Button(new Rect(12f, 12f, 270f, 38f), "Back to normal worlds", btn))
                    {
                        RestartInto(false);
                    }
                }
                else
                {
                    for (int i = 0; i < Presets.Length; i++)
                    {
                        string world = Presets[i].World.Substring(Presets[i].World.LastIndexOf('-') + 1);
                        if (GUI.Button(new Rect(12f, 12f + i * 44f, 270f, 38f), $"Start {Presets[i].Name} (world {world})", btn))
                        {
                            RestartInto(true, i);
                        }
                    }
                }
            }
            else if (ModMapSession)
            {
                var badge = new GUIStyle(GUI.skin.box) { fontSize = 16, alignment = TextAnchor.MiddleCenter };
                string text = "MOD-MAP · " + ActiveName + (Showcase.Value ? " · SHOWCASE" : "");
                GUI.Box(new Rect(12f, 12f, 12f + text.Length * 9f, 30f), text, badge);
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
