# Import-script audit (read-only)

**Methodology:** Read each `import-<city>.mjs` (and `.js`) under `scripts/mac-mini-imports/` and `scripts/`. Did NOT execute. Looking for: target project, env-var names, error-handling pattern, write strategy.

## Common shape (all scripts inspected)

```js
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
// ... createClient(URL, KEY)
// ... batched insert into schedule_reports, BATCH_SIZE=500
```

This is the **canonical pattern** — used by chicago, seattle, charlotte, columbus, fort-worth, austin, boston, phoenix, houston, dallas, denver, philadelphia, etc. (all of `mac-mini-imports/import-*.mjs`).

## Hardcoded URLs found

Only **5 scripts** reference a literal Supabase URL (and they all reference the **correct** project):
- `scripts/import-zones.mjs` — `'https://qsuzfemakaaroeakyick.supabase.co'`
- `scripts/mac-mini-imports/geocode-addresses.js` — `process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://qsuzfemakaaroeakyick.supabase.co'`
- `scripts/mac-mini-imports/import-274k.js` — same fallback pattern
- `scripts/mac-mini-imports/import-edco-remaining.js` — same
- `scripts/mac-mini-imports/import-edco-to-supabase.js` — same

**No legacy / wrong-project URLs detected.** All scripts hit `qsuzfemakaaroeakyick`, which matches what `.env.local` provides.

## Per-script summary table

| Script | Has Supabase write? | Error handling? | Target project | Write target |
|---|---|---|---|---|
| `import-austin.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-boston.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-charlotte.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-chicago.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-columbus.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-dallas.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-denver.mjs` / `-v2` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-detroit.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-fort-worth.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-houston.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-indianapolis.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-jacksonville.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-kansas-city.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-la-county.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-louisville.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-mesa.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-miami.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-milwaukee.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-nyc.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-philadelphia.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-phoenix.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-portland.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-raleigh.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-san-antonio.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-san-francisco.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-seattle.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-tucson.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-baltimore.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-albuquerque.mjs` | Y | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |
| `import-zones.mjs` (root) | Y | exit-on-missing-env | hardcoded `qsuzfemakaaroeakyick` | `schedule_reports` |
| `geocode-addresses.js` | utility | env+fallback | `qsuzfemakaaroeakyick` | n/a (geocode) |
| `import-274k.js` | Y | env+fallback | `qsuzfemakaaroeakyick` | `schedule_reports` |
| `import-edco-remaining.js` | Y | env+fallback | `qsuzfemakaaroeakyick` | `schedule_reports` |
| `import-edco-to-supabase.js` | Y | env+fallback | `qsuzfemakaaroeakyick` | `schedule_reports` |
| `import-arcgis-cities.mjs` | Y (multi-city) | exit-on-missing-env | `qsuzfemakaaroeakyick` (env) | `schedule_reports` |

**Total: ~32 import scripts.** All wired to the same project, same env-vars, same target table. None are silently dropping rows due to wrong project.

## Conclusion

There is no "scripts writing to wrong Supabase project" problem. Pipeline plumbing is consistent and correct. The data IS in `schedule_reports` (~6.28M rows from 44+ distinct cities — see `cities-actual.txt`). The "missing cities" perception comes from the audit script's broken `fetchLiveCities()` — see `DIAGNOSIS.md`.
