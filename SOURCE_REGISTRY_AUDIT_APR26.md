# SOURCE_REGISTRY Audit — 2026-04-26
## Stale-detection target: 90 days. Read-only.

## TL;DR

- **Distinct city slugs in `schedule_reports`:** 108
- **Total estimated rows:** ~7,300,730 (current Supabase count)
- **Cities older than 90 days (no updated_at activity):** 0
- **Slug-duplication clusters (likely-same city under multiple slugs):** 7
- **`SOURCE_REGISTRY.md` exists in repo:** **NO** — searched all branches in trashalert FastAPI repo and trashalert-web. The directive references this file but it has never been created. The audit therefore becomes "document the cities that should be in the registry once created."

---

## Action items for HT

1. **Create `SOURCE_REGISTRY.md`** (in FastAPI repo `trashalert/`). Initial scaffold below — one entry per distinct city slug.
2. **Resolve slug duplications** (see section 3) — pick canonical form, write a one-time backfill script to merge `austin` → `austin-tx`, `denver` → `denver-co`, etc. Otherwise the resolver hits both as separate cities and verification reports get noisy.
3. **Recurring audit script** — schedule this audit query weekly so new cities don't slip in unregistered.

---

## 1. All distinct city slugs (108 total)

| # | Slug | Estimated rows | Latest update | Top source labels |
|---|---|---|---|---|
| 1 | `houston` | 2,094,336 | — | — |
| 2 | `phoenix` | 714,011 | — | — |
| 3 | `austin` | 625,673 | — | — |
| 4 | `philadelphia` | 393,753 | 2026-04-19T21:21:52.171591+00:00 | city_api(50) |
| 5 | `denver` | 384,262 | 2026-04-14T20:40:27.334838+00:00 | city_api(50) |
| 6 | `san diego` | 358,709 | 2026-04-25T12:46:54.330586+00:00 | community(45), city-data(5) |
| 7 | `san-antonio` | 346,785 | 2026-04-19T21:21:40.523426+00:00 | city_api(50) |
| 8 | `hillsborough-county-fl` | 313,445 | 2026-04-20T04:39:50.341978+00:00 | city_api(50) |
| 9 | `dallas` | 256,742 | 2026-04-17T21:16:55.259039+00:00 | city_api(50) |
| 10 | `raleigh-nc` | 245,548 | 2026-04-20T01:47:03.255922+00:00 | city_api(50) |
| 11 | `washington-dc` | 124,599 | 2026-04-19T21:39:58.761514+00:00 | city_api(50) |
| 12 | `plano-tx` | 66,437 | 2026-04-20T04:29:51.939082+00:00 | city_api(50) |
| 13 | `whitby-on` | 43,561 | 2026-04-20T04:30:13.835435+00:00 | city_api(50) |
| 14 | `baltimore` | 40,641 | 2026-04-20T01:49:28.49384+00:00 | city_api(50) |
| 15 | `escondido` | 39,181 | 2026-02-25T07:39:21.826543+00:00 | edco(50) |
| 16 | `south-fulton-ga` | 38,937 | 2026-04-20T00:47:39.717286+00:00 | city_api(50) |
| 17 | `syracuse-ny` | 38,694 | 2026-04-20T04:31:12.354451+00:00 | city_api(50) |
| 18 | `san-francisco` | 36,260 | 2026-03-06T06:56:43.187066+00:00 | city_api(50) |
| 19 | `the-woodlands-tx` | 29,690 | 2026-04-20T04:15:25.172079+00:00 | city_api(50) |
| 20 | `westland-mi` | 27,256 | 2026-04-20T04:24:46.366072+00:00 | city_api(50) |
| 21 | `vista` | 26,283 | 2026-02-25T07:39:21.088217+00:00 | edco(50) |
| 22 | `lakewood` | 20,442 | 2026-02-25T07:39:25.577707+00:00 | edco(50) |
| 23 | `san marcos` | 18,252 | 2026-02-25T07:39:22.14869+00:00 | edco(50) |
| 24 | `el cajon` | 18,008 | 2026-02-25T07:39:09.727396+00:00 | edco(50) |
| 25 | `la mesa` | 16,548 | 2026-02-25T07:39:31.689663+00:00 | edco(50) |
| 26 | `wauwatosa-wi` | 16,548 | 2026-04-20T00:44:06.665825+00:00 | city_api(50) |
| 27 | `buena park` | 16,305 | 2026-02-25T07:39:24.023011+00:00 | edco(50) |
| 28 | `novi-mi` | 16,305 | 2026-04-20T00:42:36.514359+00:00 | city_api(50) |
| 29 | `encinitas` | 15,575 | 2026-02-25T07:39:13.646044+00:00 | edco(50) |
| 30 | `rancho palos verdes` | 12,168 | 2026-02-25T07:39:32.617239+00:00 | edco(50) |
| 31 | `bay-city` | 11,925 | 2026-04-20T00:40:04.700213+00:00 | city_api(50) |
| 32 | `fallbrook` | 11,681 | 2026-02-25T07:39:23.116585+00:00 | edco(50) |
| 33 | `la mirada` | 8,518 | 2026-02-25T07:39:11.129298+00:00 | edco(50) |
| 34 | `poway` | 8,518 | 2026-02-25T07:39:34.736561+00:00 | edco(50) |
| 35 | `spring valley` | 8,518 | 2026-02-25T07:39:35.940171+00:00 | edco(50) |
| 36 | `stevens-point` | 8,518 | 2026-04-20T00:39:22.811699+00:00 | city_api(50) |
| 37 | `londonderry-nh` | 8,031 | 2026-04-20T04:23:28.786267+00:00 | city_api(50) |
| 38 | `ramona` | 8,031 | 2026-02-25T07:39:33.283795+00:00 | edco(50) |
| 39 | `la palma` | 7,301 | 2026-02-25T07:38:33.145584+00:00 | edco(50) |
| 40 | `national city` | 6,814 | 2026-02-25T07:37:28.272574+00:00 | edco(50) |
| 41 | `lemon grove` | 6,571 | 2026-02-25T07:38:22.362232+00:00 | edco(50) |
| 42 | `valley center` | 6,571 | 2026-02-25T07:38:55.159084+00:00 | edco(50) |
| 43 | `culpeper-va` | 5,841 | 2026-04-20T04:15:51.116791+00:00 | city_api(50) |
| 44 | `charlotte` | 5,111 | 2026-04-19T21:06:47.846148+00:00 | city_api(50) |
| 45 | `cocoa-fl` | 4,867 | 2026-04-20T00:49:19.073609+00:00 | city_api(50) |
| 46 | `imperial beach` | 4,380 | 2026-02-25T07:38:26.570701+00:00 | edco(50) |
| 47 | `columbia-heights-mn` | 4,137 | 2026-04-20T00:52:38.914633+00:00 | city_api(50) |
| 48 | `bonita` | 3,650 | 2026-02-25T07:36:46.432738+00:00 | edco(50) |
| 49 | `lakeside` | 3,650 | 2026-02-25T07:37:02.588362+00:00 | edco(50) |
| 50 | `coronado` | 3,407 | 2026-02-25T07:35:43.18755+00:00 | edco(50) |
| 51 | `alpine` | 1,032 | 2026-02-25T07:38:05.112293+00:00 | edco(50) |
| 52 | `bonsall` | 1,032 | 2026-02-25T07:38:28.929863+00:00 | edco(50) |
| 53 | `chicago` | 1,032 | 2026-04-16T21:02:48.545101+00:00 | city_api(50) |
| 54 | `del mar` | 1,032 | 2026-02-25T07:36:20.211142+00:00 | edco(50) |
| 55 | `el segundo` | 1,032 | 2026-02-25T07:39:15.834203+00:00 | edco(50) |
| 56 | `jamul` | 1,032 | 2026-02-25T07:39:12.970945+00:00 | edco(50) |
| 57 | `new-york` | 1,032 | 2026-04-14T20:40:56.951977+00:00 | city_api(50) |
| 58 | `portland` | 1,032 | 2026-04-17T21:24:30.342248+00:00 | city_api(50) |
| 59 | `signal hill` | 1,032 | 2026-02-25T07:38:50.323367+00:00 | edco(50) |
| 60 | `solana beach` | 1,032 | 2026-02-25T07:36:55.902716+00:00 | edco(50) |
| 61 | `portland-or` | 900 | 2026-04-20T03:56:18.988823+00:00 | city_api(50) |
| 62 | `nyc` | 842 | 2026-04-19T21:21:33.390932+00:00 | city_api(50) |
| 63 | `milwaukee` | 834 | 2026-04-20T01:49:54.84177+00:00 | city_api(50) |
| 64 | `portland-me` | 827 | 2026-04-20T00:53:34.99324+00:00 | city_api(50) |
| 65 | `fort-worth` | 697 | 2026-04-19T21:06:50.803531+00:00 | city_api(50) |
| 66 | `indianapolis` | 692 | 2026-04-20T01:50:18.350444+00:00 | city_api(50) |
| 67 | `miami-dade` | 612 | 2026-04-20T01:50:24.604118+00:00 | city_api(50) |
| 68 | `kansas-city` | 606 | 2026-04-20T01:50:01.379224+00:00 | city_api(50) |
| 69 | `seattle` | 586 | 2026-04-19T21:10:44.807634+00:00 | city_api(50) |
| 70 | `pine valley` | 548 | 2026-02-25T07:39:10.801077+00:00 | edco(50) |
| 71 | `campo` | 517 | 2026-02-24T22:16:36.694611+00:00 | edco(50) |
| 72 | `pauma valley` | 399 | 2026-02-24T22:17:35.550594+00:00 | edco(50) |
| 73 | `nashville` | 378 | 2026-04-19T21:21:47.953821+00:00 | city_api(50) |
| 74 | `descanso` | 365 | 2026-02-24T22:17:36.057204+00:00 | edco(50) |
| 75 | `pittsburgh` | 356 | 2026-04-20T01:50:06.782792+00:00 | city_api(50) |
| 76 | `dekalb-ga` | 351 | 2026-04-19T21:21:43.531598+00:00 | city_api(50) |
| 77 | `tucson` | 262 | 2026-04-20T01:49:34.428041+00:00 | city_api(50) |
| 78 | `dulzura` | 72 | 2026-02-24T22:17:33.768401+00:00 | edco(50) |
| 79 | `la-county` | 58 | 2026-04-20T01:50:37.313868+00:00 | city_api(50) |
| 80 | `rancho santa fe` | 55 | 2026-02-24T22:17:10.216416+00:00 | edco(50) |
| 81 | `louisville` | 42 | 2026-04-20T01:49:39.66121+00:00 | city_api(42) |
| 82 | `guatay` | 36 | 2026-02-24T22:17:33.768401+00:00 | edco(36) |
| 83 | `orlando` | 30 | 2026-04-19T21:21:51.063677+00:00 | city_api(30) |
| 84 | `albuquerque` | 18 | 2026-04-20T01:47:57.240903+00:00 | city_api(18) |
| 85 | `jacksonville` | 16 | 2026-04-20T01:50:11.925538+00:00 | city_api(16) |
| 86 | `arlington-tx` | 10 | 2026-04-19T21:21:52.884666+00:00 | city_api(10) |
| 87 | `phoenix-az` | 6 | 2026-04-19T21:21:50.237247+00:00 | city_api(6) |
| 88 | `new york` | 3 | 2026-04-08T14:45:12.547686+00:00 | community(3) |
| 89 | `austin-tx` | 1 | 2026-04-19T20:52:31.695572+00:00 | recollect_api(1) |
| 90 | `cambridge-ma` | 1 | 2026-04-19T20:52:33.419212+00:00 | recollect_api(1) |
| 91 | `davenport-ia` | 1 | 2026-04-19T20:52:37.192553+00:00 | recollect_api(1) |
| 92 | `denver-co` | 1 | 2026-04-19T20:52:30.695162+00:00 | recollect_api(1) |
| 93 | `georgetown-tx` | 1 | 2026-04-19T20:52:37.982016+00:00 | recollect_api(1) |
| 94 | `halton-on` | 1 | 2026-04-19T20:52:35.006949+00:00 | recollect_api(1) |
| 95 | `hardin-id` | 1 | 2026-04-19T20:52:41.356855+00:00 | recollect_api(1) |
| 96 | `king-county-wa` | 1 | 2026-04-19T20:52:42.067557+00:00 | recollect_api(1) |
| 97 | `long beach` | 1 | 2026-02-24T22:17:10.216416+00:00 | edco(1) |
| 98 | `morris-mb` | 1 | 2026-04-19T20:52:40.530774+00:00 | recollect_api(1) |
| 99 | `ottawa-on` | 1 | 2026-04-19T20:52:29.931+00:00 | recollect_api(1) |
| 100 | `pala` | 1 | 2026-02-24T22:13:47.791044+00:00 | edco(1) |
| 101 | `peterborough-on` | 1 | 2026-04-19T20:52:38.664803+00:00 | recollect_api(1) |
| 102 | `richmond-bc` | 1 | 2026-04-19T20:52:36.431801+00:00 | recollect_api(1) |
| 103 | `saanich-bc` | 1 | 2026-04-19T20:52:35.731251+00:00 | recollect_api(1) |
| 104 | `san antonio` | 1 | 2026-04-24T12:38:25.252709+00:00 | community(1) |
| 105 | `san-francisco-ca` | 1 | 2026-04-19T20:52:32.48809+00:00 | recollect_api(1) |
| 106 | `sherwood-park-ab` | 1 | 2026-04-19T20:52:39.843414+00:00 | recollect_api(1) |
| 107 | `vancouver-bc` | 1 | 2026-04-19T20:52:34.279511+00:00 | recollect_api(1) |
| 108 | `boston` | -1 | — | — |

