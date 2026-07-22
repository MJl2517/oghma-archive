param(
    [switch]$WithoutAutostart
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonwPath = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
$trayPath = Join-Path $projectRoot "scripts\ogma_tray.py"
$devCommand = Join-Path $projectRoot "start-ogma-dev.cmd"
$prodCommand = Join-Path $projectRoot "start-ogma-server.cmd"
$iconPath = Join-Path $projectRoot "static\img\ogma-icon.ico"

foreach ($requiredPath in @($pythonwPath, $trayPath, $devCommand, $prodCommand, $iconPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required launcher component was not found: $requiredPath"
    }
}

$shell = New-Object -ComObject WScript.Shell
$programsRoot = [Environment]::GetFolderPath("Programs")
$startupRoot = [Environment]::GetFolderPath("Startup")
$applicationFolder = Join-Path $programsRoot "Архив Огмы"
New-Item -ItemType Directory -Path $applicationFolder -Force | Out-Null

function New-OgmaShortcut {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string]$Arguments,
        [int]$WindowStyle = 1
    )

    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $TargetPath
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.IconLocation = "$iconPath,0"
    $shortcut.WindowStyle = $WindowStyle
    $shortcut.Save()
}

$manualShortcut = Join-Path $applicationFolder "Архив Огмы.lnk"
New-OgmaShortcut `
    -Path $manualShortcut `
    -TargetPath $pythonwPath `
    -Arguments "`"$trayPath`" --open" `
    -WindowStyle 7

$cmdPath = Join-Path $env:SystemRoot "System32\cmd.exe"
$devShortcut = Join-Path $applicationFolder "Архив Огмы — DEV.lnk"
New-OgmaShortcut `
    -Path $devShortcut `
    -TargetPath $cmdPath `
    -Arguments "/k `"`"$devCommand`"`"" `
    -WindowStyle 1

$prodConsoleShortcut = Join-Path $applicationFolder "Архив Огмы — PROD console.lnk"
New-OgmaShortcut `
    -Path $prodConsoleShortcut `
    -TargetPath $cmdPath `
    -Arguments "/k `"`"$prodCommand`"`"" `
    -WindowStyle 1

$projectShortcut = Join-Path $projectRoot "Запустить Архив Огмы.lnk"
New-OgmaShortcut `
    -Path $projectShortcut `
    -TargetPath $pythonwPath `
    -Arguments "`"$trayPath`" --open" `
    -WindowStyle 7

$legacyStartupShortcut = Join-Path $startupRoot "DEV Архив Огмы.lnk"
if (Test-Path -LiteralPath $legacyStartupShortcut) {
    Remove-Item -LiteralPath $legacyStartupShortcut -Force
}

$startupShortcut = Join-Path $startupRoot "Архив Огмы.lnk"
if ($WithoutAutostart) {
    if (Test-Path -LiteralPath $startupShortcut) {
        Remove-Item -LiteralPath $startupShortcut -Force
    }
} else {
    New-OgmaShortcut `
        -Path $startupShortcut `
        -TargetPath $pythonwPath `
        -Arguments "`"$trayPath`" --startup" `
        -WindowStyle 7
}

Write-Host "Start Menu shortcuts installed in: $applicationFolder"
if ($WithoutAutostart) {
    Write-Host "Autostart is disabled."
} else {
    Write-Host "Production tray autostart installed: $startupShortcut"
}
Write-Host "Canonical application URL: http://oghma.local"
