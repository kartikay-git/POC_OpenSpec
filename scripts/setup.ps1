$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
foreach ($command in @('python', 'node', 'npm.cmd', 'git')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "Install prerequisite: $command" }
}
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $env:UV_CACHE_DIR = Join-Path $projectRoot '.uv-cache'
    uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
} else {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed. Install uv and retry.' }
    & .\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
}
npm.cmd ci --cache .npm-cache --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'OpenSpec installation failed.' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
$env:OPENSPEC_TELEMETRY = '0'
& .\node_modules\.bin\openspec.cmd --version
& .\.venv\Scripts\python.exe application\manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
& .\.venv\Scripts\python.exe application\manage.py seed_demo
if ($LASTEXITCODE -ne 0) { throw 'Demo seed failed.' }
Write-Host 'Setup complete. Run .\scripts\test.ps1, then .\scripts\start.ps1.'
