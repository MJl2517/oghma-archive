$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$appPath = Join-Path $projectRoot "app.py"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error "Virtual environment Python was not found: $pythonPath"
    exit 1
}

function Test-OgmaPortInUse {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connection = $client.BeginConnect("127.0.0.1", 5000, $null, $null)
        if (-not $connection.AsyncWaitHandle.WaitOne(500)) {
            return $false
        }
        $client.EndConnect($connection)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

if (Test-OgmaPortInUse) {
    Write-Error "Порт 5000 уже занят. Выключите PROD через значок в трее перед запуском DEV."
    exit 2
}

Set-Location -LiteralPath $projectRoot
$env:OGMA_DEV = "1"
$env:OGMA_HOST = "127.0.0.1"
$env:OGMA_PORT = "5000"
$env:PYTHONUNBUFFERED = "1"
Write-Host "Архив Огмы — DEV server"
Write-Host "Адрес: http://oghma.local"
Write-Host "Отладчик и автоматическая перезагрузка включены."
Write-Host "Если порт занят, сначала выключите PROD через значок в системном трее."
& $pythonPath $appPath
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Error "DEV-сервер завершился с кодом $exitCode."
}
exit $exitCode
