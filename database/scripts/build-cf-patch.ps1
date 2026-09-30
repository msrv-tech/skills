# Verified minimal CF patch builder. The Python entrypoint owns the workflow.
[CmdletBinding()]
param(
    [string]$V8Path,
    [Parameter(Mandatory=$true)][string]$BaseCf,
    [Parameter(Mandatory=$true)][string]$BaseConfigDir,
    [Parameter(Mandatory=$true)][string]$ConfigDir,
    [string]$Files,
    [string]$ListFile,
    [Parameter(Mandatory=$true)][string]$OutputFile,
    [string]$ReportFile
)

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) {
    Write-Error "Python 3 not found"
    exit 1
}

$script = Join-Path $PSScriptRoot "build-cf-patch.py"
$arguments = @($script, "-BaseCf", $BaseCf, "-BaseConfigDir", $BaseConfigDir,
    "-ConfigDir", $ConfigDir, "-OutputFile", $OutputFile)
if ($V8Path) { $arguments += "-V8Path", $V8Path }
if ($Files) { $arguments += "-Files", $Files }
if ($ListFile) { $arguments += "-ListFile", $ListFile }
if ($ReportFile) { $arguments += "-ReportFile", $ReportFile }

& $python.Source @arguments
exit $LASTEXITCODE
