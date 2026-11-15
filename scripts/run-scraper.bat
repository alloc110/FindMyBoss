@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

:: Navigate to project root directory
cd /d "%~dp0\.."
set "PROJECT_DIR=%CD%"

:: Ensure logs directory exists
if not exist "%PROJECT_DIR%\logs" (
    mkdir "%PROJECT_DIR%\logs"
)

set "LOG_FILE=%PROJECT_DIR%\logs\crawl_log.txt"

:: Locate Python executable (Priority: venv\Scripts\python.exe -> miniconda3 -> system python)
if exist "%PROJECT_DIR%\venv\Scripts\python.exe" (
    set "PYTHON_BIN=%PROJECT_DIR%\venv\Scripts\python.exe"
) else if exist "%USERPROFILE%\miniconda3\python.exe" (
    set "PYTHON_BIN=%USERPROFILE%\miniconda3\python.exe"
) else (
    set "PYTHON_BIN=python"
)

:: Intercept help flag
if "%~1"=="--help" (
    "!PYTHON_BIN!" -m crawl.orchestrator --help
    exit /b 0
)
if "%~1"=="-h" (
    "!PYTHON_BIN!" -m crawl.orchestrator --help
    exit /b 0
)
if "%~1"=="/?" (
    "!PYTHON_BIN!" -m crawl.orchestrator --help
    exit /b 0
)

echo [*] FindMyBoss Job Harvester Launcher
echo [*] Trinh thuc thi Python: !PYTHON_BIN!
echo [*] Thu muc lam viec: %PROJECT_DIR%
echo [*] Tham so chay: %*
echo [*] Dang ghi nhat ky tai: %LOG_FILE%
echo.

echo [%date% %time%] Starting job scraping pipeline with: !PYTHON_BIN! >> "%LOG_FILE%"
echo [%date% %time%] Working directory: %PROJECT_DIR% >> "%LOG_FILE%"
echo [%date% %time%] Arguments: %* >> "%LOG_FILE%"

:: Run crawler orchestrator module
"!PYTHON_BIN!" -m crawl.orchestrator %* >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

if !EXIT_CODE! equ 0 (
    echo [OK] Pipeline execution finished successfully.
    echo [%date% %time%] Pipeline execution finished successfully. >> "%LOG_FILE%"
) else (
    echo [FAIL] Pipeline failed with exit code: !EXIT_CODE!
    echo [%date% %time%] Pipeline failed with exit code: !EXIT_CODE! >> "%LOG_FILE%"
)

exit /b !EXIT_CODE!
