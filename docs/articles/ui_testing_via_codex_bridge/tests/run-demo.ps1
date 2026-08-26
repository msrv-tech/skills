param(
    [Parameter(Mandatory)]
    [string]$Scenario,

    [Parameter(Mandatory)]
    [string]$ArtifactDir,

    [string]$Database = 'fresh-bp-demo'
)

$ErrorActionPreference = 'Stop'
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex' }
$skillsRoot = Join-Path $codexRoot 'skills'
$registryPath = & (Join-Path $skillsRoot 'test-databases\scripts\resolve-registry.ps1')
$registry = Get-Content -LiteralPath $registryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$entry = @($registry.databases | Where-Object { $_.Ref -eq $Database })[0]
if ($null -eq $entry -or -not $entry.Bridge.BaseUrl) { throw "Database or Bridge is not configured: $Database" }

$platform = Get-ChildItem -LiteralPath 'C:\Program Files\1cv8' -Directory |
    Sort-Object Name -Descending |
    ForEach-Object { Join-Path $_.FullName 'bin\1cv8c.exe' } |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1
if (-not $platform) { throw '1cv8c.exe was not found' }

$env:CODEX_1C_EXECUTABLE = $platform
$env:CODEX_1C_CLIENT_SERVER_CONNECTION = "$($entry.Srvr)/$($entry.Ref)"
$env:CODEX_1C_MANAGER_SERVER_CONNECTION = "$($entry.Srvr)/$($entry.Ref)"
$env:CODEX_1C_MANAGER_BRIDGE_URL = $entry.Bridge.BaseUrl

$bridgeRoot = Join-Path $skillsRoot 'codex-test-bridge'
python (Join-Path $bridgeRoot 'scripts\run_cross_db_ui_with_bootstrap.py') `
    --allow-bootstrap-user `
    --target-bridge-base-url $entry.Bridge.BaseUrl `
    --manager-bridge-base-url $entry.Bridge.BaseUrl `
    --worker-config (Join-Path $bridgeRoot 'ui-worker.cross-db.example.json') `
    --scenario (Resolve-Path -LiteralPath $Scenario) `
    --artifact-dir $ArtifactDir `
    --report (Join-Path $ArtifactDir 'worker.json')

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
