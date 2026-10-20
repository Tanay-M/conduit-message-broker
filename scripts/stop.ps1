$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& '.venv/Scripts/python.exe' -m reporting.local stop
if ($LASTEXITCODE -ne 0) { throw 'Shutdown failed. Inspect the messages and .local logs.' }
