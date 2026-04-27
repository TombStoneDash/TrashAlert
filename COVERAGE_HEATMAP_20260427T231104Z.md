# Coverage Heatmap — 2026-04-27

**Source:** `schedule_reports` distinct cities (108) + `collection_zones` priority set
**Method:** read-only enumeration; per-city row count, latest `updated_at`, source-label sample, zone-priority status
**Method tier classification (heuristic):**
- `1/2` — ≥10K rows, likely real per-address residential data from ArcGIS imports or DB-fallback tier
- `2/3` — 100-9,999 rows, likely zone-level descriptors
- `3` — 5-99 rows, small zone import or registry entry
- `4` — 1 row, ReCollect placeholder pattern

**Cities in `collection_zones` priority set:** 4 (long-beach, indianapolis, houston, baltimore — all with PRs in this/prior session)

---

## All cities, sorted by row count

| Slug | Rows | Tier | Last update | Source sample | In `collection_zones` | Priority set |
|---|---:|---|---|---|---|---|
| `houston` | 2,094,336 | 1/2 | — | `—` | YES | YES |
| `boston` | 743,944 | 1/2 | — | `—` |  |  |
| ⚠ `phoenix` | 714,011 | 1/2 | — | `—` |  |  |
| ⚠ `austin` | 625,673 | 1/2 | — | `—` |  |  |
| `philadelphia` | 393,753 | 1/2 | 2026-04-19T21:21:52 | `city_api` |  |  |
| ⚠ `denver` | 384,262 | 1/2 | 2026-04-14T20:40:27 | `city_api` |  |  |
| `san diego` | 358,709 | 1/2 | 2026-04-27T19:17:56 | `community` |  |  |
| ⚠ `san-antonio` | 346,785 | 1/2 | 2026-04-19T21:21:40 | `city_api` |  |  |
| `hillsborough-county-fl` | 313,445 | 1/2 | 2026-04-20T04:39:50 | `city_api` |  |  |
| `dallas` | 256,742 | 1/2 | 2026-04-17T21:16:55 | `city_api` |  |  |
| `raleigh-nc` | 245,548 | 1/2 | 2026-04-20T01:47:03 | `city_api` |  |  |
| `washington-dc` | 124,599 | 1/2 | 2026-04-19T21:39:58 | `city_api` |  |  |
| `plano-tx` | 66,437 | 1/2 | 2026-04-20T04:29:51 | `city_api` |  |  |
| `whitby-on` | 43,561 | 1/2 | 2026-04-20T04:30:13 | `city_api` |  |  |
| `baltimore` | 40,641 | 1/2 | 2026-04-20T01:49:28 | `city_api` | YES | YES |
| `escondido` | 39,181 | 1/2 | 2026-02-25T07:39:21 | `edco` |  |  |
| `south-fulton-ga` | 38,937 | 1/2 | 2026-04-20T00:47:39 | `city_api` |  |  |
| `syracuse-ny` | 38,694 | 1/2 | 2026-04-20T04:31:12 | `city_api` |  |  |
| ⚠ `san-francisco` | 36,260 | 1/2 | 2026-03-06T06:56:43 | `city_api` |  |  |
| `the-woodlands-tx` | 29,690 | 1/2 | 2026-04-20T04:15:25 | `city_api` |  |  |
| `westland-mi` | 27,256 | 1/2 | 2026-04-20T04:24:46 | `city_api` |  |  |
| `vista` | 26,283 | 1/2 | 2026-02-25T07:39:21 | `edco` |  |  |
| `lakewood` | 20,442 | 1/2 | 2026-02-25T07:39:25 | `edco` |  |  |
| `san marcos` | 18,252 | 1/2 | 2026-02-25T07:39:22 | `edco` |  |  |
| `el cajon` | 18,008 | 1/2 | 2026-02-25T07:39:09 | `edco` |  |  |
| `la mesa` | 16,548 | 1/2 | 2026-02-25T07:39:31 | `edco` |  |  |
| `wauwatosa-wi` | 16,548 | 1/2 | 2026-04-20T00:44:06 | `city_api` |  |  |
| `buena park` | 16,305 | 1/2 | 2026-02-25T07:39:24 | `edco` |  |  |
| `novi-mi` | 16,305 | 1/2 | 2026-04-20T00:42:36 | `city_api` |  |  |
| `encinitas` | 15,575 | 1/2 | 2026-02-25T07:39:13 | `edco` |  |  |
| `rancho palos verdes` | 12,168 | 1/2 | 2026-02-25T07:39:32 | `edco` |  |  |
| `bay-city` | 11,925 | 1/2 | 2026-04-20T00:40:04 | `city_api` |  |  |
| `fallbrook` | 11,681 | 1/2 | 2026-02-25T07:39:23 | `edco` |  |  |
| `la mirada` | 8,518 | 2/3 | 2026-02-25T07:39:11 | `edco` |  |  |
| `poway` | 8,518 | 2/3 | 2026-02-25T07:39:34 | `edco` |  |  |
| `spring valley` | 8,518 | 2/3 | 2026-02-25T07:39:35 | `edco` |  |  |
| `stevens-point` | 8,518 | 2/3 | 2026-04-20T00:39:22 | `city_api` |  |  |
| `londonderry-nh` | 8,031 | 2/3 | 2026-04-20T04:23:28 | `city_api` |  |  |
| `ramona` | 8,031 | 2/3 | 2026-02-25T07:39:33 | `edco` |  |  |
| `la palma` | 7,301 | 2/3 | 2026-02-25T07:38:33 | `edco` |  |  |
| `national city` | 6,814 | 2/3 | 2026-02-25T07:37:28 | `edco` |  |  |
| `lemon grove` | 6,571 | 2/3 | 2026-02-25T07:38:22 | `edco` |  |  |
| `valley center` | 6,571 | 2/3 | 2026-02-25T07:38:55 | `edco` |  |  |
| `culpeper-va` | 5,841 | 2/3 | 2026-04-20T04:15:51 | `city_api` |  |  |
| `charlotte` | 5,111 | 2/3 | 2026-04-19T21:06:47 | `city_api` |  |  |
| `cocoa-fl` | 4,867 | 2/3 | 2026-04-20T00:49:19 | `city_api` |  |  |
| `imperial beach` | 4,380 | 2/3 | 2026-02-25T07:38:26 | `edco` |  |  |
| `columbia-heights-mn` | 4,137 | 2/3 | 2026-04-20T00:52:38 | `city_api` |  |  |
| `bonita` | 3,650 | 2/3 | 2026-02-25T07:36:46 | `edco` |  |  |
| `lakeside` | 3,650 | 2/3 | 2026-02-25T07:37:02 | `edco` |  |  |
| `coronado` | 3,407 | 2/3 | 2026-02-25T07:35:43 | `edco` |  |  |
| `alpine` | 1,032 | 2/3 | 2026-02-25T07:38:05 | `edco` |  |  |
| `bonsall` | 1,032 | 2/3 | 2026-02-25T07:38:28 | `edco` |  |  |
| `chicago` | 1,032 | 2/3 | 2026-04-16T21:02:48 | `city_api` |  |  |
| `del mar` | 1,032 | 2/3 | 2026-02-25T07:36:20 | `edco` |  |  |
| `el segundo` | 1,032 | 2/3 | 2026-02-25T07:39:15 | `edco` |  |  |
| `jamul` | 1,032 | 2/3 | 2026-02-25T07:39:12 | `edco` |  |  |
| ⚠ `new-york` | 1,032 | 2/3 | 2026-04-14T20:40:56 | `city_api` |  |  |
| ⚠ `portland` | 1,032 | 2/3 | 2026-04-17T21:24:30 | `city_api` |  |  |
| `signal hill` | 1,032 | 2/3 | 2026-02-25T07:38:50 | `edco` |  |  |
| `solana beach` | 1,032 | 2/3 | 2026-02-25T07:36:55 | `edco` |  |  |
| ⚠ `portland-or` | 900 | 2/3 | 2026-04-20T03:56:18 | `city_api` |  |  |
| `nyc` | 842 | 2/3 | 2026-04-19T21:21:33 | `city_api` |  |  |
| `milwaukee` | 834 | 2/3 | 2026-04-20T01:49:54 | `city_api` |  |  |
| ⚠ `portland-me` | 827 | 2/3 | 2026-04-20T00:53:34 | `city_api` |  |  |
| `fort-worth` | 697 | 2/3 | 2026-04-19T21:06:50 | `city_api` |  |  |
| `indianapolis` | 692 | 2/3 | 2026-04-20T01:50:18 | `city_api` | YES | YES |
| `miami-dade` | 612 | 2/3 | 2026-04-20T01:50:24 | `city_api` |  |  |
| `kansas-city` | 606 | 2/3 | 2026-04-20T01:50:01 | `city_api` |  |  |
| `seattle` | 586 | 2/3 | 2026-04-19T21:10:44 | `city_api` |  |  |
| `pine valley` | 548 | 2/3 | 2026-02-25T07:39:10 | `edco` |  |  |
| `campo` | 517 | 2/3 | 2026-02-24T22:16:36 | `edco` |  |  |
| `pauma valley` | 399 | 2/3 | 2026-02-24T22:17:35 | `edco` |  |  |
| `nashville` | 378 | 2/3 | 2026-04-19T21:21:47 | `city_api` |  |  |
| `descanso` | 365 | 2/3 | 2026-02-24T22:17:36 | `edco` |  |  |
| `pittsburgh` | 356 | 2/3 | 2026-04-20T01:50:06 | `city_api` |  |  |
| `dekalb-ga` | 351 | 2/3 | 2026-04-19T21:21:43 | `city_api` |  |  |
| `tucson` | 262 | 2/3 | 2026-04-20T01:49:34 | `city_api` |  |  |
| `dulzura` | 72 | 3 | 2026-02-24T22:17:33 | `edco` |  |  |
| `la-county` | 58 | 3 | 2026-04-20T01:50:37 | `city_api` |  |  |
| `rancho santa fe` | 55 | 3 | 2026-02-24T22:17:10 | `edco` |  |  |
| `louisville` | 42 | 3 | 2026-04-20T01:49:39 | `city_api` |  |  |
| `guatay` | 36 | 3 | 2026-02-24T22:17:33 | `edco` |  |  |
| `orlando` | 30 | 3 | 2026-04-19T21:21:51 | `city_api` |  |  |
| `albuquerque` | 18 | 3 | 2026-04-20T01:47:57 | `city_api` |  |  |
| `jacksonville` | 16 | 3 | 2026-04-20T01:50:11 | `city_api` |  |  |
| `arlington-tx` | 10 | 3 | 2026-04-19T21:21:52 | `city_api` |  |  |
| ⚠ `phoenix-az` | 6 | 3 | 2026-04-19T21:21:50 | `city_api` |  |  |
| ⚠ `new york` | 3 | 4 | 2026-04-08T14:45:12 | `community` |  |  |
| ⚠ `austin-tx` | 1 | 4 | 2026-04-19T20:52:31 | `recollect_api` |  |  |
| `cambridge-ma` | 1 | 4 | 2026-04-19T20:52:33 | `recollect_api` |  |  |
| `davenport-ia` | 1 | 4 | 2026-04-19T20:52:37 | `recollect_api` |  |  |
| ⚠ `denver-co` | 1 | 4 | 2026-04-19T20:52:30 | `recollect_api` |  |  |
| `georgetown-tx` | 1 | 4 | 2026-04-19T20:52:37 | `recollect_api` |  |  |
| `halton-on` | 1 | 4 | 2026-04-19T20:52:35 | `recollect_api` |  |  |
| `hardin-id` | 1 | 4 | 2026-04-19T20:52:41 | `recollect_api` |  |  |
| `king-county-wa` | 1 | 4 | 2026-04-19T20:52:42 | `recollect_api` |  |  |
| `long beach` | 1 | 4 | 2026-02-24T22:17:10 | `edco` |  |  |
| `morris-mb` | 1 | 4 | 2026-04-19T20:52:40 | `recollect_api` |  |  |
| `ottawa-on` | 1 | 4 | 2026-04-19T20:52:29 | `recollect_api` |  |  |
| `pala` | 1 | 4 | 2026-02-24T22:13:47 | `edco` |  |  |
| `peterborough-on` | 1 | 4 | 2026-04-19T20:52:38 | `recollect_api` |  |  |
| `richmond-bc` | 1 | 4 | 2026-04-19T20:52:36 | `recollect_api` |  |  |
| `saanich-bc` | 1 | 4 | 2026-04-19T20:52:35 | `recollect_api` |  |  |
| ⚠ `san antonio` | 1 | 4 | 2026-04-24T12:38:25 | `community` |  |  |
| ⚠ `san-francisco-ca` | 1 | 4 | 2026-04-19T20:52:32 | `recollect_api` |  |  |
| `sherwood-park-ab` | 1 | 4 | 2026-04-19T20:52:39 | `recollect_api` |  |  |
| `vancouver-bc` | 1 | 4 | 2026-04-19T20:52:34 | `recollect_api` |  |  |

