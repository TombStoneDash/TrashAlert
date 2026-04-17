# PRE-FLIGHT ANSWERS — 12-Hour TrashAlert Autonomous Run
## Lenovo ThinkCentre (DESKTOP-1TV907A, Tailscale 100.81.172.90)

---

## 🔴 BILLING / AUTH

### 1. Claude version + auth method
Run on the Lenovo:
```powershell
claude --version
claude auth status
```
Expected: Claude Code should show authenticated via OAuth (Max subscription). Daisy confirmed on April 17 at 10:10 AM: "Claude CLI authenticated (Max subscription, clinisyslims@gmail.com)." The auth is through clinisyslims@gmail.com OAuth — that's your Max sub.

### 2. How was it authenticated?
OAuth via `claude auth login`. Daisy ran this during Forge setup. It pulls from your $200/mo Max subscription — NOT API billing. Confirmed: no ANTHROPIC_API_KEY was set. The Claude Code Desktop app (which you've been using — visible in your screenshots at "Opus 4.7 1M · High") also uses your Max sub OAuth automatically.

### 3. Check for leaked API keys
Run on the Lenovo:
```powershell
echo $env:ANTHROPIC_API_KEY
echo $env:ANTHROPIC_AUTH_TOKEN
Get-Content "$env:USERPROFILE\.claude\config.json" -ErrorAction SilentlyContinue
```
Expected: All should be empty/not found. If ANTHROPIC_API_KEY returns a value starting with `sk-ant-`, that's a leaked key that will override OAuth and bill to API usage. Remove it immediately with:
```powershell
Remove-Item Env:ANTHROPIC_API_KEY
```
Also check system-level env vars:
```powershell
[System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "Machine")
[System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
```
If either returns a key, remove it:
```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "User")
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "Machine")
```

### 4. Proving OAuth works
After unsetting any API key (if found), run:
```powershell
claude "echo hello"
```
If it responds, OAuth is doing the work. If it fails with auth error, the key WAS the auth and you need to re-run `claude auth login`.

### 5. Native vs WSL vs Git Bash
Native Windows. Claude Code Desktop runs natively on Windows (visible in your screenshots — Windows Terminal UI, PowerShell paths with backslashes, C:\ drive references). NOT WSL. Auth is on the Windows side at `%USERPROFILE%\.claude\`.

---

## 🔴 REPO + DEPLOY STATE

### 6. Repo status
`C:\TombstoneDash\factory\trashalert` is a clone of the production repo (TombStoneDash/TrashAlert on GitHub). The Lenovo has push access — it pushed 20+ commits and created branches earlier today. Run to verify:
```powershell
cd C:\TombstoneDash\factory\trashalert
git status
git branch
git remote -v
git log --oneline -5
```
The factory sessions pushed to feature branches (e.g., `claude/sleepy-kapitsa-2b2b2d`). Those branches were merged to main earlier today. You should be on `main` now. If not:
```powershell
git checkout main
git pull origin main
```

### 7. Vercel CLI
Likely NOT installed or not linked. The factory sessions relied on git push → Vercel auto-deploy, not `vercel --prod`. Check:
```powershell
vercel --version
```
If not installed: `npm i -g vercel && vercel login && vercel link` (link to the trashalert project). But auto-deploy via git push to main is the primary path.

### 8. Vercel auto-deploy
It HAS silently broken before (documented in lessons learned). The factory sessions today all pushed to branches, not main, precisely because of this risk. After merging to main, check Vercel dashboard → TrashAlert → Deployments to confirm the latest deploy succeeded. If broken: `vercel --prod --yes` as fallback. Also check Settings → Git in Vercel to verify the GitHub integration is connected.

### 9. Supabase credentials
Check for `.env.local` in the trashalert repo:
```powershell
type C:\TombstoneDash\factory\trashalert\.env.local
```
You need at minimum:
- `SUPABASE_URL=https://[your-project].supabase.co`
- `SUPABASE_ANON_KEY=eyJ...` or `SUPABASE_SERVICE_ROLE_KEY=eyJ...`

If not present on the Lenovo, pull from the Mac Mini:
```bash
# From Mac Mini terminal:
scp ops@Mac-mini:~/Projects/trashalert/.env.local Smart_Home@100.81.172.90:/c/TombstoneDash/factory/trashalert/.env.local
```

The table is `schedule_reports`. Columns (based on import scripts):
- `address` (text)
- `city` (text)
- `state` (text)
- `zip` (text)
- `collection_day` (text — monday/tuesday/etc, CHECK CONSTRAINT)
- `waste_type` (text)
- `zone` (text)
- `provider` (text)

Verify with:
```powershell
# If you have supabase CLI, or just check the Supabase dashboard
```

This is the PRODUCTION database. Current count: 5,191,847 addresses across 26 cities. The import scripts write directly to prod — there is no staging DB. Be careful.

---

## 🔴 API CONTRACT

### 10. Schedule lookup endpoint
The actual endpoint is `/api/schedule` (or `/api/lookup` — the homepage rebuild changed this). Check the codebase:
```powershell
findstr /r /s "api/schedule\|api/lookup" C:\TombstoneDash\factory\trashalert\src\*.ts C:\TombstoneDash\factory\trashalert\src\*.js C:\TombstoneDash\factory\trashalert\api\*.py
```
The response shape likely includes `collection_day` (matching the DB column name), not `trash_day` or `trashDay`. The factory rebuild today wired the homepage to use `/api/lookup` with relative paths (removed localhost:8000 references). 

Also check for the Republic Services and ReCollect fallback — the API now has a multi-source lookup chain:
1. Supabase batch data (5.19M addresses)
2. Republic Services API fallback (~14M addresses)
3. Waste Connections/ReCollect API fallback (~3-5M addresses)

The integration files are at:
- `src/lib/republic-lookup.ts`
- `src/lib/wastecx-lookup.ts`

### 11. Geocoding / zone lookup
Check the actual code:
```powershell
type C:\TombstoneDash\factory\trashalert\src\lib\city-geocode.ts
```
This may not exist as described. The import scripts use a different pattern — they pull zone/route data from ArcGIS FeatureServers and map zones to collection days, then bulk-insert into Supabase. They don't geocode individual addresses. The LOOKUP endpoint (not import) may do geocoding for real-time queries. Check the actual file structure:
```powershell
dir C:\TombstoneDash\factory\trashalert\src\lib\
```

---

## 🟡 ENVIRONMENT

### 12. Node/npm/tsx
Daisy confirmed on April 17: Node v24.14.1, npm 11.11.0. tsx may or may not be installed. Check:
```powershell
node --version
npm --version
npx tsx --version
npm run build
```

### 13. Stay awake
YES — this was configured early in the Lenovo setup. We ran these PowerShell commands:
```powershell
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
powercfg /hibernate off
```
Windows auto-updates were set to active hours 6 AM - 2 AM. Verify:
```powershell
powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE
```
Should show 0x00000000 (never sleep).

### 14. Terminal + detachment
Claude Code Desktop runs inside its own Electron window — it's a standalone app, not inside a terminal emulator. If you close the window, the session dies. There is NO built-in detach/background mode.

Options for persistence:
- **Don't close the window.** Lock the screen instead of closing. The Lenovo stays on (power settings above).
- **Use CLI instead:** Open PowerShell, run `claude --dangerously-skip-permissions`, and use `start /b` or `nohup` equivalent. But Windows doesn't have great process detachment.
- **Best option:** Use Windows Terminal with a named session. Close the lid/lock screen. The process continues as long as the machine doesn't sleep (it won't, per power settings).
- **If you need to reboot your laptop:** The Lenovo is a separate machine. Closing your laptop doesn't affect the Lenovo. The Lenovo runs independently.

