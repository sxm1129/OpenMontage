// bake-basemap.mjs — canonical basemap-lane helper for the `maps` skill.
//
// WHAT IT DOES (and why baking at all): drives MapLibre in headless Chrome to record ONLY the
// real-imagery basemap as an MP4 (camera zoom→hold), and projects each requested country's border
// to SCREEN coordinates at the held view. The HF composition then plays the MP4 on track 0 and
// animates a *live* SVG overlay (border draw-on, colour-block / flag fills, labels, pins) from the
// exported `coords.json`. Borders/fills are NOT baked into the video — they stay editable in HF.
//
// Why bake the imagery at all (this is the real reason, not "smoothness"): HF forbids render-time
// network and requires deterministic output. Live raster tiles re-fetch every render and can change
// → non-deterministic. Baking FREEZES the imagery into pixels = deterministic + offline-reproducible.
// (Exposing the engine's per-frame `onBeforeCapture` hook would let MapLibre run live and smooth, but
// it would NOT remove the need to freeze tiles for determinism — so this bake step stays relevant.)
//
// PARAMETRIC — drive everything by env. Example (Brazil + Argentina on satellite):
//   NAME=br-ar STYLE=satellite COUNTRIES="Brazil:#22d3ee,Argentina:#f59e0b" \
//   CENTER="-60,-25" ZSTART=2.4 ZEND=3.4 FPS=30 DUR=5 node bake-basemap.mjs
// Then encode frames-<NAME>/f%04d.png → <NAME>.mp4 (all-intra: -g 1) and feed <NAME>-coords.json
// to the HF composition.
//
// FAILING CLOSED (why the guards below are not optional): this bake has two network
// dependencies, and they are not the same kind of thing.
//   - The LIBRARIES (maplibre, topojson, world-atlas) used to come from jsdelivr. They are
//     now vendored under vendor/maps/ and read off disk — no network, no CDN outage.
//   - The TILES (Esri/CARTO) cannot be vendored: real imagery is the point of the basemap
//     lane, it is ToS-bound and unbounded in size. The tile fetch is irreducible.
// A failed tile fetch used to fail OPEN, which is the whole reason this file grew guards:
// MapLibre's areTilesLoaded() counts an *errored* tile as loaded, so `idle` fires normally,
// the idle-timeout check never arms, and the bake emitted a 1920x1080 MP4 of solid #05070d
// with exit 0 and the line "all N frames reached map idle (complete tiles)" — a silent
// downgrade of the kind AGENT_GUIDE.md forbids. Hence: count tile errors off the map's own
// error event, and treat any of them as fatal. Do not soften this to a warning.
import puppeteer from "puppeteer-core";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";
import { mkdirSync, writeFileSync, readFileSync, readdirSync, existsSync, rmSync } from "node:fs";
import { homedir } from "node:os";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- resolve Chrome dynamically (no hardcoded machine path) ---
function resolveChrome() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  const exe = process.platform === "win32" ? "chrome-headless-shell.exe" : "chrome-headless-shell";
  const base = join(homedir(), ".cache", "puppeteer", "chrome-headless-shell");
  if (existsSync(base)) {
    for (const v of readdirSync(base).sort().reverse()) {
      // lexical sort; any working binary is fine
      try {
        for (const inner of readdirSync(join(base, v))) {
          const bin = join(base, v, inner, exe);
          if (existsSync(bin)) return bin;
        }
      } catch {
        /* skip */
      }
    }
  }
  for (const c of [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ])
    if (existsSync(c)) return c;
  throw new Error(
    "Chrome not found. Set CHROME=/path/to/chrome-headless-shell, or install one:\n" +
      "  npx puppeteer browsers install chrome-headless-shell",
  );
}

// --- vendored libs (no CDN on the bake path) ---
// Pinned exact: a mutable @5/@2 major would drift the bake over time, and a CDN fetch would
// put a third-party host on a step that must be reproducible. vendor/THIRD_PARTY_NOTICES.md
// carries the licenses, hashes and the `npm pack` recipe to refresh these.
const VENDORED = {
  "maplibre-gl.js": "5.24.0",
  "topojson-client.min.js": "3.1.0",
  "countries-110m.json": "2.0.2", // world-atlas
};

