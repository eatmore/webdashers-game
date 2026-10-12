#!/usr/bin/env python3
"""Convert all PNGs under assets/ to WebP and rewrite every reference.

- cwebp -q 85 (keeps alpha; atlas textures are fine with lossy at q85)
- rewrites `.png` references to `.webp` in: index.html, assets/**/*.js,
  assets/**/*.json (atlas meta.image included)
- deletes the original PNGs (git history keeps them recoverable)
- idempotent: no-op when no PNGs remain

Run AFTER patch_main.py (this rewrites minified files in place) and BEFORE
version_assets.py (which recomputes cache hashes and the SW manifest).
"""
import pathlib
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parent
assets = root / "assets"

TEXT_SUFFIXES = {".js", ".json", ".html"}


def main() -> None:
    pngs = sorted(assets.rglob("*.png"))
    if not pngs:
        print("no PNGs left (already converted)")
    else:
        before = sum(p.stat().st_size for p in pngs)
        after = 0
        for p in pngs:
            webp = p.with_suffix(".webp")
            r = subprocess.run(
                ["cwebp", "-quiet", "-q", "85", str(p), "-o", str(webp)],
                capture_output=True,
            )
            if r.returncode != 0 or not webp.exists():
                print(f"FAILED: {p}: {r.stderr.decode()[:120]}")
                continue
            after += webp.stat().st_size
            p.unlink()
        saved = (before - after) / 1024 / 1024
        print(f"converted {len(pngs)} pngs: {before/1e6:.1f}MB -> {after/1e6:.1f}MB (-{saved:.1f}MB)")

    # rewrite references in text files
    changed = 0
    for f in [root / "index.html", *assets.rglob("*")]:
        if not f.is_file() or f.suffix.lower() not in TEXT_SUFFIXES:
            continue
        s = f.read_text(encoding="utf-8", errors="replace")
        if ".png" not in s:
            continue
        n = s.replace(".png", ".webp")
        f.write_text(n, encoding="utf-8")
        changed += 1
    print(f"rewrote .png->.webp references in {changed} files")


if __name__ == "__main__":
    sys.exit(main())