---

## 🟡 COORDINATION WITH DAISY

### 15. Telegram updates
YES — have the Lenovo agent post to Telegram. But the Lenovo factory agent (Claude Code) doesn't have Telegram access natively. Two options:
- **Option A:** Write progress to a log file. Daisy reads it via SSH every 30 min and posts to Telegram.
- **Option B:** Include in the directive: "After each commit, write a one-line summary to C:\TombstoneDash\factory\logs\trashalert-progress.log" — Daisy picks it up.

Forge (when stable) would handle this natively via its Telegram bot. But Forge isn't stable yet, so for this run, use the log file approach.

### 16. Collision risk
LOW. Daisy doesn't actively commit to TrashAlert unless directed. She's on the weekend mega-directive which says "FINISH things, don't start new ones." To be safe, add to Daisy's directive:
```
STAND DOWN on TrashAlert commits until Lenovo factory run completes. Do not push to TombStoneDash/TrashAlert repo. Read-only monitoring only.
```

---

## 🟢 MONITORING / SAFETY

### 17. Watching progress
Three methods:
1. **Git log from Mac Mini:** `ssh Smart_Home@100.81.172.90 "cd C:\TombstoneDash\factory\trashalert && git log --oneline -10"` — run anytime
2. **Vercel dashboard:** Check trashalert deployments at vercel.com/team_GGlBhpGOJUGs1iAtwObFj31U
3. **Progress log:** Have the agent write to a log file after each commit. Read via SSH: `ssh Smart_Home@100.81.172.90 "type C:\TombstoneDash\factory\logs\trashalert-progress.log"`

