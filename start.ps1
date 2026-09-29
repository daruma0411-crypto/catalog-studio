param([string]$ImportFile = '', [int]$Port = 8877)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { $runtime = (Get-Command python).Source }
$serverArgs = @((Join-Path $PSScriptRoot 'server.py'), '--data', (Join-Path $PSScriptRoot 'data-live'), '--port', $Port)
if ($ImportFile) { $serverArgs += @('--import-file', $ImportFile) }
Write-Host "Catalog Studio: http://127.0.0.1:$Port (stop: Ctrl+C)"
& $runtime @serverArgs
