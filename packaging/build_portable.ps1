param(
    [string]$EnvironmentPath = ".conda-build-env"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$environmentRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $EnvironmentPath))
$python = Join-Path $environmentRoot "python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Build environment Python was not found: $python"
}

$originalPath = $env:Path
$originalCondaPrefix = $env:CONDA_PREFIX
$environmentPaths = @(
    $environmentRoot,
    (Join-Path $environmentRoot "Library\mingw-w64\bin"),
    (Join-Path $environmentRoot "Library\usr\bin"),
    (Join-Path $environmentRoot "Library\bin"),
    (Join-Path $environmentRoot "Scripts"),
    (Join-Path $environmentRoot "bin")
)
$env:Path = (($environmentPaths + $originalPath) -join [System.IO.Path]::PathSeparator)
$env:CONDA_PREFIX = $environmentRoot

Push-Location $projectRoot
try {
    & $python -m PyInstaller --noconfirm --clean "packaging\thz_calibration.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }

    $portableDir = Join-Path $projectRoot "dist\THz_Calibration_Portable"
    Copy-Item -LiteralPath (Join-Path $projectRoot "config.ini") -Destination $portableDir -Force
    Copy-Item -LiteralPath (Join-Path $projectRoot "packaging\README_zh-CN.txt") -Destination $portableDir -Force
    # Keep the script ASCII-compatible for Windows PowerShell 5.1, which may
    # otherwise decode a UTF-8 script without BOM using the active code page.
    $manualSuffix = -join @(0x4F7F, 0x7528, 0x8BF4, 0x660E | ForEach-Object { [char]$_ })
    $manualFileName = "THz_Calibration_Portable_${manualSuffix}.md"
    Copy-Item -LiteralPath (Join-Path $projectRoot "packaging\$manualFileName") -Destination $portableDir -Force
    New-Item -ItemType Directory -Path (Join-Path $portableDir "output") -Force | Out-Null

    Write-Host "Portable bundle created: $portableDir"
    Get-ChildItem -LiteralPath $portableDir | Select-Object Name, Length
}
finally {
    Pop-Location
    $env:Path = $originalPath
    $env:CONDA_PREFIX = $originalCondaPrefix
}
