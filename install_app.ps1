$ErrorActionPreference = "Stop"

$appName = "RaceTelemetryConsole"
# Install to Local AppData (standard user location)
$installDir = "$env:LOCALAPPDATA\Programs\$appName"
$sourceExe = "dist\RaceTelemetryConsole.exe"
$sourceConfig = "dashboard_config.json"
$targetExe = "$installDir\$appName.exe"
$targetConfig = "$installDir\dashboard_config.json"

# Check if build exists
if (!(Test-Path $sourceExe)) {
    Write-Error "Build not found! Please run build_app.bat first."
    exit 1
}

Write-Host "Installing $appName..."
Write-Host "Target Directory: $installDir"

# 1. Create Installation Directory
if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir | Out-Null
    Write-Host "Created directory."
}

# 2. Copy Executable (engine_start.wav is bundled inside the exe)
Copy-Item -Path $sourceExe -Destination $targetExe -Force
Write-Host "Copied executable."

# 3. Copy Config (to preserve settings)
if (Test-Path $sourceConfig) {
    Copy-Item -Path $sourceConfig -Destination $targetConfig -Force
    Write-Host "Copied configuration."
}

# 4. Create Desktop Shortcut
$wshShell = New-Object -ComObject WScript.Shell
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = "$desktopPath\Race Telemetry Console.lnk"

$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetExe
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "Race Telemetry Console - live system monitor"
$shortcut.IconLocation = "$targetExe,0"
$shortcut.Save()

Write-Host "--------------------------------"
Write-Host "Installation Complete!"
Write-Host "Shortcut 'Race Telemetry Console' created on your Desktop."
