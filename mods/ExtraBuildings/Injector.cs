using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using MultiplayerTemplate.BrickWorld;
using MultiplayerTemplate.Construction;
using MultiplayerTemplate.Core.Application;
using MultiplayerTemplate.Core.Items;
using MultiplayerTemplate.Core.Settings;
using MultiplayerTemplate.Game.Items;
using MultiplayerTemplate.Game.Placement;
using MultiplayerTemplate.Game.Scenes;
using Sisus.Init;
using UnityEngine;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace ExtraBuildings
{
    /// <summary>
    /// Builds an extra construction site before the scene starts (GameSceneInstaller.OnSceneEnterAsync):
    /// a clone of the template site without its content, own sections and slots from the blueprint,
    /// own final meshes per section, and an extended brick catalog with the material. The game's lists are only
    /// extended once everything is built and has passed the game's own validation.
    /// </summary>
    internal static class Injector
    {
        /// <summary>Slot and brick IDs of the mod: 900000001 upwards (game: bricks 1..18547, slots ~100000..120000).</summary>
        internal const uint IdBase = 900_000_000u;

        private static readonly FieldInfo GsiSlots = AccessTools.Field(typeof(GameSceneInstaller), "authoredPlacementSlots");
        private static readonly FieldInfo GsiSources = AccessTools.Field(typeof(GameSceneInstaller), "logicalItemSources");
        private static readonly FieldInfo CsiSites = AccessTools.Field(typeof(ConstructionSceneInstaller), "sites");
        private static readonly FieldInfo BwsCatalog = AccessTools.Field(typeof(BrickWorldSource), "catalog");
        private static readonly FieldInfo CatBricks = AccessTools.Field(typeof(BrickWorldCatalog), "bricks");
        private static readonly FieldInfo CatVisuals = AccessTools.Field(typeof(BrickWorldCatalog), "visuals");
        private static readonly MethodInfo SiteGetBakedSpecs = AccessTools.Method(typeof(ConstructionSite), "GetBakedSpecs");

        private static FieldInfo Site(string name) => AccessTools.Field(typeof(ConstructionSite), name);
        private static FieldInfo Section(string name) => AccessTools.Field(typeof(ConstructionSection), name);
        private static FieldInfo Slot(string name) => AccessTools.Field(typeof(ConstructionSlot), name);
        private static FieldInfo Placement(string name) => AccessTools.Field(typeof(PlacementSlot), name);

        internal static void TryInject(GameSceneInstaller gsi)
        {
            GameObject holder = null;
            try
            {
                if (!Plugin.ModMapSession)
                {
                    Plugin.Log.LogInfo("Normal session: no extra buildings.");
                    return;
                }
                Scene scene = gsi.gameObject.scene;
                // Every building has its own ConstructionSceneInstaller (on the site root)
                ConstructionSceneInstaller[] installers = Object.FindObjectsByType<ConstructionSceneInstaller>(FindObjectsInactive.Include, FindObjectsSortMode.None)
                    .Where(c => c.gameObject.scene == scene).ToArray();
                if (installers.Length == 0)
                {
                    Plugin.Log.LogInfo("Scene has no construction sites, nothing to do.");
                    return;
                }
                string bpPath = Path.Combine(Plugin.PluginDir, Plugin.BlueprintFile.Value);
                Blueprint bp = Blueprint.Load(bpPath);
                ConstructionSite[] allSites = installers.SelectMany(c => (ConstructionSite[])CsiSites.GetValue(c)).Where(s => s != null).ToArray();
                if (allSites.Any(s => bp.Parts.Any(p => p.siteId == s.SiteId)))
                {
                    Plugin.Log.LogInfo($"Site '{bp.siteId}' is already injected.");
                    return;
                }
                if (allSites.Any(s => s.State != null))
                {
                    Plugin.Log.LogWarning("Sites are already initialized (unexpected order), extra building skipped.");
                    return;
                }
                BrickWorldSource bws = ((SceneItemSource[])GsiSources.GetValue(gsi)).OfType<BrickWorldSource>().FirstOrDefault();
                if (bws == null)
                {
                    throw new InvalidOperationException("BrickWorldSource not found.");
                }
                var catalog = (BrickWorldCatalog)BwsCatalog.GetValue(bws);
                BrickRecord[] origBricks = catalog.Bricks;
                BrickVisual[] visuals = catalog.Visuals;

                // Templates per brick definition: a catalog record (visual, collider, physics) and a slot (hologram)
                var recByDef = new Dictionary<string, BrickRecord>(StringComparer.Ordinal);
                foreach (BrickRecord r in origBricks)
                {
                    if (r.definition != null && !recByDef.ContainsKey(r.definition.name))
                    {
                        recByDef.Add(r.definition.name, r);
                    }
                }
                var slotByDef = new Dictionary<string, ConstructionSlot>(StringComparer.Ordinal);
                foreach (ConstructionSite s in allSites)
                {
                    foreach (ConstructionSection sec in s.Sections)
                    {
                        foreach (ConstructionSlot cs in sec.Slots)
                        {
                            if (cs != null && cs.ExpectedDefinition != null && !slotByDef.ContainsKey(cs.ExpectedDefinition.name))
                            {
                                slotByDef.Add(cs.ExpectedDefinition.name, cs);
                            }
                        }
                    }
                }
                foreach (string def in bp.bricks.Select(b => b.def).Distinct())
                {
                    if (!recByDef.ContainsKey(def) || !slotByDef.ContainsKey(def))
                    {
                        throw new InvalidDataException($"Brick definition '{def}' does not exist in this game version.");
                    }
                }
                foreach (string def in (bp.decor ?? new DecorSpec[0]).Select(d => d.def).Distinct())
                {
                    if (!recByDef.ContainsKey(def))
                    {
                        throw new InvalidDataException($"Decor brick '{def}' does not exist in this game version.");
                    }
                }
                ConstructionSite template = allSites.FirstOrDefault(s => s.SiteId == bp.templateSite)
                    ?? throw new InvalidDataException($"Template site '{bp.templateSite}' is missing.");
                // The new site goes into the template's installer (initialization, completion, sync, rewards run there)
                ConstructionSceneInstaller csi = installers.First(c => ((ConstructionSite[])CsiSites.GetValue(c)).Contains(template));
                var sites = (ConstructionSite[])CsiSites.GetValue(csi);
                ClearArea(bp, scene);
                if (Plugin.Showcase.Value)
                {
                    BuildShowcase(bp, gsi, scene, allSites, installers, template, bws, catalog, origBricks, visuals, recByDef);
                    return;
                }

                // ---- One clone of the template per part, hidden in an inactive holder (no Awake) ----
                PartSpec[] parts = bp.Parts;
                int n = bp.bricks.Length;
                var partOfSection = new int[bp.sections.Length];
                for (int p = 0; p < parts.Length; p++)
                {
                    foreach (int s in parts[p].sections)
                    {
                        partOfSection[s] = p;
                    }
                }
                holder = new GameObject("ExtraBuildings_Holder");
                holder.SetActive(false);
                SceneManager.MoveGameObjectToScene(holder, scene);
                var clones = new GameObject[parts.Length];
                for (int p = 0; p < parts.Length; p++)
                {
                    clones[p] = Object.Instantiate(template.gameObject, holder.transform);
                    clones[p].name = parts[p].displayName + "_Construction";
                }

                // Mod map without the original buildings: hide them now (after cloning the template, before measuring the ground)
                bool clean = Plugin.RemoveVanilla.Value;
                if (clean)
                {
                    foreach (ConstructionSite s in allSites)
                    {
                        HideSite(s);
                    }
                }

                Quaternion rot = Quaternion.Euler(0f, Plugin.Yaw.Value, 0f);
                Vector3 origin = new Vector3(Plugin.OriginX.Value, 0f, Plugin.OriginZ.Value);
                origin.y = GroundY(origin.x, origin.z, out string groundName);
                Plugin.Log.LogInfo($"Site {bp.siteId}: ({origin.x:0.00}, {origin.y:0.00}, {origin.z:0.00}), rotation {Plugin.Yaw.Value}, ground '{groundName}'" +
                    (clean ? ", original buildings removed." : "."));

                // Site area of every part: around all bricks and the scaffold (placing needs the player inside it)
                Vector3 min = Vector3.positiveInfinity, max = Vector3.negativeInfinity;
                foreach (BrickSpec b in bp.bricks)
                {
                    var p = new Vector3(b.p[0], b.p[1], b.p[2]);
                    min = Vector3.Min(min, p);
                    max = Vector3.Max(max, p);
                }
                foreach (float[] b in (bp.scaffold ?? new float[0][]).Concat(bp.tempScaffold ?? new float[0][]))
                {
                    min = Vector3.Min(min, new Vector3(b[0] - b[3] / 2f, b[1] - b[4] / 2f, b[2] - b[5] / 2f));
                    max = Vector3.Max(max, new Vector3(b[0] + b[3] / 2f, b[1] + b[4] / 2f, b[2] + b[5] / 2f));
                }
                var built = new ConstructionSite[parts.Length];
                var placementSlots = new PlacementSlot[n];
                GameObject tempScaffold = null;
                for (int p = 0; p < parts.Length; p++)
                {
                    built[p] = BuildPart(bp, parts[p], p, partOfSection, clones[p], origin, rot, slotByDef, recByDef, visuals, min, max,
                        placementSlots, out GameObject temp);
                    if (temp != null)
                    {
                        tempScaffold = temp;
                    }
                }
                CrossSitePrerequisites.Clear();
                for (int i = 0; i < n; i++)
                {
                    int[] xreq = bp.bricks[i].xreq;
                    if (xreq != null && xreq.Length > 0)
                    {
                        CrossSitePrerequisites.Add(new PlacementSlotId(IdBase + 1u + (uint)i),
                            xreq.Select(j => new PlacementSlotId(IdBase + 1u + (uint)j)).ToArray());
                    }
                }
                PartFocus.Clear();
                if (parts.Length > 1)
                {
                    for (int p = 0; p < parts.Length; p++)
                    {
                        var bounds = new Bounds(origin, Vector3.zero);
                        bool first = true;
                        for (int i = 0; i < n; i++)
                        {
                            if (partOfSection[bp.bricks[i].s] != p)
                            {
                                continue;
                            }
                            Vector3 w = origin + rot * new Vector3(bp.bricks[i].p[0], bp.bricks[i].p[1], bp.bricks[i].p[2]);
                            if (first)
                            {
                                bounds = new Bounds(w, Vector3.zero);
                                first = false;
                            }
                            else
                            {
                                bounds.Encapsulate(w);
                            }
                        }
                        PartFocus.Register(built[p], bounds);
                    }
                }

                // ---- Material: extended catalog ----
                BrickRecord[] newRecords = SupplyRecords(bp, recByDef, origin, rot);
                var newCatalog = ScriptableObject.CreateInstance<BrickWorldCatalog>();
                newCatalog.name = catalog.name + "+" + bp.siteId;
                CatBricks.SetValue(newCatalog, clean ? newRecords : origBricks.Concat(newRecords).ToArray());
                CatVisuals.SetValue(newCatalog, visuals);

                // ---- Inject: only now are the game's lists changed ----
                BwsCatalog.SetValue(bws, newCatalog);
                var gsiSlots = (PlacementSlot[])GsiSlots.GetValue(gsi);
                if (clean)
                {
                    // Original slots out of the registry, original sites out of every installer; our site goes into the
                    // template's installer. Installers left empty are skipped (see ConstructionSceneInstallerEnterPatch).
                    var vanillaSlots = new HashSet<PlacementSlot>();
                    foreach (ConstructionSite s in allSites)
                    {
                        foreach (ConstructionSection sec in s.Sections)
                        {
                            foreach (ConstructionSlot cs in sec.Slots)
                            {
                                if (cs != null && cs.PlacementSlot != null)
                                {
                                    vanillaSlots.Add(cs.PlacementSlot);
                                }
                            }
                        }
                    }
                    gsiSlots = gsiSlots.Where(p => !vanillaSlots.Contains(p)).ToArray();
                    foreach (ConstructionSceneInstaller inst in installers)
                    {
                        CsiSites.SetValue(inst, inst == csi ? built : new ConstructionSite[0]);
                    }
                    Plugin.Log.LogInfo($"Original buildings removed: {allSites.Length} sites, {vanillaSlots.Count} slots, {origBricks.Length} bricks.");
                }
                else
                {
                    CsiSites.SetValue(csi, sites.Concat(built).ToArray());
                }
                GsiSlots.SetValue(gsi, gsiSlots.Concat(placementSlots).ToArray());
                foreach (GameObject clone in clones)
                {
                    clone.transform.SetParent(null, true);
                    SceneManager.MoveGameObjectToScene(clone, scene);
                }
                if (tempScaffold != null)
                {
                    TemporaryScaffold.Attach(tempScaffold, built);
                }
                Object.Destroy(holder);
                holder = null;
                Plugin.Log.LogInfo($"Site '{bp.siteId}' injected: {parts.Length} construction site(s), {n} slots in {bp.sections.Length} sections, " +
                    $"{n} bricks in the supply, IDs {IdBase + 1}..{IdBase + (uint)n}.");
            }
            catch (Exception e)
            {
                Plugin.Log.LogError("Extra building aborted, the world loads without it: " + e);
                if (holder != null)
                {
                    Object.Destroy(holder);
                }
            }
        }

        /// <summary>The game's limits per construction site (ConstructionStateNetworkSynchronizer).</summary>
        private const int MaxSlotsPerSite = 8192, MaxSectionsPerSite = 256;

        /// <summary>
        /// Turns one clone of the template into the construction site of a blueprint part: its sections with their own
        /// final meshes, its slots (prerequisites only inside the part), area, blueprint board and baked topology.
        /// The first part also carries the plinth and the scaffold (tempScaffold: the part that goes once the building is
        /// complete, or null).
        /// </summary>
        private static ConstructionSite BuildPart(Blueprint bp, PartSpec part, int partIndex, int[] partOfSection, GameObject clone,
            Vector3 origin, Quaternion rot, Dictionary<string, ConstructionSlot> slotByDef, Dictionary<string, BrickRecord> recByDef,
            BrickVisual[] visuals, Vector3 min, Vector3 max, PlacementSlot[] placementSlots, out GameObject tempScaffold)
        {
            tempScaffold = null;
            int[] mine = Enumerable.Range(0, bp.bricks.Length).Where(i => partOfSection[bp.bricks[i].s] == partIndex).ToArray();
            int nSec = part.sections.Length;
            if (mine.Length > MaxSlotsPerSite || nSec > MaxSectionsPerSite)
            {
                throw new InvalidDataException($"Part '{part.siteId}' has {mine.Length} slots in {nSec} sections; " +
                    $"the game allows {MaxSlotsPerSite} slots and {MaxSectionsPerSite} sections per site.");
            }
            foreach (SceneLifecycleHook hook in clone.GetComponentsInChildren<SceneLifecycleHook>(true))
            {
                Object.DestroyImmediate(hook);   // the ConstructionSceneInstaller sits on the House root
            }
            // Remember the layer of the house foundation (walkable) for the colliders of our own plinth and scaffold
            Transform houseGround = clone.transform.Find("House/Base_Ground");
            int groundLayer = houseGround != null ? houseGround.gameObject.layer : 0;
            foreach (string child in new[] { "CompletionObjects", "Supply", "House" })
            {
                Transform t = clone.transform.Find(child);
                if (t != null)
                {
                    Object.DestroyImmediate(t.gameObject);
                }
            }
            ConstructionSite site = clone.GetComponent<ConstructionSite>();
            Site("completedPrompts").SetValue(site, null);
            Site("completionObject").SetValue(site, null);
            Site("preCompletionObject").SetValue(site, null);
            Site("constructionFrame").SetValue(site, null);
            var oldSections = (ConstructionSection[])Site("sections").GetValue(site);
            ConstructionSection sectionTemplate = oldSections[0];
            for (int i = 1; i < oldSections.Length; i++)
            {
                Object.DestroyImmediate(oldSections[i].gameObject);
            }
            for (int i = sectionTemplate.transform.childCount - 1; i >= 0; i--)
            {
                Object.DestroyImmediate(sectionTemplate.transform.GetChild(i).gameObject);
            }
            clone.transform.SetPositionAndRotation(origin, rot);
            Transform stand = clone.transform.Find("Blueprint");
            float[] standPose = part.blueprintStand ?? bp.blueprintStand;
            if (stand != null && standPose != null && standPose.Length >= 2)
            {
                // Keep the template's height and tilt, only move it and turn it around the vertical axis
                stand.localPosition = new Vector3(standPose[0], stand.localPosition.y, standPose[1]);
                if (standPose.Length >= 3)
                {
                    stand.localRotation = Quaternion.Euler(0f, standPose[2], 0f) * stand.localRotation;
                }
            }

            // ---- Sections with their own final mesh ----
            var localOf = new Dictionary<int, int>();
            var sections = new ConstructionSection[nSec];
            var finalRoots = new GameObject[nSec];
            for (int k = 0; k < nSec; k++)
            {
                string name = bp.sections[part.sections[k]];
                localOf[part.sections[k]] = k;
                GameObject secGo = Object.Instantiate(sectionTemplate.gameObject, sectionTemplate.transform.parent);
                secGo.name = "Section_" + name;
                secGo.transform.SetPositionAndRotation(origin, rot);
                sections[k] = secGo.GetComponent<ConstructionSection>();
                Section("displayName").SetValue(sections[k], name);
                var fr = new GameObject(name + "_FinalStaticMesh");
                fr.transform.SetParent(secGo.transform, false);
                fr.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                fr.SetActive(false);
                finalRoots[k] = fr;
            }
            Object.DestroyImmediate(sectionTemplate.gameObject);

            // Site area: PlacementSlot.IsPlayerInside checks placeTrigger -> it must be the area of THIS site
            if (!(Site("constructionArea").GetValue(site) is Collider siteArea) || !siteArea.isTrigger)
            {
                throw new InvalidOperationException("The template's site area is missing or not a trigger.");
            }

            // ---- Slots (IDs over the whole blueprint) ----
            var slotOf = new Dictionary<int, ConstructionSlot>(mine.Length);
            int foreignRefs = 0;
            foreach (int i in mine)
            {
                BrickSpec b = bp.bricks[i];
                ConstructionSlot tmpl = slotByDef[b.def];
                GameObject go = Object.Instantiate(tmpl.gameObject, sections[localOf[b.s]].transform);
                go.name = $"Slot_{i:00000}_{b.def}";
                go.transform.SetPositionAndRotation(origin + rot * new Vector3(b.p[0], b.p[1], b.p[2]), rot * b.Rotation);
                PlacementSlot ps = go.GetComponent<PlacementSlot>();
                ConstructionSlot cs = go.GetComponent<ConstructionSlot>();
                Placement("slotId").SetValue(ps, new PlacementSlotId(IdBase + 1u + (uint)i));
                Slot("placementSlot").SetValue(cs, ps);
                Slot("manualPrerequisites").SetValue(cs, true);
                Slot("prerequisiteMode").SetValue(cs, (ConstructionPrerequisiteMode)b.mode);
                Slot("finalVisualRoot").SetValue(cs, finalRoots[localOf[b.s]]);
                Placement("placeTrigger").SetValue(ps, siteArea);
                foreach (string f in new[] { "placementAnchor", "hologramRoot", "ruleProvider" })
                {
                    object refValue = Placement(f).GetValue(ps);
                    Transform refTransform = refValue is Component c && c != null ? c.transform
                        : refValue is GameObject g && g != null ? g.transform : null;
                    if (refTransform != null && !refTransform.IsChildOf(go.transform))
                    {
                        foreignRefs++;
                        if (foreignRefs <= 3)
                        {
                            Plugin.Log.LogWarning($"Slot {i}: '{f}' points to '{refTransform.name}' outside the slot.");
                        }
                    }
                }
                slotOf[i] = cs;
                placementSlots[i] = ps;
            }
            if (foreignRefs > 0)
            {
                Plugin.Log.LogWarning($"{foreignRefs} slot references point outside the clone (template shares objects).");
            }
            int dropped = 0;
            foreach (int i in mine)
            {
                int[] req = bp.bricks[i].req ?? new int[0];
                ConstructionSlot[] pre = req.Where(slotOf.ContainsKey).Select(j => slotOf[j]).ToArray();
                dropped += req.Length - pre.Length;
                Slot("prerequisites").SetValue(slotOf[i], pre);
            }
            var perSection = new List<ConstructionSlot>[nSec];
            for (int k = 0; k < nSec; k++)
            {
                perSection[k] = new List<ConstructionSlot>();
            }
            foreach (int i in mine)
            {
                perSection[localOf[bp.bricks[i].s]].Add(slotOf[i]);
            }
            for (int k = 0; k < nSec; k++)
            {
                if (perSection[k].Count == 0)
                {
                    throw new InvalidDataException($"Section '{bp.sections[part.sections[k]]}' has no bricks.");
                }
                Section("slots").SetValue(sections[k], perSection[k].ToArray());
            }

            // ---- Final meshes: one combined mesh per section (shown instead of the single bricks once a section is complete) ----
            for (int k = 0; k < nSec; k++)
            {
                int sec = part.sections[k];
                GameObject fin = CombinedBricks(bp.sections[sec] + "_Mesh",
                    mine.Select(i => bp.bricks[i]).Where(b => b.s == sec).Select(b => (b.def, b.p, b.Rotation)), recByDef, visuals, finalRoots[k].transform, true);
                fin?.transform.SetPositionAndRotation(origin, rot);
            }

            // ---- Bake the topology (as the Unity editor does for the original sites) ----
            var specs = new List<ConstructionSlotSpec>(mine.Length);
            for (int k = 0; k < nSec; k++)
            {
                foreach (ConstructionSlot cs in perSection[k])
                {
                    PlacementSlotId[] pre = cs.Prerequisites.Select(p => p.PlacementSlot.SlotId).ToArray();
                    specs.Add(new ConstructionSlotSpec(cs.PlacementSlot.SlotId, cs.ExpectedDefinition.DefinitionId, k, pre, cs.PrerequisiteMode));
                }
            }
            Site("siteId").SetValue(site, part.siteId);
            Site("displayName").SetValue(site, part.displayName);
            Site("sections").SetValue(site, sections);
            Site("bakedSpecs").SetValue(site, specs.ToArray());
            Site("bakedSectionCount").SetValue(site, nSec);

            if (siteArea is BoxCollider area)
            {
                area.center = new Vector3((min.x + max.x) / 2f, (max.y + 2f) / 2f, (min.z + max.z) / 2f);
                area.size = new Vector3(max.x - min.x + 6f, max.y + 4f, max.z - min.z + 6f);
            }
            else
            {
                Plugin.Log.LogWarning("Site area is not a BoxCollider, the template's size is kept.");
            }

            if (partIndex == 0)
            {
                BuildFoundation(bp, clone.transform, recByDef, visuals, groundLayer);
                BuildScaffold(bp.scaffold, clone.transform, groundLayer, "Scaffold");
                tempScaffold = BuildScaffold(bp.tempScaffold, clone.transform, groundLayer, "ScaffoldTemporary");
            }

            // Blueprint board: our own 3D model instead of the house (the board requires a single mesh without children)
            var preview = clone.GetComponentInChildren<ConstructionBlueprintPreview>(true);
            if (preview != null)
            {
                IEnumerable<(string, float[], Quaternion)> items = mine.Select(i => bp.bricks[i]).Select(b => (b.def, b.p, b.Rotation));
                if (bp.parts == null)
                {
                    items = items.Concat((bp.decor ?? new DecorSpec[0]).Select(d => (d.def, d.p, d.Rotation)));
                }
                GameObject model = BuildPreviewModel(part.siteId, items, recByDef, visuals, clone.transform);
                if (model != null)
                {
                    AccessTools.Field(typeof(ConstructionBlueprintPreview), "modelPrefab").SetValue(preview, model);
                }
            }

            if (!site.ValidateAuthoredReferences(out string issue))
            {
                throw new InvalidOperationException($"Site validation failed for '{part.siteId}': " + issue);
            }
            try
            {
                SiteGetBakedSpecs.Invoke(site, null);
            }
            catch (TargetInvocationException tie)
            {
                throw new InvalidOperationException($"Invalid topology in '{part.siteId}': " + tie.InnerException?.Message);
            }
            Plugin.Log.LogInfo($"Part '{part.siteId}': {mine.Length} slots in {nSec} sections" +
                (dropped > 0 ? $", {dropped} prerequisites into other parts dropped." : "."));
            return site;
        }

        /// <summary>
        /// Preview model for the blueprint board: all bricks + decor bricks as one mesh, one submesh per material.
        /// The template lives in an inactive container under the site; the board instantiates it (active) into its preview rig.
        /// </summary>
        private static GameObject BuildPreviewModel(string name, IEnumerable<(string, float[], Quaternion)> items,
            Dictionary<string, BrickRecord> recByDef, BrickVisual[] visuals, Transform siteRoot)
        {
            var shelf = new GameObject("Templates");
            shelf.SetActive(false);
            shelf.transform.SetParent(siteRoot, false);
            GameObject model = CombinedBricks(name + "_PreviewModel", items, recByDef, visuals, shelf.transform, false);
            if (model == null)
            {
                Plugin.Log.LogWarning("Preview model: no readable brick meshes, the board keeps showing the template.");
            }
            return model;
        }

        /// <summary>
        /// Combine bricks (asset name, local center, rotation) into one mesh, one submesh per material.
        /// Unreadable meshes are attached individually as children if allowed, otherwise skipped.
        /// </summary>
        private static GameObject CombinedBricks(string name, IEnumerable<(string def, float[] p, Quaternion r)> items,
            Dictionary<string, BrickRecord> recByDef, BrickVisual[] visuals, Transform parent, bool allowChildren)
        {
            var groups = new Dictionary<Material, List<CombineInstance>>();
            var order = new List<Material>();
            var colorOf = new Dictionary<Material, BrickColorGroup>();
            var loose = new List<(BrickVisual vis, Matrix4x4 m, BrickColorGroup color)>();
            foreach ((string def, float[] p, Quaternion r) in items)
            {
                BrickVisual vis = visuals[recByDef[def].visualIndex];
                if (vis.mesh == null)
                {
                    continue;
                }
                BrickColorGroup color = recByDef[def].definition != null ? recByDef[def].definition.ColorGroup : null;
                Matrix4x4 m = Matrix4x4.TRS(new Vector3(p[0], p[1], p[2]), r, Vector3.one) * vis.localMatrix;
                if (!vis.mesh.isReadable)
                {
                    loose.Add((vis, m, color));
                    continue;
                }
                for (int s = 0; s < vis.mesh.subMeshCount; s++)
                {
                    Material mat = vis.materials[Math.Min(s, vis.materials.Length - 1)];
                    if (!groups.TryGetValue(mat, out List<CombineInstance> list))
                    {
                        groups[mat] = list = new List<CombineInstance>();
                        order.Add(mat);
                    }
                    if (color != null && color.Includes(mat) && !colorOf.ContainsKey(mat))
                    {
                        colorOf[mat] = color;
                    }
                    list.Add(new CombineInstance { mesh = vis.mesh, subMeshIndex = s, transform = m });
                }
            }
            if (order.Count == 0 && (loose.Count == 0 || !allowChildren))
            {
                return null;
            }
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            if (order.Count > 0)
            {
                var parts = new CombineInstance[order.Count];
                for (int g = 0; g < order.Count; g++)
                {
                    var part = new Mesh { indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
                    part.CombineMeshes(groups[order[g]].ToArray(), true, true);
                    parts[g] = new CombineInstance { mesh = part, transform = Matrix4x4.identity };
                }
                var mesh = new Mesh { name = name, indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
                mesh.CombineMeshes(parts, false, false);
                mesh.RecalculateBounds();
                foreach (CombineInstance part in parts)
                {
                    Object.Destroy(part.mesh);
                }
                go.AddComponent<MeshFilter>().sharedMesh = mesh;
                MeshRenderer renderer = go.AddComponent<MeshRenderer>();
                renderer.sharedMaterials = order.ToArray();
                FollowPalette(renderer, order, mat => colorOf.TryGetValue(mat, out BrickColorGroup c) ? c : null);
            }
            if (allowChildren)
            {
                foreach ((BrickVisual vis, Matrix4x4 m, BrickColorGroup color) in loose)
                {
                    var child = new GameObject("Brick");
                    child.transform.SetParent(go.transform, false);
                    child.transform.localPosition = m.GetColumn(3);
                    child.transform.localRotation = m.rotation;
                    child.transform.localScale = m.lossyScale;
                    child.AddComponent<MeshFilter>().sharedMesh = vis.mesh;
                    MeshRenderer renderer = child.AddComponent<MeshRenderer>();
                    renderer.sharedMaterials = vis.materials;
                    FollowPalette(renderer, vis.materials, mat => color != null && color.Includes(mat) ? color : null);
                }
            }
            if (loose.Count > 0)
            {
                Plugin.Log.LogWarning($"{name}: {loose.Count} bricks with an unreadable mesh {(allowChildren ? "attached individually" : "skipped")}.");
            }
            return go;
        }

        private static readonly AccessTools.FieldRef<BrickColorRenderer, BrickColorRenderer.Target[]> ColorTargets =
            AccessTools.FieldRefAccess<BrickColorRenderer, BrickColorRenderer.Target[]>("targets");
        private static readonly AccessTools.FieldRef<BrickColorRenderer, IBrickColorPalette> ColorPalette =
            AccessTools.FieldRefAccess<BrickColorRenderer, IBrickColorPalette>("palette");

        /// <summary>
        /// The game recolours bricks per colour group (settings, accessibility: own brick colours), each group by the
        /// brick type and only on the materials the group includes. A combined mesh gets the component the game puts on
        /// single bricks, so it follows the chosen colours like the game's own bricks.
        /// </summary>
        private static void FollowPalette(Renderer renderer, IList<Material> materials, Func<Material, BrickColorGroup> groupOf)
        {
            var targets = new List<BrickColorRenderer.Target>();
            for (int i = 0; i < materials.Count; i++)
            {
                BrickColorGroup group = groupOf(materials[i]);
                if (group != null)
                {
                    targets.Add(new BrickColorRenderer.Target { renderer = renderer, materialIndex = i, group = group });
                }
            }
            if (targets.Count == 0)
            {
                return;
            }
            var colors = renderer.gameObject.AddComponent<BrickColorRenderer>();
            ColorTargets(colors) = targets.ToArray();
            if (ColorPalette(colors) == null)
            {
                try
                {
                    ((IInitializable<IBrickColorPalette>)colors).Init(Service.Get<IBrickColorPalette>());
                }
                catch (Exception e)
                {
                    Plugin.Log.LogWarning($"{renderer.name}: does not follow the own brick colours ({e.Message}).");
                    return;
                }
            }
            colors.Apply();
        }

        /// <summary>The town's fences and small props (material M_Map_04, measured in the scene data) carry this material.</summary>
        private const string FenceMaterial = "M_Map_04";

        /// <summary>
        /// Room for a large building: in the blueprint's clear area (local rectangle) the scene objects with the fence
        /// material and a collider are switched off. Only in a mod-map session; the scene is loaded anew at every game start.
        /// </summary>
        private static void ClearArea(Blueprint bp, Scene scene)
        {
            if (bp.clearArea == null || bp.clearArea.Length != 4)
            {
                return;
            }
            Quaternion inv = Quaternion.Inverse(Quaternion.Euler(0f, Plugin.Yaw.Value, 0f));
            var origin = new Vector3(Plugin.OriginX.Value, 0f, Plugin.OriginZ.Value);
            int hidden = 0;
            foreach (MeshRenderer r in Object.FindObjectsByType<MeshRenderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
            {
                if (r.gameObject.scene != scene || r.sharedMaterial == null || r.GetComponent<Collider>() == null
                    || !r.sharedMaterial.name.StartsWith(FenceMaterial, StringComparison.Ordinal))
                {
                    continue;
                }
                Vector3 local = inv * (r.bounds.center - origin);
                if (local.x < bp.clearArea[0] || local.x > bp.clearArea[2] || local.z < bp.clearArea[1] || local.z > bp.clearArea[3])
                {
                    continue;
                }
                r.gameObject.SetActive(false);
                hidden++;
            }
            Plugin.Log.LogInfo($"Clear area: {hidden} fences and props hidden.");
        }

        /// <summary>
        /// Plinth like the original sites: bricks as visuals only (one mesh), plus walkable colliders.
        /// The blueprint's slots are already placed at plinth height.
        /// </summary>
        private static void BuildFoundation(Blueprint bp, Transform root, Dictionary<string, BrickRecord> recByDef, BrickVisual[] visuals, int groundLayer)
        {
            var container = new GameObject("Foundation");
            container.transform.SetParent(root, false);
            container.transform.localPosition = Vector3.zero;
            container.transform.localRotation = Quaternion.identity;
            CombinedBricks("Plinth", (bp.decor ?? new DecorSpec[0]).Select(d => (d.def, d.p, d.Rotation)), recByDef, visuals, container.transform, true);
            foreach (BoxSpec b in bp.colliders ?? new BoxSpec[0])
            {
                var go = new GameObject("PlinthCollider") { layer = groundLayer };
                go.transform.SetParent(container.transform, false);
                go.transform.localPosition = new Vector3(b.c[0], b.c[1], b.c[2]);
                go.transform.localRotation = Quaternion.identity;
                go.AddComponent<BoxCollider>().size = new Vector3(b.s[0], b.s[1], b.s[2]);
            }
        }

        /// <summary>
        /// Showcase: the blueprint as a finished building, one mesh with a walkable MeshCollider per section, with plinth
        /// and brick supply, but without construction sites and without the scaffold (a finished building has none);
        /// ramps stay, they are the way up onto a high plinth.
        /// For checking a design in the game.
        /// </summary>
        private static void BuildShowcase(Blueprint bp, GameSceneInstaller gsi, Scene scene, ConstructionSite[] allSites,
            ConstructionSceneInstaller[] installers, ConstructionSite template, BrickWorldSource bws, BrickWorldCatalog catalog,
            BrickRecord[] origBricks, BrickVisual[] visuals, Dictionary<string, BrickRecord> recByDef)
        {
            Transform houseGround = template.transform.Find("House/Base_Ground");
            int groundLayer = houseGround != null ? houseGround.gameObject.layer : 0;
            bool clean = Plugin.RemoveVanilla.Value;
            if (clean)
            {
                foreach (ConstructionSite s in allSites)
                {
                    HideSite(s);
                }
            }
            Quaternion rot = Quaternion.Euler(0f, Plugin.Yaw.Value, 0f);
            Vector3 origin = new Vector3(Plugin.OriginX.Value, 0f, Plugin.OriginZ.Value);
            origin.y = GroundY(origin.x, origin.z, out string groundName);
            var root = new GameObject(bp.displayName + "_Showcase");
            SceneManager.MoveGameObjectToScene(root, scene);
            root.transform.SetPositionAndRotation(origin, rot);
            BuildFoundation(bp, root.transform, recByDef, visuals, groundLayer);
            BuildScaffold(Ramps(bp.scaffold), root.transform, groundLayer, "Ramps");     // the way up onto a high plinth stays
            int solid = 0;
            for (int s = 0; s < bp.sections.Length; s++)
            {
                int sec = s;
                GameObject part = CombinedBricks(bp.sections[s], bp.bricks.Where(b => b.s == sec).Select(b => (b.def, b.p, b.Rotation)),
                    recByDef, visuals, root.transform, true);
                MeshFilter mf = part != null ? part.GetComponent<MeshFilter>() : null;
                if (mf != null)
                {
                    part.layer = groundLayer;
                    part.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
                    solid++;
                }
            }
            var newCatalog = ScriptableObject.CreateInstance<BrickWorldCatalog>();
            newCatalog.name = catalog.name + "+" + bp.siteId + "_showcase";
            BrickRecord[] supply = SupplyRecords(bp, recByDef, origin, rot);
            CatBricks.SetValue(newCatalog, clean ? supply : origBricks.Concat(supply).ToArray());
            CatVisuals.SetValue(newCatalog, visuals);
            BwsCatalog.SetValue(bws, newCatalog);
            if (clean)
            {
                // No construction site at all: original slots out of the registry, every installer empty (skipped)
                var vanillaSlots = new HashSet<PlacementSlot>(allSites.SelectMany(s => s.Sections).SelectMany(sec => sec.Slots)
                    .Where(cs => cs != null && cs.PlacementSlot != null).Select(cs => cs.PlacementSlot));
                GsiSlots.SetValue(gsi, ((PlacementSlot[])GsiSlots.GetValue(gsi)).Where(p => !vanillaSlots.Contains(p)).ToArray());
                foreach (ConstructionSceneInstaller inst in installers)
                {
                    CsiSites.SetValue(inst, new ConstructionSite[0]);
                }
            }
            Plugin.Log.LogInfo($"Showcase '{bp.siteId}': {bp.bricks.Length} bricks finished in {bp.sections.Length} meshes ({solid} with colliders) " +
                $"at ({origin.x:0.00}, {origin.y:0.00}, {origin.z:0.00}), rotation {Plugin.Yaw.Value}, ground '{groundName}'" +
                (clean ? ", original buildings removed." : "."));
        }

        /// <summary>The blueprint's bricks as loose supply: grouped by type, stacked in the pile areas (or rows).</summary>
        private static BrickRecord[] SupplyRecords(Blueprint bp, Dictionary<string, BrickRecord> recByDef, Vector3 origin, Quaternion rot)
        {
            int n = bp.bricks.Length;
            var newRecords = new BrickRecord[n];
            var order = Enumerable.Range(0, n).OrderBy(i => bp.bricks[i].def, StringComparer.Ordinal).ToArray();
            float rowZ = bp.pile.z;
            int idx = 0;
            var cursor = bp.pile.areas != null && bp.pile.areas.Length > 0 ? new AreaCursor(bp.pile.areas, 0.5f) : null;
            foreach (IGrouping<string, int> group in order.GroupBy(i => bp.bricks[i].def))
            {
                BrickRecord tmplRec = recByDef[group.Key];
                Vector3 size = tmplRec.colliderSize;
                float cellX = size.x + bp.pile.gap, cellZ = size.z + bp.pile.gap;
                int stack = bp.pile.StackFor(size.y);
                int j = 0, rows = 0;
                cursor?.NewGroup();
                Vector2 column = Vector2.zero;
                foreach (int i in group)
                {
                    int level = j % stack;
                    int col = (j / stack) % Math.Max(1, bp.pile.perRow);
                    int row = (j / stack) / Math.Max(1, bp.pile.perRow);
                    rows = Math.Max(rows, row + 1);
                    if (cursor != null && level == 0)
                    {
                        column = cursor.Next(cellX, cellZ);
                    }
                    Vector3 local = cursor != null ? new Vector3(column.x, 0f, column.y)
                        : new Vector3(bp.pile.x + col * cellX + cellX / 2f, 0f, rowZ + row * cellZ + cellZ / 2f);
                    Vector3 world = origin + rot * local;
                    world.y = GroundY(world.x, world.z, out _) + size.y / 2f + level * size.y + 0.002f;
                    BrickRecord rec = tmplRec;
                    rec.id = new ItemInstanceId(IdBase + 1u + (uint)i);
                    rec.position = world;
                    rec.rotation = rot;
                    newRecords[idx++] = rec;
                    j++;
                }
                rowZ += rows * cellZ + 0.5f;
            }
            if (cursor != null && cursor.Overflow)
            {
                Plugin.Log.LogWarning("Brick supply: the pile areas are full, the rest continues behind the last area.");
            }
            return newRecords;
        }

        /// <summary>Colour of uprights, rails and braces: plain aluminium instead of the game's red scaffold paint.</summary>
        private static readonly Color Aluminium = new Color(0.76f, 0.78f, 0.80f);

        /// <summary>Ramps of a scaffold: walkable parts tilted about x or z (turned stairs are only turned about y).</summary>
        private static float[][] Ramps(float[][] boxes) =>
            (boxes ?? new float[0][]).Where(b => b.Length >= 10 && b[9] > 0.5f && (b[6] != 0f || b[8] != 0f)).ToArray();

        /// <summary>
        /// Scaffold of the blueprint: planks as one mesh with the game's scaffolding material, uprights, rails and braces
        /// as a second mesh in aluminium, plus a walkable BoxCollider per upright part (rotated parts such as braces are
        /// visuals only), all under one container object (returned; null without parts).
        /// </summary>
        private static GameObject BuildScaffold(float[][] boxes, Transform root, int groundLayer, string name)
        {
            if (boxes == null || boxes.Length == 0)
            {
                return null;
            }
            Material mat = FindMaterial("M_Scaffolding") ?? FindMaterial("M_Pallet");
            GameObject primitive = GameObject.CreatePrimitive(PrimitiveType.Cube);
            Mesh cube = primitive.GetComponent<MeshFilter>().sharedMesh;
            Object.DestroyImmediate(primitive);
            // M_Scaffolding is a texture atlas of the game's scaffold lift (measured): planks use a plain part of a deck
            // plate, uprights, rails and braces a pole stripe (red there; its colour map is swapped for plain aluminium,
            // the stripe keeps its normal map). Without that the boxes show the whole atlas.
            Mesh plankMesh = AtlasCube(cube, new Rect(0.35f, 0.335f, 0.12f, 0.09f));
            Mesh poleMesh = AtlasCube(cube, new Rect(0.555f, 0.10f, 0.055f, 0.75f));
            var container = new GameObject(name);
            container.transform.SetParent(root, false);
            var planks = new List<CombineInstance>(boxes.Length);
            var poles = new List<CombineInstance>(boxes.Length);
            int solid = 0;
            foreach (float[] b in boxes)
            {
                var c = new Vector3(b[0], b[1], b[2]);
                var s = new Vector3(b[3], b[4], b[5]);
                bool rotated = b.Length >= 9;
                Quaternion r = rotated ? Quaternion.Euler(b[6], b[7], b[8]) : Quaternion.identity;
                bool walkable = !rotated || (b.Length >= 10 && b[9] > 0.5f);     // a rotated box is a brace, unless marked (ramps)
                bool slim = (rotated && !walkable) || Mathf.Min(s.x, s.z) < 0.15f;
                bool upright = !rotated && slim && s.y > Mathf.Max(s.x, s.z);    // no collider: the mobile scaffold rolls through
                (slim ? poles : planks).Add(new CombineInstance { mesh = slim ? poleMesh : plankMesh, transform = Matrix4x4.TRS(c, r, s) });
                if (walkable && !upright)
                {
                    var go = new GameObject("ScaffoldCollider") { layer = groundLayer };
                    go.transform.SetParent(container.transform, false);
                    go.transform.localPosition = c;
                    go.transform.localRotation = r;
                    go.AddComponent<BoxCollider>().size = s;
                    solid++;
                }
            }
            Material metal = null;
            if (mat != null)
            {
                metal = new Material(mat) { name = mat.name + "_Aluminium" };
                foreach (string map in new[] { "_BaseMap", "_MainTex" })
                {
                    if (metal.HasProperty(map))
                    {
                        metal.SetTexture(map, Texture2D.whiteTexture);
                    }
                }
                foreach (string tint in new[] { "_BaseColor", "_Color" })
                {
                    if (metal.HasProperty(tint))
                    {
                        metal.SetColor(tint, Aluminium);
                    }
                }
            }
            ScaffoldMesh(container.transform, "ScaffoldPlanks", planks, mat);
            ScaffoldMesh(container.transform, "ScaffoldMetal", poles, metal);
            string matName = mat != null ? mat.name : "(none)";
            Plugin.Log.LogInfo($"{name}: {boxes.Length} parts ({planks.Count} planks, {poles.Count} aluminium), {solid} colliders, material {matName}.");
            return container;
        }

        private static void ScaffoldMesh(Transform parent, string name, List<CombineInstance> parts, Material material)
        {
            if (parts.Count == 0)
            {
                return;
            }
            var mesh = new Mesh { name = name, indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
            mesh.CombineMeshes(parts.ToArray(), true, true);
            mesh.RecalculateBounds();
            var visual = new GameObject(name);
            visual.transform.SetParent(parent, false);
            visual.AddComponent<MeshFilter>().sharedMesh = mesh;
            MeshRenderer renderer = visual.AddComponent<MeshRenderer>();
            if (material != null)
            {
                renderer.sharedMaterial = material;
            }
        }

        /// <summary>Copy of a mesh with all UVs squeezed into one rectangle of the texture.</summary>
        private static Mesh AtlasCube(Mesh source, Rect area)
        {
            var mesh = Object.Instantiate(source);
            Vector2[] uv = mesh.uv;
            for (int i = 0; i < uv.Length; i++)
            {
                uv[i] = new Vector2(area.xMin + uv[i].x * area.width, area.yMin + uv[i].y * area.height);
            }
            mesh.uv = uv;
            return mesh;
        }

        private static Material FindMaterial(string name)
        {
            return Resources.FindObjectsOfTypeAll<Material>().FirstOrDefault(m => m.name == name);
        }

        /// <summary>Fills the pile rectangles one after the other: columns along x, rows along z, a new row per brick type.</summary>
        private sealed class AreaCursor
        {
            private readonly float[][] areas;
            private readonly float groupGap;
            private int area;
            private float x, z, rowDepth;

            internal bool Overflow { get; private set; }

            internal AreaCursor(float[][] areas, float groupGap)
            {
                this.areas = areas;
                this.groupGap = groupGap;
                x = areas[0][0];
                z = areas[0][1];
            }

            internal void NewGroup()
            {
                if (rowDepth > 0f)
                {
                    x = areas[area][0];
                    z += rowDepth + groupGap;
                    rowDepth = 0f;
                }
            }

            internal Vector2 Next(float cellX, float cellZ)
            {
                while (true)
                {
                    float[] r = areas[area];
                    if (x + cellX > r[2] + 1e-4f)
                    {
                        x = r[0];
                        z += rowDepth;
                        rowDepth = 0f;
                    }
                    if (z + cellZ <= r[3] + 1e-4f || area + 1 >= areas.Length)
                    {
                        Overflow |= z + cellZ > r[3] + 1e-4f;
                        var c = new Vector2(x + cellX / 2f, z + cellZ / 2f);
                        x += cellX;
                        rowDepth = Math.Max(rowDepth, cellZ);
                        return c;
                    }
                    area++;
                    x = areas[area][0];
                    z = areas[area][1];
                    rowDepth = 0f;
                }
            }
        }

        /// <summary>
        /// Hide an original building: its children (foundation, frames, blueprint board, props, slots) inactive, its site area
        /// trigger and the site component off. The root stays active, because it carries the building's
        /// ConstructionSceneInstaller, which also creates the UI for the site placed into it.
        /// </summary>
        private static void HideSite(ConstructionSite s)
        {
            GameObject root = s.gameObject;
            foreach (Collider col in root.GetComponents<Collider>())
            {
                col.enabled = false;
            }
            for (int i = 0; i < root.transform.childCount; i++)
            {
                root.transform.GetChild(i).gameObject.SetActive(false);
            }
            s.enabled = false;
        }

        /// <summary>Height of the topmost solid (non-trigger) collider below the point.</summary>
        private static float GroundY(float x, float z, out string colliderName)
        {
            RaycastHit[] hits = Physics.RaycastAll(new Vector3(x, 200f, z), Vector3.down, 400f, ~0, QueryTriggerInteraction.Ignore);
            if (hits.Length == 0)
            {
                colliderName = "(no ground found)";
                return 0f;
            }
            RaycastHit best = hits.OrderByDescending(h => h.point.y).First();
            colliderName = best.collider.name;
            return best.point.y;
        }
    }
}
