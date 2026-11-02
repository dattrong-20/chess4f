param([switch]$Build)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
Push-Location $projectRoot
function Invoke-CheckedDocker {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed ($LASTEXITCODE). Published release is unchanged." }
}
function Wait-Http {
    param([string]$Url, [int]$Seconds = 180)
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -UseBasicParsing
            if ($response.StatusCode -eq 200 -and (-not $Url.EndsWith("/v1/info") -or -not ($response.Content | ConvertFrom-Json).starting)) { return }
        } catch { }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $deadline)
    throw "Service did not become ready: $Url"
}
try {
    & $taskPython -m chess4f.lakehouse setup
    if ($LASTEXITCODE -ne 0) { throw 'Setup failed' }
    $composeArgs = @('compose', '--env-file', '.env.lakehouse', '-f', 'compose.lakehouse.yaml')
    if ($Build) { Invoke-CheckedDocker ($composeArgs + @('build', 'object-store', 'metastore', 'spark')) }
    Invoke-CheckedDocker ($composeArgs + @('stop', 'trino'))
    Invoke-CheckedDocker ($composeArgs + @('up', '-d', '--no-build', 'object-store', 'metastore'))
    Wait-Http 'http://127.0.0.1:19000/minio/health/live'
    $snapshotText = & $taskPython -m chess4f.lakehouse snapshot
    if ($LASTEXITCODE -ne 0) { throw 'Snapshot failed' }
    $snapshot = ($snapshotText -join "`n") | ConvertFrom-Json
    $release = $snapshot.release_id
    Write-Host "Release: $release"
    & $taskPython -m chess4f.lakehouse upload --release $release
    if ($LASTEXITCODE -ne 0) { throw 'Upload failed' }
    Invoke-CheckedDocker ($composeArgs + @('run', '--rm', '--no-deps', '-e', "CHESS4F_RELEASE=$release", 'spark'))
    Invoke-CheckedDocker ($composeArgs + @('--profile', 'query', 'up', '-d', '--no-build', 'trino'))
    Wait-Http 'http://127.0.0.1:18090/v1/info' 600
    $catalogDeadline = (Get-Date).AddMinutes(10)
    do {
        & docker @composeArgs exec -T metastore bash -c 'timeout 2 bash -c "echo > /dev/tcp/127.0.0.1/9083"' 2>$null
        if ($LASTEXITCODE -eq 0) { break }
        if ((Get-Date) -gt $catalogDeadline) { throw 'Hive Metastore did not become ready. Inspect its logs; serving pointer is unchanged.' }
        Start-Sleep -Seconds 3
    } while ($true)
    & $taskPython -m chess4f.lakehouse publish --release $release
    if ($LASTEXITCODE -ne 0) { throw 'Validation/publication failed. Previous serving pointer is unchanged.' }
    Write-Host 'Published. Open dashboard and select Query engine: trino.'
} finally {
    Pop-Location
}
