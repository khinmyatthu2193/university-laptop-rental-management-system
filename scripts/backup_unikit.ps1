$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw 'The .venv environment is missing. Follow the production setup in README.md.'
}

if (-not $env:UNIKIT_BACKUP_DIR) {
    throw 'UNIKIT_BACKUP_DIR is not set. Point it to a separate drive or device.'
}

& $python manage.py backup_database --destination $env:UNIKIT_BACKUP_DIR --keep 30
