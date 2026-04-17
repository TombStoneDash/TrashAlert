<#
 .SYNOPSIS
   TrashAlert Pre-Flight Verification — Lenovo ThinkCentre
   Run this BEFORE firing the Claude Code autonomous run.

 .DESCRIPTION
   Single-script sanity check that confirms:
     1. No leaked ANTHROPIC_API_KEY that would bill to API/Extra Usage
     2. Claude CLI is authenticated via OAuth (Max sub)
     3. Repo is in the expected state with push access
     4. Vercel CLI state
     5. Supabase .env.local is present
     6. Node + tsx are installed
     7. Power plan won't put the machine to sleep
     8. npm run build passes

   Exit code 0 = green to fire. Non-zero = fix the flagged item first.

 .USAGE
   cd C:\TombstoneDash\factory\trashalert
   powershell -ExecutionPolicy Bypass -File .\preflight.ps1

   Or from the Mac Mini over SSH:
   ssh Smart_Home@100.81.172.90 "powershell -ExecutionPolicy Bypass -File C:\TombstoneDash\factory\trashalert\preflight.ps1"
#>

$ErrorActionPreference = "Continue"
$repoPath = "C:\TombstoneDash\factory\trashalert"

# Track pass/fail
$checks = @()
function Record($name, $status, $detail) {
  $script:checks += [pscustomobject]@{ Name = $name; Status = $status; Detail = $detail }
  $icon = switch ($status) {
    "PASS" { "✅" }; "WARN" { "⚠ " }; "FAIL" { "❌" }; default { "  " }
  }
  Write-Host "$icon $name — $detail"
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host "  TrashAlert Pre-Flight Verification"
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host ""
Write-Host "── 1. BILLING / AUTH ─────────────────────────────"

# 1a. Process-level ANTHROPIC_API_KEY
$procKey = $env:ANTHROPIC_API_KEY
if ([string]::IsNullOrEmpty($procKey)) {
  Record "Process env ANTHROPIC_API_KEY" "PASS" "not set"
} else {
  Record "Process env ANTHROPIC_API_KEY" "FAIL" "SET (starts with '$($procKey.Substring(0, [Math]::Min(8,$procKey.Length)))…') — this WILL bill to API usage. Run: Remove-Item Env:ANTHROPIC_API_KEY"
}

# 1b. Process-level ANTHROPIC_AUTH_TOKEN
$procAuth = $env:ANTHROPIC_AUTH_TOKEN
if ([string]::IsNullOrEmpty($procAuth)) {
  Record "Process env ANTHROPIC_AUTH_TOKEN" "PASS" "not set"
} else {
  Record "Process env ANTHROPIC_AUTH_TOKEN" "WARN" "set — may override OAuth"
}

# 1c. User-level env var
$userKey = [System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
if ([string]::IsNullOrEmpty($userKey)) {
  Record "User env ANTHROPIC_API_KEY" "PASS" "not set"
} else {
  Record "User env ANTHROPIC_API_KEY" "FAIL" "SET at User scope — persists across sessions. Run: [System.Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', `$null, 'User')"
}

# 1d. Machine-level env var
$machineKey = [System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "Machine")
if ([string]::IsNullOrEmpty($machineKey)) {
  Record "Machine env ANTHROPIC_API_KEY" "PASS" "not set"
} else {
  Record "Machine env ANTHROPIC_API_KEY" "FAIL" "SET at Machine scope (needs admin to remove)"
}

# 1e. Claude config file
$claudeConfig = "$env:USERPROFILE\.claude\config.json"
if (Test-Path $claudeConfig) {
  $configContent = Get-Content $claudeConfig -Raw -ErrorAction SilentlyContinue
  if ($configContent -match "sk-ant-") {
    Record "Claude config file" "FAIL" "contains an API key string — investigate $claudeConfig"
  } else {
    Record "Claude config file" "PASS" "exists, no API key string visible"
  }
} else {
  Record "Claude config file" "WARN" "not found at $claudeConfig (OK if Claude stores credentials elsewhere)"
}

# 1f. Claude CLI version + auth
try {
  $claudeVersion = & claude --version 2>&1 | Out-String
  Record "Claude CLI installed" "PASS" "version: $($claudeVersion.Trim())"
} catch {
  Record "Claude CLI installed" "FAIL" "not on PATH — run: winget install Anthropic.Claude"
}

try {
  $authStatus = & claude auth status 2>&1 | Out-String
  if ($authStatus -match "oauth|max|subscription|logged in" -or $authStatus -match "@") {
    Record "Claude auth status" "PASS" "$($authStatus.Trim() -replace '\r?\n', ' ')"
  } else {
    Record "Claude auth status" "WARN" "could not determine auth mode — output: $($authStatus.Trim() -replace '\r?\n', ' ')"
  }
} catch {
  Record "Claude auth status" "WARN" "'claude auth status' not supported on this version — verify manually"
}

Write-Host ""
Write-Host "── 2. REPO + GIT ─────────────────────────────────"

if (-not (Test-Path $repoPath)) {
  Record "Repo directory" "FAIL" "not found: $repoPath"
  Write-Host ""; Write-Host "Cannot continue without repo. Aborting."; exit 1
} else {
  Record "Repo directory" "PASS" "exists at $repoPath"
}

Set-Location $repoPath

try {
  $gitStatus = git status --short 2>&1 | Out-String
  if ([string]::IsNullOrWhiteSpace($gitStatus)) {
    Record "Git status" "PASS" "clean"
  } else {
    $dirtyLines = ($gitStatus -split "`n" | Where-Object { $_.Trim() }).Count
    Record "Git status" "WARN" "$dirtyLines uncommitted changes — commit or stash before run"
  }

  $branch = git rev-parse --abbrev-ref HEAD 2>&1 | Out-String
  $branch = $branch.Trim()
  if ($branch -eq "main" -or $branch -eq "master") {
    Record "Git branch" "PASS" "$branch"
  } else {
    Record "Git branch" "WARN" "on '$branch', not main/master — switch before run"
  }

  $remote = git remote get-url origin 2>&1 | Out-String
  Record "Git remote" "PASS" "$($remote.Trim())"

  $lastCommit = git log -1 --oneline 2>&1 | Out-String
  Record "Last commit" "PASS" "$($lastCommit.Trim())"

  # Test push access with dry-run
  $pushTest = git push --dry-run origin HEAD 2>&1 | Out-String
  if ($LASTEXITCODE -eq 0) {
    Record "Git push access" "PASS" "dry-run succeeded"
  } else {
    Record "Git push access" "FAIL" "dry-run failed: $($pushTest.Trim())"
  }
} catch {
  Record "Git state" "FAIL" "$_"
}

Write-Host ""
Write-Host "── 3. VERCEL ─────────────────────────────────────"

try {
  $vercelVer = & vercel --version 2>&1 | Out-String
  Record "Vercel CLI" "PASS" "v$($vercelVer.Trim())"
  if (Test-Path ".vercel\project.json") {
    $projectJson = Get-Content ".vercel\project.json" -Raw | ConvertFrom-Json
    Record "Vercel project linked" "PASS" "project: $($projectJson.projectId)"
  } else {
    Record "Vercel project linked" "WARN" ".vercel\project.json missing — may need: vercel link"
  }
} catch {
  Record "Vercel CLI" "WARN" "not installed — will rely on git push → auto-deploy. Install: npm i -g vercel"
}

Write-Host ""
Write-Host "── 4. ENV + CREDENTIALS ──────────────────────────"

if (Test-Path ".env.local") {
  $envLocal = Get-Content ".env.local" -Raw
  $hasSupabaseUrl = $envLocal -match "SUPABASE_URL"
  $hasSupabaseKey = $envLocal -match "SUPABASE_(?:ANON|SERVICE_ROLE)_KEY"
  if ($hasSupabaseUrl -and $hasSupabaseKey) {
    Record ".env.local" "PASS" "present with Supabase credentials"
  } else {
    Record ".env.local" "WARN" "present but missing Supabase URL or key"
  }
  if ($envLocal -match "ANTHROPIC_API_KEY") {
    Record ".env.local safety" "FAIL" "contains ANTHROPIC_API_KEY — remove it, Claude Code will pick it up"
  }
} else {
  Record ".env.local" "FAIL" "not present — pull from Mac Mini: scp ops@Mac-mini:~/Projects/trashalert/.env.local ."
}

Write-Host ""
Write-Host "── 5. NODE / BUILD ───────────────────────────────"

try {
  $nodeVer = & node --version 2>&1 | Out-String
  Record "Node" "PASS" "$($nodeVer.Trim())"
} catch { Record "Node" "FAIL" "not installed" }

try {
  $npmVer = & npm --version 2>&1 | Out-String
  Record "npm" "PASS" "$($npmVer.Trim())"
} catch { Record "npm" "FAIL" "not installed" }

try {
  $tsxVer = & npx tsx --version 2>&1 | Out-String
  Record "tsx" "PASS" "$($tsxVer.Trim())"
} catch { Record "tsx" "WARN" "not installed — run: npm i -D tsx" }

Write-Host ""
Write-Host "Running 'npm run build' (this may take a minute)..."
$buildOutput = & npm run build 2>&1 | Out-String
if ($LASTEXITCODE -eq 0) {
  Record "npm run build" "PASS" "exit 0"
} else {
  $tailLines = ($buildOutput -split "`n" | Select-Object -Last 10) -join "; "
  Record "npm run build" "FAIL" "exit $LASTEXITCODE — tail: $tailLines"
}

Write-Host ""
Write-Host "── 6. POWER / SLEEP ──────────────────────────────"

try {
  $standby = powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 2>&1 | Out-String
  if ($standby -match "0x00000000") {
    Record "Sleep timeout (AC)" "PASS" "never sleeps on AC"
  } else {
    Record "Sleep timeout (AC)" "WARN" "non-zero — run: powercfg /change standby-timeout-ac 0"
  }
} catch {
  Record "Power query" "WARN" "couldn't query powercfg"
}

# Summary
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
$passCount = ($checks | Where-Object { $_.Status -eq "PASS" }).Count
$warnCount = ($checks | Where-Object { $_.Status -eq "WARN" }).Count
$failCount = ($checks | Where-Object { $_.Status -eq "FAIL" }).Count
Write-Host "  $passCount passed · $warnCount warnings · $failCount failed"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ($failCount -gt 0) {
  Write-Host ""
  Write-Host "❌ DO NOT LAUNCH. Fix these failures first:" -ForegroundColor Red
  $checks | Where-Object { $_.Status -eq "FAIL" } | ForEach-Object {
    Write-Host "   • $($_.Name): $($_.Detail)" -ForegroundColor Red
  }
  exit 1
}

if ($warnCount -gt 0) {
  Write-Host ""
  Write-Host "⚠  Warnings (review before launch):" -ForegroundColor Yellow
  $checks | Where-Object { $_.Status -eq "WARN" } | ForEach-Object {
    Write-Host "   • $($_.Name): $($_.Detail)" -ForegroundColor Yellow
  }
  Write-Host ""
  Write-Host "Warnings are OK if you understand them. Read each one, then proceed."
  exit 0
}

Write-Host ""
Write-Host "✅ All green. Safe to fire the Claude Code run." -ForegroundColor Green
exit 0
