$ErrorActionPreference = "Continue"

Write-Host "=== DIAGNOSTIC PROJET CHURN ===" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "1. Version de Python:" -ForegroundColor Yellow
python --version 2>&1
Write-Host ""

# Check virtual environment
Write-Host "2. Environnement virtuel:" -ForegroundColor Yellow
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "   [OK] Virtual environment exists" -ForegroundColor Green
} else {
    Write-Host "   [ERROR] Virtual environment not found!" -ForegroundColor Red
}
Write-Host ""

# Check PostgreSQL
Write-Host "3. PostgreSQL:" -ForegroundColor Yellow
$dbStatus = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
if ($dbStatus) {
    Write-Host "   Service: $($dbStatus.Name)" -ForegroundColor White
    Write-Host "   Status: $($dbStatus.Status)" -ForegroundColor $(if ($dbStatus.Status -eq "Running") { "Green" } else { "Red" })
} else {
    Write-Host "   [ERROR] PostgreSQL service not found!" -ForegroundColor Red
}
Write-Host ""

# Check ports
Write-Host "4. Ports:" -ForegroundColor Yellow
$port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$port8080 = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue

if ($port8000) {
    Write-Host "   Port 8000 (FastAPI): IN USE" -ForegroundColor Yellow
} else {
    Write-Host "   Port 8000 (FastAPI): AVAILABLE" -ForegroundColor Green
}

if ($port8080) {
    Write-Host "   Port 8080 (Django):  IN USE" -ForegroundColor Yellow
} else {
    Write-Host "   Port 8080 (Django):  AVAILABLE" -ForegroundColor Green
}
Write-Host ""

# Check database connection
Write-Host "5. Database Connection Test:" -ForegroundColor Yellow
. .\.venv\Scripts\Activate.ps1
python -c "
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connections
try:
    connections['default'].ensure_connection()
    print('   [OK] Database connection successful')
except Exception as e:
    print(f'   [ERROR] Database connection failed: {e}')
" 2>&1
Write-Host ""

# Check required files
Write-Host "6. Fichiers importants:" -ForegroundColor Yellow
$files = @("manage.py", "config/settings.py", ".env", "requirements.txt")
foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "   [OK] $file" -ForegroundColor Green
    } else {
        Write-Host "   [MISSING] $file" -ForegroundColor Red
    }
}
Write-Host ""

Write-Host "=== DIAGNOSTIC COMPLETE ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Si vous avez des problemes, verifiez les points marques [ERROR] ou [MISSING]" -ForegroundColor Yellow
