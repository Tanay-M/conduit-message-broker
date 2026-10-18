param([string]$PostgresBin = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not [Environment]::Is64BitOperatingSystem) { throw 'This bootstrap requires Windows x64.' }
New-Item -ItemType Directory -Path '.runtime','.local/downloads' -Force | Out-Null
$uvPath = Join-Path $projectRoot '.runtime/uv/uv.exe'
if (-not (Test-Path -LiteralPath $uvPath)) {
    if (-not (Test-Path -LiteralPath '.local/downloads/uv.zip')) {
        Invoke-WebRequest -Uri 'https://github.com/astral-sh/uv/releases/download/0.13.1/uv-x86_64-pc-windows-msvc.zip' -OutFile '.local/downloads/uv.zip.part'
        Move-Item -LiteralPath '.local/downloads/uv.zip.part' -Destination '.local/downloads/uv.zip'
    }
    Expand-Archive -LiteralPath '.local/downloads/uv.zip' -DestinationPath '.runtime/uv' -Force
}
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.runtime/python'
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    & $uvPath venv --python 3.12.12 --managed-python .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
}
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
& $uvPath pip sync --python $pythonPath requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $uvPath pip install --python $pythonPath --no-deps -e client
if ($LASTEXITCODE -ne 0) { throw 'Conduit SDK installation failed.' }
if ($PostgresBin) {
    $env:CONDUIT_PG_BIN = (Resolve-Path -LiteralPath $PostgresBin).Path
} elseif (-not (Test-Path -LiteralPath '.runtime/pgsql/bin/pg_ctl.exe')) {
    $archive = '.local/downloads/postgresql-16.15.zip'
    if (-not (Test-Path -LiteralPath $archive)) {
        Invoke-WebRequest -Uri 'https://get.enterprisedb.com/postgresql/postgresql-16.15-1-windows-x64-binaries.zip' -OutFile ($archive + '.part')
        Move-Item -LiteralPath ($archive + '.part') -Destination $archive
    }
    & $pythonPath -m reporting.bootstrap $archive
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL extraction failed.' }
}
if (-not (Test-Path -LiteralPath '.env.local')) { Copy-Item -LiteralPath '.env.example' -Destination '.env.local' }
& $pythonPath -m reporting.local setup
if ($LASTEXITCODE -ne 0) { throw 'Local database setup failed. Inspect .local/postgres.log.' }
Write-Host 'Setup complete. Run: powershell -ExecutionPolicy Bypass -File scripts/start.ps1'
