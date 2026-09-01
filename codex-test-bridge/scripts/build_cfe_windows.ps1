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
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $WorkDir) {
    $WorkDir = Join-Path ([System.IO.Path]::GetTempPath()) "codex-test-bridge-build"
}
if (-not $OutFile) {
    $OutFile = Join-Path $root "codex-test-bridge.cfe"
}

$ibcmd = $null
if (Test-Path $PlatformPath -PathType Container) {
    $candidate = Join-Path $PlatformPath "ibcmd.exe"
    if (Test-Path $candidate -PathType Leaf) {
        $ibcmd = $candidate
    }
} elseif ((Split-Path -Leaf $PlatformPath) -ieq "ibcmd.exe" -and (Test-Path $PlatformPath -PathType Leaf)) {
    $ibcmd = $PlatformPath
}
if (-not $ibcmd) {
    $platformExe = $PlatformPath
    if (Test-Path $platformExe -PathType Container) {
        $platformExe = Join-Path $platformExe "1cv8.exe"
    }
    if (-not (Test-Path $platformExe)) {
        throw "Neither ibcmd.exe nor 1cv8.exe was found in: $PlatformPath"
    }
    & python (Join-Path $root "scripts\build_cfe_designer_hidden.py") `
        --platform $platformExe --work-dir $WorkDir --out-file $OutFile
    exit $LASTEXITCODE
}

$db = Join-Path $WorkDir "ib"
$data = Join-Path $WorkDir "data"
if (Test-Path $WorkDir) {
    Remove-Item -LiteralPath $WorkDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $WorkDir, $data | Out-Null

& $ibcmd infobase create --database-path $db
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $ibcmd extension --database-path $db create --name=CodexTestBridge --name-prefix=CTB --purpose=add-on
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $ibcmd config --data $data --database-path $db import --extension CodexTestBridge (Join-Path $root "src")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $ibcmd config --data $data --database-path $db check --extension CodexTestBridge --force
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $ibcmd config --data $data --database-path $db save --extension CodexTestBridge $OutFile
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host $OutFile
