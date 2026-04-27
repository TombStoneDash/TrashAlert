# Long Beach Polygon Source — Stage 1 Investigation

**Session:** Resolver chain repair follow-up, 2026-04-27
**Prerequisite:** Schema gate from earlier session passed 5/5 (`resolver_repair_apr28.md`)
**Stage 1 directive:** Identify Long Beach source layer, document fields, decide Case A/B/C/D. **Do not modify anything.**

---

## TL;DR

**Verdict: Case D — refuse only.** Source ArcGIS has a single `DAY` string field. No sibling service in the Long Beach catalog carries separate recycling-day or yard-waste-day data.

But the "recycling day" that motivated this fix turned out to be a **parsing bug** in the existing `normalizeDay()` helper, not real data. Long Beach has same-day refuse + recycling collection; the apparent "Wednesday, Saturday" output was a string-decomposition artifact. The right action is to **fix the bug**, not to design a multi-day schema for Long Beach.

The schema-fix work (adding `refuse_day` / `recycling_day` / `yard_waste_day` columns) is still desirable for cities like Tampa that have genuinely separate layers, but Long Beach isn't a driver for it.

Per directive: halt. End session. HT picks the path.

---

## 1. Source layer

**URL:** `https://services6.arcgis.com/yCArG7wGXGyWLqav/arcgis/rest/services/Refuse_Collection_Days/FeatureServer/0`

**Service org:** Long Beach (`yCArG7wGXGyWLqav`), public access.

**Where the link lives in our code:**
- `src/lib/city-geocode.ts:1485` — `LONGBEACH_REFUSE_URL` constant
- `factory/scripts/import-recollect.mjs` does NOT cover Long Beach (Long Beach is not on the ReCollect path)
- The 19 polygons in `collection_zones` were inserted manually overnight by my Python script, sourcing from this same URL via GeoJSON query

## 2. Field schema

```
OBJECTID       esriFieldTypeOID
DAY            esriFieldTypeString    (length=10)
Shape__Area    esriFieldTypeDouble
Shape__Length  esriFieldTypeDouble
```

**Total non-system fields: 1** (`DAY`).

## 3. Sample records (5)

```
{'OBJECTID': 1, 'DAY': 'Monday',    'Shape__Area': 9_895_312,  'Shape__Length': 15_081}
{'OBJECTID': 2, 'DAY': 'Wednesday', 'Shape__Area': 12_844_638, 'Shape__Length': 20_959}
{'OBJECTID': 3, 'DAY': 'Thursday',  'Shape__Area': 11_168_231, 'Shape__Length': 15_841}
{'OBJECTID': 4, 'DAY': 'Tuesday',   'Shape__Area': 18_355_611, 'Shape__Length': 18_827}
{'OBJECTID': 5, 'DAY': 'Friday',    'Shape__Area': 6_799_793,  'Shape__Length': 14_830}
```

All 19 features carry one of the five weekday strings. **No alternate day field exists** (no `recycling_day`, `yard_waste_day`, `bulk_day`, etc.).

## 4. Sibling services in the same Long Beach catalog

Searched `services6.arcgis.com/yCArG7wGXGyWLqav/arcgis/rest/services?f=json` for `recycle|refuse|trash|garbage|waste|organic|yard|compost|sweep|collection`:

| Service | Layer geometry | Schema relevance |
|---|---|---|
| `ESB_OrgWaste_Pilot` | Point | Single field: `address`. **Pilot program point list.** No day field. Limited to a small set of addresses, not citywide. |
| `Recycle_Centers` | Point | Drop-off-center locations, not curbside pickup days. |
| `Refuse_Collection_Days` | **Polygon** | Already used. `DAY` only. |
| `RouteSmart_Refuse_Routing_Project_Data` | mixed (5 layers) | Layer 10 "Mixed Areas" has `TEAM` + `DAY` + audit fields. Layer 15 "Map Areas", Layer 3 "LB Routes", Layer 5 "LB Supervisor Areas" similar. **All have only single `DAY` field.** None separate refuse/recycling. |
| `Street_Sweeping` | (not probed) | Different service entirely; outside refuse/recycling scope. |

**Conclusion:** no sibling service in this catalog carries separate refuse vs recycling vs yard-waste day data. The 19-polygon `Refuse_Collection_Days` layer is the only relevant source.

## 5. Where the "Wednesday, Saturday" came from — code bug, not data

Yesterday's PoC observed prod responses like `"collection_day": "Wednesday, Saturday"` for Long Beach addresses (source `longbeach_arcgis`). Today's investigation traced this to:

`src/lib/city-geocode.ts` lines 1487–1511 (`lookupLongBeach`):
- Queries the Refuse_Collection_Days FeatureServer with `outFields='DAY'`
- Gets back a single string like `"Wednesday"`
- Passes it through `normalizeDay()`
- Returns `{ collectionDay: day, recyclingDay: day, ... }` — **already same value**

`src/lib/city-geocode.ts` lines 135–172 (`normalizeDay`):

