using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using MultiplayerTemplate.Bootstrap;
using MultiplayerTemplate.Construction;
using MultiplayerTemplate.Game.Scenes;
using MultiplayerTemplate.Player;
using MultiplayerTemplate.Progression;
using UnityEngine;

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

    /// <summary>
    /// The parts of a building share one site area, so every part would show its progress panel at once. Only the part
    /// whose bricks are nearest to the player keeps it; the others release theirs. Placing bricks is not affected
    /// (PlacementSlot.IsPlayerInside checks the area collider itself).
    /// </summary>
    [HarmonyPatch(typeof(ConstructionSite), "ObserveLocalPlayer")]
    internal static class PartFocusPatch
    {
        private static readonly FieldInfo LocalPlayer = AccessTools.Field(typeof(ConstructionSite), "localPlayer");
        private static readonly MethodInfo ClearPresence = AccessTools.Method(typeof(ConstructionSite), "ClearLocalPresence");

        private static bool Prefix(ConstructionSite __instance, Collider other)
        {
            if (other == null || !PartFocus.IsPart(__instance))
            {
                return true;
            }
            NetworkPlayerController player = other.GetComponentInParent<NetworkPlayerController>();
            if (player == null || player.BodyCollider != other || !player.IsOwner || PartFocus.Nearest(other.transform.position) == __instance)
            {
                return true;   // other colliders and the chosen part: the game's own handling
            }
            if (LocalPlayer.GetValue(__instance) != null)
            {
                ClearPresence.Invoke(__instance, null);
            }
            return false;
        }
    }

    internal static class PartFocus
    {
        private static readonly Dictionary<ConstructionSite, Bounds> Parts = new Dictionary<ConstructionSite, Bounds>();
        private static int cachedFrame = -1;
        private static ConstructionSite cached;

        internal static void Clear() => Parts.Clear();

        internal static void Register(ConstructionSite site, Bounds bricks) => Parts[site] = bricks;

        internal static bool IsPart(ConstructionSite site) => Parts.ContainsKey(site);

        /// <summary>Part with the nearest bricks; inside several brick boxes the smaller box wins.</summary>
        internal static ConstructionSite Nearest(Vector3 position)
        {
            if (cachedFrame == Time.frameCount && cached != null)
            {
                return cached;
            }
            ConstructionSite best = null;
            float bestDistance = float.MaxValue, bestVolume = float.MaxValue;
            foreach (KeyValuePair<ConstructionSite, Bounds> part in Parts)
            {
                if (part.Key == null)
                {
                    continue;
                }
                float distance = part.Value.SqrDistance(position);
                Vector3 size = part.Value.size;
                float volume = size.x * size.y * size.z;
                if (distance < bestDistance - 0.01f || (Mathf.Abs(distance - bestDistance) <= 0.01f && volume < bestVolume))
                {
                    best = part.Key;
                    bestDistance = distance;
                    bestVolume = volume;
                }
            }
            cachedFrame = Time.frameCount;
            cached = best;
            return best;
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

    /// <summary>Remembers the game's progression service for <see cref="StartPoints"/>.</summary>
    [HarmonyPatch(typeof(ProgressionService), MethodType.Constructor, typeof(ProgressionDefinitionCatalog), typeof(IProgressionAuthority))]
    internal static class ProgressionServicePatch
    {
        private static void Postfix(ProgressionService __instance)
        {
            StartPoints.Service = __instance;
        }
    }

    /// <summary>
    /// A new mod world starts with the configured skill points. New = its shared progression was never changed (revision 0:
    /// no brick placed, no point earned or spent; the revision is saved with the world). The grant itself raises the
    /// revision, so it happens once per world. It uses the game's own currency grant, which only the host may call; until
    /// the host runs (main menu, loading) it is retried once a second.
    /// </summary>
    internal static class StartPoints
    {
        internal static ProgressionService Service;
        private static float nextTry;

        internal static void Tick()
        {
            int amount = Plugin.StartSkillPoints.Value;
            if (!Plugin.ModMapSession || amount <= 0 || Service == null || Service.Revision != 0 || Time.unscaledTime < nextTry)
            {
                return;
            }
            nextTry = Time.unscaledTime + 1f;
            ProgressionCommandResult result = Service.GrantCurrencyForDevelopment("skill-point", amount);
            if (result.Succeeded)
            {
                Plugin.Log.LogInfo($"New mod world: {amount} start skill points granted.");
                Plugin.Toast($"New mod world: {amount} skill points to start with.");
            }
            else if (result.Status != ProgressionCommandStatus.NotAuthoritative)
            {
                Plugin.Log.LogWarning($"Start skill points not granted: {result.Status} {result.Message}");
                Service = null;
            }
        }
    }
}
