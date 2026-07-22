$ErrorActionPreference = "Stop"
$startupRoot = [Environment]::GetFolderPath("Startup")
$programsRoot = [Environment]::GetFolderPath("Programs")

foreach ($shortcutName in @("Архив Огмы.lnk", "DEV Архив Огмы.lnk")) {
    $shortcutPath = Join-Path $startupRoot $shortcutName
    if (Test-Path -LiteralPath $shortcutPath -PathType Leaf) {
        Remove-Item -LiteralPath $shortcutPath -Force
    }
}

$legacyProgramsFolder = Join-Path $programsRoot "Архив Огмы"
if (Test-Path -LiteralPath $legacyProgramsFolder -PathType Container) {
    $resolvedProgramsRoot = [IO.Path]::GetFullPath($programsRoot)
    $resolvedLegacyFolder = [IO.Path]::GetFullPath($legacyProgramsFolder)
    $programsPrefix = $resolvedProgramsRoot.TrimEnd("\") + "\"
    if (-not $resolvedLegacyFolder.StartsWith($programsPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a legacy folder outside the Start Menu."
    }
    Remove-Item -LiteralPath $resolvedLegacyFolder -Recurse -Force
}
