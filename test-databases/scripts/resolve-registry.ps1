[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$RegistryPath,

    [Parameter(Mandatory = $false)]
    [string]$LocalConfigPath
)

$ErrorActionPreference = "Stop"

function Resolve-FullPath([string]$Path, [string]$BasePath) {
    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    if (-not [IO.Path]::IsPathRooted($expanded)) {
        $expanded = Join-Path $BasePath $expanded
    }
    return [IO.Path]::GetFullPath($expanded)
}

function Get-DefaultLocalConfigPath {
    $codexRoot = $env:CODEX_HOME
    if ([string]::IsNullOrWhiteSpace($codexRoot)) {
        $userProfile = [Environment]::GetFolderPath("UserProfile")
        if ([string]::IsNullOrWhiteSpace($userProfile)) {
            throw "Cannot determine the user profile. Specify -LocalConfigPath."
        }
        $codexRoot = Join-Path $userProfile ".codex"
    }
    return Join-Path $codexRoot "1c\local.json"
}

$source = $null
$candidate = $null

if (-not [string]::IsNullOrWhiteSpace($RegistryPath)) {
    $source = "-RegistryPath"
    $candidate = $RegistryPath
} elseif (-not [string]::IsNullOrWhiteSpace($env:CODEX_1C_TEST_DATABASES)) {
    $source = "CODEX_1C_TEST_DATABASES"
    $candidate = $env:CODEX_1C_TEST_DATABASES
} else {
    if ([string]::IsNullOrWhiteSpace($LocalConfigPath)) {
        $LocalConfigPath = Get-DefaultLocalConfigPath
    }
    $LocalConfigPath = [IO.Path]::GetFullPath(
        [Environment]::ExpandEnvironmentVariables($LocalConfigPath)
    )
    if (-not (Test-Path -LiteralPath $LocalConfigPath -PathType Leaf)) {
        throw "Test database registry is not configured. Specify -RegistryPath, CODEX_1C_TEST_DATABASES, or create the local Codex 1C config."
    }
    try {
        $localConfig = Get-Content -LiteralPath $LocalConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        throw "Cannot read local Codex 1C config: $($_.Exception.Message)"
    }
    if ([string]::IsNullOrWhiteSpace($localConfig.testDatabasesPath)) {
        throw "Local Codex 1C config has no testDatabasesPath."
    }
    $source = "local Codex 1C config"
    $candidate = Resolve-FullPath $localConfig.testDatabasesPath (Split-Path -Parent $LocalConfigPath)
}

$candidate = Resolve-FullPath $candidate (Get-Location).Path
if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
    throw "Test database registry selected by $source does not exist."
}

try {
    $registry = Get-Content -LiteralPath $candidate -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    throw "Cannot read test database registry selected by ${source}: $($_.Exception.Message)"
}
if ($null -eq $registry.databases -or $registry.databases -isnot [Array]) {
    throw "Test database registry selected by $source has no databases array."
}

Write-Output $candidate
