$ErrorActionPreference = "Stop"

$etcDirectory = Join-Path $env:SystemRoot "System32\drivers\etc"
$hostsPath = Join-Path $etcDirectory "hosts"
$entry = "127.0.0.1 oghma.local"

$principal = [Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Error "Run PowerShell as Administrator, then run this script again."
    exit 1
}

$sourcePath = $hostsPath
$hostsFile = Get-Item -LiteralPath $hostsPath -ErrorAction Stop
if ($hostsFile.Length -eq 0) {
    $recoveryCopy = Get-ChildItem -LiteralPath $etcDirectory -Filter "hosts_PowerToysBackup_*" -File |
        Where-Object { $_.Length -gt 0 } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -eq $recoveryCopy) {
        throw "The hosts file is empty and no non-empty PowerToys backup was found."
    }

    $sourcePath = $recoveryCopy.FullName
    Write-Host "Recovering the empty hosts file from: $sourcePath"
}

$result = [System.Collections.Generic.List[string]]::new()
foreach ($line in [System.IO.File]::ReadAllLines($sourcePath)) {
    if ($line -notmatch "^\s*127\.0\.0\.1\s+(?:ogma|oghma)\.local\s*(?:#.*)?$") {
        $result.Add($line)
    }
}
$result.Add($entry)

$workDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "Oghma"
[System.IO.Directory]::CreateDirectory($workDirectory) | Out-Null
$temporaryPath = Join-Path $workDirectory ("hosts.{0}.tmp" -f [Guid]::NewGuid().ToString("N"))
$rollbackPath = Join-Path $workDirectory "hosts.rollback"

try {
    [System.IO.File]::WriteAllLines($temporaryPath, $result, [System.Text.Encoding]::ASCII)
    $temporaryContent = [System.IO.File]::ReadAllText($temporaryPath)
    if ((Get-Item -LiteralPath $temporaryPath).Length -eq 0 -or $temporaryContent -notmatch "(?m)^127\.0\.0\.1 oghma\.local\r?$") {
        throw "The generated hosts file failed validation."
    }

    if ($hostsFile.Length -gt 0) {
        Copy-Item -LiteralPath $hostsPath -Destination $rollbackPath -Force
    }
    Copy-Item -LiteralPath $temporaryPath -Destination $hostsPath -Force

    $installedContent = [System.IO.File]::ReadAllText($hostsPath)
    if ((Get-Item -LiteralPath $hostsPath).Length -eq 0 -or $installedContent -notmatch "(?m)^127\.0\.0\.1 oghma\.local\r?$") {
        if (Test-Path -LiteralPath $rollbackPath) {
            Copy-Item -LiteralPath $rollbackPath -Destination $hostsPath -Force
        }
        throw "The installed hosts file failed validation. The previous file was restored when a rollback copy was available."
    }
}
finally {
    if (Test-Path -LiteralPath $temporaryPath) {
        Remove-Item -LiteralPath $temporaryPath -Force
    }
}

Clear-DnsClientCache
Write-Host "Canonical local host installed: $entry"
Write-Host "The obsolete ogma.local entry was removed."
