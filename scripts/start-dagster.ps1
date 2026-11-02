$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$env:CHESS4F_PROJECT = $project
$env:CHESS4F_DATA = Join-Path $project 'data'
$env:DAGSTER_HOME = Join-Path $project 'data/dagster'
New-Item -ItemType Directory -Force $env:DAGSTER_HOME | Out-Null
Copy-Item (Join-Path $project 'infra/dagster/dagster.yaml') (Join-Path $env:DAGSTER_HOME 'dagster.yaml')
$pidFile = Join-Path $env:DAGSTER_HOME 'processes.json'
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile -Raw | ConvertFrom-Json
    if (Get-Process -Id $old.daemon -ErrorAction SilentlyContinue) { throw 'Tracked Dagster daemon is already running; use existing instance.' }
}
if (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 3000 is already occupied; no process has been stopped.' }
$web = Start-Process (Join-Path $project '.venv/Scripts/dagster-webserver.exe') -ArgumentList @('-m','chess4f.definitions','-h','127.0.0.1','-p','3000') -WorkingDirectory $project -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $env:DAGSTER_HOME 'web.out.log') -RedirectStandardError (Join-Path $env:DAGSTER_HOME 'web.err.log')
$daemon = Start-Process (Join-Path $project '.venv/Scripts/dagster-daemon.exe') -ArgumentList @('run','-m','chess4f.definitions') -WorkingDirectory $project -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $env:DAGSTER_HOME 'daemon.out.log') -RedirectStandardError (Join-Path $env:DAGSTER_HOME 'daemon.err.log')
@{web=$web.Id;daemon=$daemon.Id} | ConvertTo-Json | Set-Content $pidFile
Write-Host 'Dagster: http://127.0.0.1:3000/ (daily checks 07:00; Sunday capped refresh 08:00; Asia/Barnaul). Processes must remain running.'