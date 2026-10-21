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
using MultiplayerTemplate.Game.Items;
using MultiplayerTemplate.Game.Placement;
using MultiplayerTemplate.Game.Scenes;
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
                if (allSites.Any(s => s.SiteId == bp.siteId))
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

                // ---- Clone of the template, hidden in an inactive holder (no Awake) ----
                holder = new GameObject("ExtraBuildings_Holder");
                holder.SetActive(false);
                SceneManager.MoveGameObjectToScene(holder, scene);
                GameObject clone = Object.Instantiate(template.gameObject, holder.transform);
                clone.name = bp.displayName + "_Construction";

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
                foreach (SceneLifecycleHook hook in clone.GetComponentsInChildren<SceneLifecycleHook>(true))
                {
                    Object.DestroyImmediate(hook);   // the ConstructionSceneInstaller sits on the House root
                }
                // Remember the layer of the house foundation (walkable) for the colliders of our own plinth
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
                if (stand != null && bp.blueprintStand != null && bp.blueprintStand.Length >= 2)
                {
                    // Keep the template's height and tilt, only move it and turn it around the vertical axis
                    stand.localPosition = new Vector3(bp.blueprintStand[0], stand.localPosition.y, bp.blueprintStand[1]);
                    if (bp.blueprintStand.Length >= 3)
                    {
                        stand.localRotation = Quaternion.Euler(0f, bp.blueprintStand[2], 0f) * stand.localRotation;
                    }
                }

                // ---- Sections with their own final mesh ----
                int nSec = bp.sections.Length;
                var sections = new ConstructionSection[nSec];
                var finalRoots = new GameObject[nSec];
                for (int s = 0; s < nSec; s++)
                {
                    GameObject secGo = Object.Instantiate(sectionTemplate.gameObject, sectionTemplate.transform.parent);
                    secGo.name = "Section_" + bp.sections[s];
                    secGo.transform.SetPositionAndRotation(origin, rot);
                    sections[s] = secGo.GetComponent<ConstructionSection>();
                    Section("displayName").SetValue(sections[s], bp.sections[s]);
                    var fr = new GameObject(bp.sections[s] + "_FinalStaticMesh");
                    fr.transform.SetParent(secGo.transform, false);
                    fr.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                    fr.SetActive(false);
                    finalRoots[s] = fr;
                }
                Object.DestroyImmediate(sectionTemplate.gameObject);

                // Site area: PlacementSlot.IsPlayerInside checks placeTrigger -> it must be the area of THIS site
                if (!(Site("constructionArea").GetValue(site) is Collider siteArea) || !siteArea.isTrigger)
                {
                    throw new InvalidOperationException("The template's site area is missing or not a trigger.");
                }

                // ---- Slots ----
                int n = bp.bricks.Length;
                var slots = new ConstructionSlot[n];
                var placementSlots = new PlacementSlot[n];
                int foreignRefs = 0;
                for (int i = 0; i < n; i++)
                {
                    BrickSpec b = bp.bricks[i];
                    ConstructionSlot tmpl = slotByDef[b.def];
                    GameObject go = Object.Instantiate(tmpl.gameObject, sections[b.s].transform);
                    go.name = $"Slot_{i:0000}_{b.def}";
                    go.transform.SetPositionAndRotation(origin + rot * new Vector3(b.p[0], b.p[1], b.p[2]), rot * Quaternion.Euler(0f, b.yaw, 0f));
                    PlacementSlot ps = go.GetComponent<PlacementSlot>();
                    ConstructionSlot cs = go.GetComponent<ConstructionSlot>();
                    Placement("slotId").SetValue(ps, new PlacementSlotId(IdBase + 1u + (uint)i));
                    Slot("placementSlot").SetValue(cs, ps);
                    Slot("manualPrerequisites").SetValue(cs, true);
                    Slot("prerequisiteMode").SetValue(cs, (ConstructionPrerequisiteMode)b.mode);
                    Slot("finalVisualRoot").SetValue(cs, finalRoots[b.s]);
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
                    slots[i] = cs;
                    placementSlots[i] = ps;
                }
                if (foreignRefs > 0)
                {
                    Plugin.Log.LogWarning($"{foreignRefs} slot references point outside the clone (template shares objects).");
                }
                for (int i = 0; i < n; i++)
                {
                    int[] req = bp.bricks[i].req ?? new int[0];
                    Slot("prerequisites").SetValue(slots[i], req.Select(j => slots[j]).ToArray());
                }
                var perSection = new List<ConstructionSlot>[nSec];
                for (int s = 0; s < nSec; s++)
                {
                    perSection[s] = new List<ConstructionSlot>();
                }
                for (int i = 0; i < n; i++)
                {
                    perSection[bp.bricks[i].s].Add(slots[i]);
                }
                for (int s = 0; s < nSec; s++)
                {
                    if (perSection[s].Count == 0)
                    {
                        throw new InvalidDataException($"Section '{bp.sections[s]}' has no bricks.");
                    }
                    Section("slots").SetValue(sections[s], perSection[s].ToArray());
                }

                // ---- Final meshes: one combined mesh per section (shown instead of the single bricks once a section is complete) ----
                for (int s = 0; s < nSec; s++)
                {
                    int sec = s;
                    GameObject fin = CombinedBricks(bp.sections[s] + "_Mesh",
                        bp.bricks.Where(b => b.s == sec).Select(b => (b.def, b.p, b.yaw)), recByDef, visuals, finalRoots[s].transform, true);
                    fin?.transform.SetPositionAndRotation(origin, rot);
                }

                // ---- Bake the topology (as the Unity editor does for the original sites) ----
                var specs = new List<ConstructionSlotSpec>(n);
                for (int s = 0; s < nSec; s++)
                {
                    foreach (ConstructionSlot cs in perSection[s])
                    {
                        PlacementSlotId[] pre = cs.Prerequisites.Select(p => p.PlacementSlot.SlotId).ToArray();
                        specs.Add(new ConstructionSlotSpec(cs.PlacementSlot.SlotId, cs.ExpectedDefinition.DefinitionId, s, pre, cs.PrerequisiteMode));
                    }
                }
                Site("siteId").SetValue(site, bp.siteId);
                Site("displayName").SetValue(site, bp.displayName);
                Site("sections").SetValue(site, sections);
                Site("bakedSpecs").SetValue(site, specs.ToArray());
                Site("bakedSectionCount").SetValue(site, nSec);

                // Site area (trigger) around the footprint
                Vector3 min = Vector3.positiveInfinity, max = Vector3.negativeInfinity;
                foreach (BrickSpec b in bp.bricks)
                {
                    var p = new Vector3(b.p[0], b.p[1], b.p[2]);
                    min = Vector3.Min(min, p);
                    max = Vector3.Max(max, p);
                }
                if (siteArea is BoxCollider area)
                {
                    area.center = new Vector3((min.x + max.x) / 2f, (max.y + 2f) / 2f, (min.z + max.z) / 2f);
                    area.size = new Vector3(max.x - min.x + 6f, max.y + 4f, max.z - min.z + 6f);
                }
                else
                {
                    Plugin.Log.LogWarning("Site area is not a BoxCollider, the template's size is kept.");
                }

                BuildFoundation(bp, clone.transform, recByDef, visuals, groundLayer);

                // Blueprint board: our own 3D model instead of the house (the board requires a single mesh without children)
                var preview = clone.GetComponentInChildren<ConstructionBlueprintPreview>(true);
                if (preview != null)
                {
                    GameObject model = BuildPreviewModel(bp, recByDef, visuals, clone.transform);
                    if (model != null)
                    {
                        AccessTools.Field(typeof(ConstructionBlueprintPreview), "modelPrefab").SetValue(preview, model);
                    }
                }

                if (!site.ValidateAuthoredReferences(out string issue))
                {
                    throw new InvalidOperationException("Site validation failed: " + issue);
                }
                try
                {
                    SiteGetBakedSpecs.Invoke(site, null);
                }
                catch (TargetInvocationException tie)
                {
                    throw new InvalidOperationException("Invalid topology: " + tie.InnerException?.Message);
                }

                // ---- Material: extended catalog ----
                var newRecords = new BrickRecord[n];
                var order = Enumerable.Range(0, n).OrderBy(i => bp.bricks[i].def, StringComparer.Ordinal).ToArray();
                float rowZ = bp.pile.z;
                int idx = 0;
                foreach (IGrouping<string, int> group in order.GroupBy(i => bp.bricks[i].def))
                {
                    BrickRecord tmplRec = recByDef[group.Key];
                    Vector3 size = tmplRec.colliderSize;
                    float cellX = size.x + bp.pile.gap, cellZ = size.z + bp.pile.gap;
                    int j = 0, rows = 0;
                    foreach (int i in group)
                    {
                        int level = j % Math.Max(1, bp.pile.stack);
                        int col = (j / Math.Max(1, bp.pile.stack)) % Math.Max(1, bp.pile.perRow);
                        int row = (j / Math.Max(1, bp.pile.stack)) / Math.Max(1, bp.pile.perRow);
                        rows = Math.Max(rows, row + 1);
                        Vector3 local = new Vector3(bp.pile.x + col * cellX + cellX / 2f, 0f, rowZ + row * cellZ + cellZ / 2f);
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
                        CsiSites.SetValue(inst, inst == csi ? new[] { site } : new ConstructionSite[0]);
                    }
                    Plugin.Log.LogInfo($"Original buildings removed: {allSites.Length} sites, {vanillaSlots.Count} slots, {origBricks.Length} bricks.");
                }
                else
                {
                    CsiSites.SetValue(csi, sites.Concat(new[] { site }).ToArray());
                }
                GsiSlots.SetValue(gsi, gsiSlots.Concat(placementSlots).ToArray());
                clone.transform.SetParent(null, true);
                SceneManager.MoveGameObjectToScene(clone, scene);
                Object.Destroy(holder);
                holder = null;
                Plugin.Log.LogInfo($"Site '{bp.siteId}' injected: {n} slots in {nSec} sections, {n} bricks in the supply, " +
                    $"IDs {IdBase + 1}..{IdBase + (uint)n}.");
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

        /// <summary>
        /// Preview model for the blueprint board: all bricks + decor bricks as one mesh, one submesh per material.
        /// The template lives in an inactive container under the site; the board instantiates it (active) into its preview rig.
        /// </summary>
        private static GameObject BuildPreviewModel(Blueprint bp, Dictionary<string, BrickRecord> recByDef, BrickVisual[] visuals, Transform siteRoot)
        {
            var shelf = new GameObject("Templates");
            shelf.SetActive(false);
            shelf.transform.SetParent(siteRoot, false);
            var items = bp.bricks.Select(b => (b.def, b.p, b.yaw)).Concat((bp.decor ?? new DecorSpec[0]).Select(d => (d.def, d.p, d.yaw)));
            GameObject model = CombinedBricks(bp.siteId + "_PreviewModel", items, recByDef, visuals, shelf.transform, false);
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
        private static GameObject CombinedBricks(string name, IEnumerable<(string def, float[] p, float yaw)> items,
            Dictionary<string, BrickRecord> recByDef, BrickVisual[] visuals, Transform parent, bool allowChildren)
        {
            var groups = new Dictionary<Material, List<CombineInstance>>();
            var order = new List<Material>();
            var loose = new List<(BrickVisual vis, Matrix4x4 m)>();
            foreach ((string def, float[] p, float yaw) in items)
            {
                BrickVisual vis = visuals[recByDef[def].visualIndex];
                if (vis.mesh == null)
                {
                    continue;
                }
                Matrix4x4 m = Matrix4x4.TRS(new Vector3(p[0], p[1], p[2]), Quaternion.Euler(0f, yaw, 0f), Vector3.one) * vis.localMatrix;
                if (!vis.mesh.isReadable)
                {
                    loose.Add((vis, m));
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
                go.AddComponent<MeshRenderer>().sharedMaterials = order.ToArray();
            }
            if (allowChildren)
            {
                foreach ((BrickVisual vis, Matrix4x4 m) in loose)
                {
                    var child = new GameObject("Brick");
                    child.transform.SetParent(go.transform, false);
                    child.transform.localPosition = m.GetColumn(3);
                    child.transform.localRotation = m.rotation;
                    child.transform.localScale = m.lossyScale;
                    child.AddComponent<MeshFilter>().sharedMesh = vis.mesh;
                    child.AddComponent<MeshRenderer>().sharedMaterials = vis.materials;
                }
            }
            if (loose.Count > 0)
            {
                Plugin.Log.LogWarning($"{name}: {loose.Count} bricks with an unreadable mesh {(allowChildren ? "attached individually" : "skipped")}.");
            }
            return go;
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
            CombinedBricks("Plinth", (bp.decor ?? new DecorSpec[0]).Select(d => (d.def, d.p, d.yaw)), recByDef, visuals, container.transform, true);
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
