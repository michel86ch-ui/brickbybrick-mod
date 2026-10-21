using System.IO;
using Newtonsoft.Json;

#pragma warning disable CS0649 // Felder werden von Newtonsoft.Json befuellt

namespace ExtraBuildings
{
    /// <summary>Bauplan im JSON-Format, erzeugt von tools\gen_*.py.</summary>
    internal sealed class Blueprint
    {
        public string siteId;
        public string displayName;
        public string templateSite = "house";
        public string[] sections;
        /// <summary>Bauplan-Tafel lokal zur Grundriss-Mitte: x, z, Drehung in Grad.</summary>
        public float[] blueprintStand;
        public PileSpec pile;
        /// <summary>Begehbare Kollider des Sockels (lokal).</summary>
        public BoxSpec[] colliders;
        /// <summary>Sockelsteine: nur Optik, keine Steinplaetze.</summary>
        public DecorSpec[] decor;
        public BrickSpec[] bricks;

        public static Blueprint Load(string path)
        {
            Blueprint bp = JsonConvert.DeserializeObject<Blueprint>(File.ReadAllText(path));
            if (bp == null || string.IsNullOrWhiteSpace(bp.siteId) || bp.sections == null || bp.sections.Length == 0
                || bp.bricks == null || bp.bricks.Length == 0 || bp.pile == null)
            {
                throw new InvalidDataException("Bauplan unvollstaendig: " + path);
            }
            for (int i = 0; i < bp.bricks.Length; i++)
            {
                BrickSpec b = bp.bricks[i];
                if (b.p == null || b.p.Length != 3 || b.s < 0 || b.s >= bp.sections.Length || (b.mode != 0 && b.mode != 1))
                {
                    throw new InvalidDataException($"Bauplan-Stein {i} ist ungueltig.");
                }
                foreach (int r in b.req ?? new int[0])
                {
                    if (r < 0 || r >= bp.bricks.Length || r == i)
                    {
                        throw new InvalidDataException($"Bauplan-Stein {i} hat eine ungueltige Vorbedingung {r}.");
                    }
                }
            }
            return bp;
        }
    }

    internal sealed class PileSpec
    {
        public float x;
        public float z;
        public float gap = 0.06f;
        public int perRow = 10;
        public int stack = 2;
    }

    internal sealed class BoxSpec
    {
        public float[] c;
        public float[] s;
    }

    internal sealed class DecorSpec
    {
        public string def;
        public float[] p;
        public float yaw;
    }

    internal sealed class BrickSpec
    {
        /// <summary>Asset-Name der Steindefinition, z. B. Bakery_Brick_2D1CAFD3.</summary>
        public string def;
        /// <summary>Steinmitte in Metern, lokal zur Grundriss-Mitte auf Bodenhoehe.</summary>
        public float[] p;
        public float yaw;
        /// <summary>Index des Bauabschnitts.</summary>
        public int s;
        /// <summary>0 = alle Vorbedingungen (All), 1 = eine genuegt (Any).</summary>
        public int mode;
        public int[] req;
    }
}
