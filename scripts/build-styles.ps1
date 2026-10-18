$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
# Optional developer step. The compiled stylesheet is committed for offline use.
& npx --yes tailwindcss@3.4.17 -c server/styles/tailwind.config.cjs -i server/styles/tailwind.css -o server/app/static/vendor/tailwind.min.css --minify
if ($LASTEXITCODE -ne 0) { throw 'Stylesheet compilation failed.' }
