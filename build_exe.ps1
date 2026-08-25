$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm --clean --onedir --windowed `
  --name "SCP-SL-Auto-Joiner" --icon assets\app.ico `
  --add-data "assets\app.ico;assets" --add-data "webui;webui" `
  --collect-all webview --collect-all clr_loader --hidden-import clr app_web.py

Write-Host "Built dist\SCP-SL-Auto-Joiner\SCP-SL-Auto-Joiner.exe"
