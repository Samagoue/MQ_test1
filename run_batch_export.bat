@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo.

REM ========================================================================
REM Database Master Password Configuration
REM ========================================================================
REM Option 1: Set UnlockKey as environment variable (recommended for CI/CD)
REM Option 2: Set DB_MASTER_PASSWORD directly below (for local testing only)
REM ========================================================================

REM Check if UnlockKey is set (CI/CD variable)
if defined UnlockKey (
    SET DB_MASTER_PASSWORD=%UnlockKey%
    echo Using UnlockKey from environment variable
) else (
    REM Fallback: Set password here for local testing (NOT recommended for production)
    REM SET DB_MASTER_PASSWORD=your_password_here
    echo.
    echo WARNING: UnlockKey environment variable not set!
    echo Please set the UnlockKey variable before running:
    echo   set UnlockKey=your_master_password
    echo.
    if not defined DB_MASTER_PASSWORD (
        echo ERROR: No password configured. Exiting.
        exit /b 1
    )
)

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

REM Log start (banner is handled by Python setup_logging)
echo. > %LOG_FILE%
echo Export started at %date% %time% >> %LOG_FILE%

REM Run database export
python db_export.py --profile production --batch 2>&1 >> %LOG_FILE%

REM Check result
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Database export failed with code %ERRORLEVEL% >> %LOG_FILE%
    echo ERROR: Database export failed with code %ERRORLEVEL%
    call :SendEmail "MQ CMDB Export Failed" "Database export failed. Check attached log file for details." "%LOG_FILE%"
    goto :END
)

REM Run processing pipeline
echo. >> %LOG_FILE%
echo Running MQ processing pipeline... >> %LOG_FILE%
python orchestrator.py 2>&1 >> %LOG_FILE%

REM Check pipeline result
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Pipeline failed with code %ERRORLEVEL% >> %LOG_FILE%
    echo ERROR: Pipeline failed with code %ERRORLEVEL%
    call :SendEmail "MQ CMDB Pipeline Failed" "Pipeline processing failed. Check attached log file for details." "%LOG_FILE%"
    goto :END
)

REM Log completion
echo. >> %LOG_FILE%
echo ======================================================================== >> %LOG_FILE%
echo Completed at %date% %time% >> %LOG_FILE%
echo ======================================================================== >> %LOG_FILE%

echo.
echo ✓ Complete! Check %LOG_FILE%
echo.
echo Latest reports generated:
dir /b /o-d output\reports\*.html 2>nul | findstr /i "change_report gateway_analytics"
echo.
echo Latest diagrams generated:
dir /b /o-d output\diagrams\topology\*.svg 2>nul
echo.

REM Send success notification with log attached
call :SendEmail "MQ CMDB Export Complete" "Processing completed successfully. See attached log file for details." "%LOG_FILE%"

:END
exit /b %ERRORLEVEL%

REM ========================================================================
REM Email Notification Function (Python-based - External Utility)
REM
REM This calls a reusable send_email.py utility that can be placed in any
REM common scripts directory and shared across multiple projects.
REM ========================================================================
:SendEmail
REM Usage: call :SendEmail "Subject" "Body" "AttachmentPath"
REM
REM Configure these paths for your environment:
SET EMAIL_SCRIPT=C:\Scripts\send_email.py
SET EMAIL_CONFIG=C:\Scripts\smtp_config.ini
SET EMAIL_TO=ops-team@yourcompany.com
SET EMAIL_FROM=mqcmdb@yourcompany.com

REM Alternative: Use environment variables instead of config file
REM   set SMTP_SERVER=smtp.yourcompany.com
REM   set SMTP_PORT=587
REM   set SMTP_USER=your_username
REM   set SMTP_PASSWORD=your_password
REM   set SMTP_FROM=mqcmdb@yourcompany.com
REM   set SMTP_USE_TLS=true

REM Check if external script exists, fall back to local copy
if not exist "%EMAIL_SCRIPT%" (
    SET EMAIL_SCRIPT=%~dp0tools\send_email.py
)

REM Get the attachment path (3rd parameter)
SET ATTACHMENT_PATH=%~3

REM Check if config file exists and send email with attachment
if exist "%EMAIL_CONFIG%" (
    if defined ATTACHMENT_PATH (
        python "%EMAIL_SCRIPT%" --config "%EMAIL_CONFIG%" --from %EMAIL_FROM% --to %EMAIL_TO% --subject "%~1" --body "%~2" --attach "%ATTACHMENT_PATH%"
    ) else (
        python "%EMAIL_SCRIPT%" --config "%EMAIL_CONFIG%" --from %EMAIL_FROM% --to %EMAIL_TO% --subject "%~1" --body "%~2"
    )
) else (
    if defined ATTACHMENT_PATH (
        python "%EMAIL_SCRIPT%" --from %EMAIL_FROM% --to %EMAIL_TO% --subject "%~1" --body "%~2" --attach "%ATTACHMENT_PATH%"
    ) else (
        python "%EMAIL_SCRIPT%" --from %EMAIL_FROM% --to %EMAIL_TO% --subject "%~1" --body "%~2"
    )
)
exit /b 0
