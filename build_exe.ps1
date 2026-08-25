$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

py -3.13 -m PyInstaller --noconfirm --clean --onedir --windowed `
  --name "SCP-SL-Auto-Joiner" --icon assets\app.ico `
  --add-data "assets\app.ico;assets" gui.py

Write-Host "Built dist\SCP-SL-Auto-Joiner\SCP-SL-Auto-Joiner.exe"
