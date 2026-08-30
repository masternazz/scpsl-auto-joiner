$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $env:SL_REFERENCES) {
    throw "Set SL_REFERENCES to the SCP:SL server SCPSL_Data\Managed directory before building the LabAPI companion."
}
foreach ($name in @("Assembly-CSharp.dll", "LabAPI.dll")) {
    if (-not (Test-Path -LiteralPath (Join-Path $env:SL_REFERENCES $name))) {
        throw "Missing $name in SL_REFERENCES: $env:SL_REFERENCES"
    }
}
dotnet build .\companion-plugin\AutoJoinerCompanion.csproj -c Release
