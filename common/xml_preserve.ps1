# Byte-preserving XML helpers for PowerShell skills (Windows PowerShell 5.1+).
# Keep the same source properties that a DOM round-trip normally loses.

function Get-XmlSourceStyle {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [pscustomobject]@{
            Exists = $false
            Bom = $true
            Eol = "`n"
            Declaration = '<?xml version="1.0" encoding="UTF-8"?>'
            FinalNewline = $true
            PairedEmpty = @{}
        }
    }

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $bom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
    $text = [System.Text.Encoding]::UTF8.GetString($bytes)
    if ($bom -and $text.Length -gt 0) {
        $text = $text.Substring(1)
    }

    $crlf = ([regex]::Matches($text, "`r`n")).Count
    $lf = ([regex]::Matches($text, "`n")).Count - $crlf
    $eol = if ($crlf -gt $lf) { "`r`n" } else { "`n" }

    $declaration = $null
    $match = [regex]::Match($text, '^<\?xml[^>]*\?>')
    if ($match.Success) {
        $declaration = $match.Value
    }

    $paired = @{}
    foreach ($item in [regex]::Matches($text, '<([A-Za-z_][\w:.-]*)(\s[^<>]*?)?></\1>')) {
        $name = $item.Groups[1].Value
        if ($paired.ContainsKey($name)) {
            $paired[$name] = $paired[$name] + 1
        } else {
            $paired[$name] = 1
        }
    }

    return [pscustomobject]@{
        Exists = $true
        Bom = $bom
        Eol = $eol
        Declaration = $declaration
        FinalNewline = $text.EndsWith("`n")
        PairedEmpty = $paired
    }
}

function Restore-XmlPairedEmpty {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][hashtable]$Counts
    )

    if ($Counts.Count -eq 0) {
        return $Text
    }
    $remaining = @{}
    foreach ($key in $Counts.Keys) {
        $remaining[$key] = [int]$Counts[$key]
    }
    $evaluator = [System.Text.RegularExpressions.MatchEvaluator]{
        param($match)
        $name = $match.Groups[1].Value
        if (-not $remaining.ContainsKey($name) -or $remaining[$name] -le 0) {
            return $match.Value
        }
        $remaining[$name] = $remaining[$name] - 1
        $raw = $match.Value
        return $raw.Substring(0, $raw.Length - 2) + '></' + $name + '>'
    }
    return [regex]::Replace($Text, '<([A-Za-z_][\w:.-]*)(\s[^<>]*?)?/>', $evaluator)
}

function Save-XmlTextPreserving {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][AllowEmptyString()][string]$Text
    )

    $style = Get-XmlSourceStyle -Path $Path

    if ($null -eq $style.Declaration) {
        $normalized = [regex]::Replace($Text, '^<\?xml[^>]*\?>', '').TrimStart("`r", "`n")
    } else {
        $normalized = [regex]::Replace($Text, '^<\?xml[^>]*\?>', [System.Text.RegularExpressions.MatchEvaluator]{
            param($match)
            return $style.Declaration
        })
    }

    $normalized = Restore-XmlPairedEmpty -Text $normalized -Counts $style.PairedEmpty
    $normalized = $normalized.Replace("`r`n", "`n")
    if ($style.Eol -eq "`r`n") {
        $normalized = $normalized.Replace("`n", "`r`n")
    }
    $normalized = $normalized.TrimEnd("`r", "`n")
    if ($style.FinalNewline) {
        $normalized += $style.Eol
    }

    $payload = [byte[]][System.Text.Encoding]::UTF8.GetBytes($normalized)
    if ($style.Bom) {
        $payload = [byte[]](([byte[]](0xEF, 0xBB, 0xBF)) + $payload)
    }
    [System.IO.File]::WriteAllBytes($Path, $payload)
}

function Save-XmlDocumentPreserving {
    param(
        [Parameter(Mandatory)][System.Xml.XmlDocument]$XmlDoc,
        [Parameter(Mandatory)][string]$Path
    )

    $settings = New-Object System.Xml.XmlWriterSettings
    $settings.Encoding = New-Object System.Text.UTF8Encoding($false)
    $settings.Indent = $false
    $settings.NewLineHandling = [System.Xml.NewLineHandling]::None

    $stream = New-Object System.IO.MemoryStream
    $writer = [System.Xml.XmlWriter]::Create($stream, $settings)
    try {
        $XmlDoc.Save($writer)
        $writer.Flush()
        $bytes = $stream.ToArray()
    } finally {
        $writer.Close()
        $stream.Close()
    }

    $text = [System.Text.Encoding]::UTF8.GetString($bytes)
    if ($text.Length -gt 0 -and $text[0] -eq [char]0xFEFF) {
        $text = $text.Substring(1)
    }
    Save-XmlTextPreserving -Path $Path -Text $text
}
