# bootstrap.ps1 — Vault Obsidian Architecture bootstrap (Windows)
# Usage: .\bootstrap.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== Vault Obsidian Architecture Bootstrap ===" -ForegroundColor Cyan

# 1. Check Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "ERROR: Python not found. Install Python 3.9+ first." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python: $($py.Source)" -ForegroundColor Green

# 2. Optional: editable install
$pyproject = Join-Path $RepoRoot "pyproject.toml"
if (Test-Path $pyproject) {
    Write-Host "pyproject.toml found — installing dev deps..." -ForegroundColor Yellow
    pip install -e "$RepoRoot[dev]" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] pip install done" -ForegroundColor Green
    } else {
        Write-Host "[WARN] pip install failed (non-critical)" -ForegroundColor Yellow
    }
}

# 3. Run vault_init
Write-Host "Initializing vault..." -ForegroundColor Yellow
python "$RepoRoot/scripts/vault_init.py"
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] vault_init complete" -ForegroundColor Green
} else {
    Write-Host "[WARN] vault_init had issues (may need vault sandbox)" -ForegroundColor Yellow
}

# 4. Run audit
Write-Host "Running health audit..." -ForegroundColor Yellow
python "$RepoRoot/scripts/vault_audit.py"
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] audit done" -ForegroundColor Green
}

Write-Host "=== Bootstrap complete ===" -ForegroundColor Cyan
