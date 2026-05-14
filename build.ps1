# build.ps1 — Script de build PANDORA v1.0.0 (Windows)
#
# Usage :
#   .\build.ps1              # PyInstaller uniquement
#   .\build.ps1 -Installer   # PyInstaller + Inno Setup
#
# Prérequis :
#   - Python 3.14 installé (pythoncore-3.14-64)
#   - pip install pyinstaller pillow  (dans le même Python)
#   - Inno Setup 6 (si -Installer) : https://jrsoftware.org/isinfo.php

param(
    [switch]$Installer   # Compile aussi l'installeur Inno Setup
)

$ErrorActionPreference = "Stop"
$PYTHON = "C:\Users\22eme\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$ISCC   = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

# ── Vérifications ─────────────────────────────────────────────────────────────
if (-not (Test-Path $PYTHON)) {
    Write-Error "Python introuvable : $PYTHON"
    exit 1
}

Write-Host "`n=== PANDORA Build ===" -ForegroundColor Cyan

# ── 1. Génération du .ico ─────────────────────────────────────────────────────
Write-Host "`n[1/4] Génération de l'icône .ico..." -ForegroundColor Yellow
& $PYTHON tools\make_ico.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Échec de la génération du .ico"
    exit 1
}

# ── 2. Nettoyage du build précédent ───────────────────────────────────────────
Write-Host "`n[2/4] Nettoyage des builds précédents..." -ForegroundColor Yellow
if (Test-Path "dist\PANDORA") { Remove-Item -Recurse -Force "dist\PANDORA" }
if (Test-Path "build\PANDORA") { Remove-Item -Recurse -Force "build\PANDORA" }

# ── 3. PyInstaller ────────────────────────────────────────────────────────────
Write-Host "`n[3/4] Build PyInstaller..." -ForegroundColor Yellow
& $PYTHON -m PyInstaller pandora.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Error "Échec PyInstaller"
    exit 1
}

# Vérification : data/config.json ne doit PAS être dans le build
$CONFIG_IN_BUILD = "dist\PANDORA\_internal\data\config.json"
if (Test-Path $CONFIG_IN_BUILD) {
    Write-Warning "ATTENTION : dist\PANDORA\_internal\data\config.json trouvé dans le build !"
    Write-Warning "Ce fichier contient des clés API et ne doit pas être distribué."
    Remove-Item -Force $CONFIG_IN_BUILD
    Write-Host "config.json supprimé du build." -ForegroundColor Green
}

# ── 4. Inno Setup (optionnel) ─────────────────────────────────────────────────
if ($Installer) {
    Write-Host "`n[4/4] Compilation de l'installeur Inno Setup..." -ForegroundColor Yellow
    if (-not (Test-Path $ISCC)) {
        Write-Warning "Inno Setup introuvable : $ISCC"
        Write-Warning "Installez Inno Setup 6 depuis https://jrsoftware.org/isinfo.php"
    } else {
        & $ISCC pandora_setup.iss
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Échec Inno Setup"
            exit 1
        }
        Write-Host "Installeur créé : dist\PANDORA_Setup_1.0.0.exe" -ForegroundColor Green
    }
} else {
    Write-Host "`n[4/4] Inno Setup ignoré (utilisez -Installer pour créer l'installeur)." -ForegroundColor DarkGray
}

# ── Résultat ──────────────────────────────────────────────────────────────────
Write-Host "`n=== Build terminé ===" -ForegroundColor Green
Write-Host "Distribution  : dist\PANDORA\" -ForegroundColor Green
if ($Installer -and (Test-Path "dist\PANDORA_Setup_1.0.0.exe")) {
    Write-Host "Installeur    : dist\PANDORA_Setup_1.0.0.exe" -ForegroundColor Green
}
Write-Host ""
