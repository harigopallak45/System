@echo off
setlocal
cd /d "%~dp0"

set SERVER=ubuntu@client.truewilly.com
set REMOTE_DIR=/home/ubuntu/server_autoboost

echo ========================================================
echo       Deploying AutoBoost to %SERVER%
echo ========================================================

echo [1/3] Creating remote directory on server...
ssh -o BatchMode=yes %SERVER% "mkdir -p %REMOTE_DIR%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to connect to server via SSH.
    pause
    exit /b 1
)

echo [2/3] Uploading AutoBoost files...
scp autoboost_daemon.py autoboost.conf autoboost.service autoboost install.sh %SERVER%:%REMOTE_DIR%/
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to upload files.
    pause
    exit /b 1
)

echo [3/3] Installing and starting AutoBoost service...
ssh -t %SERVER% "chmod +x %REMOTE_DIR%/install.sh %REMOTE_DIR%/autoboost %REMOTE_DIR%/autoboost_daemon.py && sudo %REMOTE_DIR%/install.sh"

echo.
echo ========================================================
echo  AutoBoost deployed and running on %SERVER%!
echo ========================================================
pause
