# + -- --=[ Sn1per + Jarvis installer for Windows (PowerShell)
#
# Installs the Jarvis reporting/ASM/export layer natively on Windows. The bash
# scanning engine (sniper) does NOT run on native Windows — use WSL2 or Docker
# for that (see README). This installer:
#   * checks for Python 3,
#   * deploys the repo to a user directory (or runs in place with -InPlace),
#   * puts the 'jarvis' command on your user PATH (unless -NoPath).
#
# Usage (no admin required):
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -InPlace
#
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Sn1per'),
    [switch]$InPlace,
    [switch]$NoPath
)
$ErrorActionPreference = 'Stop'

function Info($m) { Write-Host "[*] $m" -ForegroundColor Cyan }
function Good($m) { Write-Host "[+] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }

Write-Host ""
Write-Host " Sn1per + Jarvis - Windows installer" -ForegroundColor Red
Write-Host ""

# --- 1. locate Python 3 ---------------------------------------------------
$launcher = $null
if (Get-Command py -ErrorAction SilentlyContinue)      { $launcher = 'py -3' }
elseif (Get-Command python -ErrorAction SilentlyContinue)  { $launcher = 'python' }
elseif (Get-Command python3 -ErrorAction SilentlyContinue) { $launcher = 'python3' }
if (-not $launcher) {
    Warn "Python 3 was not found."
    Warn "Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'),"
    Warn "or from the Microsoft Store, then re-run this script."
    exit 1
}
Good "Python launcher: $launcher"

# --- 2. deploy files ------------------------------------------------------
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($InPlace) {
    $InstallDir = $src
    Info "Using in-place install at $InstallDir"
} else {
    Info "Deploying to $InstallDir"
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    # Copy everything except the .git directory.
    Get-ChildItem -Path $src -Force | Where-Object { $_.Name -ne '.git' } | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $InstallDir -Recurse -Force
    }
    Good "Files deployed"
}

# jarvis.cmd must sit at the install root (it is shipped in the repo).
$jarvisCmd = Join-Path $InstallDir 'jarvis.cmd'
if (-not (Test-Path $jarvisCmd)) {
    Warn "jarvis.cmd not found in $InstallDir — run this script from the repo root."
    exit 1
}

# --- 3. add to user PATH --------------------------------------------------
if (-not $NoPath) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not $userPath) { $userPath = '' }
    if ($userPath -split ';' -notcontains $InstallDir) {
        $newPath = if ($userPath) { "$userPath;$InstallDir" } else { $InstallDir }
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
        Good "Added $InstallDir to your user PATH (open a NEW terminal to pick it up)."
    } else {
        Info "$InstallDir already on your user PATH."
    }
}

# --- 4. smoke test --------------------------------------------------------
Info "Verifying..."
& cmd /c "`"$jarvisCmd`" --version"

Write-Host ""
Good "Installation complete."
Write-Host ""
Info  "Use it (open a new terminal first if PATH was just updated):"
Write-Host "    jarvis report -w <WORKSPACE>"
Write-Host "    jarvis asm    -w <WORKSPACE> --client ""<CLIENT>"""
Write-Host "    jarvis export -w <WORKSPACE> --serve"
Write-Host ""
Warn  "The 'sniper' scanning engine is Linux-only. On Windows, run scans via"
Warn  "WSL2 (bash install.sh inside a Kali/Ubuntu distro) or Docker, then use"
Warn  "Jarvis on the loot. See README for details."
Warn  "Only test targets you are explicitly authorised to assess."
