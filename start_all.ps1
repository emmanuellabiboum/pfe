$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvActivate = Join-Path $projectRoot ".venv\Scripts\Activate.ps1"

if (-not (Test-Path $venvActivate)) {
    Write-Host "Environnement virtuel introuvable: $venvActivate" -ForegroundColor Red
    Write-Host "Creer d'abord l'environnement avec: py -3.13 -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# Check PostgreSQL
Write-Host "Verification de PostgreSQL..." -ForegroundColor Cyan
$dbStatus = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
if (-not $dbStatus -or $dbStatus.Status -ne "Running") {
    Write-Host "ATTENTION: PostgreSQL ne semble pas etre en execution!" -ForegroundColor Yellow
    Write-Host "Lancez PostgreSQL avant de continuer." -ForegroundColor Yellow
    $continue = Read-Host "Voulez-vous continuer quand meme? (o/n)"
    if ($continue -ne "o") { exit 0 }
} else {
    Write-Host "PostgreSQL est en execution." -ForegroundColor Green
}

# Check if ports are available
Write-Host "Verification des ports..." -ForegroundColor Cyan
$port8080 = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
if ($port8080) {
    Write-Host "ATTENTION: Le port 8080 est deja utilise!" -ForegroundColor Yellow
    $usePort = Read-Host "Voulez-vous utiliser le port 8081 a la place? (o/n)"
    if ($usePort -eq "o") {
        $djangoPort = 8081
    } else {
        $djangoPort = 8080
    }
} else {
    $djangoPort = 8080
    Write-Host "Port 8080 disponible." -ForegroundColor Green
}

$fastapiDir = Join-Path $projectRoot "pfe_final\churn_api"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

$fastapiCommand = @"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass;
Set-Location '$fastapiDir';
. '$venvActivate';
`$env:DJANGO_SETTINGS_MODULE='config.settings';
try {
    & '$venvPython' -m uvicorn app.main:app --reload --port 8001
} catch {
    Write-Host "`nFastAPI Error: `$_" -ForegroundColor Red;
    Write-Host "`nPress any key to close...";
    Pause
}
"@

$djangoCommand = @"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass;
Set-Location '$projectRoot';
. '$venvActivate';
`$env:FASTAPI_BASE_URL='http://127.0.0.1:8001';
`$env:DJANGO_SETTINGS_MODULE='config.settings';
try {
    & '$venvPython' manage.py runserver $djangoPort
} catch {
    Write-Host "`nDjango Error: `$_" -ForegroundColor Red;
    Write-Host "`nPress any key to close...";
    Pause
}
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $fastapiCommand
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-Command", $djangoCommand

Write-Host "`nServices demarres dans deux fenetres PowerShell:" -ForegroundColor Green
Write-Host "- FastAPI: http://127.0.0.1:8001/docs" -ForegroundColor White
Write-Host "- Django : http://127.0.0.1:$djangoPort/" -ForegroundColor White
