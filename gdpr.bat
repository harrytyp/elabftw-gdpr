@echo off
rem eLabFTW GDPR disclosure - Windows entry point (double-click or cmd).
rem No admin rights required. Works from UNC paths and network shares.
rem
rem pushd makes a UNC path (\\server\share) usable as working directory by
rem mapping it to a temporary drive letter; popd restores afterwards.
rem PYTHONUTF8=1 avoids UnicodeEncodeError on cp1252 consoles (umlauts etc.).
rem The Python venv lives under %LOCALAPPDATA% (see gdpr.py), never on the
rem network share, so no admin rights and no share-write issues for pip.
rem On error the window stays open so the message can be read.

setlocal EnableExtensions
set "PYTHONUTF8=1"

pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo [gdpr] Cannot access the project directory: "%~dp0"
    echo [gdpr] Check the network share path and your permissions.
    pause
    exit /b 1
)

rem Locate a working Python. Prefer the launcher (py), then plain python.
rem The --version probe skips the Microsoft Store app-execution aliases,
rem which otherwise open the Store instead of running Python.
set "PYCMD="
py -3 --version >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD (
    python --version >nul 2>&1 && set "PYCMD=python"
)
if not defined PYCMD (
    echo [gdpr] Python 3 was not found on this system.
    echo [gdpr] Install it from https://www.python.org/downloads/
    echo [gdpr] In the installer choose "Install Now" - this installs
    echo [gdpr] for the current user only, no admin rights are needed.
    echo [gdpr] Make sure "Add python.exe to PATH" stays enabled.
    pause
    exit /b 1
)

%PYCMD% "%~dp0gdpr.py" %*
set "EXITCODE=%errorlevel%"
popd

if not "%EXITCODE%"=="0" (
    echo.
    echo [gdpr] Finished with error code %EXITCODE%. See message above.
    pause
)
exit /b %EXITCODE%
