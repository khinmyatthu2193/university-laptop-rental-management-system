$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$waitress = Join-Path $projectRoot '.venv\Scripts\waitress-serve.exe'

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $waitress)) {
    throw 'The .venv environment is missing. Follow the production setup in README.md.'
}

if (-not $env:DJANGO_SECRET_KEY) {
    throw 'DJANGO_SECRET_KEY is not set. Configure it before starting UniKit.'
}

$env:DJANGO_SETTINGS_MODULE = 'unikit_university_laptop_rental_management_system.production'
& $python manage.py migrate --noinput
& $python manage.py collectstatic --noinput
& $waitress --listen=127.0.0.1:8080 unikit_university_laptop_rental_management_system.wsgi:application