---

## Headlines

- **Total rows across all cities:** 7,295,395
- **Cities with `collection_zones` polygon data:** 3
  - `houston` (2,094,336 `schedule_reports` rows)
  - `baltimore` (40,641 `schedule_reports` rows)
  - `indianapolis` (692 `schedule_reports` rows)
- **Cities with ≥10K rows:** 33
- **Cities with 100-9,999 rows (mostly zone descriptors):** 45
- **Cities with <100 rows:** 30

---

## Source-label distribution

| Source label | Cities |
|---|---:|
| `city_api` | 47 |
| `edco` | 38 |
| `recollect_api` | 16 |
| `—` | 4 |
| `community` | 3 |

---

## Cities flagged for slug-dup

⚠ marker indicates the slug appears in a duplicate cluster per `SLUG_DUPS_20260427T231104Z.md`.

Cleanup recommended for:
- **austin** cluster: `austin`, `austin-tx`
- **denver** cluster: `denver`, `denver-co`
- **new york** cluster: `new york`, `new-york`
- **phoenix** cluster: `phoenix`, `phoenix-az`
- **portland** cluster: `portland`, `portland-me`, `portland-or`
- **san antonio** cluster: `san antonio`, `san-antonio`
- **san francisco** cluster: `san-francisco`, `san-francisco-ca`

---

## What this heatmap explicitly does NOT do

- Modify `schedule_reports`
- Resolve slug duplicates (handled in `migrations/2026XX_normalize_city_slugs.sql.draft`)
- Re-import any city
- Update `SOURCE_REGISTRY.md` (entries are added per-city as PRs ship — see PR #11/#13/#14/#16)
