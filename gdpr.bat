@echo off
rem eLabFTW GDPR disclosure - Windows entry point (double-click or cmd).
rem Uses the Python launcher if available, falls back to plain python.
setlocal
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0gdpr.py" %*
) else (
    python "%~dp0gdpr.py" %*
)
