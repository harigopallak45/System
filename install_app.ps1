$ErrorActionPreference = "Stop"

$appName = "SystemDashboardPro"
# Install to Local AppData (standard user location)
$installDir = "$env:LOCALAPPDATA\Programs\$appName"
$sourceExe = "dist\SystemDashboardPro.exe"
$sourceConfig = "dashboard_config.json"
$targetExe = "$installDir\$appName.exe"
$targetConfig = "$installDir\dashboard_config.json"

# Check if build exists
if (!(Test-Path $sourceExe)) {
    Write-Error "Build not found! Please run the build script first."
    exit 1
}

Write-Host "Installing $appName..."
Write-Host "Target Directory: $installDir"

# 1. Create Installation Directory
if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir | Out-Null
    Write-Host "Created directory."
}

# 2. Copy Executable
Copy-Item -Path $sourceExe -Destination $targetExe -Force
Write-Host "Copied executable."

# 3. Copy Config and Data if they exist (to preserve settings)
if (Test-Path $sourceConfig) {
    Copy-Item -Path $sourceConfig -Destination $targetConfig -Force
    Write-Host "Copied configuration."
}

# 4. Create Desktop Shortcut
$wshShell = New-Object -ComObject WScript.Shell
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = "$desktopPath\System Dashboard Pro.lnk"

$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetExe
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "Advanced System Monitoring Dashboard"
$shortcut.IconLocation = "$targetExe,0"
$shortcut.Save()

Write-Host "--------------------------------"
Write-Host "Installation Complete!"
Write-Host "Shortcut created on your Desktop."
Write-Host "You can now delete the 'dist' and 'build' folders if you wish."
