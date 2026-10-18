param([int]$Workers = 1, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& '.venv/Scripts/python.exe' -m reporting.local start --workers $Workers --port $Port
if ($LASTEXITCODE -ne 0) { throw 'Startup failed. Run scripts/doctor.ps1.' }
