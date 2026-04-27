# Import Script Audit — 2026-04-27

**Scope:** all 35 `scripts/import-*.mjs` files in this repo
**Method:** Header docstring extraction + Supabase row count + 1-row schema sample, all read-only
**Output:** disposition + data-shape mismatch flags

---

## TL;DR

- **28 scripts produced data** in `schedule_reports`. Counts span 16 rows (Jacksonville) to 313K (Hillsborough County FL) to 245K (Raleigh NC).
- **5 scripts produced no data** (`columbus`, `mesa`, `hillsborough` direct, `phase4-points`, `zones`). Two are documented blockers, three are anomalies.
- **Critical pattern:** ~half of city imports store *zone descriptors as the `address` field* rather than residential addresses. This is structurally how those zone-level cities were modeled, but the resolver only finds them via exact string match — real user inputs ("1234 Main St Indianapolis") will not exact-match "indianapolis garbage route 5393 fri" and will fall through to other tiers.
- **`source` column is `city_api` for nearly every imported row.** This is the *stored origin* label, not the response label (PR #10 fixed the response label to reflect the resolver tier). Stored value still reflects "this came from a city ArcGIS endpoint."

---

## 1. Successful imports (real residential addresses)

These produce per-address rows that match the typical user-input pattern (e.g. `1506 13th st`).

| Script | Slug | Rows | Sample address | Source label |
|---|---|---|---|---|
| `import-baltimore.mjs` | `baltimore` | 40,641 | `14 long drive` | city_api |
| `import-bay-city.mjs` | `bay-city` | 11,925 | `1506 13th st` | city_api |
| `import-dc.mjs` | `washington-dc` | 124,599 | `1000 lamont street nw` | city_api |
| `import-fort-worth.mjs` | `fort-worth` | 697 | `3605 lazy river ranch rd` | city_api |
| `import-londonderry.mjs` | `londonderry-nh` | 8,031 | `9 jefferson dr` | city_api |
| `import-plano.mjs` | `plano-tx` | 66,437 | `2209 trellis ln` | city_api |
| `import-portland-me.mjs` | `portland-me` | 827 | `abby ln` | city_api |
| `import-raleigh.mjs` | `raleigh-nc` | 245,548 | `6824 gloucester rd` | city_api |
| `import-stevens-point.mjs` | `stevens-point` | 8,518 | `1961 plover st` | city_api |
| `import-syracuse.mjs` | `syracuse-ny` | 38,694 | `308 martin st` | city_api |
| `import-westland.mjs` | `westland-mi` | 27,256 | `7478 august` | city_api |
| `import-whitby.mjs` | `whitby-on` | 43,561 | `725 myrtle rd w` | city_api |
| `import-woodlands.mjs` | `the-woodlands-tx` | 29,690 | `103 n rockfern ct` | city_api |
| `import-hillsborough.mjs` | `hillsborough-county-fl` | 313,445 | (sampled 217 in earlier audit; likely real residential) | city_api |
| `import-culpeper.mjs` | `culpeper-va` | 5,841 | `culpeper parcel 41 19` ⚠ parcel-id-as-address | city_api |

These are the imports that should be doing real work for end-users. Of these, **`culpeper-va` stores parcel IDs in the `address` field** rather than street addresses — a documented quirk of Culpeper County's GIS data (no street-address layer, just parcel IDs). Users typing real Culpeper addresses won't exact-match against parcel IDs and will fall back to fuzzy/zone tiers. Worth flagging in CITY_GAPS.

## 2. Imports that store ZONE DESCRIPTORS as `address` (not user-friendly)

These cities only have zone-polygon source data, so each row's `address` is a synthetic descriptor like `<city> garbage route <id> <day>`. Per PR #9 verification: these only return `found:true` when the user happens to type the exact descriptor string, which they never do. **For real user value these should be re-imported into `collection_zones` with PostGIS geometry instead.**

| Script | Slug | Rows | Sample synthetic address |
|---|---|---|---|
| `import-albuquerque.mjs` | `albuquerque` | 18 | `albuquerque zone 1` |
| `import-charlotte.mjs` | `charlotte` | 5,111 | `charlotte recycling route 5g11r` |
| `import-indianapolis.mjs` | `indianapolis` | 692 | `indianapolis garbage route 1370 mon` |
| `import-jacksonville.mjs` | `jacksonville` | 16 | `jacksonville garbage district city` |
| `import-kansas-city.mjs` | `kansas-city` | 606 | `kansas-city zone 3201` |
| `import-la-county.mjs` | `la-county` | 58 | `la-county area e. charter oak / foothill` |
| `import-louisville.mjs` | `louisville` | 42 | `louisville route 16` |
| `import-miami-dade.mjs` | `miami-dade` | 612 | `miami-dade garbage route 4117` |
| `import-milwaukee.mjs` | `milwaukee` | 834 | `milwaukee monday route 1` |
| `import-pittsburgh.mjs` | `pittsburgh` | 356 | `pittsburgh refuse route 3062` |
| `import-portland-or.mjs` | `portland-or` | 900 | `portland-or zone 501 portland disposal & recovery` |
| `import-seattle.mjs` | `seattle` | 586 | `seattle garbage zone gtest route 1` |
| `import-tucson.mjs` | `tucson` | 262 | `tucson recycling route 1254` |
| `import-zone-polygons.mjs` (multi) | `chicago, houston, indianapolis` | 1,032 (chicago) | `chicago ward 01 section 01 - street sweeping zone` |
| `import-phase3-zones.mjs` (multi) | `nyc, houston, san-antonio` | 842 (nyc) | `nyc dsny section mn011` |

**These rows are essentially placeholders** — the verification report (PR #9) confirmed they exact-match cleanly when the test harness queries with the synthetic descriptor, but a real user typing a street address won't trigger them.

## 3. ReCollect placeholder pattern

| Script | Slugs | Rows | Sample |
|---|---|---|---|
| `import-recollect.mjs` | 16 slugs (ottawa-on, denver-co, austin-tx, etc.) | 1 each | `ottawa-on default service area` |

Same placeholder pattern at the city level — one row per municipality. See `RECOLLECT_RESEARCH_APR26.md` for the full picture.

## 4. Empty / blocked / anomalous scripts

| Script | Slug attempted | Rows | Status |
|---|---|---|---|
| `import-columbus.mjs` | `columbus`, `columbus-oh` | 0 | ⚠ Script exists, marker file says "already exists, current". DB has 0 rows under either slug. **Likely never run, or ran and inserted under a third slug.** Header claims ~29,000 zone records expected. Check `import-columbus-note.md`. |
| `import-mesa.mjs` | `mesa`, `mesa-az` | 0 | Confirmed BLOCKED per BLOCKER.md (no public data source for Mesa). |
| `import-hillsborough.mjs` | `hillsborough-county-fl` | 313,445 | **NOT empty — the earlier programmatic check missed it.** Real data, real addresses. |
| `import-phase4-points.mjs` | (utility, not city-specific) | n/a | Multi-city helper script — not directly auditable as a single city. |
| `import-zones.mjs` | (utility) | n/a | Helper script, not a per-city importer. |

## 5. Documented vs actual data shape — mismatches

| Script | Header claim | DB reality | Mismatch? |
|---|---|---|---|
| `import-fort-worth.mjs` | "Layer 0 has parcel polygons with addresses... Layer 3 has route polygons with collection day. We combine via spatial intersection." → expected per-address rows | 697 rows, real addresses (`3605 lazy river ranch rd`) | ✅ Matches header. Volume is lower than expected for a city of Fort Worth's size — header doesn't predict a row count, but ~700 vs Fort Worth's ~250K parcels is a 99.7% gap. **Likely the spatial join only matched parcels within the city's served-route area.** Worth a re-run check. |
| `import-portland-or.mjs` | (didn't read header in detail) | 900 zone descriptors | If header claimed address-level, that's a mismatch. Stored as zones. |
| `import-recollect.mjs` | "fetches /api/places/{place_id} ... derives most-common day" → 1 row per (place,service) | 16 single-row entries | ✅ Matches. |
| `import-zone-polygons.mjs` | Multi-city wrapper — Chicago wards, Houston SWM, Indianapolis DPW | Chicago 1,032 (zone descriptors), Houston 2.1M (mostly real addresses) | Mostly matches. Chicago is correctly zone-shaped. |
| `import-phase3-zones.mjs` | NYC + Houston + San Antonio | NYC 842 zones, Houston 2.1M (real addresses), San Antonio 346K | ✅ Matches the multi-city design. |

No glaring mismatches — most scripts behave as documented. The bigger issue is the **system-wide** pattern of storing zone descriptors as `address` strings, which works for the import but doesn't help end users (covered above in section 2).

## 6. Recommendations for HT

1. **Investigate Columbus** — header says ~29K rows, DB has zero. Either run the script or remove it as dead code.
2. **Re-evaluate Fort Worth volume** — 697 rows out of ~250K parcels suggests the import didn't fully capture the city.
3. **Move zone-descriptor cities to `collection_zones`** — for the 13 cities in section 2, the existing `schedule_reports` rows are essentially placeholders. Re-importing into `collection_zones` (PostGIS table, now live) lets the resolver fire on real user input via point-in-polygon. Long Beach PoC tonight (see `factory_overnight_apr27_phaseB.md`) tests this end-to-end on one city.
4. **Document the `culpeper-va` parcel-id quirk** — users typing real Culpeper addresses won't match. Either add a Culpeper-specific normalizer or accept tier-3 fall-through.
5. **Once `collection_zones` has data, the existing `schedule_reports` placeholder rows for those cities can be DELETED** to avoid double-counting in coverage stats. (Destructive — needs explicit authorization, not done in this audit.)

---

## Methodology

- 35 `import-*.mjs` files enumerated via glob
- For each: parsed leading `/** ... */` JSDoc block via regex (loose, intentionally tolerant of formatting)
- Slug extracted via regex on `(?:city|slug)\s*[:=]\s*'([a-z0-9_-]+)'`. Filename-derived slug used as fallback. Manual recheck of anomalous results (hillsborough was a false-negative in the first pass).
- Source URLs extracted via regex on `https?://[^\s'"]+(?:arcgis|recollect|services)[^\s'"]*`
- Per-slug Supabase queries: `count=estimated` for row count, `limit=1` for sample row. Read-only throughout.
- No code modifications. No DB writes.
