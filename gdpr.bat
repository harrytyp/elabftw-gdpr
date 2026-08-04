@echo off
rem eLabFTW GDPR disclosure - Windows entry point (double-click or cmd).
rem Uses the Python launcher if available, falls back to plain python.
rem pushd makes UNC paths (\\server\share) usable as working directory
rem by mapping them to a temporary drive letter; popd restores afterwards.
rem On error the window stays open (pause) so the message can be read.
setlocal
pushd "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0gdpr.py" %*
) else (
    python "%~dp0gdpr.py" %*
)
set EXITCODE=%errorlevel%
popd
if not "%EXITCODE%"=="0" (
    echo.
    echo [gdpr] Finished with error code %EXITCODE%. Press any key to close.
    pause >nul
)
exit /b %EXITCODE%
