using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using MultiplayerTemplate.Bootstrap;
using MultiplayerTemplate.Construction;
using MultiplayerTemplate.Game.Placement;
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

    /// <summary>
    /// Place through bricks: the game only lets the player aim at a brick slot when no placed brick is hit closer along
    /// the view (client side; the server checks slot, brick type, site area and reach, not the view). Where two roofs
    /// overlap (the crossing) or a base lies under the drum, slots end up under bricks of another section. While
    /// <see cref="Plugin.PlaceThrough"/> is on, every slot counts as visible.
    /// </summary>
    [HarmonyPatch(typeof(NetworkPlayerPlacementController), "IsPlacementHitVisible")]
    internal static class PlacementVisibilityPatch
    {
        private static bool Prefix(float placementDistance, ref bool __result)
        {
            if (!Plugin.ModMapSession || !Plugin.PlaceThrough || !(placementDistance >= 0f) || float.IsInfinity(placementDistance))
            {
                return true;
            }
            __result = true;
            return false;
        }
    }

    /// <summary>Remembers the game's progression service for <see cref="ModWorldProgression"/>.</summary>
    [HarmonyPatch(typeof(ProgressionService), MethodType.Constructor, typeof(ProgressionDefinitionCatalog), typeof(IProgressionAuthority))]
    internal static class ProgressionServicePatch
    {
        private static void Postfix(ProgressionService __instance)
        {
            ModWorldProgression.Service = __instance;
        }
    }

    /// <summary>
    /// Progression of the mod world, through the game's own commands. Only the host may call them; until it runs (main
    /// menu, loading) they are retried once a second.
    /// - Start skill points: a new mod world (its shared progression never changed: revision 0, which is saved with the
    ///   world) gets StartSkillPoints. The grant raises the revision, so it happens once per world.
    /// - Mobile scaffold: the game grants it only for the finished town house (completion reward "construction-building"
    ///   at occurrence "house", measured in the skill tree data), and the mod map has no house. While the scaffold skill
    ///   is still 0 the mod claims that reward, with the house's 10 skill points; the game never grants a claim twice.
    /// </summary>
    internal static class ModWorldProgression
    {
        internal static ProgressionService Service;
        private const string ScaffoldSkill = "skill.mobile-scaffold";
        private static float nextTry;

        internal static void Tick()
        {
            if (!Plugin.ModMapSession || Service == null || Time.unscaledTime < nextTry)
            {
                return;
            }
            int amount = Plugin.StartSkillPoints.Value;
            bool points = amount > 0 && Service.Revision == 0;
            bool lift = Plugin.UnlockScaffoldLift.Value && Service.GetSkillLevel(ScaffoldSkill) == 0;
            if (!points && !lift)
            {
                return;
            }
            nextTry = Time.unscaledTime + 1f;
            var done = new List<string>();
            if (points)
            {
                if (!Applied(Service.GrantCurrencyForDevelopment("skill-point", amount), "start skill points"))
                {
                    return;
                }
                done.Add($"{amount} skill points to start with");
            }
            if (lift && Applied(Service.TryClaimCompletionReward("construction-building", "house"), "mobile scaffold"))
            {
                done.Add("mobile scaffold unlocked");
            }
            if (done.Count > 0)
            {
                Plugin.Log.LogInfo("Mod world: " + string.Join(", ", done) + ".");
                Plugin.Toast("Mod world: " + string.Join(", ", done) + ".");
            }
        }

        private static bool Applied(ProgressionCommandResult result, string what)
        {
            if (result.Succeeded)
            {
                return true;
            }
            if (result.Status != ProgressionCommandStatus.NotAuthoritative)
            {
                Plugin.Log.LogWarning($"Mod world: {what} not granted: {result.Status} {result.Message}");
                Service = null;
            }
            return false;
        }
    }
}
