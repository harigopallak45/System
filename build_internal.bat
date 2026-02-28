@echo off
pip install -r requirements.txt > build_log.txt 2>&1
if %errorlevel% neq 0 exit /b %errorlevel%
pip install pyinstaller >> build_log.txt 2>&1
if %errorlevel% neq 0 exit /b %errorlevel%
pyinstaller --noconsole --onefile --name "SystemDashboardPro" --clean "system_dashboard_pro.py" --hidden-import=wmi --hidden-import=screen_brightness_control --hidden-import=comtypes --hidden-import=pycaw --collect-all=pycaw >> build_log.txt 2>&1
