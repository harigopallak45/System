@echo off
setlocal
echo ===================================================
echo   Compiling Windows Native AutoBoost (Headless)
echo   No Python / No Node required
echo ===================================================

set CSC_PATH=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe

if not exist "%CSC_PATH%" (
    echo [ERROR] C# Compiler not found at: %CSC_PATH%
    pause
    exit /b 1
)

echo Compiling AutoBoost.cs into AutoBoost.exe...
"%CSC_PATH%" /target:winexe /optimize+ /platform:anycpu /out:"%~dp0AutoBoost.exe" "%~dp0AutoBoost.cs"

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCCESS] AutoBoost.exe successfully compiled!
    echo Location: %~dp0AutoBoost.exe
    echo File size:
    dir "%~dp0AutoBoost.exe" | findstr /i "AutoBoost.exe"
    echo.
) else (
    echo.
    echo [ERROR] Compilation failed.
)

pause
