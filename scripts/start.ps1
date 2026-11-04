# Starts the server without Docker. Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

if (-not (Test-Path ".env")) {
    Write-Host "Copy .env.example to .env and replace its values, then run this again."
    exit 1
}
$model = "qwen2.5:7b"
$line = Select-String -Path ".env" -Pattern "^SLM_MODEL=(.+)$" | Select-Object -First 1
if ($line) { $model = $line.Matches[0].Groups[1].Value.Trim() }

$python = ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { python -m venv .venv }
& $python -m pip install --quiet --disable-pip-version-check -r backend\requirements.txt
if ($LASTEXITCODE) { exit $LASTEXITCODE }

if (-not (Test-Path "frontend\dist\index.html")) {
    Push-Location frontend
    npm ci
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    npm run build
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    Pop-Location
}

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "WARNING: Ollama was not found, so only rule-based fields will be filled. Install it from ollama.com."
} else {
    try {
        Invoke-RestMethod -TimeoutSec 3 http://localhost:11434/api/version | Out-Null
    } catch {
        Start-Process -WindowStyle Hidden $ollama.Source -ArgumentList "serve"
        Start-Sleep -Seconds 3
    }
    & $ollama.Source pull $model
    if ($LASTEXITCODE) { Write-Host "WARNING: could not download $model. Only rule-based fields will be filled." }
}

Set-Location backend
& "..\$python" manage.py migrate --noinput
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& "..\$python" manage.py reset_connections
if ($LASTEXITCODE) { exit $LASTEXITCODE }
Write-Host "Console: http://localhost:8000  (press Ctrl+C to stop)"
& "..\$python" -m daphne -b 0.0.0.0 -p 8000 config.asgi:application
