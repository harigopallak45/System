@echo off
TITLE Building System Dashboard Pro

echo ===================================================
echo      System Dashboard Pro - Build Utility
echo ===================================================
echo.

REM Check for Python Launcher
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python Launcher (py) is not found.
    echo Please install Python (and check 'Install launcher for all users').
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
py -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/3] Installing PyInstaller...
py -m pip install pyinstaller
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)

echo [3/3] Creating Executable...
echo This may take a minute...
py -m PyInstaller --noconsole --onefile --name "SystemDashboardPro" --clean "system_dashboard_pro.py" --hidden-import=wmi --hidden-import=screen_brightness_control --hidden-import=comtypes --hidden-import=pycaw --collect-all=pycaw

if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo      BUILD SUCCESSFUL!
echo ===================================================
echo.
echo The executable is located in the 'dist' folder:
echo dist\SystemDashboardPro.exe
echo.
pause
