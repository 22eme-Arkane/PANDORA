# tools/sign_release.ps1 — Signature code signing de l'installeur PANDORA
#
# Prérequis :
#   - Certificat EV Code Signing installé dans le Windows Certificate Store
#     (Sectigo, Certum, DigiCert, etc.)
#   - signtool.exe disponible (SDK Windows 10/11)
#
# Usage :
#   .\tools\sign_release.ps1 -ExePath "dist\PANDORA_Setup_1.0.0.exe"
#   .\tools\sign_release.ps1 -ExePath "dist\PANDORA_Setup_1.0.0.exe" -ThumbPrint "VOTRE_THUMBPRINT"
#
# Pour trouver le thumbprint du certificat :
#   Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*ARKANE*" }

param(
    [string]$ExePath   = "dist\PANDORA_Setup_1.0.0.exe",
    [string]$ThumbPrint = ""   # Si vide, le premier certificat Code Signing est utilisé
)

$ErrorActionPreference = "Stop"

# ── Localiser signtool.exe ────────────────────────────────────────────────────
$SIGNTOOL = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "x64" } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1 -ExpandProperty FullName

if (-not $SIGNTOOL) {
    Write-Error "signtool.exe introuvable. Installez le Windows SDK."
    exit 1
}

# ── Vérifier le fichier à signer ─────────────────────────────────────────────
if (-not (Test-Path $ExePath)) {
    Write-Error "Fichier introuvable : $ExePath — lancez d'abord .\build.ps1 -Installer"
    exit 1
}

Write-Host "`n=== Signature de $ExePath ===" -ForegroundColor Cyan

# ── Paramètres signtool ───────────────────────────────────────────────────────
$SIGN_ARGS = @(
    "sign",
    "/tr", "http://timestamp.sectigo.com",   # Timestamp TSA (Sectigo) — change si autre CA
    "/td", "sha256",
    "/fd", "sha256",
    "/d",  "PANDORA — Plugin de pré-production cinéma"
)

if ($ThumbPrint -ne "") {
    $SIGN_ARGS += "/sha1"
    $SIGN_ARGS += $ThumbPrint
} else {
    # Sélection automatique : premier certificat Code Signing du store
    $SIGN_ARGS += "/a"
}

$SIGN_ARGS += $ExePath

# ── Signer ────────────────────────────────────────────────────────────────────
& $SIGNTOOL @SIGN_ARGS
if ($LASTEXITCODE -ne 0) {
    Write-Error "Échec de la signature"
    exit 1
}

Write-Host "`nSignature OK : $ExePath" -ForegroundColor Green
Write-Host ""
Write-Host "Vérification :"
& $SIGNTOOL verify /pa /v $ExePath
