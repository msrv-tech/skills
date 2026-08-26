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
Copy-Item -LiteralPath (Join-Path $root "src\Configuration.xml") -Destination $sourceDir
Copy-Item -LiteralPath (Join-Path $root "src\HTTPServices") -Destination $sourceDir -Recurse

$modulePath = Join-Path $sourceDir "HTTPServices\CodexTestBridge\Ext\Module.bsl"
$moduleText = Get-Content -LiteralPath $modulePath -Raw -Encoding UTF8
$moduleText = [regex]::Replace(
    $moduleText,
    '(?ms)^[^\r\n]*"uijobcreate"[^\r\n]*\r?\n.*?^[^\r\n]*"uijobdelete"[^\r\n]*\r?\n^[^\r\n]*\r?\n',
    '')
$moduleText = [regex]::Replace(
    $moduleText,
    '(?ms)^[^\r\n]*UIJobCreate\(.*?(?=^[^\r\n]*Health\(\))',
    '')
[System.IO.File]::WriteAllText($modulePath, $moduleText, [System.Text.UTF8Encoding]::new($false))

$configurationPath = Join-Path $sourceDir "Configuration.xml"
[xml]$configuration = Get-Content -LiteralPath $configurationPath -Raw -Encoding UTF8
$namespace = New-Object System.Xml.XmlNamespaceManager($configuration.NameTable)
$namespace.AddNamespace("md", "http://v8.1c.ru/8.3/MDClasses")
$properties = $configuration.SelectSingleNode("/md:MetaDataObject/md:Configuration/md:Properties", $namespace)
$properties.SelectSingleNode("md:ConfigurationExtensionCompatibilityMode", $namespace).InnerText = "Version8_3_8"
$defaultRoles = $properties.SelectSingleNode("md:DefaultRoles", $namespace)
if ($defaultRoles) {
    [void]$properties.RemoveChild($defaultRoles)
}
$children = $configuration.SelectSingleNode("/md:MetaDataObject/md:Configuration/md:ChildObjects", $namespace)
foreach ($child in @($children.ChildNodes)) {
    if ($child.LocalName -ne "HTTPService") {
        [void]$children.RemoveChild($child)
    }
}
$configuration.Save($configurationPath)

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