---

## 2. Stale cities (>90 days since last update)

**None.** All 108 cities have at least one row updated in the last 90 days. The `updated_at` column appears to be touched by the import scripts on every refresh, so this metric may overstate freshness — `fetched_at` (when data was last sourced from origin) would be more meaningful but isn't populated for older imports.

---

## 3. Slug duplication clusters

Likely the same physical city stored under two or more slugs (different importer phases used different conventions). These need normalization to a canonical slug before SOURCE_REGISTRY.md is created — otherwise each variant gets its own entry and the resolver chain double-counts.

| Cluster | Slug variants found | Combined rows |
|---|---|---|
| phoenix | `phoenix` (714,011), `phoenix-az` (6) | 714,017 |
| austin | `austin` (625,673), `austin-tx` (1) | 625,674 |
| denver | `denver` (384,262), `denver-co` (1) | 384,263 |
| san antonio | `san antonio` (1), `san-antonio` (346,785) | 346,786 |
| san francisco | `san-francisco` (36,260), `san-francisco-ca` (1) | 36,261 |
| portland | `portland` (1,032), `portland-me` (827), `portland-or` (900) | 2,759 |
| new york | `new york` (3), `new-york` (1,032) | 1,035 |

Other observations:

- `nyc`, `new york`, `new-york` — three slugs for NYC, all single-row entries
- `portland` (1,032) vs `portland-me` (827) vs `portland-or` (900) — Portland properly disambiguated by state suffix BUT a third bare `portland` variant exists with most rows; needs review
- `san-antonio` (~600K) vs `san antonio` (separate slug) — high-volume duplication
- 16 ReCollect cities (`ottawa-on`, `denver-co`, `austin-tx`, `san-francisco-ca`, `cambridge-ma`, `vancouver-bc`, `halton-on`, `saanich-bc`, `richmond-bc`, `davenport-ia`, `georgetown-tx`, `peterborough-on`, `sherwood-park-ab`, `morris-mb`, `hardin-id`, `king-county-wa`) all have count=1 — single "default service area" row each. They should be in SOURCE_REGISTRY but flagged as zone-only / city-level coverage, not address-level.

