using System.Linq;
using MultiplayerTemplate.Construction;
using UnityEngine;

namespace ExtraBuildings
{
    /// <summary>
    /// The temporary scaffold of a building (blueprint field "tempScaffold") stands while the building is being built. Once
    /// every construction site of the building is complete it is switched off, and on again should a site become
    /// incomplete (another world, a reset). Checked twice a second, so a finished building loads without it.
    /// </summary>
    internal sealed class TemporaryScaffold : MonoBehaviour
    {
        private GameObject scaffold;
        private ConstructionSite[] sites;
        private float nextCheck;

        /// <summary>The watcher sits on the scaffold's parent (the first site), which stays active.</summary>
        internal static void Attach(GameObject scaffold, ConstructionSite[] sites)
        {
            TemporaryScaffold watcher = scaffold.transform.parent.gameObject.AddComponent<TemporaryScaffold>();
            watcher.scaffold = scaffold;
            watcher.sites = sites;
        }

        private void Update()
        {
            if (Time.unscaledTime < nextCheck || scaffold == null)
            {
                return;
            }
            nextCheck = Time.unscaledTime + 0.5f;
            bool finished = sites.All(s => s != null && s.State != null && s.State.IsComplete);
            if (scaffold.activeSelf == finished)
            {
                scaffold.SetActive(!finished);
                Plugin.Log.LogInfo(finished ? "Building complete: the temporary scaffold is removed."
                    : "Building not complete: the temporary scaffold stands.");
            }
        }
    }
}
