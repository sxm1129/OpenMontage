# Third-party notices — vendored runtime assets

Assets here are committed on purpose. They are runtime dependencies of generated
compositions, and fetching them from a CDN at render time made every render
depend on that CDN being reachable — see `lib/gsap_runtime.py` for the failure
mode that motivated vendoring.

## GSAP 3.14.2 — GreenSock Standard License

`gsap/gsap.min.js`

Copyright 2025, GreenSock. All rights reserved. Subject to the terms at
<https://gsap.com/standard-license>. GSAP's standard license covers the core
runtime bundled here (the file's own banner records the same terms).

Obtained from the npm registry, not a CDN mirror:

```sh
npm pack gsap@3.14.2   # then: package/dist/gsap.min.js
```

- Version: 3.14.2 (pinned in `lib/gsap_runtime.py` as `GSAP_VERSION`)
- SHA-256: `c174bfce53a729418d57a8ad8625e7247c793a22fef8e2851e3cfa3de9cd8280`

To upgrade: re-pack at the new version, replace the file, update `GSAP_VERSION`
and the hash above, and re-run `tests/contracts/test_character_animation_pipeline.py`.
