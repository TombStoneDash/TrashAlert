# CITY_GAPS.md — Recommended Updates (2026-04-26)

**Why this is a separate doc:** `CITY_GAPS.md` currently lives only on HT's in-progress branch `feat/phase-c-durham-gaps` (uncommitted merge state in the main worktree). To honor "no touching HT's dirty state" sacred rule, this update is documented as a paste-ready patch instead of as a competing PR that would conflict with HT's planned merge.

**Apply when:** HT next touches `feat/phase-c-durham-gaps` or after that branch lands on main, whichever comes first.

---

## Source: PR #9 verification findings (50-address probe)

The verification probe surfaced two coverage facts that update the gap list:

1. **Detroit, MI is covered.** `detroit_arcgis` returned `found:true` for 2/2 plausible Detroit addresses (`1234 Woodward Ave`, `5678 Michigan Ave`). The current CITY_GAPS.md lists Detroit under Tier 1 ("ready to import — direct ArcGIS endpoints confirmed"), but the resolver is already calling Detroit's ArcGIS in production. This is a **DONE**, not a TODO.
2. **Tampa, FL is covered.** `tampa_arcgis` returned `found:true` for 2/2 plausible Tampa addresses (`1234 Kennedy Blvd`, `5678 Bayshore Blvd`). Tampa is currently listed under Tier 3 ("no open data source surfaced — investigation needed"). It is in fact wired up at tier 1.

## Source: SOURCE_REGISTRY audit (this run)

The 108 distinct city slugs in `schedule_reports` include several already-covered cities that are not on CITY_GAPS.md and don't need to be (correctly absent), and one that *is* on the list but already has data:

3. **Whitby, ON has data.** `whitby-on` has 43,561 rows in `schedule_reports` (per ReCollect import). It is not on CITY_GAPS.md, which is correct — it was never a "gap." But it is not flagged as a ReCollect-served city anywhere either, which is a documentation gap, not a coverage gap.

## Recommended edits to `CITY_GAPS.md`

### Edit 1 — Move Detroit from Tier 1 to a new "Already covered" section

**Find:**

```markdown
### Detroit, MI
- **Source:** City data hub — "Trash, Recycling, Bulk Pick Up Zones"
- **Dataset:** `https://data.detroitmi.gov/datasets/trash-recycling-bulk-pick-up-zones`
- **Shape:** polygon zones (weekly since June 2024)
- **Next step:** Follow the GeoService link on the dataset page to get
  the FeatureServer query URL; small feature count.
- **Provider note:** Priority Waste (east/SW) + Advance & GFL (others).
```

**Replace with:** *(delete entirely; move to Already-Covered list — see Edit 3)*

### Edit 2 — Move Tampa from Tier 3 to Already-Covered

**Find:**

```markdown
- **Tampa, FL** — app/web lookup only. Needs deeper network trace.
```

**Replace with:** *(delete entirely; move to Already-Covered list — see Edit 3)*

### Edit 3 — Add new section at top of file

**Insert after the opening intro, before "## Tier 1":**

```markdown
## Already covered (verified 2026-04-26 via PR #9)

These cities WERE listed as gaps in earlier sprints but the production
`/api/schedule` resolver successfully returned `found:true` from a
city ArcGIS endpoint during the 50-address verification probe. They
should not be re-imported; they should be reflected in the homepage
city count.

| City | Resolver source | Verified addresses |
|---|---|---|
| Detroit, MI | `detroit_arcgis` | `1234 Woodward Ave`, `5678 Michigan Ave` |
| Tampa, FL | `tampa_arcgis` | `1234 Kennedy Blvd`, `5678 Bayshore Blvd` |

```

### Edit 4 — Update the delivery plan section

**Find:**

```markdown
2. Anaheim, Detroit, Rochester — small polygon sets; each ~30 min once FeatureServer URL is confirmed
```

**Replace with:**

```markdown
2. Anaheim, Rochester — small polygon sets; each ~30 min once FeatureServer URL is confirmed (Detroit removed: already live via city ArcGIS)
```

---

## Apply mechanically

If HT prefers, save this snippet as `git-apply` input. The Detroit and Tampa removals are independent; the Already-Covered insert depends on the section header being present.

---

## What this doc explicitly does NOT do

- Does not modify `CITY_GAPS.md` directly (it's on a branch I'm not touching)
- Does not open a PR (would compete with HT's planned merge of `feat/phase-c-durham-gaps`)
- Does not re-test Detroit/Tampa (already proven by PR #9 results)
- Does not address the slug duplication issue from SOURCE_REGISTRY_AUDIT_APR26.md (separate concern)