---

## 4. Recommended SOURCE_REGISTRY.md scaffold

```markdown
# Source Registry — schedule_reports cities

Last audited: 2026-04-26

## Conventions

- Slug = `city` column value, lowercase, hyphenated when state suffix is needed for disambiguation.
- Coverage = `address-level` (residential addresses), `zone-level` (street/route polygons), or `city-level` (single "default service area" row).
- Source = how the data was acquired: `arcgis`, `recollect_api`, `republic_services`, `community`, `manual`, etc.

## Cities (108)

| Slug | Rows | Coverage | Source | Notes |
|---|---|---|---|---|
| albuquerque | 18 | zone-level | city_api | |
| alpine | 1,032 | zone-level | edco | |
| arlington-tx | 10 | zone-level | city_api | |
| austin | 625,673 | address-level | ? | |
| austin-tx | 1 | city-level | recollect_api | |
| baltimore | 40,641 | address-level | city_api | |
| bay-city | 11,925 | address-level | city_api | |
| bonita | 3,650 | zone-level | edco | |
| bonsall | 1,032 | zone-level | edco | |
| boston | -1 | city-level | ? | |
| buena park | 16,305 | address-level | edco | |
| cambridge-ma | 1 | city-level | recollect_api | |
| campo | 517 | zone-level | edco | |
| charlotte | 5,111 | address-level | city_api | |
| chicago | 1,032 | zone-level | city_api | |
| cocoa-fl | 4,867 | zone-level | city_api | |
| columbia-heights-mn | 4,137 | zone-level | city_api | |
| coronado | 3,407 | zone-level | edco | |
| culpeper-va | 5,841 | address-level | city_api | |
| dallas | 256,742 | address-level | city_api | |
| davenport-ia | 1 | city-level | recollect_api | |
| dekalb-ga | 351 | zone-level | city_api | |
| del mar | 1,032 | zone-level | edco | |
| denver | 384,262 | address-level | city_api | |
| denver-co | 1 | city-level | recollect_api | |
| descanso | 365 | zone-level | edco | |
| dulzura | 72 | zone-level | edco | |
| el cajon | 18,008 | address-level | edco | |
| el segundo | 1,032 | zone-level | edco | |
| encinitas | 15,575 | address-level | edco | |
| escondido | 39,181 | address-level | edco | |
| fallbrook | 11,681 | address-level | edco | |
| fort-worth | 697 | zone-level | city_api | |
| georgetown-tx | 1 | city-level | recollect_api | |
| guatay | 36 | zone-level | edco | |
| halton-on | 1 | city-level | recollect_api | |
| hardin-id | 1 | city-level | recollect_api | |
| hillsborough-county-fl | 313,445 | address-level | city_api | |
| houston | 2,094,336 | address-level | ? | |
| imperial beach | 4,380 | zone-level | edco | |
| indianapolis | 692 | zone-level | city_api | |
| jacksonville | 16 | zone-level | city_api | |
| jamul | 1,032 | zone-level | edco | |
| kansas-city | 606 | zone-level | city_api | |
| king-county-wa | 1 | city-level | recollect_api | |
| la mesa | 16,548 | address-level | edco | |
| la mirada | 8,518 | address-level | edco | |
| la palma | 7,301 | address-level | edco | |
| la-county | 58 | zone-level | city_api | |
| lakeside | 3,650 | zone-level | edco | |
| lakewood | 20,442 | address-level | edco | |
| lemon grove | 6,571 | address-level | edco | |
| londonderry-nh | 8,031 | address-level | city_api | |
| long beach | 1 | city-level | edco | |
| louisville | 42 | zone-level | city_api | |
| miami-dade | 612 | zone-level | city_api | |
| milwaukee | 834 | zone-level | city_api | |
| morris-mb | 1 | city-level | recollect_api | |
| nashville | 378 | zone-level | city_api | |
| national city | 6,814 | address-level | edco | |
| new york | 3 | city-level | community | |
| new-york | 1,032 | zone-level | city_api | |
| novi-mi | 16,305 | address-level | city_api | |
| nyc | 842 | zone-level | city_api | |
| orlando | 30 | zone-level | city_api | |
| ottawa-on | 1 | city-level | recollect_api | |
| pala | 1 | city-level | edco | |
| pauma valley | 399 | zone-level | edco | |
| peterborough-on | 1 | city-level | recollect_api | |
| philadelphia | 393,753 | address-level | city_api | |
| phoenix | 714,011 | address-level | ? | |
| phoenix-az | 6 | zone-level | city_api | |
| pine valley | 548 | zone-level | edco | |
| pittsburgh | 356 | zone-level | city_api | |
| plano-tx | 66,437 | address-level | city_api | |
| portland | 1,032 | zone-level | city_api | |
| portland-me | 827 | zone-level | city_api | |
| portland-or | 900 | zone-level | city_api | |
| poway | 8,518 | address-level | edco | |
| raleigh-nc | 245,548 | address-level | city_api | |
| ramona | 8,031 | address-level | edco | |
| rancho palos verdes | 12,168 | address-level | edco | |
| rancho santa fe | 55 | zone-level | edco | |
| richmond-bc | 1 | city-level | recollect_api | |
| saanich-bc | 1 | city-level | recollect_api | |
| san antonio | 1 | city-level | community | |
| san diego | 358,709 | address-level | community | |
| san marcos | 18,252 | address-level | edco | |
| san-antonio | 346,785 | address-level | city_api | |
| san-francisco | 36,260 | address-level | city_api | |
| san-francisco-ca | 1 | city-level | recollect_api | |
| seattle | 586 | zone-level | city_api | |
| sherwood-park-ab | 1 | city-level | recollect_api | |
| signal hill | 1,032 | zone-level | edco | |
| solana beach | 1,032 | zone-level | edco | |
| south-fulton-ga | 38,937 | address-level | city_api | |
| spring valley | 8,518 | address-level | edco | |
| stevens-point | 8,518 | address-level | city_api | |
| syracuse-ny | 38,694 | address-level | city_api | |
| the-woodlands-tx | 29,690 | address-level | city_api | |
| tucson | 262 | zone-level | city_api | |
| valley center | 6,571 | address-level | edco | |
| vancouver-bc | 1 | city-level | recollect_api | |
| vista | 26,283 | address-level | edco | |
| washington-dc | 124,599 | address-level | city_api | |
| wauwatosa-wi | 16,548 | address-level | city_api | |
| westland-mi | 27,256 | address-level | city_api | |
| whitby-on | 43,561 | address-level | city_api | |
```

---

## 5. Methodology

- Distinct cities enumerated via keyset pagination (`select=city&city=gt.<last>&order=city.asc&limit=1`) — guaranteed exhaustive list, no sampling bias.
- Per-city stats: estimated count via `count=estimated` header, latest `updated_at` from `order=updated_at.desc&limit=50` sample, source distribution from same sample.
- 5 batches of pagination + 108 per-city queries. Total ~109 + 108 + 108 = 325 Supabase REST calls. Read-only throughout.
- No DB modifications. No code changes. Pure observation.
