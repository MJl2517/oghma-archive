$listenAddress = "127.0.0.1"
$listenPort = "80"
$connectAddress = "127.0.0.1"
$connectPort = "5000"

$principal = [Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Error "Run PowerShell as Administrator, then run this script again."
    exit 1
}

$existing = netsh interface portproxy show v4tov4 |
    Select-String -Pattern "^\s*$listenAddress\s+$listenPort\s+"

if ($existing) {
    netsh interface portproxy delete v4tov4 listenaddress=$listenAddress listenport=$listenPort | Out-Null
}

netsh interface portproxy add v4tov4 listenaddress=$listenAddress listenport=$listenPort connectaddress=$connectAddress connectport=$connectPort
Write-Host "Added port proxy: http://oghma.local -> internal loopback port 5000"
