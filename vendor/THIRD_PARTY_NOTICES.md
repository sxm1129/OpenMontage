# Third-party notices — vendored runtime assets

Assets here are committed on purpose. They are runtime dependencies of generated
compositions, and fetching them from a CDN at render time made every render
depend on that CDN being reachable — see `lib/gsap_runtime.py` for the failure
mode that motivated vendoring.

## GSAP 3.14.2 — GreenSock Standard License

`gsap/gsap.min.js`, `gsap/TextPlugin.min.js`, `gsap/MotionPathPlugin.min.js`

Copyright 2025, GreenSock. All rights reserved. Subject to the terms at
<https://gsap.com/standard-license>. GSAP's standard license covers the core
runtime and both plugins bundled here (each file's own banner records the same
terms).

Obtained from the npm registry, not a CDN mirror — all three come from the one
tarball, so they are version-locked to each other by construction:

```sh
npm pack gsap@3.14.2   # then: package/dist/{gsap,TextPlugin,MotionPathPlugin}.min.js
```

- Version: 3.14.2 (pinned in `lib/gsap_runtime.py` as `GSAP_VERSION`)
- SHA-256:
  - `gsap.min.js` — `c174bfce53a729418d57a8ad8625e7247c793a22fef8e2851e3cfa3de9cd8280`
  - `TextPlugin.min.js` — `14f3898c5e985cd5d985918e2368813d35e9629da4884f05d03bb3d0d10f170f`
  - `MotionPathPlugin.min.js` — `aa5f955ca4ce3095ebe5726f43a46b72532230edb3501b28fb853f189f023cab`

The two plugins are here because `.agents/skills/hyperframes-animation/` documents
techniques that require them (`techniques.md` #9 MotionPathPlugin, `rules/gsap-effects.md`
TextPlugin). Without a local copy those docs would have to teach a CDN `<script>`
tag, reintroducing the exact failure vendoring removes. `lib/gsap_runtime.py`
stages all three into every workspace; see `PLUGIN_SRCS`.

To upgrade: re-pack at the new version, replace all three files, update
`GSAP_VERSION` and the hashes above, and re-run
`tests/contracts/test_character_animation_pipeline.py`.
