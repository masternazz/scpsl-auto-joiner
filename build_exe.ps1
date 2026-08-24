$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name "SCP-SL-Auto-Joiner" --icon assets\app.ico `
  --add-data "assets\app.ico;assets" gui.py

Write-Host "Built dist\SCP-SL-Auto-Joiner.exe"
