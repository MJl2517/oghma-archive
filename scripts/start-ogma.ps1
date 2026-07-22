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
    Write-Error "Порт 5000 уже занят. Закройте работающий PROD/DEV перед запуском второй копии."
    exit 2
}

Set-Location -LiteralPath $projectRoot
$env:OGMA_DEV = "0"
$env:OGMA_HOST = "127.0.0.1"
$env:OGMA_PORT = "5000"
$env:PYTHONUNBUFFERED = "1"
Write-Host "Архив Огмы — production server"
Write-Host "Адрес: http://oghma.local"
Write-Host "Для остановки нажмите Ctrl+C."
& $pythonPath $appPath
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Error "Production-сервер завершился с кодом $exitCode. Возможно, порт 5000 уже занят."
}
exit $exitCode
