$ErrorActionPreference = "Stop"
$programsRoot = [Environment]::GetFolderPath("Programs")
$startupRoot = [Environment]::GetFolderPath("Startup")
$applicationFolder = Join-Path $programsRoot "Архив Огмы"
$startupShortcuts = @(
    (Join-Path $startupRoot "Архив Огмы.lnk"),
    (Join-Path $startupRoot "DEV Архив Огмы.lnk")
)

foreach ($shortcut in $startupShortcuts) {
    if (Test-Path -LiteralPath $shortcut) {
        Remove-Item -LiteralPath $shortcut -Force
    }
}
if (Test-Path -LiteralPath $applicationFolder) {
    $resolvedPrograms = [System.IO.Path]::GetFullPath($programsRoot)
    $resolvedApplicationFolder = [System.IO.Path]::GetFullPath($applicationFolder)
    if (-not $resolvedApplicationFolder.StartsWith($resolvedPrograms, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a Start Menu folder outside the user Programs directory."
    }
    Remove-Item -LiteralPath $resolvedApplicationFolder -Recurse -Force
}

Write-Host "Oghma Start Menu and autostart shortcuts were removed."
