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
    $WorkDir = Join-Path ([System.IO.Path]::GetTempPath()) "codex-ui-test-fixtures-build"
}
if (-not $OutFile) {
    $OutFile = Join-Path $root "codex-ui-test-fixtures.cfe"
}

$ibcmd = $PlatformPath
if (Test-Path -LiteralPath $ibcmd -PathType Container) {
    $ibcmd = Join-Path $ibcmd "ibcmd.exe"
}
if (-not (Test-Path -LiteralPath $ibcmd -PathType Leaf)) {
    throw "ibcmd.exe was not found in: $PlatformPath"
}

$db = Join-Path $WorkDir "ib"
$data = Join-Path $WorkDir "data"
if (Test-Path -LiteralPath $WorkDir) {
    Remove-Item -LiteralPath $WorkDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $WorkDir, $data | Out-Null

& $ibcmd infobase create --database-path $db
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $ibcmd extension --database-path $db create --name=CodexUITestFixtures --name-prefix=CTF --purpose=add-on
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $ibcmd config --data $data --database-path $db import --extension CodexUITestFixtures (Join-Path $root "src")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $ibcmd config --data $data --database-path $db check --extension CodexUITestFixtures --force
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $ibcmd config --data $data --database-path $db save --extension CodexUITestFixtures $OutFile
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not (Test-Path -LiteralPath $OutFile -PathType Leaf) -or (Get-Item -LiteralPath $OutFile).Length -eq 0) {
    throw "ibcmd completed without creating a non-empty CFE: $OutFile"
}
Write-Host $OutFile
