; pandora_setup.iss — Inno Setup script pour PANDORA v1.0.0
;
; Prérequis :
;   - Inno Setup 6.x installé (https://jrsoftware.org/isinfo.php)
;   - Le build PyInstaller doit être fait avant : .\build.ps1
;   - dist\PANDORA\ doit exister
;
; Pour compiler :
;   iscc pandora_setup.iss
; Produit : dist\PANDORA_Setup_1.0.0.exe

#define MyAppName      "PANDORA"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "22eme Arkane"
#define MyAppURL       "https://github.com/22eme-arkane/pandora"
#define MyAppExeName   "PANDORA.exe"
#define MyBuildDir     "dist\PANDORA"

[Setup]
; Identifiant unique — NE PAS CHANGER entre versions (permet la mise à jour en place)
AppId={{A8F3C21D-7B4E-4F9A-B2C6-D5E8F1A3B7C9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases

; Emplacement par défaut : C:\Program Files\PANDORA\
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=no
DisableProgramGroupPage=yes

; L'application est 64 bits uniquement
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

; Icône de l'installeur
SetupIconFile=assets\pandora_badge.ico

; Exige les droits administrateur (pour écrire dans Program Files)
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Fichier de sortie
OutputDir=dist
OutputBaseFilename=PANDORA_Setup_{#MyAppVersion}

; EULA obligatoire avant installation
LicenseFile=EULA.txt

; Page de bienvenue
WizardStyle=modern

; Désinstalleur
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
french.WelcomeLabel2=Ce programme va installer {#MyAppName} {#MyAppVersion} sur votre ordinateur.%n%nVeuillez fermer toutes les autres applications avant de continuer.
english.WelcomeLabel2=This will install {#MyAppName} {#MyAppVersion} on your computer.%n%nPlease close all other applications before continuing.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Tous les fichiers du build PyInstaller
Source: "{#MyBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Raccourci menu Démarrer
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
; Raccourci bureau (optionnel)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Lancer PANDORA à la fin de l'installation (optionnel)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Nettoyage propre — supprimer les données utilisateur seulement si vide
; (les données projet sont dans les dossiers choisis par l'utilisateur — jamais supprimées)
; La config dans %LOCALAPPDATA%\PANDORA\ est intentionnellement conservée

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
