# Bidsa - one-shot setup + fetch for Windows.
# Installs Python 3.12 if missing (winget), installs fetch dependencies,
# stores the database URL in backend\.env (asked once), runs a dry-run
# probe, then the real fetch. -Schedule registers a daily Task Scheduler job.
#
# Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File backend\scripts\setup_fetch.ps1
#   powershell -ExecutionPolicy Bypass -File backend\scripts\setup_fetch.ps1 -Schedule
#
# NOTE: messages are ASCII-only on purpose - Windows PowerShell 5.1 parses
# BOM-less .ps1 files as ANSI and non-ASCII literals corrupt the parser.

param(
    [string]$DatabaseUrl = "",
    [switch]$Schedule,
    [switch]$SkipFetch
)

$ErrorActionPreference = "Stop"
$Backend = Split-Path -Parent $PSScriptRoot   # backend/
$EnvFile = Join-Path $Backend ".env"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# --- 1. Python 3.10+ ---------------------------------------------------------
Step "Checking for Python 3.12"
$py = $null
try { & py -3.12 --version *> $null; if ($LASTEXITCODE -eq 0) { $py = "py -3.12" } } catch {}
if (-not $py) {
    try { & py -3.13 --version *> $null; if ($LASTEXITCODE -eq 0) { $py = "py -3.13" } } catch {}
}
if (-not $py) {
    Step "Python 3.12 not found - installing via winget (may take a few minutes)"
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "winget is not available. Install Python 3.12 manually from python.org, then re-run this script." -ForegroundColor Red
        exit 1
    }
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    & py -3.12 --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Install finished but the launcher cannot see 3.12 yet. Close this window, open a NEW PowerShell, and re-run the script." -ForegroundColor Yellow
        exit 1
    }
    $py = "py -3.12"
}
$pyParts = $py.Split(" ")
$pyExe = $pyParts[0]
$pyVer = $pyParts[1]
Write-Host "Using: $py"

# --- 2. dependencies ---------------------------------------------------------
Step "Installing fetch dependencies"
& $pyExe $pyVer -m pip install --quiet --disable-pip-version-check -r (Join-Path $Backend "requirements-fetch.txt")
if ($LASTEXITCODE -ne 0) { Write-Host "Dependency install failed." -ForegroundColor Red; exit 1 }

Step "Installing headless Chromium for browser mode (first run downloads ~130MB)"
& $pyExe $pyVer -m playwright install chromium
if ($LASTEXITCODE -ne 0) { Write-Host "Chromium install failed." -ForegroundColor Red; exit 1 }

# --- 3. database URL (asked once, stored in backend\.env) --------------------
Step "Database URL"
$existing = ""
if (Test-Path $EnvFile) {
    $line = Select-String -Path $EnvFile -Pattern '^DATABASE_URL=' | Select-Object -First 1
    if ($line) { $existing = $line.Line.Substring(13) }
}
if ($DatabaseUrl) { $existing = $DatabaseUrl }
if (-not $existing) {
    Write-Host "Paste your Neon URL as-is (postgresql://...neon.tech/neondb?sslmode=require...):"
    $existing = Read-Host "DATABASE_URL"
}
if (-not $existing) { Write-Host "No URL provided - stopping." -ForegroundColor Red; exit 1 }
[IO.File]::WriteAllText($EnvFile, "DATABASE_URL=$existing`n", (New-Object Text.UTF8Encoding $false))
Write-Host "Saved to backend\.env - you will not be asked again."

# --- 4. fetch ----------------------------------------------------------------
# One browser session does the field-check AND the fetch. We deliberately do
# NOT run a separate --dry-run first: Etimad's WAF clears roughly one attempt
# per IP, so a throwaway probe would burn it and make the real fetch fail.
Push-Location $Backend
try {
    if ($SkipFetch) {
        Step "Field-check only (--dry-run, no database writes)"
        & $pyExe $pyVer "scripts\fetch_live.py" --dry-run
    } else {
        Step "Fetching from Etimad into the production database (browser mode)"
        & $pyExe $pyVer "scripts\fetch_live.py"
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nFetch did not complete - send the output above to the developer." -ForegroundColor Red
        exit 1
    }
} finally { Pop-Location }

# --- 5. optional daily schedule ----------------------------------------------
if ($Schedule) {
    Step "Registering daily scheduled task (09:00)"
    $cmd = "cd /d `"$Backend`" && $py scripts\fetch_live.py"
    schtasks /Create /F /TN "BidsaFetch" /SC DAILY /ST 09:00 /TR "cmd /c $cmd" | Out-Null
    Write-Host "Task 'BidsaFetch' created - runs daily at 09:00 while the machine is on."
}

Step "DONE. Open bidsa.vercel.app and try the matching page."
