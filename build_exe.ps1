$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

py -3.13 -m PyInstaller --noconfirm --clean --onedir --windowed `
  --name "SCP-SL-Auto-Joiner" --icon assets\app.ico `
  --add-data "assets\app.ico;assets" `
  --add-data "assets\generated\containment-mark-purple.png;assets\generated" gui.py

Write-Host "Built dist\SCP-SL-Auto-Joiner\SCP-SL-Auto-Joiner.exe"

py -3.13 -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name "SCP-SL-Auto-Joiner-Updater" updater_helper.py
Copy-Item -LiteralPath "dist\SCP-SL-Auto-Joiner-Updater.exe" `
  -Destination "dist\SCP-SL-Auto-Joiner\SCP-SL-Auto-Joiner-Updater.exe" -Force
