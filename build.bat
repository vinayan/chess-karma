@echo off
REM Chess Karma – full Windows installer build
REM
REM Prerequisites:
REM   pip install pyinstaller
REM   Inno Setup 6 installed (iscc.exe on PATH, or set ISCC below)
REM
REM Usage:  build.bat

setlocal

set PYTHON=python

REM ── Locate iscc.exe ────────────────────────────────────────────────────────
set ISCC=
for %%D in (
    "%ProgramFiles(x86)%\Inno Setup 6\iscc.exe"
    "%ProgramFiles%\Inno Setup 6\iscc.exe"
    "%ProgramFiles(x86)%\Inno Setup 5\iscc.exe"
    "%ProgramFiles%\Inno Setup 5\iscc.exe"
) do (
    if exist %%D if not defined ISCC set ISCC=%%D
)
if not defined ISCC (
    where iscc >nul 2>&1 && set ISCC=iscc
)
if not defined ISCC (
    echo ERROR: iscc.exe not found.
    echo Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
    echo or add its directory to your PATH.
    exit /b 1
)

echo ==========================================================
echo  Step 1: Generate blank SQLite schema database
echo ==========================================================
%PYTHON% tools\create_blank_db.py
if errorlevel 1 (
    echo ERROR: create_blank_db.py failed.
    exit /b 1
)

echo.
echo ==========================================================
echo  Step 2: Bundle application with PyInstaller
echo ==========================================================
%PYTHON% -m PyInstaller chess_karma.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

echo.
echo ==========================================================
echo  Step 3: Build installer with Inno Setup
echo ==========================================================
if not exist installer mkdir installer
%ISCC% installer.iss
if errorlevel 1 (
    echo ERROR: Inno Setup build failed.
    exit /b 1
)

echo.
echo ==========================================================
echo  Build complete!
echo  Installer: installer\Chess_Karma_Setup.exe
echo ==========================================================
endlocal