### 18. Halt and revert
Fastest halt: Kill the process on the Lenovo:
```bash
# From Mac Mini:
ssh Smart_Home@100.81.172.90 "taskkill /F /IM node.exe"
```
To revert: Each commit is atomic (one feature per commit). Find the last good commit:
```bash
ssh Smart_Home@100.81.172.90 "cd C:\TombstoneDash\factory\trashalert && git log --oneline -20"
```
Then revert:
```bash
ssh Smart_Home@100.81.172.90 "cd C:\TombstoneDash\factory\trashalert && git revert HEAD~N..HEAD --no-edit && git push"
```
Or hard reset to the last known good:
```bash
ssh Smart_Home@100.81.172.90 "cd C:\TombstoneDash\factory\trashalert && git reset --hard <good-commit-sha> && git push --force"
```

### 19. Claude Code usage limits on Max sub
This is the key question. Anthropic's Max plan ($200/mo) includes Claude Code usage but with limits. The exact caps change — check https://docs.claude.com for current limits. As of recent knowledge:
- There are hourly and daily token caps on Max
- A 12-hour continuous run WILL likely hit the hourly cap multiple times, causing pauses
- The agent won't die — it pauses and resumes when the cap resets
- You may lose ~30-60 min per cap reset
- The weekly limit is the bigger concern for a 12-hour run

**Recommendation:** Run the 4-hour test fire FIRST (as planned). Monitor how many times it gets rate-limited. That tells you whether a 12-hour run is realistic or needs to be broken into 3x 4-hour sessions.

---

## SUMMARY — GREEN / YELLOW / RED

| Item | Status |
|------|--------|
| 1-5. Billing/Auth | 🟢 OAuth via Max sub confirmed. Verify no leaked API key (run the echo commands). |
| 6. Repo | 🟢 Clone with push access. Verify on main branch. |
| 7. Vercel CLI | 🟡 Likely not installed. Auto-deploy via git push is primary path. |
| 8. Auto-deploy | 🟡 Has broken before. Check after first push. |
| 9. Supabase | 🟡 Verify .env.local exists on Lenovo. May need to copy from Mac Mini. |
| 10-11. API contract | 🟡 Check actual endpoint paths and response shapes in codebase. |
| 12. Node/npm | 🟢 v24.14.1 confirmed. |
| 13. Stay awake | 🟢 Power settings configured. |
| 14. Detach | 🟡 No background mode. Don't close the window. Lenovo runs independently. |
| 15. Telegram | 🟡 Use log file approach. Daisy reads via SSH. |
| 16. Collision | 🟢 Low risk. Tell Daisy to stand down on TrashAlert. |
| 17-18. Monitor/revert | 🟢 SSH + git log + taskkill. |
| 19. Rate limits | 🟡 Test with 4-hour run first. Expect pauses at hourly caps. |

**Bottom line:** Run the verification commands (questions 1-4, 6, 9, 10-11) on the Lenovo. Paste results back. If no API key is leaking, you're clear to fire the 4-hour test tonight.