// Walk up for vendor/maps rather than hardcoding ../../../../../ — the skill tree gets
// relocated (module.md is explicit that artifacts go to cwd, "NOT the installed skill dir"),
// and a brittle relative hop would break silently on the next reshuffle.
function resolveVendorDir() {
  if (process.env.MAPS_VENDOR_DIR) return resolve(process.env.MAPS_VENDOR_DIR);
  const tried = [];
  for (let dir = __dirname; ; dir = dirname(dir)) {
    const candidate = join(dir, "vendor", "maps");
    tried.push(candidate);
    if (existsSync(candidate)) return candidate;
    if (dirname(dir) === dir) break; // hit the filesystem root
  }
  throw new Error(
    "Vendored map libs not found. They are committed to the repo on purpose — the bake must " +
      "not fetch them from a CDN. Set MAPS_VENDOR_DIR, or restore vendor/maps/ per " +
      "vendor/THIRD_PARTY_NOTICES.md.\nLooked in:\n  " +
      tried.join("\n  "),
  );
}

const VENDOR_DIR = resolveVendorDir();

function readVendored(name) {
  const source = join(VENDOR_DIR, name);
  if (!existsSync(source))
    throw new Error(
      `Vendored file missing at ${source} (pinned ${VENDORED[name]}). It is committed to the ` +
        "repo on purpose — the bake must not fetch it from a CDN. Restore it per " +
        "vendor/THIRD_PARTY_NOTICES.md.",
    );
  return readFileSync(source, "utf8");
}

// --- params (all overridable by env) ---
const NAME = process.env.NAME || "basemap";
const STYLE = process.env.STYLE || "satellite"; // satellite | dark | light | raw {z}/{x}/{y} template
const CENTER = (process.env.CENTER || "2.6,46.6").split(",").map(Number);
const ZSTART = +(process.env.ZSTART || 4.2);
const ZEND = +(process.env.ZEND || 5.4);
const PITCH = +(process.env.PITCH || 0);
const BEARING = +(process.env.BEARING || 0);
const FPS = +(process.env.FPS || 30),
  DUR = +(process.env.DUR || 5),
  N = Math.max(1, Math.round(FPS * DUR));
