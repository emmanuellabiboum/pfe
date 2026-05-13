$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvActivate = Join-Path $projectRoot ".venv\Scripts\Activate.ps1"

if (-not (Test-Path $venvActivate)) {
    Write-Host "Environnement virtuel introuvable: $venvActivate" -ForegroundColor Red
    Write-Host "Creer d'abord l'environnement avec: py -3.13 -m venv .venv" -ForegroundColor Yellow
    exit 1
}

$fastapiDir = Join-Path $projectRoot "pfe_final\churn_api"
$fastapiCommand = @"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass;
Set-Location '$fastapiDir';
. '$venvActivate';
python -m uvicorn app.main:app --reload --port 8000
"@

$djangoCommand = @"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass;
Set-Location '$projectRoot';
. '$venvActivate';
python manage.py runserver 8080
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $fastapiCommand
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList "-NoExit", "-Command", $djangoCommand

Write-Host "Services demarres dans deux fenetres PowerShell:" -ForegroundColor Green
Write-Host "- FastAPI: http://127.0.0.1:8000/docs"
Write-Host "- Django : http://127.0.0.1:8080/"
