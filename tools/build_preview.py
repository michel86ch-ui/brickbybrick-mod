"""Builds the stand-alone 3D preview page of the Notre-Dame for GitHub Pages.

Embeds the generator output (blueprints/notredame_preview.json) and the game's brick meshes (tools/brick_meshes.json)
into tools/preview_template.html. The page loads three.js from a CDN and needs nothing else.

Usage:  py gen_notredame.py 1.2  then  py build_preview.py   ->  ../docs/notre-dame/index.html
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))


def embed(path):
    """JSON text, safe inside a <script> element."""
    with open(path, encoding="utf-8") as f:
        text = json.dumps(json.load(f), separators=(",", ":"), ensure_ascii=False)
    return text.replace("</", "<\\/")


with open(os.path.join(HERE, "preview_template.html"), encoding="utf-8") as f:
    page = f.read()
for placeholder, path in (("__DATA__", os.path.join(ROOT, "blueprints", "notredame_preview.json")),
                          ("__MESHES__", os.path.join(HERE, "brick_meshes.json"))):
    if page.count(placeholder) != 1:
        raise SystemExit(f"{placeholder} must occur exactly once in the template")
    page = page.replace(placeholder, embed(path))
dst = os.path.join(ROOT, "docs", "notre-dame", "index.html")
os.makedirs(os.path.dirname(dst), exist_ok=True)
with open(dst, "w", encoding="utf-8", newline="\n") as f:
    f.write(page)
print(f"{len(page) / 1024:.0f} KB -> {dst}")
