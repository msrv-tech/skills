# repo-update v1.0 - Update 1C configuration from repository
<#
.SYNOPSIS
    Получение конфигурации 1С из хранилища конфигурации.

.DESCRIPTION
    Разрешает приватный реестр через скил test-databases, находит базу и параметры Repository,
    затем запускает 1cv8.exe DESIGNER /ConfigurationRepositoryUpdateCfg.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$Database,

    [Parameter(Mandatory=$false)]
    [string]$ProjectPath = (Get-Location).Path,

    [Parameter(Mandatory=$false)]
    [string]$RegistryPath,

    [Parameter(Mandatory=$false)]
    [string]$V8Path,

    [Parameter(Mandatory=$false)]
    [int]$Version,

    [Parameter(Mandatory=$false)]
    [switch]$Revised,

    [Parameter(Mandatory=$false)]
    [switch]$Force,

    [Parameter(Mandatory=$false)]
    [string]$Objects,

    [Parameter(Mandatory=$false)]
    [string]$Extension,

    [Parameter(Mandatory=$false)]
    [switch]$UpdateDB,

    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Fail([string]$Message) {
    Write-Host "Error: $Message" -ForegroundColor Red
    exit 1
}

function Resolve-V8Exe([string]$Path) {
    if (-not $Path) {
        $candidates = @()
        $candidates += Get-ChildItem "C:\Program Files\1cv8\*\bin\1cv8.exe" -ErrorAction SilentlyContinue
        $candidates += Get-ChildItem "C:\Program Files (x86)\1cv8\*\bin\1cv8.exe" -ErrorAction SilentlyContinue
        $found = $candidates | Sort-Object FullName -Descending | Select-Object -First 1
        if (-not $found) { Fail "1cv8.exe not found. Specify -V8Path" }
        return $found.FullName
    }

    if (Test-Path -LiteralPath $Path -PathType Container) {
        $Path = Join-Path $Path "1cv8.exe"
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Fail "1cv8.exe not found at $Path"
    }
    return $Path
}

