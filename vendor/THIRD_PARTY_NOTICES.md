# Third-party notices — vendored runtime assets

Assets here are committed on purpose. They are runtime dependencies of generated
compositions and of the Source-time bakes that feed them, and fetching them from
a CDN made those steps depend on that CDN being reachable — see
`lib/gsap_runtime.py` and `.agents/skills/motion-graphics/categories/maps/bake-basemap.mjs`
for the failure modes that motivated vendoring.

## MapLibre GL JS 5.24.0 — BSD-3-Clause

`maps/maplibre-gl.js`

Copyright MapLibre contributors. Full license text:
<https://github.com/maplibre/maplibre-gl-js/blob/v5.24.0/LICENSE.txt> (the file's
own banner records the same terms).

This is the minified production build — `dist/maplibre-gl.js` from the tarball is
already minified (the 3.0 MB `maplibre-gl-dev.js` is the unminified one). There is
no smaller build that keeps the raster + `map.project()` surface the bake needs.

The companion `dist/maplibre-gl.css` is deliberately **not** vendored: it styles
controls, popups and markers, and the bake runs `interactive:false` with
`attributionControl:false` and the control container hidden. Dropping the
stylesheet was verified to produce a byte-identical frame, so it was removed
rather than vendored.

## topojson-client 3.1.0 — ISC

`maps/topojson-client.min.js`

Copyright 2019 Mike Bostock. Used to decode `countries-110m.json` into GeoJSON
features before projecting them to screen coordinates.

## world-atlas 2.0.2 — ISC

`maps/countries-110m.json`

Copyright 2013-2019 Michael Bostock. Natural Earth country boundaries at 1:110m,
as TopoJSON.

Only `countries-110m.json` (105 KB) is vendored. The package also ships
`countries-50m.json` (738 KB), `countries-10m.json` (3.6 MB) and the `land-*`
variants; the bake references none of them. If a future shot needs a finer
resolution, vendor that file explicitly and add it here — do not reintroduce a
CDN fetch.

## Obtaining / upgrading

All three come from the npm registry, not a CDN mirror:

```sh
npm pack maplibre-gl@5.24.0     # then: package/dist/maplibre-gl.js
npm pack topojson-client@3.1.0  # then: package/dist/topojson-client.min.js
npm pack world-atlas@2.0.2      # then: package/countries-110m.json
```

- Versions are pinned in `bake-basemap.mjs` as `VENDORED` and asserted at bake time.
- SHA-256:
  - `maps/maplibre-gl.js` — `45a9b07a9189ce56054c620a947ccf41e291e58c95e9b61533b740aaa65ee5cb`
  - `maps/topojson-client.min.js` — `25cd02ae486cc5063e0215a4e4cfb15de83700c87ac48bac4d57dc6aaf3ebb89`
  - `maps/countries-110m.json` — `2516c915867c7baf18ddec727aec46c315541a07cfb3d79a6559b05d5e94eee8`

To upgrade: re-pack at the new version, replace the file, update the version and
hash here and in `bake-basemap.mjs`, and re-run
`tests/skills/test_bake_basemap_fails_closed.py`. A MapLibre bump additionally
needs a visual re-check of the bake — `areTilesLoaded()` / `idle` semantics are
what the tile-error guard reasons about.

**The basemap tile endpoints (Esri, CARTO) are not vendorable and remain a live
network dependency of the bake.** Real imagery is the point of the basemap lane,
it is ToS-bound, and it is unbounded in size. Vendoring the libraries above
removes the *library* network from the bake; it does not make the bake offline.
That is what the tile-error guard in `bake-basemap.mjs` exists to catch — see
"Attribution (hard rule)" in `categories/maps/module.md` for the usage terms that
ride along with the imagery.
