param(
    [switch]$Install,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$CanonicalEntry = "127.0.0.1 oghma.local # Oghma Archive"
$ManagedEntryPattern = "^\s*127\.0\.0\.1\s+oghma\.local\s+#\s*Oghma Archive\s*$"
$HostsPath = Join-Path $env:SystemRoot "System32\drivers\etc\hosts"

if ($Install -eq $Uninstall) {
    throw "Specify exactly one action: -Install or -Uninstall."
}

$principal = [Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Administrator privileges are required to configure oghma.local."
}

function Invoke-Netsh {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & "$env:SystemRoot\System32\netsh.exe" @Arguments | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "netsh failed with exit code $LASTEXITCODE."
    }
}

function Get-PortProxyState {
    $output = & "$env:SystemRoot\System32\netsh.exe" interface portproxy show v4tov4 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect the Windows port proxy configuration."
    }

    $matchingRows = @($output | Where-Object { $_ -match "^\s*127\.0\.0\.1\s+80\s+" })
    $desiredRows = @($matchingRows | Where-Object { $_ -match "^\s*127\.0\.0\.1\s+80\s+127\.0\.0\.1\s+5000\s*$" })
    [pscustomobject]@{
        HasDesired = $desiredRows.Count -gt 0
        HasConflict = $matchingRows.Count -gt $desiredRows.Count
    }
}

function Test-Port80Listener {
    try {
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort 80 -ErrorAction Stop)
    }
    catch [Microsoft.PowerShell.Cmdletization.Cim.CimJobException] {
        return $false
    }
    catch [Microsoft.Management.Infrastructure.CimException] {
        return $false
    }
    return $listeners.Count -gt 0
}

function Get-TextEncodingInfo {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)

    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) {
        return [pscustomobject]@{ Encoding = [Text.UTF8Encoding]::new($false); Preamble = [byte[]](0xEF, 0xBB, 0xBF); Offset = 3 }
    }
    if ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFF -and $Bytes[1] -eq 0xFE) {
        return [pscustomobject]@{ Encoding = [Text.UnicodeEncoding]::new($false, $false); Preamble = [byte[]](0xFF, 0xFE); Offset = 2 }
    }
    if ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFE -and $Bytes[1] -eq 0xFF) {
        return [pscustomobject]@{ Encoding = [Text.UnicodeEncoding]::new($true, $false); Preamble = [byte[]](0xFE, 0xFF); Offset = 2 }
    }

    try {
        $strictUtf8 = [Text.UTF8Encoding]::new($false, $true)
        [void]$strictUtf8.GetString($Bytes)
        return [pscustomobject]@{ Encoding = [Text.UTF8Encoding]::new($false); Preamble = [byte[]]@(); Offset = 0 }
    }
    catch [Text.DecoderFallbackException] {
        return [pscustomobject]@{ Encoding = [Text.Encoding]::Default; Preamble = [byte[]]@(); Offset = 0 }
    }
}

function Convert-HostsContent {
    param(
        [Parameter(Mandatory = $true)][string]$Content,
        [Parameter(Mandatory = $true)][bool]$ForInstall
    )

    $newline = if ($Content.Contains("`r`n")) { "`r`n" } else { "`n" }
    $hadTrailingNewline = $Content.EndsWith("`n") -or $Content.EndsWith("`r")
    $lines = [Collections.Generic.List[string]]::new()
    foreach ($line in [Regex]::Split($Content, "\r\n|\n|\r")) {
        $lines.Add($line)
    }
    if ($hadTrailingNewline -and $lines.Count -gt 0 -and $lines[$lines.Count - 1] -eq "") {
        $lines.RemoveAt($lines.Count - 1)
    }

    $result = [Collections.Generic.List[string]]::new()
    foreach ($line in $lines) {
        if (-not $ForInstall) {
            if ($line -notmatch $ManagedEntryPattern) {
                $result.Add($line)
            }
            continue
        }

        $commentIndex = $line.IndexOf("#")
        $body = if ($commentIndex -ge 0) { $line.Substring(0, $commentIndex) } else { $line }
        $comment = if ($commentIndex -ge 0) { $line.Substring($commentIndex).Trim() } else { "" }
        $tokens = @($body.Trim() -split "\s+" | Where-Object { $_ })
        if ($tokens.Count -lt 2) {
            if ($line -notmatch $ManagedEntryPattern) {
                $result.Add($line)
            }
            continue
        }

        $remainingHosts = @($tokens[1..($tokens.Count - 1)] | Where-Object {
            $_.ToLowerInvariant() -notin @("oghma.local", "ogma.local")
        })
        if ($remainingHosts.Count -eq ($tokens.Count - 1)) {
            $result.Add($line)
            continue
        }
        if ($remainingHosts.Count -gt 0) {
            $rebuilt = "$($tokens[0]) $($remainingHosts -join ' ')"
            if ($comment) {
                $rebuilt += " $comment"
            }
            $result.Add($rebuilt)
        }
        elseif ($comment -and $line -notmatch $ManagedEntryPattern) {
            $result.Add($comment)
        }
    }

    if ($ForInstall) {
        $result.Add($CanonicalEntry)
    }
    return ($result -join $newline) + $newline
}

