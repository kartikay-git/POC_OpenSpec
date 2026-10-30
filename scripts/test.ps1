$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$env:OPENSPEC_TELEMETRY = '0'
& .\.venv\Scripts\python.exe application\manage.py check
if ($LASTEXITCODE -ne 0) { throw 'Django checks failed.' }
& .\.venv\Scripts\python.exe application\manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Uncommitted model migration detected.' }
& .\.venv\Scripts\python.exe application\manage.py test todos --verbosity 2
if ($LASTEXITCODE -ne 0) { throw 'Baseline tests failed.' }
& .\node_modules\.bin\openspec.cmd validate --specs --strict --json --no-interactive
if ($LASTEXITCODE -ne 0) { throw 'Baseline specifications failed validation.' }
& .\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp
if ($LASTEXITCODE -ne 0) { throw 'Agent/OpenSpec integration tests failed.' }
