param([int]$FrontendPort = 8502)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Create .venv and install requirements-dev.txt first. See README.md.'
}

# .env keeps its Docker address; local processes use the host PostgreSQL.
$env:SQL_AGENT_DB_HOST = '127.0.0.1'
$env:PGCONNECT_TIMEOUT = '5'
$env:API_URL = 'http://127.0.0.1:8123'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$logs = Join-Path $PSScriptRoot '.local-logs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null

function Test-Endpoint([string]$Url) {
    try { return (Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing).StatusCode -eq 200 }
    catch { return $false }
}

if (-not (Test-Endpoint "$env:API_URL/ok")) {
    $api = Start-Process -FilePath $python -ArgumentList @('-m', 'langgraph_cli', 'dev', '--host', '127.0.0.1', '--port', '8123', '--no-browser', '--no-reload', '--allow-blocking') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$logs\api.out.log" -RedirectStandardError "$logs\api.err.log" -PassThru
    $ready = $false
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        if (Test-Endpoint "$env:API_URL/ok") { $ready = $true; break }
        if ($api.HasExited) { break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "Backend failed to start. Read $logs\api.err.log" }
}

$frontendUrl = "http://127.0.0.1:$FrontendPort"
if (-not (Test-Endpoint "$frontendUrl/_stcore/health")) {
    $frontend = Start-Process -FilePath $python -ArgumentList @('-m', 'streamlit', 'run', 'frontend/app.py', '--server.address=127.0.0.1', "--server.port=$FrontendPort", '--server.headless=true', '--browser.gatherUsageStats=false') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$logs\frontend.out.log" -RedirectStandardError "$logs\frontend.err.log" -PassThru
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (Test-Endpoint "$frontendUrl/_stcore/health") { $ready = $true; break }
        if ($frontend.HasExited) { break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "Frontend failed to start. Read $logs\frontend.err.log" }
}
Write-Output "Frontend: $frontendUrl"
Write-Output "Logs: $logs"
