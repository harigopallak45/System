@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo         Windows AutoBoost Service Manager
echo ===================================================
echo [1] Start AutoBoost in Background (Silent)
echo [2] Stop AutoBoost Process
echo [3] Add AutoBoost to Windows Startup (Auto-boot)
echo [4] Remove AutoBoost from Windows Startup
echo [5] Check AutoBoost Status
echo [6] Exit
echo ===================================================
set /p CHOICE="Select an option (1-6): "

if "%CHOICE%"=="1" goto START
if "%CHOICE%"=="2" goto STOP
if "%CHOICE%"=="3" goto ADD_STARTUP
if "%CHOICE%"=="4" goto REMOVE_STARTUP
if "%CHOICE%"=="5" goto STATUS
if "%CHOICE%"=="6" exit /b 0
goto :eof

:START
if not exist "%~dp0AutoBoost.exe" (
    echo AutoBoost.exe not found! Compiling now...
    call "%~dp0build_autoboost.bat"
)
start "" "%~dp0AutoBoost.exe"
echo [OK] AutoBoost is now running silently in background.
pause
goto :eof

:STOP
taskkill /F /IM AutoBoost.exe 2>nul
if %ERRORLEVEL% equ 0 (
    echo [OK] AutoBoost has been stopped.
) else (
    echo AutoBoost is not currently running.
)
pause
goto :eof

:ADD_STARTUP
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP_DIR%\AutoBoost.lnk'); $s.TargetPath = '%~dp0AutoBoost.exe'; $s.WorkingDirectory = '%~dp0'; $s.Save()"
echo [OK] Added AutoBoost shortcut to Windows Startup!
echo It will now run silently every time your PC turns on.
pause
goto :eof

:REMOVE_STARTUP
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
if exist "%STARTUP_DIR%\AutoBoost.lnk" (
    del "%STARTUP_DIR%\AutoBoost.lnk"
    echo [OK] Removed from Windows Startup.
) else (
    echo Shortcut was not found in Startup.
)
pause
goto :eof

:STATUS
tasklist /FI "IMAGENAME eq AutoBoost.exe" | findstr /i "AutoBoost.exe" >nul
if %ERRORLEVEL% equ 0 (
    echo [STATUS] AutoBoost is RUNNING.
    tasklist /FI "IMAGENAME eq AutoBoost.exe"
) else (
    echo [STATUS] AutoBoost is NOT running.
)
pause
goto :eof
