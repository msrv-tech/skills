param(
    [Parameter(Mandatory = $true)]
    [string]$VrdPath,

    [string]$ServiceName = "CodexTestBridge",
    [string]$RootUrl = "codex-test"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $VrdPath)) {
    throw "VRD file not found: $VrdPath"
}

[xml]$doc = Get-Content -Raw -LiteralPath $VrdPath
$nsUri = $doc.DocumentElement.NamespaceURI
$nsm = New-Object System.Xml.XmlNamespaceManager($doc.NameTable)
$nsm.AddNamespace("vrs", $nsUri)

$point = $doc.DocumentElement
$httpServices = $point.SelectSingleNode("vrs:httpServices", $nsm)
if ($null -eq $httpServices) {
    $httpServices = $doc.CreateElement("httpServices", $nsUri)
    [void]$point.AppendChild($httpServices)
}

$httpServices.SetAttribute("publishByDefault", "true")
$httpServices.SetAttribute("publishExtensionsByDefault", "true")

$service = $httpServices.SelectSingleNode("vrs:service[@name='$ServiceName']", $nsm)
if ($null -eq $service) {
    $service = $doc.CreateElement("service", $nsUri)
    [void]$httpServices.AppendChild($service)
}

$service.SetAttribute("name", $ServiceName)
$service.SetAttribute("rootUrl", $RootUrl)
$service.SetAttribute("enable", "true")
$service.SetAttribute("reuseSessions", "dontuse")
$service.SetAttribute("sessionMaxAge", "20")

$settings = New-Object System.Xml.XmlWriterSettings
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$settings.Indent = $true
$settings.NewLineChars = "`r`n"
$writer = [System.Xml.XmlWriter]::Create($VrdPath, $settings)
try {
    $doc.Save($writer)
}
finally {
    $writer.Close()
}

Write-Host "CodexTestBridge HTTP service enabled in $VrdPath"
