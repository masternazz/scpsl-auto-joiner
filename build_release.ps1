param([string]$Version = $(if ($env:SCP_SL_RELEASE_VERSION) { $env:SCP_SL_RELEASE_VERSION } else { "0.3.34" }))
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:SCP_SL_APP_VERSION = $Version

$version = $Version
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
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed with exit code $LASTEXITCODE. No valid setup installer was produced."
    }
    $setup = Join-Path $PSScriptRoot "dist\SCP-SL-Auto-Joiner-v$version-win-x64-setup.exe"
    if (-not (Test-Path -LiteralPath $setup)) {
        throw "Inno Setup completed without producing $setup."
    }
    $hashes = @($portableZip, $setup) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Get-FileHash -LiteralPath $_ -Algorithm SHA256 }
    $hashes | ForEach-Object { "$($_.Hash)  $([IO.Path]::GetFileName($_.Path))" } | Set-Content -LiteralPath (Join-Path $PSScriptRoot "dist\SCP-SL-Auto-Joiner-v$version-SHA256SUMS.txt") -Encoding ascii
    Write-Host "Built $portableZip and the Inno Setup installer in dist."
} else {
    Write-Warning "Portable ZIP built. Install Inno Setup to create the setup installer, then run: iscc installer.iss"
}
