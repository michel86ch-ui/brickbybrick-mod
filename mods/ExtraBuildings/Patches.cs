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

    /// <summary>
    /// Installers whose sites the mod removed (mod map without the original buildings) are skipped: the game's
    /// ConstructionStateNetworkSynchronizer requires 1..32 sites. Their cleanup copes with the parts never created.
    /// Otherwise logging only.
    /// </summary>
    [HarmonyPatch(typeof(ConstructionSceneInstaller), nameof(ConstructionSceneInstaller.OnSceneEnterAsync))]
    internal static class ConstructionSceneInstallerEnterPatch
    {
        private static readonly System.Reflection.FieldInfo Sites = AccessTools.Field(typeof(ConstructionSceneInstaller), "sites");

        private static bool Prefix(ConstructionSceneInstaller __instance, ref System.Threading.Tasks.Task __result)
        {
            if (Plugin.ModMapSession && Sites.GetValue(__instance) is ConstructionSite[] s && s.Length == 0)
            {
                Plugin.Log.LogInfo($"Skipping empty construction installer on '{__instance.name}'.");
                __result = System.Threading.Tasks.Task.CompletedTask;
                return false;
            }
            Plugin.Log.LogDebug("ConstructionSceneInstaller.OnSceneEnterAsync starts.");
            return true;
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
