$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
New-Item -ItemType Directory -Path 'artifacts' -Force | Out-Null
& '.venv/Scripts/python.exe' -m reporting.local doctor
if ($LASTEXITCODE -ne 0) { throw 'Database diagnosis failed.' }
& '.venv/Scripts/python.exe' -m reporting.evidence
if ($LASTEXITCODE -ne 0) { throw 'SQL evidence execution failed.' }
$testOutput = & '.venv/Scripts/python.exe' -m pytest tests -v --tb=short
$testExit = $LASTEXITCODE
$testOutput | Set-Content -LiteralPath 'artifacts/test-results.txt' -Encoding UTF8
$testOutput | Write-Output
if ($testExit -ne 0) { throw 'Tests failed. Inspect artifacts/test-results.txt.' }
