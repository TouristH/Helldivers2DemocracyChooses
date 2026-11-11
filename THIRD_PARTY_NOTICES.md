# Third-party notices

This file records third-party sources used by Helldivers2DemocracyChooses. It is an
attribution record, not a new license grant.

## Source project: HelldiversPatchFeed

Helldivers2DemocracyChooses is an independent, loadout-only extraction from
[TouristH/HelldiversPatchFeed](https://github.com/TouristH/HelldiversPatchFeed/tree/555c3a5),
revision `555c3a5`, whose plugin version was `0.2.2`. The source project's
original code and documentation are Copyright (c) 2026 TouristH under the
MIT License; that copyright notice and license are retained in `LICENSE`.
Its project and AI-assisted contributions remain acknowledged in
`CONTRIBUTORS.md`.

Helldivers2DemocracyChooses starts its own version sequence at `0.1.0` and does not
carry over old announcement data. The equipment catalog and embedded icon
bundle are retained unchanged from the source project, with a catalog check
date of 2026-10-21 and 221 items. The `0.2.0` and `0.2.2` versions mentioned
below refer only to that source-project history, not Helldivers2DemocracyChooses releases.

## Helldivers 2 Random Loadout Generator CN

- Project: [Xenfo-LC/Helldivers-2-Random-Loadout-Generator-CN](https://github.com/Xenfo-LC/Helldivers-2-Random-Loadout-Generator-CN)
- Referenced revision: `141ba007b52940903b22067571d87ec0263902d6`
- Upstream project credit: original project by Erlend Dahl; Android port and
  version maintenance by Xenfo; Chinese localization credited upstream to
  GPT 5.6 Sol and Xenfo.
- Use in this repository:
  - the initial random-loadout slot structure and early catalog organization
    were developed with reference to the upstream data set;
  - the random-loadout slot organization and reroll experience in `plugin.py`
    were designed with reference to that project.

Starting with source-project version `0.2.0`, no equipment record or embedded icon in
`loadout_data.json` or `loadout_icons.json` is sourced from the upstream
`static/images` tree. The catalog and icon bundle were rebuilt from the Wiki
sources described below. The acknowledgement remains because the initial
feature design was assisted by the upstream project.

The referenced repository did not contain a standalone open-source license at
the time of review on 2026-09-29. Accordingly, the material identified above
is not represented as being licensed under this repository's MIT License.
Copyright and other rights remain with the upstream contributors and the
applicable rights holders. Redistributors must independently obtain any
permission they require.

## User-provided animated plugin icon

`assets/icon.webp` is a lossless animated-WebP conversion of the green Helldiver
helmet nodding animation supplied and selected by the user for this plugin. The supplied
file contained GIF data despite its `.jpg` filename. All 18 frames, the 96 x 96
dimensions and the frame timing were retained; no original authorship is claimed.

The original creator and redistribution license were not identified in the
attachment. This animation and the game imagery it contains are not represented
as covered by the repository's MIT License. Rights remain with the respective
creators and game-material rights holders.

## HELLDIVERS 2 material

HELLDIVERS, HELLDIVERS 2, related names, artwork, icons, and other game media
are the property of their respective rights holders, including Arrowhead Game
Studios and Sony Interactive Entertainment. This repository is an unofficial
fan project and is not affiliated with, endorsed by, or sponsored by them.

## Helldivers Wiki

The following catalog sources are credited to the **Helldivers Wiki
contributors** and were checked on 2026-10-21 for source-project version `0.2.2`:

- Chinese [武器](https://helldivers.wiki.gg/zh/wiki/武器), revision `14373`:
  primary weapons, secondary weapons, throwables, Chinese names, and
  support-weapon names;
- Chinese [战略配备](https://helldivers.wiki.gg/zh/wiki/战略配备), revision `9248`:
  the Chinese stratagem catalog and Chinese names;
- English [Weapons](https://helldivers.wiki.gg/wiki/Weapons), revision `139355`:
  catalog discovery at that check date and canonical English weapon names;
- English [Boosters](https://helldivers.wiki.gg/wiki/Boosters), revision `136929`:
  catalog discovery at that check date and canonical English booster names;
- English [Stratagems](https://helldivers.wiki.gg/wiki/Stratagems), revision
  `138203`: catalog discovery at that check date and canonical English stratagem names.

Individual Chinese item pages were also checked for translated infobox titles.
Their exact page URLs and available revision IDs are recorded per item in
`loadout_data.json`. The source-project `0.2.0` baseline used Chinese catalog revisions `6540`
and `6647`, English Weapons revision `137028`, Boosters revision `136929`,
and Stratagems revision `133897`. Established sourced or curated names and
their item-level provenance remain where no replacement was needed; the
current catalog check does not imply that every older page was fetched again.

The two Chinese pages are available under the
[Creative Commons Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/deed.zh-hans)
(CC BY-SA 4.0). The three English pages are available under the
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-nc-sa/4.0/)
(CC BY-NC-SA 4.0).

For `loadout_data.json`, this project extracted and combined the Chinese and
English catalogs, normalized model prefixes and names, assigned plugin slots,
and converted the result to JSON. The final display language is Chinese. The
current catalog contains 221 items, including five Scope of Authority additions.
Names formerly marked as community translations were updated where current
Chinese Wiki titles were available, including P-34 爆破者, G-8 焚身,
G-60 反坦克追踪者, LAS-12 钗, TD-110 风暴漩涡, and A/GM-17 瓦斯迫击哨戒炮.
Two boosters still use transparent community translations: Surplus EAT
Allocation (额外消耗性反坦克武器配额) and Integrated Extinguishers (集成灭火器).
They carry `translation_source: community_translation`; other curated labels
are likewise distinguished from direct Wiki titles. The Chinese- and
English-Wiki-derived portions of the database,
including adaptations, are redistributed under CC BY-SA 4.0 and CC BY-NC-SA
4.0 respectively. The English-derived portions are therefore subject to the
CC BY-NC-SA 4.0 non-commercial restriction.

`loadout_icons.json` retains the 216 icons originally resolved through the
Chinese Wiki API on 2026-09-30. The API resolved shared files to the Wiki's
English media repository. Historical raster artwork generally uses the API's
224-pixel thumbnail, while vector artwork retains the Wiki-provided SVG. The
previously embedded EAT PNG is intentionally retained rather than replaced
with the currently linked traced SVG.

Five additional developer-render PNGs were retrieved on 2026-10-21 through
the English Wiki file-description pages' original-file links (`format=original`)
because the Wiki API and thumbnail endpoints were unavailable during this
refresh. They retain their original dimensions, rather than a 224-pixel
thumbnail. The uploader and retrieval credit for all five is **Tech Support
Squid / Helldivers Wiki.gg**:

| Equipment | File description and revision | Embedded dimensions |
| --- | --- | --- |
| R-40 Sightliner / R-40 视界者 | [Primary Render.png](https://helldivers.wiki.gg/wiki/File:R-40_Sightliner_Primary_Render.png?oldid=138586) | 2312 × 534 |
| P-44 Mist / P-44 迷雾 | [Secondary Render.png](https://helldivers.wiki.gg/wiki/File:P-44_Mist_Secondary_Render.png?oldid=138590) | 1386 × 630 |
| G-11 Caltrops / G-11 铁蒺藜 | [Throwable Render.png](https://helldivers.wiki.gg/wiki/File:G-11_Caltrops_Throwable_Render.png?oldid=138591) | 782 × 484 |
| AMW-20 Apex / AMW-20 尖峰 | [Weapon and Backpack Support Render.png](https://helldivers.wiki.gg/wiki/File:AMW-20_Apex_Weapon_and_Backpack_Support_Render.png?oldid=138588) | 2998 × 1868 |
| LAS-44 Nova / LAS-44 新星 | [Support Render.png](https://helldivers.wiki.gg/wiki/File:LAS-44_Nova_Support_Render.png?oldid=138592) | 2985 × 659 |

The two support weapons use equipment-render PNGs instead of the traced SVG
stratagem symbols, whose separate file notices impose their own reuse terms.
The five selected file pages identify their source as developer artwork and
their licensing as Arrowhead Game Studios and its licensors under the
HELLDIVERS EULA. Their selection does not represent a new permission grant.
`loadout_icons.json` records file-page revisions, retrieval method, original
source URLs, computed source SHA-1, dimensions, and embedded SHA-256. The five
original files total about 6.6 MB; Base64 encoding brings the combined historical
and new JSON bundle to about 11 MB.

Querying or downloading a file through either Wiki language does not itself
grant additional rights in the underlying game art or apply the Wiki's text
license to an image. The HELLDIVERS 2 material section above therefore remains
controlling for game artwork, alongside each linked file's specific notice.
These images are not represented as covered by this repository's MIT License.

For release-date and equipment cross-checks, this refresh also used the official
PlayStation Blog announcements by Arrowhead Game Studios:

- [Ironclad Democracy](https://blog.playstation.com/2026/09/15/helldivers-2-ironclad-democracy-warbond-launches-sept-22/),
  published 2026-09-15 for release on 2026-09-22; its seven equipment entries
  were already present in the baseline catalog.
- [Scope of Authority](https://blog.playstation.com/2026/10/13/helldivers-2-scope-of-authority-premium-warbond-launches-oct-20/),
  published 2026-10-13 for release on 2026-10-20; its five equipment entries
  are added in `0.2.2`.

These announcements were checked on 2026-10-21. Their text, names, and media
remain subject to their respective rights holders; they are not relicensed
under MIT by this attribution.

Helldivers2DemocracyChooses does not retrieve Wiki excerpts at runtime. Its manual
maintainer refresh tool still accesses the sources above; removing the old
runtime queries does not remove the attribution or license obligations for
the bundled Wiki-derived catalog and game artwork.

## Equipment knowledge annotations

`loadout_tags.xlsx` is the primary editable runtime workbook in the `0.4.0`
development branch. `loadout_tags.csv` is its textual export and fallback.
`loadout_knowledge.json` preserves its initial research, project-authored tag
definitions, per-claim source references, and access limitations. The research
date is 2026-11-08; its equipment coverage remains the 2026-10-21 catalog.

The source registry credits Helldivers Wiki contributors, Arrowhead Game Studios
through the official PlayStation Blog, and the authors and commenters of the
linked Reddit, Bilibili, Baidu Tieba, and Steam Community discussions and guides.
For video sources, the registry distinguishes descriptions and comments actually
read from the video itself; a cited description is not a claim to have watched
the full video. Community experiences are recorded as concise
project-written annotations, not copied posts or claims of player consensus.
The Wiki-derived portions retain the respective CC BY-SA 4.0 and CC BY-NC-SA 4.0
boundaries described above; this repository does not relicense third-party
source material under MIT. Linked official and community material remains
subject to its respective rights holders and terms.

Wiki sources read through search excerpts are explicitly recorded as
`search_excerpt` with no invented revision ID. Entries depending on those
excerpts remain partially verified. The fixed, independent `player.*` tags,
including the subjective `player.toy` tag, are kept separate from mechanism
descriptions and preserve conditions, disagreement, and counterexamples where
reported. A semicolon-joined tag collection is only a review/export view, not
a composite tag or a convenience score. Editing the workbook or CSV
does not rewrite or fabricate the initial source evidence.

## Python dependencies

Python dependencies are installed from their own distributions and are not
vendored here. Each dependency remains governed by the license published by
its maintainer.

## Repository license boundary

The root MIT License applies to this project's original code and documentation.
It does not replace the CC BY-SA 4.0 or CC BY-NC-SA 4.0 terms for Wiki-derived
catalog material or the separate rights described above for referenced code,
data, game media, and embedded icons.
