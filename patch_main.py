#!/usr/bin/env python3
"""Apply webdashers community patches to game main.js.

Rebuilds main.js from the pristine upstream version in git (HEAD) and applies:
  1. expose the Phaser instance + auto-download the ?id= level
  2. hook run start/complete to report scores to the site leaderboard
Then minifies in place (esbuild, run separately by build.sh or manually).

Usage: python3 patch_main.py [--no-minify]
Run from the game/ directory (or pass the repo root).
"""
import subprocess
import sys
import pathlib

root = pathlib.Path(__file__).resolve().parent
MAIN = root / "assets/scripts/core/main.js"

PATCH_ANCHOR = "new Phaser.Game(phaserConfig);"

INJECT_INSTANCE_AND_AUTOLEVEL = '''window.__wdGame = new Phaser.Game(phaserConfig);

/* webdashers community patch 1: expose instance + auto-download the ?id= level */
(function () {
  var m = location.search.match(/[?&]id=(\\d+)/);
  if (!m) return;
  var tries = 0;
  var t = setInterval(function () {
    tries++;
    var g = window.__wdGame;
    if (!g || !g.scene) { if (tries > 120) clearInterval(t); return; }
    var s = null;
    try { s = g.scene.getScene("GameScene"); } catch (e) {}
    if (!s || typeof s._openSearchResultScene !== "function") { if (tries > 120) clearInterval(t); return; }
    clearInterval(t);
    if (window.alreadydownloaded || window._onlineLevelString) return;
    window.alreadydownloaded = true;
    window.fetchGdApi("/downloadGJLevel22.php", {
      method: "POST",
      body: "levelID=" + m[1] + "&secret=Wmfd2893gb7"
    })
      .then(function (r) { return r.text(); })
      .then(function (txt) {
        var kv = {}, p = txt.split(":");
        for (var i = 0; i + 1 < p.length; i += 2) kv[p[i]] = p[i + 1];
        if (!kv[3]) throw new Error("bad response");
        window._onlineLevelString = atob(kv[3]);
        window._onlineLevelId = m[1];
        if (typeof s._openSearchResultScene === "function") {
          s._openSearchResultScene({ name: kv[1], title: kv[1], author: kv[2], songName: "" });
        }
      })
      .catch(function (e) {
        window.alreadydownloaded = false;
        console.warn("[webdashers] auto level failed:", e);
      });
  }, 400);
})();'''

INJECT_SCORE_REPORT = '''

/* webdashers community patch 2: report run results to the site leaderboard.
   The game runs same-origin in an iframe, so the session cookie rides along. */
(function () {
  function waitForScene(cb) {
    var tries = 0;
    var t = setInterval(function () {
      tries++;
      var g = window.__wdGame;
      if (!g || !g.scene) { if (tries > 150) clearInterval(t); return; }
      var s = null;
      try { s = g.scene.getScene("GameScene"); } catch (e) {}
      if (!s || typeof s._startGame !== "function" || s.__wdScoreHook) { if (tries > 150) clearInterval(t); return; }
      clearInterval(t);
      cb(s);
    }, 400);
  }
  waitForScene(function (s) {
    s.__wdScoreHook = true;
    var attempt = 0, startedAt = 0;
    window.__wdRunState = {
      get attempt() { return attempt; },
      get startedAt() { return startedAt; }
    };
    var origStart = s._startGame;
    s._startGame = function () {
      var r = origStart.apply(this, arguments);
      if (window._onlineLevelId) { attempt++; startedAt = Date.now(); }
      return r;
    };
    var origComplete = s._levelComplete;
    s._levelComplete = function () {
      var id = window._onlineLevelId;
      if (id && startedAt && !this._practiced) {
        window.__wdLastReport = { id: String(id), time_ms: Math.max(Date.now() - startedAt, 1000), attempts: attempt, progress: 100 };
        // cross-origin host: report through the parent page bridge (it owns the
        // session cookie on webdashers.io)
        try {
          window.parent.postMessage({ type: "wd-score", payload: window.__wdLastReport }, "*");
        } catch (e) {}
      }
      return origComplete.apply(this, arguments);
    };
  });
})();'''


def main() -> None:
    minify = "--no-minify" not in sys.argv
    pristine = (root / "main.pristine.js").read_text(encoding="utf-8")

    assert PATCH_ANCHOR in pristine, "anchor missing in upstream main.js"
    patched = pristine.replace(
        PATCH_ANCHOR, INJECT_INSTANCE_AND_AUTOLEVEL, 1
    ) + INJECT_SCORE_REPORT

    MAIN.write_text(patched, encoding="utf-8")
    print("patched main.js (readable form)")

    if minify:
        subprocess.run([
            "npx", "esbuild", str(MAIN), "--minify", "--allow-overwrite",
            "--log-level=error", "--outfile=" + str(MAIN),
        ], cwd=root.parent / "site", check=True)
        print("minified")


if __name__ == "__main__":
    main()
