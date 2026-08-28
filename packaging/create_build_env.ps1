$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$environmentRoot = Join-Path $projectRoot ".conda-build-env"

Push-Location $projectRoot
try {
    conda create -p $environmentRoot python=3.11.15 pip=26.1.2 -y
    if ($LASTEXITCODE -ne 0) {
        throw "Conda environment creation failed with exit code $LASTEXITCODE"
    }

    & (Join-Path $environmentRoot "python.exe") -m pip install -r "packaging\requirements-build.lock.txt"
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
