# Factory Queue Triage — 2026-04-26

Source: `C:/TombstoneDash/factory/queue/` (43 items including subdirectories)
Method: filename + spot-sample classification. Items marked NEEDS-EYES warrant a closer human look.

## Disposition codes

- **DONE** — work shipped (verified by file location, recent PR/commit, or this run's outputs)
- **IN-PROGRESS** — actively being worked
- **STALE** — older than 10 days with no signal of recent attention
- **OUT-OF-SCOPE** — different project (LIMS, BotCaptcha, etc.) or different agent (Daisy)
- **ACTIONABLE** — still relevant, not yet addressed
- **REFERENCE** — strategic/idea note, not a directive
- **NEEDS-EYES** — can't classify without HT review

---

## TrashAlert directives

| File | Disposition | Note |
|---|---|---|
| `DIRECTIVE_50_address_verification.md` | DONE | PR #9 merged-pending; report committed today |
| `DIRECTIVE_OVERNIGHT_APR24.md` | IN-PROGRESS | This run |
| `DIRECTIVE_label_fix.md` (referenced, not in queue) | DONE | PR #10 merged today, prod verified |
| `LENOVO_FACTORY_OVERNIGHT_APR16.md` | STALE | 10 days old; superseded by APR24 overnight directive |
| `LENOVO_FACTORY_PASTE_AND_GO.md` | REFERENCE | Template for paste-and-go runs, not an active directive |
| `CLAUDE_CODE_FIX_PERMISSIONS.md` | NEEDS-EYES | Permissions directive — verify whether settings already cover it |
| `CLAUDE_CODE_TRASHALERT_MEGA_APR15_LATE.md` | STALE | 11 days old "mega" — almost certainly superseded by phase-by-phase work since |
| `CLAUDE_CODE_TRASHALERT_MEGA_APR15_LATE1.md` | STALE | Duplicate-with-suffix of the above |
| `PR1_MERGE_DIRECTIVE.md` | NEEDS-EYES | Specific PR merge — check if PR #1 referenced is shipped |
| `TRASHALERT_HANDOFF_v3.md` | REFERENCE | Handoff doc, not a directive — keep but archive out of queue |
| `SPRINT_IMPORT_FULL_CAMPAIGN.md` | STALE | Phase-1 import campaign already executed (per BLOCKER.md history) |
| `SPRINT_PM_READINESS.md` | NEEDS-EYES | PM readiness sprint — check whether NARPM follow-up tasks landed |
| `SPRINT_trashalert-pipe-fix_2026-04-19.md` | STALE? | 7 days old; check if pipe fix shipped (related to verify-coverage script in PRs #5/#6/#7?) |
| `SPRINT_APR18.md` | STALE | 8 days old generic sprint |

## Cross-project / Daisy / out of scope

| File | Disposition | Note |
|---|---|---|
| `DAISY_DIRECTIVE_ROAD_TO_45M.md` | OUT-OF-SCOPE | Daisy's queue, do not touch |
| `LIMS_FORWARD_BUILD_DIRECTIVE.md` | OUT-OF-SCOPE | LIMS project |
| `LIMS_HOMEPAGE_REVERT_DIRECTIVE.md` | OUT-OF-SCOPE | LIMS project |
| `BOT_CAPTCHA/` (directory, ~5 items) | OUT-OF-SCOPE | BotCaptcha project — separate product |
| `actorlab/` (directory, 1 sprint) | OUT-OF-SCOPE | Actorlab project |
| `visual-check-deploy.md` | OUT-OF-SCOPE | Visual Check CLI, separate tool |

## Old SPRINT_* files (mid-April)

All of these are 12–14 days old. Spot-checking would be needed to know which shipped vs which were abandoned. For overnight purposes, treat all as STALE pending HT review.

| File | Disposition |
|---|---|
| `SPRINT_bazaar_provider_pages_2026-04-13.md` | STALE |
| `SPRINT_calendly_demo_apr13.md` | STALE |
| `SPRINT_city_landing_pages_2026-04-13.md` | STALE |
| `SPRINT_demo_video_recording_prep_2026-04-13.md` | STALE |
| `SPRINT_founding_actor_stripe_apr13.md` | STALE (out-of-scope: Actorlab) |
| `SPRINT_founding_actor_update_2026-04-12.md` | STALE (out-of-scope: Actorlab) |
| `SPRINT_health_endpoint_2026-04-12.md` | STALE |
| `SPRINT_podcast_landing_page_2026-04-12.md` | STALE |
| `SPRINT_portfolio_dashboard_apr13.md` | STALE |
| `SPRINT_portfolio_stripe_apr13.md` | STALE |
| `SPRINT_pro_stripe_apr13.md` | STALE |
| `SPRINT_push_notifications_apr13.md` | STALE |
| `SPRINT_senaite_demo_data_2026-04-13.md` | STALE (out-of-scope: SENAITE) |
| `SPRINT_senaite_voice_interface_apr13.md` | STALE (out-of-scope: SENAITE) |
| `SPRINT_seo_public_pages_fix_2026-04-12.md` | STALE |
| `SPRINT_stripe_dashboard_apr13.md` | STALE |
| `SPRINT_visual-check-v1_2026-04-19.md` | STALE (out-of-scope: Visual Check) |
| `SPRINT_voice_cloning_apr13.md` | STALE (out-of-scope: Actorlab) |
| `SPRINT_zone_map_mvp_2026-04-12.md` | STALE / REFERENCE — see "COLLECTION MAP.txt" below for the same idea |

## Strategy / idea notes (not directives)

| File | Disposition | Note |
|---|---|---|
| `50 million.txt` | REFERENCE | Strategic goal: scale `schedule_reports` to 50M+. Three strategies. Not a directive but useful planning input. |
| `COLLECTION MAP.txt` | REFERENCE | Product idea: Google-Traffic-style map colored by pickup day. Same idea as `SPRINT_zone_map_mvp_2026-04-12.md`. |
| `Option 1.txt` | REFERENCE | One-paragraph note on Vercel installCommand setup, related to a SETUP_REPORT.md item — not actionable as a directive. |
| `kapitsa.txt` | REFERENCE | Branch-merge plan for "sleepy-kapitsa-2b2b2d". Outside this overnight's scope. |
| `test-sprint.md` | STALE | Test artifact, "TEST SPRINT — Forge Pipeline Verification" |

---

## Recommended cleanup actions for HT

1. **Archive 17 STALE sprints from apr-12/13** — move to `factory/archive/sprint-april-2026/` or just delete. They're 2 weeks old and the codebase has moved past them.
2. **Decide on the 4 NEEDS-EYES items**: `CLAUDE_CODE_FIX_PERMISSIONS.md`, `PR1_MERGE_DIRECTIVE.md`, `SPRINT_PM_READINESS.md`, `SPRINT_trashalert-pipe-fix_2026-04-19.md`. 5 minutes of HT time.
3. **Move OUT-OF-SCOPE items to project-specific queues** (Daisy, LIMS, BotCaptcha, Actorlab, Visual Check, SENAITE all have their own homes).
4. **Keep REFERENCE notes** but move them to `factory/notes/` so they don't show up in directive triage.

After this cleanup, the actual queue should drop from ~43 to ~5 truly active items.

## Methodology

- File listing via `ls`, dispositions inferred from filename patterns (date stamps, project prefixes) and spot-checks of 8 ambiguous files (Option 1, 50 million, kapitsa, test-sprint, COLLECTION MAP, visual-check-deploy, BOT_CAPTCHA dir, actorlab dir).
- No file modifications or moves performed — this is an audit only.
- Confidence: high on STALE/OUT-OF-SCOPE classifications; medium on the four NEEDS-EYES items where context isn't visible from filename alone.