function Set-HostsContent {
    param([Parameter(Mandatory = $true)][bool]$ForInstall)

    $bytes = [IO.File]::ReadAllBytes($HostsPath)
    $encodingInfo = Get-TextEncodingInfo -Bytes $bytes
    $bodyLength = $bytes.Length - $encodingInfo.Offset
    $content = $encodingInfo.Encoding.GetString($bytes, $encodingInfo.Offset, $bodyLength)
    $updated = Convert-HostsContent -Content $content -ForInstall $ForInstall

    $temporaryPath = Join-Path ([IO.Path]::GetTempPath()) ("oghma-hosts-{0}.tmp" -f [Guid]::NewGuid().ToString("N"))
    $rollbackPath = Join-Path ([IO.Path]::GetTempPath()) ("oghma-hosts-{0}.bak" -f [Guid]::NewGuid().ToString("N"))
    try {
        $payload = $encodingInfo.Encoding.GetBytes($updated)
        if ($encodingInfo.Preamble.Length -gt 0) {
            $combined = [byte[]]::new($encodingInfo.Preamble.Length + $payload.Length)
            [Array]::Copy($encodingInfo.Preamble, 0, $combined, 0, $encodingInfo.Preamble.Length)
            [Array]::Copy($payload, 0, $combined, $encodingInfo.Preamble.Length, $payload.Length)
            $payload = $combined
        }
        [IO.File]::WriteAllBytes($temporaryPath, $payload)
        Copy-Item -LiteralPath $HostsPath -Destination $rollbackPath -Force
        Copy-Item -LiteralPath $temporaryPath -Destination $HostsPath -Force

        $installed = [IO.File]::ReadAllText($HostsPath, $encodingInfo.Encoding)
        if ($ForInstall -and $installed -notmatch "(?m)$ManagedEntryPattern") {
            Copy-Item -LiteralPath $rollbackPath -Destination $HostsPath -Force
            throw "The oghma.local hosts entry could not be verified. The previous hosts file was restored."
        }
    }
    finally {
        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $rollbackPath -Force -ErrorAction SilentlyContinue
    }
}

function Clear-LocalDnsCache {
    try {
        Clear-DnsClientCache -ErrorAction Stop
    }
    catch {
        & "$env:SystemRoot\System32\ipconfig.exe" /flushdns | Out-Null
    }
}

if ($Install) {
    $proxyState = Get-PortProxyState
    if ($proxyState.HasConflict) {
        throw "127.0.0.1:80 is already assigned to another Windows port proxy."
    }
    if (-not $proxyState.HasDesired -and (Test-Port80Listener)) {
        throw "Local port 80 is already in use. Stop the conflicting application and run setup again."
    }

    $addedProxy = $false
    try {
        if (-not $proxyState.HasDesired) {
            Invoke-Netsh -Arguments @(
                "interface", "portproxy", "add", "v4tov4",
                "listenaddress=127.0.0.1", "listenport=80",
                "connectaddress=127.0.0.1", "connectport=5000"
            )
            $addedProxy = $true
        }
        Set-HostsContent -ForInstall $true
    }
    catch {
        if ($addedProxy) {
            Invoke-Netsh -Arguments @(
                "interface", "portproxy", "delete", "v4tov4",
                "listenaddress=127.0.0.1", "listenport=80"
            )
        }
        throw
    }
    Clear-LocalDnsCache
    exit 0
}

Set-HostsContent -ForInstall $false
$proxyState = Get-PortProxyState
if ($proxyState.HasDesired -and -not $proxyState.HasConflict) {
    Invoke-Netsh -Arguments @(
        "interface", "portproxy", "delete", "v4tov4",
        "listenaddress=127.0.0.1", "listenport=80"
    )
}
Clear-LocalDnsCache
