@echo off
rem + -- --=[ Jarvis launcher for Windows (cmd / PowerShell)
rem Runs the Jarvis reporting/ASM/export layer without bash. The scanning
rem engine (sniper) is Linux-only; use WSL2 or Docker for that.
setlocal
set "SCRIPT_DIR=%~dp0"
rem Put the repo root (which contains the 'jarvis' package) on PYTHONPATH.
if defined PYTHONPATH (
  set "PYTHONPATH=%SCRIPT_DIR%;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%SCRIPT_DIR%"
)
rem Prefer the Python launcher 'py -3', fall back to 'python'.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m jarvis %*
) else (
  python -m jarvis %*
)
exit /b %errorlevel%
