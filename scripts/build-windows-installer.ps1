param(
    [ValidatePattern("^\d+\.\d+\.\d+$")]
    [string]$Version = "1.1.0"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$specPath = Join-Path $projectRoot "installer\Oghma.spec"
$issPath = Join-Path $projectRoot "installer\Oghma.iss"
$versionInfoTemplatePath = Join-Path $projectRoot "installer\version-info.template.txt"
$buildRoot = Join-Path $projectRoot "build"
$packageRoot = Join-Path $buildRoot "package"
$workRoot = Join-Path $buildRoot "pyinstaller"
$installerOutput = Join-Path $projectRoot "dist-installer"

if (-not [Environment]::Is64BitOperatingSystem) {
    throw "The Oghma installer currently supports 64-bit Windows only."
}
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Build Python was not found at $pythonPath"
}

$sourceVersion = (& $pythonPath -c "from ogma.version import APP_VERSION; print(APP_VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or $sourceVersion -ne $Version) {
    throw "Requested build version $Version does not match ogma.version APP_VERSION $sourceVersion."
}

& $pythonPath -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is missing. Run: .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt"
}

foreach ($path in @($buildRoot, $installerOutput)) {
    $resolvedParent = [IO.Path]::GetFullPath((Split-Path -Parent $path))
    if (-not $resolvedParent.Equals([IO.Path]::GetFullPath($projectRoot), [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a build path outside the project root: $path"
    }
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

[IO.Directory]::CreateDirectory($buildRoot) | Out-Null
$versionParts = @($Version.Split(".") | ForEach-Object { [int]$_ })
$versionTuple = ($versionParts + 0) -join ", "
$versionInfo = [IO.File]::ReadAllText($versionInfoTemplatePath)
$versionInfo = $versionInfo.Replace("@VERSION_TUPLE@", $versionTuple).Replace("@VERSION@", $Version)
[IO.File]::WriteAllText(
    (Join-Path $buildRoot "version-info.txt"),
    $versionInfo,
    [Text.UTF8Encoding]::new($false)
)

& $pythonPath -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $packageRoot `
    --workpath $workRoot `
    $specPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$innoRegistryLocations = @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
    "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"
)
$innoInstallLocations = @($innoRegistryLocations | ForEach-Object {
    (Get-ItemProperty -LiteralPath $_ -ErrorAction SilentlyContinue).InstallLocation
} | Where-Object { $_ })

$isccCandidates = @(
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
    @($innoInstallLocations | ForEach-Object { Join-Path $_ "ISCC.exe" })
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }
$isccPath = $isccCandidates | Select-Object -First 1
if (-not $isccPath) {
    throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isdl.php"
}

& $isccPath "/DAppVersion=$Version" $issPath
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}

$setupPath = Join-Path $installerOutput "Oghma-Archive-Setup-$Version.exe"
if (-not (Test-Path -LiteralPath $setupPath -PathType Leaf)) {
    throw "The expected installer was not created: $setupPath"
}
$hash = (Get-FileHash -LiteralPath $setupPath -Algorithm SHA256).Hash
$hashPath = "$setupPath.sha256"
[IO.File]::WriteAllText(
    $hashPath,
    "$hash *$([IO.Path]::GetFileName($setupPath))`r`n",
    [Text.UTF8Encoding]::new($false)
)
Write-Host "Installer: $setupPath"
Write-Host "SHA256:   $hash"
Write-Host "Checksum:  $hashPath"
