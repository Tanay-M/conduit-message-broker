param(
    [ValidateRange(1,65535)][int]$Port = 8001,
    [ValidateRange(1,8)][int]$Workers = 2,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

try {
    Write-Host 'Conduit - Retail Operations and Explainable Reporting' -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe') -or
        -not (Test-Path -LiteralPath '.local/native.json') -or
        -not (Test-Path -LiteralPath '.env.local')) {
        Write-Host 'First-time setup: downloading local dependencies. Internet is required.'
        & (Join-Path $PSScriptRoot 'setup.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'First-time setup failed.' }
    }

    $launchArgs = @('-m', 'reporting.launcher', '--port', "$Port", '--workers', "$Workers")
    if ($NoBrowser) { $launchArgs += '--no-browser' }
    & '.venv/Scripts/python.exe' @launchArgs
    if ($LASTEXITCODE -ne 0) { throw 'Demo startup failed. See the message and .local logs.' }
} catch {
    Write-Host "Startup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
