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

$ibcmd = $null
if (Test-Path -LiteralPath $PlatformPath -PathType Container) {
    $candidate = Join-Path $PlatformPath "ibcmd.exe"
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $ibcmd = $candidate
    }
} elseif ((Split-Path -Leaf $PlatformPath) -ieq "ibcmd.exe" -and
          (Test-Path -LiteralPath $PlatformPath -PathType Leaf)) {
    $ibcmd = $PlatformPath
}

if ($ibcmd) {
    $buildDir = Join-Path $WorkDir "ibcmd"
    $db = Join-Path $buildDir "ib"
    $data = Join-Path $buildDir "data"
    if (Test-Path -LiteralPath $buildDir) {
        Remove-Item -LiteralPath $buildDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $buildDir, $data | Out-Null

    & $ibcmd infobase create --database-path $db
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $ibcmd extension --database-path $db create `
        --name=CodexTestBridge --name-prefix=CTB --purpose=add-on
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $ibcmd config --data $data --database-path $db import `
        --extension CodexTestBridge $sourceDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $ibcmd config --data $data --database-path $db check `
        --extension CodexTestBridge --force
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $ibcmd config --data $data --database-path $db save `
        --extension CodexTestBridge $OutFile
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if (-not (Test-Path -LiteralPath $OutFile -PathType Leaf) -or
        (Get-Item -LiteralPath $OutFile).Length -eq 0) {
        throw "ibcmd completed without creating a non-empty CFE: $OutFile"
    }
    Write-Host $OutFile
    exit 0
}

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
