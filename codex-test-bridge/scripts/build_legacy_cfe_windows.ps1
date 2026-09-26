[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$PlatformPath,

    [Parameter(Mandatory=$false)]
    [string]$WorkDir,

    [Parameter(Mandatory=$false)]
    [string]$OutFile
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $WorkDir) {
    $WorkDir = Join-Path ([System.IO.Path]::GetTempPath()) "codex-test-bridge-legacy-build"
}
if (-not $OutFile) {
    $OutFile = Join-Path $root "codex-test-bridge-legacy.cfe"
}

$sourceDir = Join-Path $WorkDir "source"
if (Test-Path -LiteralPath $sourceDir) {
    Remove-Item -LiteralPath $sourceDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $sourceDir | Out-Null
& python (Join-Path $root "scripts\prepare_legacy_source.py") `
    --source (Join-Path $root "src") --output $sourceDir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$platform = $PlatformPath
if (Test-Path -LiteralPath $platform -PathType Container) {
    $platform = Join-Path $platform "1cv8.exe"
}
& python (Join-Path $root "scripts\build_cfe_designer_hidden.py") `
    --platform $platform `
    --work-dir (Join-Path $WorkDir "designer") `
    --source-dir $sourceDir `
    --out-file $OutFile
exit $LASTEXITCODE
