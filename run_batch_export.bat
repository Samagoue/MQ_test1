@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo.


REM Set master password (KEEP SECURE!)
SET DB_MASTER_PASSWORD=mypsswd

REM Navigate to script directory
cd /d "%~dp0"

REM Create directories
if not exist "output" mkdir output
if not exist "logs" mkdir logs

REM Log cleanup on Sunday
for /f "skip=1" %%a in ('wmic path win32_localtime get dayofweek') do (
    set DOW=%%a
    goto :checkday
)

:checkday
if "%DOW%"=="1" (
    echo Cleaning up old logs...
    forfiles /p "logs" /s /m *.log /d -7 /c "cmd /c del @path" 2>nul
)

REM Set log file
SET LOG_FILE=logs\export_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log
SET LOG_FILE=%LOG_FILE: =0%

REM Set UTF-8 encoding
SET PYTHONIOENCODING=utf-8

REM Log start with banner
echo. > %LOG_FILE%
echo. >> %LOG_FILE%
echo     ╔════════════════════════════════════════════════════════════════════╗ >> %LOG_FILE%
echo     ║                                                                    ║ >> %LOG_FILE%
echo     ║       ███╗   ███╗ ██████╗      ██████╗███╗   ███╗██████╗ ██████╗   ║ >> %LOG_FILE%
echo     ║       ████╗ ████║██╔═══██╗    ██╔════╝████╗ ████║██╔══██╗██╔══██╗  ║ >> %LOG_FILE%
echo     ║       ██╔████╔██║██║   ██║    ██║     ██╔████╔██║██████╔╝██████╔╝  ║ >> %LOG_FILE%
echo     ║       ██║╚██╔╝██║██║   ██║    ██║     ██║╚██╔╝██║██╔══██╗██╔══██╗  ║ >> %LOG_FILE%
echo     ║       ██║ ╚═╝ ██║╚██████╔╝    ╚██████╗██║ ╚═╝ ██║██████╔╝██║  ██║  ║ >> %LOG_FILE%
echo     ║       ╚═╝     ╚═╝ ╚═════╝      ╚═════╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝  ║ >> %LOG_FILE%
echo     ║        MQ CMDB HIERARCHICAL AUTOMATION SYSTEM                      ║ >> %LOG_FILE%
echo     ║        Version 1.0                                                 ║ >> %LOG_FILE%
echo     ║                                                                    ║ >> %LOG_FILE%
echo     ║        Processes IBM MQ CMDB data and generates:                   ║ >> %LOG_FILE%
echo     ║        • Hierarchical organization topology diagrams               ║ >> %LOG_FILE%
echo     ║        • Application-focused connection diagrams                   ║ >> %LOG_FILE%
echo     ║        • Individual MQ manager connection diagrams                 ║ >> %LOG_FILE%
echo     ║        • JSON data with full organizational enrichment             ║ >> %LOG_FILE%
echo     ║                                                                    ║ >> %LOG_FILE%
echo     ╚════════════════════════════════════════════════════════════════════╝ >> %LOG_FILE%
echo. >> %LOG_FILE%
echo ======================================================================== >> %LOG_FILE%
echo Export started at %date% %time% >> %LOG_FILE%
echo ======================================================================== >> %LOG_FILE%

REM Run database export
python db_export.py --profile production --batch 2>&1 >> %LOG_FILE%

REM Check result
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Script failed with code %ERRORLEVEL% >> %LOG_FILE%
)

REM Run processing pipeline
echo. >> %LOG_FILE%
echo Running MQ processing pipeline... >> %LOG_FILE%
python orchestrator.py --mode full 2>&1 >> %LOG_FILE%

REM Log completion
echo. >> %LOG_FILE%
echo ======================================================================== >> %LOG_FILE%
echo Completed at %date% %time% >> %LOG_FILE%
echo ======================================================================== >> %LOG_FILE%

echo.
echo ✓ Complete! Check %LOG_FILE%
echo.
