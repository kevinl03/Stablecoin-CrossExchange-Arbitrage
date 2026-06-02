@echo off
REM ========================================================================
REM Auto-restarting data collector wrapper for Windows.
REM Survives laptop sleep (process resumes) and crash/shutdown (auto-restarts).
REM
REM Usage:
REM   run_collector.bat                        -- default 24h, 60s interval
REM   run_collector.bat --interval 30 --hours 48
REM   run_collector.bat --resume data\statarb\20260602_185451
REM
REM To stop cleanly: press Ctrl+C in the window, or close it.
REM ========================================================================

setlocal enabledelayedexpansion

cd /d "%~dp0\.."

REM Default args if none provided
set "ARGS=%*"
if "%ARGS%"=="" set "ARGS=--interval 60 --hours 24"

REM Track the output directory for auto-resume
set "RESUME_DIR="

:LOOP
echo.
echo [%date% %time%] Starting collector...
echo.

if defined RESUME_DIR (
    echo [RESUME] Resuming from %RESUME_DIR%
    python -m experiments.collect_statarb_data --resume "%RESUME_DIR%"
) else (
    python -m experiments.collect_statarb_data %ARGS%
)

set "EXIT_CODE=%ERRORLEVEL%"

REM Exit code 0 = completed normally (duration reached), stop.
if %EXIT_CODE%==0 (
    echo.
    echo [DONE] Collection finished normally.
    goto :END
)

REM Exit code 2 = user Ctrl+C, stop.
if %EXIT_CODE%==2 (
    echo.
    echo [STOPPED] User interrupted.
    goto :END
)

REM Any other exit = crash or sleep-wake kill. Find the most recent run to resume.
echo.
echo [CRASH] Exit code %EXIT_CODE%. Looking for latest run to resume...

set "LATEST_DIR="
for /f "delims=" %%d in ('dir /b /o-n /ad "data\statarb" 2^>nul') do (
    if not defined LATEST_DIR (
        if exist "data\statarb\%%d\_state.json" (
            set "LATEST_DIR=data\statarb\%%d"
        )
    )
)

if defined LATEST_DIR (
    set "RESUME_DIR=!LATEST_DIR!"
    echo [RESUME] Will resume from !RESUME_DIR! in 5 seconds...
    timeout /t 5 /nobreak >nul
    goto :LOOP
) else (
    echo [ERROR] No resumable run found. Starting fresh in 5 seconds...
    set "RESUME_DIR="
    timeout /t 5 /nobreak >nul
    goto :LOOP
)

:END
echo.
echo [EXIT] Collector stopped at %date% %time%.
pause
