param([string]$Run = '', [switch]$Latest, [switch]$Reference, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (([int][bool]$Run + [int][bool]$Latest + [int][bool]$Reference) -gt 1) { throw 'Choose one of -Run, -Latest, or -Reference.' }
if ($Latest -or $Reference) {
    $candidates = Get-ChildItem -LiteralPath (Join-Path $projectRoot 'runs') -Directory | Sort-Object Name -Descending
    foreach ($candidate in $candidates) {
        $statePath = Join-Path $candidate.FullName 'state.json'
        if (Test-Path -LiteralPath $statePath) {
            $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
            $matches = ($Latest -and $state.mode -eq 'live') -or ($Reference -and $state.mode -eq 'fixture' -and $state.change -eq 'reference-task-deletion')
            if ($matches -and $state.phase -in @('VERIFIED', 'ARCHIVED')) { $Run = $candidate.FullName; break }
        }
    }
    if (-not $Run) { throw 'No matching verified run exists. For a reference run use: python -m agent.cli demo --mode fixture --change reference-task-deletion' }
}
$appRoot = Join-Path $projectRoot 'application'
if ($Run) { $appRoot = Join-Path (Resolve-Path -LiteralPath $Run).Path 'workspace\application' }
$manage = Join-Path $appRoot 'manage.py'
if (-not (Test-Path -LiteralPath $manage)) { throw "Cannot find application: $manage" }
& .\.venv\Scripts\python.exe $manage migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
& .\.venv\Scripts\python.exe $manage seed_demo
if ($LASTEXITCODE -ne 0) { throw 'Seed failed.' }
Write-Host "Application: $appRoot"
Write-Host "Open http://127.0.0.1:$Port/ (alice or bob / DemoPass123!)"
& .\.venv\Scripts\python.exe $manage runserver "127.0.0.1:$Port" --noreload
