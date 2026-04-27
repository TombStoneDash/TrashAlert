# ReCollect API Research — 2026-04-26

**Investigated by:** Claude Code (Lenovo factory overnight session)
**Question:** Can the ReCollect public API expand TrashAlert's coverage tonight?
**Short answer:** Not directly. The public surface area is too narrow for new-city imports without prior knowledge of `(place_id, service_id)` tuples; the existing 16 imported tuples represent the practical limit of what's discoverable without auth.

---

## 1. Authentication model

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /api/places/{uuid}` | **Public, no auth** | Returns place metadata: street, city, lat, lng, postal_code, name |
| `GET /api/places/{uuid}/services/{int}/events?after&before&locale` | **Public, no auth** | Returns event calendar with zone metadata, day-of-week pickups, flag types (garbage/recycle/organics/yardtrimmings/bluebox/greenbin) |
| `GET /api/areas` | **401 Unauthorized** | Requires session cookie or token (presumably partner-portal credentials) |
| `GET /v2/areas` | **401 Unauthorized** | Same |
| `GET /api/places?service_id=X&q=…&suggest=1` | Returns `{"msg":"parcel_id is required"}` | Address-search needs a `parcel_id` which itself comes from auth-gated endpoints |
| `GET /widget` | Public, returns HTML widget shell | Not useful for programmatic discovery |

**Implication:** the data is public *if you already know which place to ask about*. There is no public way to (a) list which municipalities are served, (b) list which addresses are served within a municipality, or (c) geocode an arbitrary address into a `parcel_id`.

## 2. Rate limits

No documented rate limit was hit during the research probes (10 fetches over ~3 minutes, all returned 200 within 200-400ms). The existing import script uses a 250ms gap between requests; that has not produced 429s in past runs (per the script's own commit history).

**Recommended cadence for any future ReCollect work:** ≥250ms between calls, ≥1s when fetching events (which return larger payloads).

## 3. Endpoint shape — concrete sample

### `GET /api/places/BCCDF30E-578B-11E4-AD38-5839C200407A`

```json
{
  "place": {
    "id": "BCCDF30E-578B-11E4-AD38-5839C200407A",
    "name": "Laurier Avenue East, Ottawa, Ontario, Canada",
    "house": "0", "street": "laurier ave e", "city": "ottawa", "province": "ontario", "country": "canada",
    "lat": "45.4261437000001", "lng": "-75.6814128999999",
    "source": "mapbox", "locale": "en", "unit": ""
  }
}
```

### `GET /api/places/{uuid}/services/208/events?after=2026-04-26&before=2026-05-10`

Returns `{ zones: { <zone_id>: {…} }, events: [{day, flags:[{name,…}], …}, …] }`. Events have flag arrays; common flag names observed:
- `blackbox` / `garbage` (residual waste pickup)
- `bluebox` / `recycling` (recyclables)
- `greenbin` / `compost` / `yardtrimmings` (organics + yard waste)

The existing `import-recollect.mjs` script counts day-of-week occurrences across these flag categories and picks the dominant day. That logic is correct and works.

## 4. Coverage discovery

There is **no `/api/services` endpoint and no `/api/areas` enumeration without auth.** The existing curated 16-entry list in `scripts/import-recollect.mjs` was sourced from the [Home Assistant `hacs_waste_collection_schedule`](https://github.com/mampfes/hacs_waste_collection_schedule) project's canonical mapping table.

| Source for new (place, service) tuples | Effort | Reliability |
|---|---|---|
| HACS waste-collection-schedule repo (parse their service map) | 30-60 min one-time scrape | High — community-curated |
| Crawl city websites for embedded ReCollect widget config | 30-60 min per city, error-prone | Medium |
| Routeware partner portal access | unknown (sales contact) | Highest if obtained |
| Inspect Routeware/ReCollect customer list pages | Manual review | Low — many cities listed without service IDs |

## 5. Probe of TrashAlert priority cities

The overnight directive's tier-1 priority US metros (Atlanta, Cleveland, Oakland, Orlando, Cincinnati, Sacramento, San Jose, Fort Worth) — **none appear in the existing 16-entry curated list.** Verifying their ReCollect presence would require crawling city websites for widget code, which is not viable overnight.

Verification report (PR #9) already established that **Detroit and Tampa are covered via city ArcGIS**, not ReCollect. They should be removed from the gap list regardless.

## 6. Existing 16 tuples — already imported

All 16 entries in `scripts/import-recollect.mjs` already have rows in `schedule_reports`:

| slug | rows | type |
|---|---|---|
| ottawa-on, denver-co, austin-tx, san-francisco-ca, cambridge-ma, vancouver-bc, halton-on, saanich-bc, richmond-bc, davenport-ia, georgetown-tx, peterborough-on, sherwood-park-ab, morris-mb, hardin-id, king-county-wa | 1 each | "default service area" placeholder rows |

These ReCollect imports produce **city-level coverage signals only** (one row per city, address = "<slug> default service area"). They mark the city as "in our DB" for the resolver chain but don't help individual-address lookups. A user typing a real Ottawa address would not match the placeholder row directly — they'd hit the API's geocoding/zone tiers, which currently aren't wired to the ReCollect backing data.

## 7. Strategic recommendation

**For tonight:** treat ReCollect as a closed chapter. The public API doesn't admit further automated expansion without significant upstream research effort (HACS scrape or partner outreach).

**For tomorrow / this week:** if HT wants more ReCollect coverage, the highest-leverage move is:

1. **Scrape HACS `hacs_waste_collection_schedule` repo** for ReCollect service mappings beyond the existing 16. This likely surfaces dozens of additional municipalities.
2. **Decide what "ReCollect coverage" means** — is one placeholder row per city enough (current state) or do we want address-level data? Address-level data isn't accessible via the public API; it would require Routeware partner credentials.
3. **Reach out to Routeware/ReCollect partners program** — `support@routeware.com` is the public contact (from `https://www.routeware.com/`).

A discovery script for the HACS scrape is documented separately in `RECOLLECT_DISCOVERY_PLAN.md`.

---

## Hard-stop check (per directive Step 3)

The directive listed three hard-stop conditions for Step 3:

| Condition | Triggered? | Notes |
|---|---|---|
| ReCollect requires paid API key registration we don't have | **No** | Public endpoints work without auth |
| ReCollect requires CAPTCHA or human-only signup | No | No CAPTCHA encountered |
| ReCollect's public endpoint returns 401/403 with no documented auth path | **Partial** | `/api/areas` does (401) but the `/api/places/{uuid}` path is fully public; the discovery limitation is structural, not an auth wall |

**Overnight pivot triggered:** the directive's Step 4 ("ReCollect Batch 1 — pick 10 municipalities") cannot be executed because all known tuples are already imported and discovering new ones requires either crawling (slow) or partner access (not available). HT confirmed pivot to Step 6 fallback work.
