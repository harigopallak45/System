@echo off
TITLE Building Race Telemetry Console

echo ===================================================
echo      Race Telemetry Console - Build Utility
echo ===================================================
echo.

py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python Launcher (py) is not found.
    echo Please install Python (check 'Install launcher for all users').
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
py -m pip install -r requirements.txt
if %errorlevel% neq 0 ( echo [ERROR] Failed to install dependencies. & pause & exit /b 1 )

echo [2/3] Installing PyInstaller...
py -m pip install pyinstaller
if %errorlevel% neq 0 ( echo [ERROR] Failed to install PyInstaller. & pause & exit /b 1 )

echo [3/3] Creating Executable (this may take a minute)...
py -m PyInstaller RaceTelemetryConsole.spec --clean --noconfirm
if %errorlevel% neq 0 ( echo [ERROR] Build failed. & pause & exit /b 1 )

echo.
echo ===================================================
echo      BUILD SUCCESSFUL!
echo ===================================================
echo The executable is here:  dist\RaceTelemetryConsole.exe
echo.
pause
