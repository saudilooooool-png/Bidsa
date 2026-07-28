# Bidsa — one-shot setup + fetch for Windows.
# Does everything: installs Python 3.12 if missing (winget), installs the
# fetch dependencies, stores the database URL in backend\.env (asked once),
# runs a dry-run probe, then the real fetch. Optionally registers a daily
# Task Scheduler job with -Schedule.
#
# Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_fetch.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\setup_fetch.ps1 -Schedule

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
Step "التحقق من Python 3.12"
$py = $null
try { & py -3.12 --version *> $null; if ($LASTEXITCODE -eq 0) { $py = "py -3.12" } } catch {}
if (-not $py) {
    try { & py -3.13 --version *> $null; if ($LASTEXITCODE -eq 0) { $py = "py -3.13" } } catch {}
}
if (-not $py) {
    Step "Python 3.12 غير موجود — التثبيت عبر winget (قد يستغرق دقائق)"
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "winget غير متوفر — ثبّت Python 3.12 يدويًا من python.org ثم أعد تشغيل هذا السكربت." -ForegroundColor Red
        exit 1
    }
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    & py -3.12 --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "اكتمل التثبيت لكن المشغّل لا يرى 3.12 بعد — أغلق النافذة وافتح PowerShell جديدة وأعد تشغيل السكربت." -ForegroundColor Yellow
        exit 1
    }
    $py = "py -3.12"
}
$pyExe, $pyArgs = $py.Split(" ")
Write-Host "استخدام: $py ($(& $pyExe $pyArgs --version))"

# --- 2. dependencies ---------------------------------------------------------
Step "تثبيت متطلبات الجلب"
& $pyExe $pyArgs -m pip install --quiet --disable-pip-version-check -r (Join-Path $Backend "requirements-fetch.txt")
if ($LASTEXITCODE -ne 0) { Write-Host "فشل تثبيت المتطلبات." -ForegroundColor Red; exit 1 }

# --- 3. database URL (asked once, stored in backend\.env) --------------------
Step "رابط قاعدة البيانات"
$existing = ""
if (Test-Path $EnvFile) {
    $line = Select-String -Path $EnvFile -Pattern '^DATABASE_URL=' | Select-Object -First 1
    if ($line) { $existing = $line.Line.Substring(13) }
}
if ($DatabaseUrl) { $existing = $DatabaseUrl }
if (-not $existing) {
    Write-Host "الصق رابط Neon كما هو (postgresql://...neon.tech/neondb?sslmode=require...):"
    $existing = Read-Host "DATABASE_URL"
}
if (-not $existing) { Write-Host "لا رابط — إيقاف." -ForegroundColor Red; exit 1 }
[IO.File]::WriteAllText($EnvFile, "DATABASE_URL=$existing`n", (New-Object Text.UTF8Encoding $false))
Write-Host "حُفظ في backend\.env — لن يُطلب مجددًا."

# --- 4. probe then fetch -----------------------------------------------------
Step "فحص الاتصال بمنصة اعتماد (--dry-run)"
Push-Location $Backend
try {
    & $pyExe $pyArgs "scripts\fetch_live.py" --dry-run
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nالفحص فشل — أرسل المخرجات أعلاه للمطوّر. لن يُنفذ الجلب." -ForegroundColor Red
        exit 1
    }
    if (-not $SkipFetch) {
        Step "الجلب الحقيقي إلى قاعدة الإنتاج"
        & $pyExe $pyArgs "scripts\fetch_live.py"
        if ($LASTEXITCODE -ne 0) { Write-Host "الجلب فشل — أرسل المخرجات للمطوّر." -ForegroundColor Red; exit 1 }
    }
} finally { Pop-Location }

# --- 5. optional daily schedule ---------------------------------------------
if ($Schedule) {
    Step "جدولة مهمة يومية (9:00 صباحًا)"
    $cmd = "cd /d `"$Backend`" && $py scripts\fetch_live.py"
    schtasks /Create /F /TN "BidsaFetch" /SC DAILY /ST 09:00 /TR "cmd /c $cmd" | Out-Null
    Write-Host "أُنشئت المهمة 'BidsaFetch' — تعمل يوميًا 9:00 صباحًا (بشرط أن يكون الجهاز مشغّلًا)."
}

Step "اكتمل ✓  افتح bidsa.vercel.app وجرّب المطابقة."
