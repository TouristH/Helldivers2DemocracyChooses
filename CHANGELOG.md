# Changelog

All notable changes to this project will be documented in this file.

## 0.2.3 - 2026-11-08

- Final retirement and migration-notice release. Marked the plugin as retired
  in its README and manifest, with no further feature maintenance planned.
- Directed random-loadout users to
  [Helldivers2DemocracyChooses](https://github.com/TouristH/Helldivers2DemocracyChooses),
  and users seeking broader war intelligence and news features to
  [fiatlux2333/maibot_plugin_Helldivers](https://github.com/fiatlux2333/maibot_plugin_Helldivers).
- Explained the scope reduction, manual migration and new group allowlist;
  preserved the old documentation and third-party attribution for reference.
- Replaced the unsupported Host upper bound `999.999.999` with `1.3.99`
  to meet the current plugin-center version format requirements. This does
  not claim new end-to-end Host validation.
- Kept the detail-link test announcement within its intended recent-news
  window instead of relying on a fixed date that expires over time.
- Kept the runtime behavior intact; this release does not automatically
  disable installed plugins or transfer their data to either replacement.

## 0.2.2 - 2026-10-21

- Checked the current Chinese and English Wiki catalogs and expanded the
  loadout pool to 221 items: 56 primaries, 26 secondaries, 24 throwables,
  20 boosters, and 95 stratagems. The seven Ironclad Democracy items were
  already present in the existing catalog.
- Added R-40 视界者, P-44 迷雾, G-11 铁蒺藜, AMW-20 尖峰, and LAS-44 新星,
  with current Chinese Wiki names and actual embedded equipment artwork.
- Updated Chinese Wiki translations, including P-34 爆破者, G-8 焚身, and
  G-60 反坦克追踪者, while retaining applicable curated baseline names.
  Only Surplus EAT Allocation and Integrated Extinguishers still use
  explicitly identified community translations.
- Retained the existing 216 icons and added five developer-render PNGs from
  the English Wiki's original-file links while its API and thumbnails were
  unavailable. The additions retain their original dimensions and include
  file-page provenance, source hashes, and embedded-content checksums.
- Documented the distinction between the historical API thumbnail bundle
  and the five full-resolution additions, their separate game-art rights,
  and the plugin registry's Release-based update and review process.
- Checked cached image dimensions and MIME types before reuse so later
  refreshes cannot label original-size artwork as a thumbnail.

## 0.2.1 - 2026-09-30

- Rejected loopback, private, link-local, local-name, metadata-service, and
  credential-bearing configurable source URLs; DNS results and every redirect
  target are rechecked before the corresponding network request.
- Preserved Clash/Mihomo Fake-IP compatibility through a narrow proxy-sentinel
  exception for the three fixed official upstream hostnames only.
- Logged an explicit warning when the MaiBot SDK is unavailable instead of
  silently entering the test-only compatibility stubs.
- Kept raw and typed render paths argument-compatible, including `selector`,
  `render_timeout_ms`, and the no-network policy; documented the SDK/Host basis
  for the extended RPC and command timeouts.
- Raised the declared SDK minimum to 2.7.1, which includes both transport
  timeouts and correctly flattened custom command metadata.

## 0.2.0 - 2026-09-30

- Rebuilt the random-loadout database as a 216-item, Chinese-only catalog with
  stable IDs, canonical English names, source pages, translation provenance,
  and per-file Wiki SHA-1 values.
- Replaced the legacy partial artwork bundle with current icons for every item,
  resolved through the Chinese Helldivers Wiki API and embedded for offline
  card rendering.
- Added a reproducible maintainer refresh tool and strict catalog, language,
  icon-coverage, integrity, and attribution tests.
- Updated third-party notices to identify the Chinese Wiki as the new icon
  source and to distinguish Wiki titles from the ten community translations.

## 0.1.1 - 2026-09-29

- Refreshed the random-loadout catalog against the current Helldivers Wiki data.
- Corrected outdated or mistranslated Chinese equipment names and added newly documented weapons, boosters, and stratagems; untranslated additions retain their canonical English names.
- Kept equipment without reusable artwork name-only in rendered cards.
- Expanded CC BY-SA 4.0 and CC BY-NC-SA 4.0 attribution and disclosed OpenAI Codex AI assistance.

## 0.1.0 - 2026-09-29

- Initial public release for MaiBot Plugin SDK 2.x.
- Added autonomous official Steam update polling and per-group delivery state.
- Added on-demand Steam and Helldivers Wiki queries with Chinese-first output.
- Added subscription, permission, rate-limit, diagnostics, and status commands.
- Added image-based random loadouts with single-slot rerolls and text fallback.
- Added WebUI configuration metadata, tests, licensing, and third-party notices.
