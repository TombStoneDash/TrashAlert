# Branch Audit — TrashAlert
## 2026-04-18T (investigation only, no changes made)

## 1. Is there a `main` branch?

**No.** `git fetch --all --prune` followed by `git branch -r` shows no `main` (or `master`) on origin. Nothing local either.

Full remote branch list (11 claude/* branches + HEAD alias):
```
origin/HEAD -> origin/claude/sample-addresses-per-city-018Sy3dmmPibwGHSBHMkh6cQ
origin/claude/add-city-subdivisions-01TCLWRyyUCNvByLep7poDJG
origin/claude/add-logging-config-production-01TmmM9MJaQPrMcS52HG7Sug
origin/claude/dev-backlog-implementation-01F3qB6TrkNiJwhfdYSj66Nk
origin/claude/extract-osm-addresses-0173qeaVftpnt51TWtCB9h2h
origin/claude/fix-security-dependencies-01WYnLvRHpCj4hvWi3PfXVqE
origin/claude/load-sqlite-database-01TdxLDvf6NxK2ipJn5jxu4J
origin/claude/multi-domain-strategy-01TJfhofW6HFFxWqwoJkmAwd
origin/claude/sample-addresses-per-city-018Sy3dmmPibwGHSBHMkh6cQ
origin/claude/setup-city-boundaries-01FAUGN9C24jswuk9tN1BaYJ
origin/claude/sleepy-kapitsa-2b2b2d
origin/claude/trash-day-database-pilot-01J6tWWMEh8xoqv72NqYTDLK
```

(You said 13 earlier — I count 11 remote claude branches. Possibly 2 were pruned by the `--prune` this session, or the count was approximate.)

## 2. What is GitHub's default branch?

```
$ gh repo view TombStoneDash/TrashAlert --json defaultBranchRef,name,url
{"defaultBranchRef":{"name":"claude/sample-addresses-per-city-018Sy3dmmPibwGHSBHMkh6cQ"}, ...}

$ git ls-remote --symref origin HEAD
ref: refs/heads/claude/sample-addresses-per-city-018Sy3dmmPibwGHSBHMkh6cQ	HEAD
```

**The `claude/sample-addresses-per-city-018Sy3dmmPibwGHSBHMkh6cQ` branch IS the production / default branch on GitHub.** Two independent sources agree (GitHub API via gh, Git protocol via ls-remote symref).

## 3. What branch does Vercel deploy from?

**Not explicitly stated in-repo.** `.vercel/project.json` carries only project/org IDs:
```json
{"projectId":"prj_nk45EIrK69GV6iB0yXA5X6gfX35U","orgId":"team_GGlBhpGOJUGs1iAtwObFj31U","projectName":"trashalert"}
```
`vercel.json` defines routes and Python builds but no branch setting (Vercel typically reads deploy-branch config from the dashboard, not the repo).

**Reasonable inference: Vercel deploys from the GitHub default branch.** When a Vercel project is set up with GitHub integration and no override, the "production branch" in Vercel settings defaults to the GitHub default — which is `claude/sample-addresses-per-city-...`. This is consistent with what we've observed: every commit to this branch has been triggering deploys (seen indirectly via trashalert.io serving the latest homepage/routes).

Can't 100% confirm without Vercel dashboard access or `vercel project ls`. If you want certainty, run (from your shell, not the agent):
```powershell
npx vercel project ls
# or
npx vercel inspect trashalert --token=<token>
```

## 4. Divergence from current branch

Against current `origin/claude/sample-addresses-per-city-018Sy3dmmPibwGHSBHMkh6cQ` (tip: `585d38a`):

| Branch | Ahead | Behind | Last commit | Status |
|---|---:|---:|---|---|
| add-city-subdivisions | 1 | 299 | 2025-11-16 | STALE — early work; 1 commit never merged |
| add-logging-config-production | 1 | 299 | 2025-11-16 | STALE |
| dev-backlog-implementation | 1 | 120 | 2025-11-19 | STALE |
| extract-osm-addresses | 1 | 299 | 2025-11-16 | STALE |
| fix-security-dependencies | 0 | 113 | 2025-12-04 | **MERGED** (0 ahead — all content already on main) |
| load-sqlite-database | 1 | 299 | 2025-11-16 | STALE |
| multi-domain-strategy | 2 | 116 | 2025-11-28 | STALE |
| setup-city-boundaries | 1 | 299 | 2025-11-16 | STALE |
| **sleepy-kapitsa-2b2b2d** | **5** | **8** | **2026-04-16** | ⚠ **ACTIVE, DIVERGED** |
| trash-day-database-pilot | 2 | 299 | 2025-11-16 | STALE |

### The one that matters: `sleepy-kapitsa-2b2b2d`

**Last commit 2026-04-16 — 2 days before now.** Has a local worktree checked out at `.claude/worktrees/sleepy-kapitsa-2b2b2d` (Daisy's parallel workflow, presumably).

5 unique commits on sleepy-kapitsa that are NOT on our branch:
```
fa81087 fix: align address-count fallback with actual DB (5.2M+, rounded 100K)
0893a10 feat(coverage): add Request Your City form + /api/request-city endpoint
2dde835 fix(api): /api/stats endpoints query Supabase on every request
1bbdb27 feat(homepage): add App Store download badge to hero section
8b22b15 feat: add 14 city import scripts for address expansion
```

8 commits on our branch NOT on sleepy-kapitsa (mostly the SETUP + TEST_FIRE_v2 series):
```
585d38a chore(pre-fire): align audit defaults + directive baseline
88fb8a1 feat(audit): add Chicago and Seattle landmarks
e5c26f8 fix(audit): replace silently-undercounting fetchLiveCities
5dea32c chore(diag): reality check on city import pipeline
4060204 chore(setup): complete preflight + baseline audit
a9cd889 chore(setup): organize directive files + wire audit script
0593b4a feat(scripts): add Raleigh NC (128K addresses) and Mesa AZ (270 zones)
cba6504 feat: add /api/request-city endpoint + form, disable stats caching
```

### Diff scope between the two

```
$ git diff --stat origin/claude/sleepy-kapitsa-2b2b2d origin/claude/sample-addresses-per-city-...
39 files changed, 5194 insertions(+), 1823 deletions(-)
```

**Real conflicts / overlapping touches:**
- `package.json`, `package-lock.json` — both branches added deps
- `scripts/audit-cities.ts` — both branches modified (our audit fix vs sleepy's work)
- `vercel_app/handler.py` — sleepy has +143 lines (the `/api/stats` Supabase-on-every-request fix — this is the stats-cache fix I flagged as "out-of-scope" in the v2 diagnosis; it's actually been done, just on the other branch)
- `specs/property-managers-page.tsx` — sleepy added +676 lines (we parked an empty stub; sleepy carries the real spec or a substantially different version)
- `frontend/about.html`, `coverage.html`, `for-property-managers.html`, `index.html` — sleepy has frontend changes
- `scripts/import-<city>.mjs` — sleepy added **14 new import scripts at the `scripts/` root level** (albuquerque, baltimore, columbus-note, indianapolis, jacksonville, kansas-city, la-county, louisville, mesa, miami-dade, milwaukee, pittsburgh, raleigh, tucson). Note: some of these ALSO exist under `scripts/mac-mini-imports/` on both branches — potential duplication.
- `DAISY_DIRECTIVE_ROAD_TO_150M.md`, `DAISY_DIRECTIVE_TEST_FIRE_4H.md`, `SETUP.md`, `FINISH_SETUP.md`, `DIRECTIVE_TEST_FIRE_v2.md`, `DIAGNOSIS.md` — sleepy has a version of each, different from ours

**Probable semantic conflicts:**
- Our commit `cba6504 feat: add /api/request-city endpoint + form, disable stats caching` was made ON our branch before the divergence began.
- Sleepy's `0893a10 feat(coverage): add Request Your City form + /api/request-city endpoint` and `2dde835 fix(api): /api/stats endpoints query Supabase on every request` continue that same feature direction.
- Result: sleepy IS an extension of our work, not a parallel fork — it's a continuation with 5 commits we haven't merged back.

### Local `.git/config` quirk

```
[branch "claude/sleepy-kapitsa-2b2b2d"]
    remote = origin
    merge = refs/heads/claude/sample-addresses-per-city-018Sy3dmmPibwGHSBHMkh6cQ
```

Sleepy's local upstream is configured to pull/merge from our current branch — meaning whoever set up the worktree intended the two to be integrated. They haven't been yet.

## 5. Is the current branch the effective production branch?

**Yes.** Three pieces of evidence:

1. GitHub marks it as `defaultBranchRef`.
2. Git protocol (`ls-remote --symref`) reports it as origin HEAD.
3. Vercel's GitHub integration defaults to the GitHub default branch for production deploys — and every recent trashalert.io behavior has been consistent with commits to this branch taking effect.

There is no hidden `main` being ignored. The current branch, despite its auto-generated `claude/...` name, IS production.

## Implications for ROAD_TO_150M

**Three hygiene issues need a decision before firing a 12-hour autonomous run:**

### A) The `sleepy-kapitsa` divergence is a real merge problem

The 5 commits on sleepy include high-value work that overlaps with content likely to be generated during ROAD_TO_150M:
- Address-count alignment fix (which may conflict with any counter work the agent does)
- `/api/stats` Supabase-on-every-request fix (the same lie we flagged as out-of-scope — it IS fixed, on sleepy)
- 14 new city import scripts at `scripts/` root (would collide with any new imports the agent commits there)
- Frontend HTML updates (would collide with any coverage/homepage changes)

If ROAD_TO_150M fires now and sleepy never merges back, we end up with two divergent "main-lines" carrying different truths about:
- How many cities have scripts (we'd look at `ls scripts/` and miss sleepy's 14)
- What `/api/stats` actually does in production (sleepy's deployed version ≠ what this branch's code says)

**Recommended action before firing:**
1. Either **rebase/merge sleepy-kapitsa onto current branch** (5 commits on top of our 8 — manageable conflicts, mostly in `audit-cities.ts`, `package.json`, and the directive .md files), OR
2. **Fire ROAD_TO_150M from sleepy-kapitsa** (it has the stats fix + extra import scripts, and the merge target is already configured). But then you'd have to first pull our 8 setup/diag commits into it.

Either way, the two should be reconciled to a single head.

### B) The 9 stale claude/* branches are noise

Any one of them could theoretically be claimed by a future agent run (`git checkout origin/claude/add-city-subdivisions-...`). Their age and "1 ahead, 299 behind" shape mean they're dead — safe to delete on origin once you've confirmed no one's using them. Non-blocking for ROAD_TO_150M, but clutters `git branch -r`.

### C) No real `main` branch

The current setup works (`claude/sample-addresses-per-city-...` IS production), but the name is opaque and the branch will keep accumulating cruft. For a 12-hour autonomous run, this is fine — commits just go to the default. But worth considering: renaming the default to `main` (GitHub has a one-click operation) would make `git log --oneline main` work for any human who looks at the repo later, and matches convention for tooling that assumes `main` exists.

**Non-blocking for ROAD_TO_150M.** Flag it now, do it later.

## Recommended order of ops before firing

1. **Decide on sleepy-kapitsa**: merge it in (recommended), abandon it, or run from it. Do NOT fire with it diverged.
2. Optional: delete the 9 stale claude/* branches on origin (one-liner each via `gh api -X DELETE …` or GitHub UI).
3. Optional: rename GitHub default `claude/sample-addresses-per-city-...` → `main`. Vercel auto-follows. Stale remote refs update on next fetch.
4. THEN fire ROAD_TO_150M.

No files changed in this investigation. `BRANCH_AUDIT.md` is the only new file, not yet committed. Awaiting GO.
