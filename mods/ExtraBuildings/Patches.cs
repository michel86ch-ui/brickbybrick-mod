using System;
using HarmonyLib;
using MultiplayerTemplate.Bootstrap;
using MultiplayerTemplate.Construction;
using MultiplayerTemplate.Game.Scenes;

namespace ExtraBuildings
{
    /// <summary>
    /// Weltwahl absichern. Die Spielszene wird nur einmal pro Spielstart geladen, deshalb gilt der Modus fuer die ganze Sitzung:
    /// Mod-Map-Sitzung -> jede Wahl oeffnet die Mod-Welt. Normale Sitzung -> die Mod-Welt ist gesperrt, weil das Spiel
    /// ohne die Mod beim Laden die Steine der Zusatzbauten aus dem Spielstand verwerfen wuerde.
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
                    Plugin.Log.LogInfo($"Mod-Map-Sitzung: Weltwahl '{slotId}' wird zu '{target}'.");
                    slotId = target;
                }
                return;
            }
            if (isTarget)
            {
                Plugin.Toast($"'{target}' ist die Mod-Map. Bitte als Mod-Map starten.", 10f);
                Plugin.Log.LogWarning($"Normale Sitzung: '{target}' ist die Mod-Map und hier gesperrt.");
                throw new InvalidOperationException($"'{target}' ist die Mod-Map und nur in einer Mod-Map-Sitzung ladbar.");
            }
        }
    }

    /// <summary>Vor dem Szenenstart: Steinplaetze, Katalog und Baustelle einhaengen (GameSceneInstaller laeuft vor ConstructionSceneInstaller).</summary>
    [HarmonyPatch(typeof(GameSceneInstaller), nameof(GameSceneInstaller.OnSceneEnterAsync))]
    internal static class GameSceneInstallerEnterPatch
    {
        private static void Prefix(GameSceneInstaller __instance)
        {
            Injector.TryInject(__instance);
        }
    }

    /// <summary>Nur Protokoll: Reihenfolge und Fehler bei der Initialisierung der Baustellen.</summary>
    [HarmonyPatch(typeof(ConstructionSceneInstaller), nameof(ConstructionSceneInstaller.OnSceneEnterAsync))]
    internal static class ConstructionSceneInstallerEnterPatch
    {
        private static void Prefix()
        {
            Plugin.Log.LogDebug("ConstructionSceneInstaller.OnSceneEnterAsync beginnt.");
        }

        private static Exception Finalizer(Exception __exception)
        {
            if (__exception != null)
            {
                Plugin.Log.LogError("Baustellen-Initialisierung des Spiels fehlgeschlagen: " + __exception);
            }
            else
            {
                Plugin.Log.LogDebug("ConstructionSceneInstaller.OnSceneEnterAsync fertig.");
            }
            return __exception;
        }
    }
}
