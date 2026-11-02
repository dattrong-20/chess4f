$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
function Invoke-DockerChecked([string[]]$Arguments) {
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed: $LASTEXITCODE" }
}
try {
    if (-not (Test-Path 'data/published/latest.json')) { throw 'No published release. Run scripts/run-lakehouse.ps1 first.' }
    Invoke-DockerChecked @('compose','--env-file','.env.lakehouse','-f','compose.lakehouse.yaml','--profile','query','up','-d','--no-build','object-store','metastore','trino')
    Invoke-DockerChecked @('compose','up','-d','--no-build','api')
    $deadline = (Get-Date).AddMinutes(10)
    do {
        $ready = $false
        try {
            $api = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 5
            $trino = Invoke-RestMethod 'http://127.0.0.1:18090/v1/info' -TimeoutSec 5
            if ($api.status -eq 'ok' -and -not $trino.starting) {
                $overview = Invoke-RestMethod 'http://127.0.0.1:8000/overview?source=lichess&engine=trino' -TimeoutSec 60
                $ready = [bool]$overview.release_id
            }
        } catch { }
        if ($ready) { break }
        if ((Get-Date) -gt $deadline) { throw 'Readiness timed out. Inspect docker compose logs. Data has not been changed.' }
        Start-Sleep -Seconds 5
    } while ($true)
    Invoke-DockerChecked @('compose','up','-d','--no-build','--no-deps','dashboard')
    Write-Host 'Dashboard: http://127.0.0.1:8501/ — select Query engine: trino'
    Write-Host "Published release: $($overview.release_id)"
} finally { Pop-Location }