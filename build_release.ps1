$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$version = "0.2.2"
$distDir = Join-Path $PSScriptRoot "dist\SCP-SL-Auto-Joiner"
$portableZip = Join-Path $PSScriptRoot "dist\SCP-SL-Auto-Joiner-v$version-win-x64-portable.zip"

& (Join-Path $PSScriptRoot "build_exe.ps1")

if (Test-Path -LiteralPath $portableZip) {
    Remove-Item -LiteralPath $portableZip -Force
}
Compress-Archive -Path (Join-Path $distDir "*") -DestinationPath $portableZip -CompressionLevel Optimal

$isccPath = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $isccPath) {
    $knownIscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
    if (Test-Path -LiteralPath $knownIscc) {
        $isccPath = $knownIscc
    }
}
if ($isccPath) {
    & $isccPath (Join-Path $PSScriptRoot "installer.iss")
    Write-Host "Built $portableZip and the Inno Setup installer in dist."
} else {
    Write-Warning "Portable ZIP built. Install Inno Setup to create the setup installer, then run: iscc installer.iss"
}