const HOLD = +(process.env.HOLD || 0.5); // p∈[0,1] at which the zoom finishes; camera holds after
const MARGIN = (process.env.KEEPMARGIN || "16,13").split(",").map(Number); // [lon°,lat°] keep-box around each country's mainland
// COUNTRIES="Name:#hex,Name:#hex" — borders to project (optional; omit for a pure zoom-to / pin shot)
const COUNTRIES = (process.env.COUNTRIES || "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean)
  .map((s) => {
    const [name, color] = s.split(":");
    return { name, color: color || "#38bdf8" };
  });

// fail fast on bad numeric env — otherwise NaN silently bakes zero/garbage frames and still prints "done"
for (const [k, v] of Object.entries({
  "CENTER.lng": CENTER[0],
  "CENTER.lat": CENTER[1],
  ZSTART,
  ZEND,
  PITCH,
  BEARING,
  FPS,
  DUR,
  HOLD,
}))
  if (!Number.isFinite(v))
    throw new Error(
      `bad numeric env: ${k}=${v} — check CENTER="lng,lat" / ZSTART / ZEND / FPS / DUR`,
    );

// IMPORTANT: tileSize:256 matches Esri/CARTO raster endpoints. MapLibre's INTERNAL world width is
// 512·2^zoom regardless — a 512px (@2x/retina/vector) tile source needs tileSize:512 or every zoom
// level is off by one. Keep 256 for these raster sources.
const TILES =
  {
    satellite:
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    dark: "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    light: "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
  }[STYLE] || STYLE; // STYLE may also be a raw {z}/{x}/{y} template

const OUT = process.env.OUT || process.cwd(); // artifacts → workspace (cwd), NOT the installed skill dir
const framesDir = join(OUT, "frames-" + NAME);
mkdirSync(framesDir, { recursive: true });

// maplibre-gl.css is intentionally absent: it styles controls/popups/markers, and this page runs
// interactive:false + attributionControl:false with the control container hidden. Verified to
// render a byte-identical frame without it, so it isn't vendored at all.
const SHELL = `<!doctype html><html><head>
<style>*{margin:0}html,body{width:1920px;height:1080px;overflow:hidden;background:#05070d}#map{width:1920px;height:1080px}.maplibregl-control-container{display:none!important}</style>
</head><body><div id="map"></div></body></html>`;

// The page logic runs only after the vendored libs are injected (see addScriptTag order below).
const LOGIC = `
var CENTER=${JSON.stringify(CENTER)}, ZSTART=${ZSTART}, ZEND=${ZEND}, PITCH=${PITCH}, BEARING=${BEARING}, HOLD=${HOLD};
var MARGIN=${JSON.stringify(MARGIN)}, WANT=${JSON.stringify(COUNTRIES)};
var map=new maplibregl.Map({container:"map",style:{version:8,projection:{type:"mercator"},
  sources:{s:{type:"raster",tiles:[${JSON.stringify(TILES)}],tileSize:256,maxzoom:19}},
  layers:[{id:"bg",type:"background",paint:{"background-color":"#05070d"}},{id:"s",type:"raster",source:"s"}]},
  center:CENTER,zoom:ZSTART,pitch:0,bearing:0,interactive:false,attributionControl:false,fadeDuration:0,preserveDrawingBuffer:true,maxTileCacheSize:6000});
// TILE ERROR HOOK — the load-bearing guard. Registered before any tile request so nothing is
// missed. areTilesLoaded()/idle cannot be used to detect this: an errored tile counts as loaded,
// which is exactly how a fully-blank bake used to sail through with exit 0.
window.__tileErrors=[];
map.on("error", function(e){
  var err = e && e.error;
  window.__tileErrors.push({
    msg: (err && err.message) ? err.message : String(err || "unknown map error"),
    status: (err && err.status) || null,
    url: (err && err.url) || null,
    source: (e && e.sourceId) || null
  });
});
function ease(x){return x<0.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;} // easeInOutCubic (= Remotion interpolate+Easing)
function camAt(p){ var t=ease(Math.min(1,p/HOLD)); return {center:CENTER, zoom:ZSTART+(ZEND-ZSTART)*t, pitch:PITCH*t, bearing:BEARING*t}; }
function ringCentroid(r){ var sx=0,sy=0; for(var k=0;k<r.length;k++){sx+=r[k][0];sy+=r[k][1];} return [sx/r.length, sy/r.length]; }
// Keep the polygons in a lon/lat box around the country's MAINLAND (the vertex-richest polygon),
// dropping far-flung overseas territories that would blow up the bbox. Generalizes per subject —
// no continent-specific constant. Keeps near islands (Corsica, Sicily); drops Guiana, Alaska, Hawaii.
function mainland(f){
  if(!f) return f;
  if(f.geometry.type!=="MultiPolygon"){ f.__anchorRing=f.geometry.coordinates[0]; return f; } // Polygon: outer ring
  var polys=f.geometry.coordinates, anchor=polys[0], amax=-1;
  polys.forEach(function(poly){ if(poly[0].length>amax){amax=poly[0].length;anchor=poly;} });
  var ac=ringCentroid(anchor[0]);
  var kept=polys.filter(function(poly){ var c=ringCentroid(poly[0]); return Math.abs(c[0]-ac[0])<=MARGIN[0] && Math.abs(c[1]-ac[1])<=MARGIN[1]; });
  var nf={type:"Feature",properties:f.properties,geometry:{type:"MultiPolygon",coordinates:kept}}; nf.__anchorRing=anchor[0]; return nf;
}
function lonSpan(f){ var mn=1e9,mx=-1e9; (f.geometry.type==="Polygon"?[f.geometry.coordinates]:f.geometry.coordinates).forEach(function(poly){poly[0].forEach(function(c){if(c[0]<mn)mn=c[0];if(c[0]>mx)mx=c[0];});}); return mx-mn; }
// ANTIMERIDIAN unwrap (Russia/Fiji/NZ): make all lon contiguous around the camera-center ref so a
// feature touching ±180° doesn't smear when map.project() runs per-vertex (mercatorX is linear and
// accepts out-of-range lon, so 181 sits just east of center, not far-west at -179). Mutates in place;
// __anchorRing shares the same arrays so it's covered.
function unwrapLon(f, ref){ if(!f) return; function fix(r){ for(var i=0;i<r.length;i++){ var lon=r[i][0]; while(lon-ref>180)lon-=360; while(lon-ref<-180)lon+=360; r[i][0]=lon; } }
  var g=f.geometry; if(g.type==="Polygon") g.coordinates.forEach(fix); else g.coordinates.forEach(function(poly){ poly.forEach(fix); }); }
var FEATS=[]; window.__warn=[]; window.__missing=[];
// WORLD_ATLAS is injected from vendor/maps/countries-110m.json before this script runs. It used
// to be a fetch() with no .catch(), so a jsdelivr blip left this promise forever unresolved and
// the whole bake hung until someone killed it. Reading it off disk removes both the hang and the
// dependency; the try/catch below turns any remaining decode failure into a rejection, never a hang.
window.__ready=new Promise(function(res, rej){ map.on("load", function(){
  try {
    if(!WANT.length){ res(); return; }
    var fc=topojson.feature(WORLD_ATLAS, WORLD_ATLAS.objects.countries);
    WANT.forEach(function(want){
      var f=fc.features.filter(function(x){return x.properties.name===want.name;})[0];
      // Fatal, not a warning: an unmatched name silently wrote {"countries":[]} and exited 0,
      // handing the HF composition a basemap with no borders to animate.
      if(!f){ window.__missing.push(want.name); return; }
      f=mainland(f);
      unwrapLon(f, CENTER[0]); // antimeridian: unwrap lons around the camera ref (CENTER must be near the subject) before projecting
      if(lonSpan(f)>180) window.__warn.push(want.name+" spans >180° lon even after unwrap — projection may still smear.");
      FEATS.push({name:want.name, color:want.color, f:f});
    });
    res();
  } catch(e) { rej(e); }
});});
window.__setCam=function(p){ map.jumpTo(camAt(p)); };
// returns true if the idle event did NOT fire within ms (i.e. tiles may be incomplete)
// returns true only if tiles are GENUINELY not loaded at timeout — CARTO/Esri idle is flaky and
// often never fires even when every tile is painted, so check areTilesLoaded() before crying timeout.
window.__waitIdle=function(ms){ return new Promise(function(res){ var done=false; function fin(t){if(done)return;done=true;res(t);} map.once("idle",function(){fin(false);}); setTimeout(function(){ fin(!map.areTilesLoaded()); }, ms||9000); }); };
function featurePath(f){ function ring(r){ return r.map(function(c,i){ var p=map.project(c); return (i?"L":"M")+p.x.toFixed(1)+" "+p.y.toFixed(1); }).join(" ")+"Z"; }
  var g=f.geometry,d=""; if(g.type==="Polygon") g.coordinates.forEach(function(r){d+=ring(r);}); else g.coordinates.forEach(function(poly){poly.forEach(function(r){d+=ring(r);});}); return d; }
function bboxOf(f){ var mnx=1e9,mny=1e9,mxx=-1e9,mxy=-1e9;
  function eat(r){ r.forEach(function(c){ var p=map.project(c); if(p.x<mnx)mnx=p.x; if(p.y<mny)mny=p.y; if(p.x>mxx)mxx=p.x; if(p.y>mxy)mxy=p.y; }); }
  var g=f.geometry; if(g.type==="Polygon")g.coordinates.forEach(eat); else g.coordinates.forEach(function(poly){poly.forEach(eat);});
  return {x:+mnx.toFixed(1),y:+mny.toFixed(1),w:+(mxx-mnx).toFixed(1),h:+(mxy-mny).toFixed(1)}; }
window.__project=function(){ return {
  view:{center:CENTER, zoom:ZEND, pitch:PITCH, bearing:BEARING},
  countries: FEATS.map(function(e){ var lc=ringCentroid(e.f.__anchorRing); var lp=map.project(lc);
    return { name:e.name, color:e.color, d:featurePath(e.f), bbox:bboxOf(e.f), label:{x:+lp.x.toFixed(1),y:+lp.y.toFixed(1)} }; }),
}; };
`;

// Read the vendored libs before launching Chrome: a missing file is then an instant, obvious
// failure instead of one that first pays for a browser spin-up. topojson/world-atlas are only
// needed when borders were requested.
const LIB_MAPLIBRE = readVendored("maplibre-gl.js");
const LIB_TOPOJSON = COUNTRIES.length ? readVendored("topojson-client.min.js") : null;
const ATLAS_JSON = COUNTRIES.length ? readVendored("countries-110m.json") : null;

// --no-sandbox is intentional: trusted Source-time bake, headless, often root/CI; deps are version-pinned above.
const browser = await puppeteer.launch({
  executablePath: resolveChrome(),
  headless: true,
  args: [
    "--no-sandbox",
    "--hide-scrollbars",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--enable-webgl",
    "--window-size=1920,1080",
  ],
});
// Nothing after this point may leave a consumable artifact behind on failure — see failClosed().
const mp4 = join(OUT, NAME + ".mp4"),
  coordsPath = join(OUT, NAME + "-coords.json"),
  pat = join(framesDir, "f%04d.png");

// A half-good bake is worse than no bake: it looks like an asset, so it gets consumed. Remove the
// two files the HF composition actually reads, and point at the frames as evidence rather than
// deleting them — a blank PNG is how you diagnose this in ten seconds.
//
// Throws rather than calling process.exit() so the `finally` below still closes the browser —
// process.exit() skips finally blocks and would orphan a headless Chrome on every failed bake.
class BakeFailure extends Error {}
function failClosed(headline, detail) {
  for (const stale of [mp4, coordsPath]) if (existsSync(stale)) rmSync(stale, { force: true });
  // Only advertise frames when some were actually captured — the pre-bake guards fail with the
  // directory still empty, and pointing at nothing sends the reader on a hunt.
  const baked = existsSync(framesDir) && readdirSync(framesDir).some((f) => f.endsWith(".png"));
  throw new BakeFailure(
    `${headline}${detail ? "\n" + detail : ""}\n  No MP4/coords written (any partial ones removed).` +
      (baked ? ` Suspect frames left in ${framesDir} for inspection.` : ""),
  );
}

try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
  await page.setContent(SHELL, { waitUntil: "load" });
  // Inject vendored libs in dependency order, then the page logic. addScriptTag sets textContent
  // rather than re-parsing HTML, so minified payloads can't break out of the tag.
  await page.addScriptTag({ content: LIB_MAPLIBRE });
  if (COUNTRIES.length) {
    await page.addScriptTag({ content: LIB_TOPOJSON });
    await page.addScriptTag({ content: `var WORLD_ATLAS=${ATLAS_JSON};` });
  }
  // Vendored files exist but didn't define what they should → a corrupt/truncated copy. Say that,
  // rather than letting it surface later as "(intermediate value) is not iterable".
  const libs = await page.evaluate(() => ({
    maplibre: typeof window.maplibregl !== "undefined",
    topojson: typeof window.topojson !== "undefined",
    atlas: typeof window.WORLD_ATLAS !== "undefined",
  }));
  if (!libs.maplibre)
    failClosed(
      "vendored maplibre-gl.js loaded but did not define `maplibregl`.",
      `  Check ${join(VENDOR_DIR, "maplibre-gl.js")} against the SHA-256 in vendor/THIRD_PARTY_NOTICES.md.`,
    );
  if (COUNTRIES.length && (!libs.topojson || !libs.atlas))
    failClosed(
      `vendored ${!libs.topojson ? "topojson-client.min.js" : "countries-110m.json"} loaded but did not define what it should.`,
      "  Check the SHA-256s in vendor/THIRD_PARTY_NOTICES.md.",
    );

  await page.addScriptTag({ content: LOGIC });
  // `await page.evaluate(() => window.__ready)` resolves to undefined — not an error — if LOGIC
  // never ran, which would walk straight past every guard below on a page with no map at all.
  // Assert the handles exist before trusting anything they report.
  const wired = await page.evaluate(
    () => typeof window.__ready !== "undefined" && typeof window.__setCam === "function",
  );
  if (!wired)
    failClosed(
      "page logic did not initialize — window.__ready/__setCam are missing.",
      "  The map was never constructed, so no frame would contain imagery.",
    );

  // Bounded: a WebGL/style failure could leave "load" unfired, and an unbounded await here is how
  // this script used to hang forever rather than report.
  const READY_TIMEOUT = +(process.env.READY_TIMEOUT || 60000);
  await Promise.race([
    page.evaluate(() => window.__ready),
    new Promise((_, rej) =>
      setTimeout(
        () => rej(new Error(`map never became ready within ${READY_TIMEOUT}ms`)),
        READY_TIMEOUT,
      ),
    ),
  ]).catch((e) =>
    failClosed(
      String(e.message || e),
      "  Re-run with a larger READY_TIMEOUT if the machine is slow.",
    ),
  );

  const missing = await page.evaluate(() => window.__missing);
  if (missing.length)
    failClosed(
      `country not found in world-atlas: ${missing.join(", ")}`,
      '  Names must match world-atlas exactly (e.g. "United States of America", not "USA").\n' +
        "  Baking anyway would write an empty coords.json and hand HF a basemap with no borders.",
    );

  for (const w of await page.evaluate(() => window.__warn)) console.warn(`[${NAME}] WARN: ${w}`);
  console.log(
    `[${NAME}] ready (${STYLE}); baking ${N} frames, zoom ${ZSTART}→${ZEND} hold@p=${HOLD}, ${COUNTRIES.length} border(s)`,
  );
  // Group by failure SHAPE, not raw message: every tile carries its own URL, so keying on the
  // message would print one line per tile (52 identical-but-for-the-URL lines on a dead endpoint).
  // "50x connection refused / 2x 404" is the diagnosis; one sample URL each is enough to act on.
  const describeTileErrors = (errs) => {
    const urlRe = /https?:\/\/\S+/;
    const byKind = new Map();
    for (const e of errs) {
      const kind =
        String(e.msg)
          .replace(new RegExp(urlRe.source, "g"), "")
          .replace(/[:\s]+$/, "")
          .trim() || "unknown error";
      const key = `${e.status ? `HTTP ${e.status} — ` : ""}${kind}${e.source ? ` (source: ${e.source})` : ""}`;
      if (!byKind.has(key))
        byKind.set(key, { n: 0, sample: e.url || (String(e.msg).match(urlRe) || [])[0] || null });
      byKind.get(key).n++;
    }
    const lines = [...byKind]
      .sort((a, b) => b[1].n - a[1].n)
      .slice(0, 5)
      .map(([k, v]) => `    ${v.n}x  ${k}${v.sample ? `\n           e.g. ${v.sample}` : ""}`);
    if (byKind.size > 5) lines.push(`    … and ${byKind.size - 5} other failure kind(s)`);
    return lines.join("\n");
  };

  let coords = null;
  const timeouts = [];
  for (let i = 0; i < N; i++) {
    const p = N === 1 ? 1 : i / (N - 1);
    await page.evaluate((pp) => window.__setCam(pp), p);
    const timedOut = await page.evaluate((ms) => window.__waitIdle(ms), 9000);
    if (timedOut) {
      timeouts.push(i);
      console.warn(`[${NAME}] idle TIMEOUT at frame ${i} — tiles may be incomplete`);
    }
    const tileErrors = await page.evaluate(() => window.__tileErrors);
    if (tileErrors.length)
      failClosed(
        `${tileErrors.length} tile error(s) by frame ${i} — the basemap imagery is incomplete or absent.`,
        `  Tile source: ${TILES}\n${describeTileErrors(tileErrors)}\n` +
          "  The camera holds a real-imagery view; without tiles the frames are flat background.\n" +
          "  Check the tile endpoint is reachable and its URL template is correct, then re-run.",
      );
    await page.screenshot({
      path: join(framesDir, `f${String(i).padStart(4, "0")}.png`),
      clip: { x: 0, y: 0, width: 1920, height: 1080 },
      optimizeForSpeed: true,
    });
    if (p >= HOLD && !coords && COUNTRIES.length)
      coords = await page.evaluate(() => window.__project()); // capture at first hold frame
    if (i % 20 === 0 || i === N - 1) console.log(`  [${NAME}] ${i + 1}/${N}`);
  }
  // Check before encoding, not after: a suspect bake shouldn't cost an ffmpeg pass, and it must
  // never reach disk as a playable MP4 in the first place.
  if (timeouts.length)
    failClosed(
      `${timeouts.length}/${N} frame(s) hit the idle timeout (frames ${timeouts.slice(0, 8).join(",")}${timeouts.length > 8 ? "…" : ""}) — tiles were still incomplete when captured.`,
      "  Re-run with a slower zoom / larger timeout, or check the tile server.",
    );
  // HOLD > 1 means the camera never reaches the hold, so __project() never ran. Without this the
  // bake would write an MP4 and no coords.json, leaving HF with nothing to align overlays to.
  if (COUNTRIES.length && !coords)
    failClosed(
      `no hold frame was reached, so ${COUNTRIES.length} border(s) were never projected.`,
      `  HOLD=${HOLD} must be <= 1 (it is the progress point p at which the zoom finishes).`,
    );

  // encode frames → all-intra MP4 (every frame seekable for HF); fall back to printing the command if ffmpeg is absent
  const ff = spawnSync(
    "ffmpeg",
    [
      "-y",
      "-framerate",
      String(FPS),
      "-i",
      pat,
      "-c:v",
      "libx264",
      "-pix_fmt",
      "yuv420p",
      "-g",
      "1",
      "-crf",
      "16",
      "-movflags",
      "+faststart",
      mp4,
    ],
    { stdio: "ignore" },
  );
  if (ff.status === 0) console.log(`[${NAME}] encoded → ${mp4}`);
  else
    console.warn(
      `[${NAME}] ffmpeg unavailable (status ${ff.status}) — encode manually:\n  ffmpeg -y -framerate ${FPS} -i ${pat} -c:v libx264 -pix_fmt yuv420p -g 1 -crf 16 -movflags +faststart ${mp4}`,
    );
  if (coords) {
    writeFileSync(coordsPath, JSON.stringify(coords));
    console.log(
      `[${NAME}] coords written: ${coords.countries.map((c) => c.name + "(" + c.d.length + "ch)").join(", ")}`,
    );
  }
  // Only claims what was actually verified: zero tile errors from the map's own error event, and
  // every frame reached idle. The old wording asserted "complete tiles" off the idle check alone,
  // which is satisfied just as happily by tiles that all failed to load.
  console.log(
    `[${NAME}] done — ${N} frames, 0 tile errors, all reached map idle (verified complete tiles).`,
  );
} catch (e) {
  if (!(e instanceof BakeFailure)) throw e; // a real crash keeps its stack
  console.error(`[${NAME}] BAKE FAILED — ${e.message}`);
  process.exitCode = 1;
} finally {
  await browser.close();
}