function Normalize-PathText([string]$Path) {
    if (-not $Path) { return "" }
    try {
        return ([System.IO.Path]::GetFullPath($Path)).TrimEnd('\')
    } catch {
        return $Path.TrimEnd('\')
    }
}

function Test-DbMatch($Db, [string]$Query) {
    if (-not $Query) { return $false }
    $q = $Query.ToLowerInvariant()
    $pathLeaf = ""
    if ($Db.path) { $pathLeaf = Split-Path -Leaf $Db.path }
    $values = @(
        $Db.Ref,
        $pathLeaf,
        $Db.path,
        $Db.Srvr,
        "$(if ($Db.Srvr) { $Db.Srvr })/$(if ($Db.Ref) { $Db.Ref })",
        $Db.IBConnectionString,
        $Db.Repository.Name,
        $Db.Repository.Url
    )
    foreach ($value in $values) {
        if ($value -and $value.ToString().ToLowerInvariant().Contains($q)) {
            return $true
        }
    }
    return $false
}

function Select-Database($Databases, [string]$Query, [string]$CurrentPath) {
    if ($Query) {
        $matches = @($Databases | Where-Object { Test-DbMatch $_ $Query })
        return $matches
    }

    $project = Normalize-PathText $CurrentPath
    $matches = @()
    foreach ($db in $Databases) {
        if (-not $db.path) { continue }
        $dbPath = Normalize-PathText $db.path
        if ($project.Equals($dbPath, [System.StringComparison]::OrdinalIgnoreCase) -or
            $project.StartsWith($dbPath + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
            $matches += $db
        }
    }

    return @($matches | Sort-Object { (Normalize-PathText $_.path).Length } -Descending)
}

function Quote-Arg([string]$Value) {
    return '"' + ($Value -replace '"', '\"') + '"'
}

$resolverPath = Join-Path $PSScriptRoot "..\..\test-databases\scripts\resolve-registry.ps1"
if (-not (Test-Path -LiteralPath $resolverPath -PathType Leaf)) {
    Fail "test-databases registry resolver not found"
}
try {
    $RegistryPath = & $resolverPath -RegistryPath $RegistryPath -ErrorAction Stop
} catch {
    Fail $_.Exception.Message
}

try {
    $registry = Get-Content -LiteralPath $RegistryPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Fail "cannot read JSON registry: $($_.Exception.Message)"
}

if (-not $registry.databases) {
    Fail "registry has no databases array: $RegistryPath"
}

$matches = @(Select-Database $registry.databases $Database $ProjectPath)
if ($matches.Count -eq 0) {
    Fail "database not found in $RegistryPath"
}
if ($matches.Count -gt 1) {
    Write-Host "Multiple databases matched. Specify -Database more precisely:" -ForegroundColor Yellow
    foreach ($db in $matches) {
        $repoUrl = if ($db.Repository) { $db.Repository.Url } else { "-" }
        Write-Host "  $($db.path) | $($db.Srvr)/$($db.Ref) | $repoUrl"
    }
    exit 2
}

$db = $matches[0]
if (-not $db.Repository) {
    Fail "Repository is not configured for $($db.path)"
}
if (-not $db.Repository.Url) {
    Fail "Repository.Url is empty for $($db.path)"
}

if (-not $DryRun) {
    $V8Path = Resolve-V8Exe $V8Path
}

$argString = "DESIGNER"
if ($db.Srvr -and $db.Ref) {
    $argString += " /S " + (Quote-Arg "$($db.Srvr)/$($db.Ref)")
} elseif ($db.IBConnectionString) {
    $argString += " /IBConnectionString " + (Quote-Arg $db.IBConnectionString)
} elseif ($db.path) {
    $argString += " /F " + (Quote-Arg $db.path)
} else {
    Fail "database connection is incomplete for selected entry"
}

if ($db.User) { $argString += " /N" + (Quote-Arg $db.User) }
if ($db.Password) { $argString += " /P" + (Quote-Arg $db.Password) }

$argString += " /ConfigurationRepositoryF " + (Quote-Arg $db.Repository.Url)
if ($db.Repository.User) { $argString += " /ConfigurationRepositoryN " + (Quote-Arg $db.Repository.User) }
if ($db.Repository.Password) { $argString += " /ConfigurationRepositoryP " + (Quote-Arg $db.Repository.Password) }

$argString += " /ConfigurationRepositoryUpdateCfg"
if ($Version) { $argString += " -v $Version" }
if ($Revised) { $argString += " -revised" }
if ($Force) { $argString += " -force" }
if ($Objects) { $argString += " -objects " + (Quote-Arg $Objects) }
if ($Extension) { $argString += " -Extension " + (Quote-Arg $Extension) }
if ($UpdateDB) { $argString += " /UpdateDBCfg" }

$tempDir = Join-Path $env:TEMP "repo_update_$(Get-Random)"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$outFile = Join-Path $tempDir "repo_update.log"
$argString += " /Out " + (Quote-Arg $outFile)
$argString += " /DisableStartupDialogs"

$masked = $argString
if ($db.Password) {
    $masked = $masked.Replace("/P" + (Quote-Arg $db.Password), "/P""***""")
}
if ($db.Repository.Password) {
    $masked = $masked.Replace("/ConfigurationRepositoryP " + (Quote-Arg $db.Repository.Password), "/ConfigurationRepositoryP ""***""")
}

try {
    Write-Host "Database: $($db.path) | $($db.Srvr)/$($db.Ref)"
    Write-Host "Repository: $($db.Repository.Name) | $($db.Repository.Url)"
    Write-Host "Running: 1cv8.exe $masked"

    if ($DryRun) {
        Write-Host "Dry run: 1C was not started" -ForegroundColor Yellow
        exit 0
    }

    $process = Start-Process -FilePath $V8Path -ArgumentList $argString -NoNewWindow -Wait -PassThru
    $exitCode = $process.ExitCode

    if (Test-Path -LiteralPath $outFile) {
        $logContent = Get-Content -LiteralPath $outFile -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
        if ($logContent) {
            Write-Host "--- Log ---"
            Write-Host $logContent
            Write-Host "--- End ---"
        }
    }

    if ($exitCode -eq 0) {
        Write-Host "Configuration updated from repository successfully" -ForegroundColor Green
    } else {
        Write-Host "Repository update failed (code: $exitCode)" -ForegroundColor Red
    }
    exit $exitCode
} finally {
    if (Test-Path -LiteralPath $tempDir) {
        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
