<#
    התקנה אוטומטית של TapeInk.
    מריצים על ידי לחיצה כפולה על Install-TapeInk.bat
#>

[CmdletBinding()]
param(
    [switch]$SkipModel,
    [switch]$NoLaunch,
    [string]$ModelSize = "small"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$TotalSteps = 5

function Write-Step {
    param([int]$Number, [string]$Text)
    Write-Host ""
    Write-Host "[$Number/$TotalSteps] $Text" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Text)
    Write-Host "      $Text" -ForegroundColor Green
}

function Write-Info {
    param([string]$Text)
    Write-Host "      $Text" -ForegroundColor Gray
}

function Fail {
    param([string]$Text)
    Write-Host ""
    Write-Host "שגיאה: $Text" -ForegroundColor Red
    Write-Host ""
    Write-Host "אם ההתקנה נכשלת שוב, שלחו את הטקסט שמופיע כאן לתמיכה." -ForegroundColor Yellow
    exit 1
}

function Test-PythonExe {
    param([string]$Path)
    if (-not $Path -or -not (Test-Path $Path)) { return $false }
    try {
        # The Microsoft Store alias exits non-zero and prints nothing usable.
        $version = & $Path --version 2>&1
        return ($LASTEXITCODE -eq 0 -and $version -match "Python 3\.(1[0-9]|[89])")
    } catch {
        return $false
    }
}

function Find-Python {
    $candidates = @()

    foreach ($name in @("python.exe", "python3.12.exe", "python3.exe")) {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if ($found) { $candidates += $found.Source }
    }

    $globs = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:ProgramFiles\Python3*\python.exe",
        "${env:ProgramFiles(x86)}\Python3*\python.exe"
    )
    foreach ($glob in $globs) {
        $candidates += Get-ChildItem $glob -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -ExpandProperty FullName
    }

    foreach ($candidate in $candidates) {
        # Skip the WindowsApps stub that only opens the Store.
        if ($candidate -like "*\WindowsApps\*") { continue }
        if (Test-PythonExe $candidate) { return $candidate }
    }
    return $null
}

function Install-WithWinget {
    param([string]$Id, [string]$Label)

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "לא נמצא winget במחשב. יש לעדכן את Windows, או להתקין $Label ידנית."
    }

    Write-Info "מתקין $Label ... (עשוי לקחת מספר דקות)"
    & winget install --id $Id -e --accept-source-agreements --accept-package-agreements | Out-Null
}

function Test-NvidiaGpu {
    try {
        $cards = Get-CimInstance Win32_VideoController -ErrorAction Stop
        return [bool]($cards | Where-Object { $_.Name -match "NVIDIA" })
    } catch {
        return $false
    }
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor DarkCyan
Write-Host "   TapeInk - התקנה" -ForegroundColor White
Write-Host "   תמלול אודיו בעברית, מקומי לחלוטין" -ForegroundColor Gray
Write-Host "==================================================" -ForegroundColor DarkCyan

# ---------- 1. Python ----------
Write-Step 1 "בדיקת Python"
$python = Find-Python
if ($python) {
    Write-Ok "נמצא: $python"
} else {
    Write-Info "Python לא נמצא במחשב."
    Install-WithWinget -Id "Python.Python.3.12" -Label "Python 3.12"
    $python = Find-Python
    if (-not $python) {
        Fail "Python הותקן אך לא זוהה. נסו להפעיל מחדש את המחשב ולהריץ שוב."
    }
    Write-Ok "הותקן: $python"
}

# ---------- 2. ffmpeg ----------
Write-Step 2 "בדיקת ffmpeg (תמיכה בפורמטי אודיו)"
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Ok "ffmpeg קיים"
} else {
    Install-WithWinget -Id "Gyan.FFmpeg" -Label "ffmpeg"
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        Write-Ok "ffmpeg הותקן"
    } else {
        Write-Info "ffmpeg יהיה זמין לאחר פתיחה מחדש של החלון. ההתקנה ממשיכה."
    }
}

# ---------- 3. Virtual environment ----------
Write-Step 3 "יצירת סביבת עבודה"
if (-not (Test-Path $VenvPython)) {
    & $python -m venv (Join-Path $Root ".venv")
    if (-not (Test-Path $VenvPython)) { Fail "לא ניתן היה ליצור את סביבת העבודה." }
    Write-Ok "נוצרה"
} else {
    Write-Ok "קיימת"
}

& $VenvPython -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { Fail "עדכון pip נכשל. בדקו חיבור לאינטרנט." }

# ---------- 4. Dependencies ----------
Write-Step 4 "התקנת ספריות (ההורדה עשויה לקחת כמה דקות)"
& $VenvPython -m pip install -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) { Fail "התקנת הספריות נכשלה. בדקו חיבור לאינטרנט ונסו שוב." }
Write-Ok "הספריות הותקנו"

if (Test-NvidiaGpu) {
    Write-Info "זוהה כרטיס NVIDIA - מתקין תמיכת GPU להאצה"
    & $VenvPython -m pip install -r (Join-Path $Root "requirements-gpu.txt")
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "תמיכת GPU הותקנה"
    } else {
        Write-Info "התקנת GPU נכשלה - האפליקציה תעבוד על המעבד"
    }
} else {
    Write-Info "לא זוהה כרטיס NVIDIA - האפליקציה תעבוד על המעבד"
}

# ---------- 5. Shortcut + model ----------
Write-Step 5 "יצירת קיצור דרך"
& $VenvPython (Join-Path $Root "make_shortcut.py") --desktop
if ($LASTEXITCODE -ne 0) { Fail "יצירת קיצור הדרך נכשלה." }
Write-Ok "קיצור דרך נוצר על שולחן העבודה"

if (-not $SkipModel) {
    Write-Host ""
    Write-Host "מוריד את מודל התמלול ($ModelSize) - פעם אחת בלבד" -ForegroundColor Cyan
    & $VenvPython (Join-Path $Root "scripts\download_model.py") $ModelSize
    if ($LASTEXITCODE -ne 0) {
        Write-Info "הורדת המודל לא הושלמה. היא תתבצע אוטומטית בהפעלה הראשונה."
    }
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "   ההתקנה הושלמה" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "להפעלה: לחיצה כפולה על TapeInk שעל שולחן העבודה" -ForegroundColor White
Write-Host ""

if ($NoLaunch) { exit 0 }

$answer = Read-Host "לפתוח את TapeInk כעת? (y/n)"
if ($answer -match "^(y|Y|כ)") {
    Start-Process -FilePath (Join-Path $Root ".venv\Scripts\pythonw.exe") `
        -ArgumentList ('"' + (Join-Path $Root "TapeInk.pyw") + '"') `
        -WorkingDirectory $Root
}
