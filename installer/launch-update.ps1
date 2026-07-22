param(
    [Parameter(Mandatory = $true)][string]$InstallerPath,
    [Parameter(Mandatory = $true)][string]$OghmaExePath,
    [Parameter(Mandatory = $true)][int]$TrayProcessId,
    [Parameter(Mandatory = $true)][int]$ServerProcessId,
    [Parameter(Mandatory = $true)][ValidatePattern("^[0-9A-Fa-f]{64}$")][string]$ExpectedSha256
)

$ErrorActionPreference = "Stop"
$installer = [IO.Path]::GetFullPath($InstallerPath)
$oghmaExe = [IO.Path]::GetFullPath($OghmaExePath)

if (-not (Test-Path -LiteralPath $installer -PathType Leaf) -or [IO.Path]::GetExtension($installer) -ne ".exe") {
    throw "The verified update installer is missing."
}
if (-not (Test-Path -LiteralPath $oghmaExe -PathType Leaf)) {
    throw "The installed Oghma executable is missing."
}
$actualSha256 = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
if (-not $actualSha256.Equals($ExpectedSha256, [StringComparison]::OrdinalIgnoreCase)) {
    throw "The update installer failed the final SHA-256 check."
}

Start-Sleep -Seconds 3
& $oghmaExe --stop | Out-Null

$deadline = [DateTime]::UtcNow.AddSeconds(30)
foreach ($processId in @($ServerProcessId, $TrayProcessId)) {
    while ([DateTime]::UtcNow -lt $deadline -and (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        Start-Sleep -Milliseconds 250
    }
}

Start-Process -FilePath $installer -WorkingDirectory (Split-Path -Parent $installer)
