using System;
using HarmonyLib;
using MultiplayerTemplate.Bootstrap;
using MultiplayerTemplate.Construction;
using MultiplayerTemplate.Game.Scenes;

namespace ExtraBuildings
{
    /// <summary>
    /// Guards the world choice. The gameplay scene is loaded only once per game start, so the mode applies to the whole session:
    /// mod-map session -> every choice opens the mod world. Normal session -> the mod world is locked, because without the mod
    /// the game would drop the extra buildings' bricks from the save when loading it.
    /// </summary>
    [HarmonyPatch(typeof(AppBootstrap), nameof(AppBootstrap.ConfigureHostSaveSlot))]
    internal static class SlotGuardPatch
    {
        private static void Prefix(ref string slotId)
        {
            string target = Plugin.TargetSlot.Value;
            bool isTarget = string.Equals(slotId, target, StringComparison.Ordinal);
            if (Plugin.ModMapSession)
            {
                if (!isTarget)
                {
                    Plugin.Log.LogInfo($"Mod-map session: world choice '{slotId}' becomes '{target}'.");
                    slotId = target;
                }
                return;
            }
            if (isTarget)
            {
                Plugin.Toast($"'{target}' is the mod map. Please start the game as mod map.", 10f);
                Plugin.Log.LogWarning($"Normal session: '{target}' is the mod map and locked here.");
                throw new InvalidOperationException($"'{target}' is the mod map and can only be loaded in a mod-map session.");
            }
        }
    }

    /// <summary>Before the scene starts: inject slots, catalog and site (GameSceneInstaller runs before ConstructionSceneInstaller).</summary>
    [HarmonyPatch(typeof(GameSceneInstaller), nameof(GameSceneInstaller.OnSceneEnterAsync))]
    internal static class GameSceneInstallerEnterPatch
    {
        private static void Prefix(GameSceneInstaller __instance)
        {
            Injector.TryInject(__instance);
        }
    }

    /// <summary>Logging only: order and errors of the game's site initialization.</summary>
    [HarmonyPatch(typeof(ConstructionSceneInstaller), nameof(ConstructionSceneInstaller.OnSceneEnterAsync))]
    internal static class ConstructionSceneInstallerEnterPatch
    {
        private static void Prefix()
        {
            Plugin.Log.LogDebug("ConstructionSceneInstaller.OnSceneEnterAsync starts.");
        }

        private static Exception Finalizer(Exception __exception)
        {
            if (__exception != null)
            {
                Plugin.Log.LogError("The game's site initialization failed: " + __exception);
            }
            else
            {
                Plugin.Log.LogDebug("ConstructionSceneInstaller.OnSceneEnterAsync done.");
            }
            return __exception;
        }
    }
}
