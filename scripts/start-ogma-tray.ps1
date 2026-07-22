$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonwPath = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
$trayPath = Join-Path $projectRoot "scripts\ogma_tray.py"

if (-not (Test-Path -LiteralPath $pythonwPath)) {
    Write-Error "Virtual environment PythonW was not found: $pythonwPath"
    exit 1
}

if (-not (Test-Path -LiteralPath $trayPath)) {
    Write-Error "Tray script was not found: $trayPath"
    exit 1
}

Set-Location -LiteralPath $projectRoot
Start-Process `
    -FilePath $pythonwPath `
    -ArgumentList @("`"$trayPath`"", "--open") `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden
