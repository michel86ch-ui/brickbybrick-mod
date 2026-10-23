"""Builds a stand-alone 3D preview page for GitHub Pages.

Embeds the generator output (blueprints/*_preview.json) and the game's brick meshes into a page template. The page
loads three.js from a CDN and needs nothing else.

Usage:  py gen_notredame.py 1.2  then  py build_preview.py       ->  ../docs/notre-dame/index.html
        py gen_tajmahal.py       then  py build_preview.py taj   ->  ../docs/taj-mahal/index.html
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))


def embed(path):
    """JSON text, safe inside a <script> element."""
    with open(path, encoding="utf-8") as f:
        text = json.dumps(json.load(f), separators=(",", ":"), ensure_ascii=False)
    return text.replace("</", "<\\/")


BUILDINGS = {
    "notre-dame": ("preview_template.html", "notredame_preview.json", "brick_meshes.json", "notre-dame"),
    "taj": ("preview_template_taj.html", "tajmahal_preview.json", "brick_meshes_taj.json", "taj-mahal"),
}
template, data_file, mesh_file, folder = BUILDINGS[sys.argv[1] if len(sys.argv) > 1 else "notre-dame"]
with open(os.path.join(HERE, template), encoding="utf-8") as f:
    page = f.read()
for placeholder, path in (("__DATA__", os.path.join(ROOT, "blueprints", data_file)),
                          ("__MESHES__", os.path.join(HERE, mesh_file))):
    if page.count(placeholder) != 1:
        raise SystemExit(f"{placeholder} must occur exactly once in the template")
    page = page.replace(placeholder, embed(path))
dst = os.path.join(ROOT, "docs", folder, "index.html")
os.makedirs(os.path.dirname(dst), exist_ok=True)
with open(dst, "w", encoding="utf-8", newline="\n") as f:
    f.write(page)
print(f"{len(page) / 1024:.0f} KB -> {dst}")
