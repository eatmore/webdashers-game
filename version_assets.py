#!/usr/bin/env python3
"""Content-hash cache busting + Service Worker manifest for the game.

1. Rewrites every local src/href in index.html to `?v=<hash>` (hash covers ALL
   referenced file contents) — any game file change invalidates browser cache.
2. Emits asset-manifest.json (file list + hash) consumed by the site's service
   worker for background preloading.

Run after ANY game file change (including after convert_webp.py).
"""
import hashlib
import json
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent
index = root / "index.html"

REF = re.compile(r'(src|href)="(assets/[^"?]+)(\?[^"]*)?"')


def main() -> None:
    html = index.read_text(encoding="utf-8")
    refs = REF.findall(html)
    files = sorted({p for _, p, _ in refs})
    h = hashlib.sha256()
    for f in files:
        p = root / f
        if p.exists():
            h.update(f.encode())
            h.update(p.read_bytes())
    version = h.hexdigest()[:10]

    def sub(m: re.Match) -> str:
        attr, path, _old_q = m.group(1), m.group(2), m.group(3)
        return f'{attr}="{path}?v={version}"'

    new_html = REF.sub(sub, html)
    index.write_text(new_html, encoding="utf-8")
    print(f"versioned {len(refs)} refs -> ?v={version}")

    # SW preload manifest: every file under assets/ (relative to assets/)
    asset_files = sorted(
        str(p.relative_to(root / "assets"))
        for p in (root / "assets").rglob("*")
        if p.is_file()
    )
    manifest = {"hash": version, "files": asset_files}
    (root / "asset-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    total = sum((root / "assets" / f).stat().st_size for f in asset_files)
    print(f"manifest: {len(asset_files)} files, {total/1e6:.1f}MB -> asset-manifest.json")


if __name__ == "__main__":
    sys.exit(main())
