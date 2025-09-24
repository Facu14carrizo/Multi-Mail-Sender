Param(
    [string]$AppName = "EnviadorMiGusto"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "==> Iniciando build ($AppName)" -ForegroundColor Cyan
Set-Location -Path $PSScriptRoot

# 1) Crear venv si no existe
if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    Write-Host "==> Creando entorno virtual .venv" -ForegroundColor Cyan
    py -3 -m venv .venv
}

# 2) Activar venv
& ".\.venv\Scripts\Activate.ps1"

# 3) Instalar dependencias
Write-Host "==> Instalando dependencias" -ForegroundColor Cyan
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# 4) Preparar archivos de datos (crear si faltan)
@("config.json","destinatarios.json","respondidos.txt") | ForEach-Object {
    if (-not (Test-Path $_)) {
        Write-Host "Creando placeholder: $_" -ForegroundColor DarkGray
        New-Item -ItemType File -Path $_ | Out-Null
    }
}

# 5) Limpiar dist/build previos
Write-Host "==> Limpiando artefactos previos" -ForegroundColor Cyan
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist)  { Remove-Item -Recurse -Force dist }
if (Test-Path "$AppName.spec") { Remove-Item -Force "$AppName.spec" }

# 6) Ejecutar PyInstaller
Write-Host "==> Ejecutando PyInstaller" -ForegroundColor Cyan
pyinstaller --noconfirm `
  --name $AppName `
  --onefile --windowed `
  --add-data "config.json;." `
  --add-data "destinatarios.json;." `
  --add-data "respondidos.txt;." `
  main.py

# 7) Copiar archivos de datos al lado del .exe
Write-Host "==> Copiando archivos de datos a dist" -ForegroundColor Cyan
Copy-Item -Force config.json dist\ 2>$null
Copy-Item -Force destinatarios.json dist\ 2>$null
Copy-Item -Force respondidos.txt dist\ 2>$null

$exePath = Join-Path (Join-Path $PWD "dist") ("{0}.exe" -f $AppName)
Write-Host "==> Build terminado: $exePath" -ForegroundColor Green

# 8) Abrir carpeta de salida
Start-Process explorer.exe (Join-Path $PWD "dist")


