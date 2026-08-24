$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name "SCP-SL-Auto-Joiner" gui.py

Write-Host "Built dist\SCP-SL-Auto-Joiner.exe"