The `DAY_MAP` only contains abbreviations (`M`, `MON`, `T`, `TUE`, `TUES`, `W`, `WED`, `TH`, `THU`, `THUR`, `THURS`, `R`, `F`, `FRI`, `S`, `SAT`, `SU`, `SUN`). It does **not** contain full-word entries (`MONDAY`, `WEDNESDAY`, etc.). When given the full word, the function falls through to the multi-day decoder, which greedy-matches abbreviations within the word. Reproduced locally with the same DAY_MAP:

| Input | normalizeDay output | Correct? |
|---|---|---|
| `'MONDAY'` | `'Monday'` | ✅ |
| `'TUESDAY'` | `'Tuesday'` | ✅ |
| `'WEDNESDAY'` | `'Wednesday, Saturday'` | ❌ — `WED` matches, leftover `ESDAY` includes `S` → Saturday |
| `'THURSDAY'` | `'Thursday, Saturday'` | ❌ — same pattern |
| `'FRIDAY'` | `'Friday'` | ✅ |
| `'SATURDAY'` | `'Saturday, Thursday'` | ❌ — `SAT` matches, leftover `URDAY` matches `R` → Thursday |
| `'SUNDAY'` | `'Sunday'` | ✅ |

**Three of seven days corrupt.** Any city whose ArcGIS source returns full-word days (Long Beach, possibly others) has been emitting wrong recycling-day data for Wednesday, Thursday, and Saturday zones since this code shipped.

**This is a separate, real bug worth its own PR.** It's outside the scope of the Stage 1 investigation but flagging because it affects the entire framing of "we need recycling-day data." We had bad recycling-day data, not missing recycling-day data.

## 6. Case decision

Per the directive's case definitions:

- **Case A** (refuse + recycling + yard_waste separate fields): NO. Source has 1 day field.
- **Case B** (refuse + recycling only): NO. Source has 1 day field.
- **Case C** (one combined day field encoding multiple services): NO. The `DAY` field is just refuse-day text, not encoded.
- **Case D** (refuse only, recycling lives elsewhere): **YES, with caveat.** Refuse only is correct. But recycling does NOT live in any discoverable Long Beach ArcGIS source.

The "elsewhere" sourcing recommendation per Case D would be:

| Where recycling data could come from | Likelihood |
|---|---|
| **Same as refuse day** (city policy: same-day collection) | **Most likely.** The existing code (`recyclingDay: day`) already encodes this assumption. Common practice in CA cities. The "Wednesday, Saturday" we saw was the parsing bug, NOT real evidence of a separate recycling day. |
| Separate ArcGIS layer somewhere outside this catalog | Possible but unverified. Searched `services6.arcgis.com/yCArG7wGXGyWLqav/arcgis/rest/services` — no such layer. Other Long Beach hostnames (e.g. internal) may have it but aren't public. |
| `maps.longbeach.gov` open data hub | Worth a manual look but I couldn't browse its dataset listing for `recycling-collection-days` automatically. HT to check. |
| City of Long Beach phone-call / email request | The fallback if no public data exists. |

## 7. Recommendation — what HT should pick next

Three branches, ranked by user value:

### Branch 1 (highest leverage, lowest scope): fix `normalizeDay` bug, ship fix

This is a real bug affecting 3 of 7 days for cities that return full-word day values. It's a 5-line fix: add full-word entries to `DAY_MAP`, OR change the multi-day decoder to skip if the input is one of the canonical full-word days. Acceptance test: re-run my normalizeDay reproduction script after the fix; all 7 days must round-trip correctly.

This **doesn't require schema changes** to `collection_zones` and **doesn't require recycling-day data**. It just stops emitting wrong data for cities that already have correct data internally.

### Branch 2 (medium leverage, medium scope): generalize `collection_zones` schema for cities that genuinely have separate data

Tampa has 3 separate ArcGIS layers (trash / recycling / yard-waste — see `src/lib/city-geocode.ts:1515`). When Tampa's polygons get imported, the schema gap matters. The migration the directive's Stage 2 sketches is the right fix, but **Long Beach isn't its driver — Tampa is.** Schema redesign should happen alongside the Tampa import, not standalone.

### Branch 3 (low leverage right now): hunt for separate Long Beach recycling source

If HT confirms Long Beach has NON-same-day collection, then a separate source is needed. But the existing `recyclingDay: day` assumption is consistent with same-day, and that's what most California cities do. Until there's evidence Long Beach is different, this branch isn't worth time.

## 8. Stage 2 — NOT EXECUTED

Per directive: "If Case C or D: do NOT design a schema speculatively. End the session after documenting findings. HT picks the path next."

This file is the entire deliverable. Halting before any code change. No worktree on trashalert-web was created. `collection_zones` row count remains 19. `schedule_reports` row count remains 7,300,730.

---

## Investigation methodology (read-only throughout)

- Layer schema: `<url>/?f=json`
- Sample records: `<url>/query?where=1=1&outFields=*&resultRecordCount=5&f=json`
- Sibling enumeration: `<catalog>/?f=json` filtered with regex on service name
- normalizeDay reproduction: ported the function to Python 1:1 with the same `DAY_MAP`, fed all seven full-word days, observed outputs
- Code references read from the existing `fix/zone-tier-priority` worktree at `C:/TombstoneDash/factory/trashalert-web-zonetier`
- Zero writes performed. Zero commits.
