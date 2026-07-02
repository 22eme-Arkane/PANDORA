; pandora_setup.iss — Inno Setup script pour PANDORA v1.2.1
;
; Prérequis :
;   - Inno Setup 6.x installé (https://jrsoftware.org/isinfo.php)
;   - Le build PyInstaller doit être fait avant : .\build.ps1
;   - dist\PANDORA\ doit exister
;
; Pour compiler :
;   iscc pandora_setup.iss
; Produit : dist\PANDORA_Setup_1.2.1.exe

#define MyAppName      "PANDORA"
#define MyAppVersion   "1.3.0"
#define MyAppPublisher "22eme Arkane"
#define MyAppURL       "https://github.com/22eme-arkane/pandora"
#define MyAppExeName   "PANDORA.exe"
#define MyBuildDir     "dist\PANDORA"
#define MyGithubAPI    "https://api.github.com/repos/22eme-arkane/pandora/releases/latest"

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

; Images de l'assistant (générées par tools/make_wizard_images.py)
WizardImageFile=assets\wizard_large.bmp
WizardSmallImageFile=assets\wizard_small.bmp

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

; Sélection de langue au démarrage
ShowLanguageDialog=yes

[Languages]
Name: "english";    MessagesFile: "compiler:Default.isl"
Name: "french";     MessagesFile: "compiler:Languages\French.isl"
Name: "german";     MessagesFile: "compiler:Languages\German.isl"
Name: "spanish";    MessagesFile: "compiler:Languages\Spanish.isl"
Name: "italian";    MessagesFile: "compiler:Languages\Italian.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "dutch";      MessagesFile: "compiler:Languages\Dutch.isl"
Name: "russian";    MessagesFile: "compiler:Languages\Russian.isl"
Name: "polish";     MessagesFile: "compiler:Languages\Polish.isl"
Name: "turkish";    MessagesFile: "compiler:Languages\Turkish.isl"
Name: "japanese";   MessagesFile: "compiler:Languages\Japanese.isl"

[CustomMessages]
; ── English ──────────────────────────────────────────────────────────────────
english.WelcomeLabel2=This will install {#MyAppName} {#MyAppVersion} on your computer.%n%nPlease close all other applications before continuing.
english.UpdateCheckTitle=Update available
english.UpdateCheckMsg=A newer version of {#MyAppName} is available: %1%n%nYou are about to install version {#MyAppVersion} (older).%n%nDo you want to download the latest version instead?%n(Click No to continue installing this older version.)
english.UpdateCheckBtn=Download latest version
english.WatchPresentation=Watch the presentation video (YouTube)
english.WatchTutorial=Watch the complete tutorial (YouTube)
english.DaVinciGroup=DaVinci Resolve Studio integration (requires Studio edition)
english.DaVinciScriptsDesc=Install Pandora Send and Pandora Bridge scripts%n  Pandora Send — sends selected clips from DaVinci timeline to PANDORA AI Studio (Workspace > Scripts > pandora_send, or assign a keyboard shortcut)%n  Pandora Bridge — runs as a background service in DaVinci Resolve Studio; listens on port 9877 and automatically imports AI-generated videos into your Media Pool (Workspace > Scripts > seedance_bridge)

; ── French ───────────────────────────────────────────────────────────────────
french.WelcomeLabel2=Ce programme va installer {#MyAppName} {#MyAppVersion} sur votre ordinateur.%n%nVeuillez fermer toutes les autres applications avant de continuer.
french.UpdateCheckTitle=Mise à jour disponible
french.UpdateCheckMsg=Une nouvelle version de {#MyAppName} est disponible : %1%n%nVous êtes sur le point d'installer la version {#MyAppVersion} (ancienne).%n%nVoulez-vous télécharger la dernière version à la place ?%n(Cliquez Non pour continuer quand même avec cette ancienne version.)
french.UpdateCheckBtn=Télécharger la dernière version
french.WatchPresentation=Voir la présentation vidéo (YouTube)
french.WatchTutorial=Voir le tutoriel complet (YouTube)
french.DaVinciGroup=Intégration DaVinci Resolve Studio (requiert l'édition Studio)
french.DaVinciScriptsDesc=Installer les scripts Pandora Send et Pandora Bridge%n  Pandora Send — envoie les clips sélectionnés depuis la timeline DaVinci vers le Studio IA de PANDORA (Espace de travail > Scripts > pandora_send, ou assignez un raccourci clavier)%n  Pandora Bridge — tourne en arrière-plan dans DaVinci Resolve Studio ; ecoute sur le port 9877 et importe automatiquement les videos generees par l'IA dans votre Media Pool (Espace de travail > Scripts > seedance_bridge)

; ── German ───────────────────────────────────────────────────────────────────
german.WelcomeLabel2=Dieses Programm installiert {#MyAppName} {#MyAppVersion} auf Ihrem Computer.%n%nBitte schließen Sie alle anderen Anwendungen, bevor Sie fortfahren.
german.UpdateCheckTitle=Update verfügbar
german.UpdateCheckMsg=Eine neuere Version von {#MyAppName} ist verfügbar: %1%n%nSie sind dabei, Version {#MyAppVersion} (älter) zu installieren.%n%nMöchten Sie stattdessen die neueste Version herunterladen?%n(Klicken Sie Nein, um trotzdem diese ältere Version zu installieren.)
german.UpdateCheckBtn=Neueste Version herunterladen
german.WatchPresentation=Präsentationsvideo ansehen (YouTube)
german.WatchTutorial=Vollständiges Tutorial ansehen (YouTube)
german.DaVinciGroup=DaVinci Resolve Studio Integration (erfordert Studio-Edition)
german.DaVinciScriptsDesc=Pandora Send und Pandora Bridge Skripte installieren%n  Pandora Send — sendet ausgewählte Clips aus DaVinci zur PANDORA KI-Studio%n  Pandora Bridge — Hintergrunddienst in DaVinci; importiert KI-Videos automatisch in den Media Pool

; ── Spanish ──────────────────────────────────────────────────────────────────
spanish.WelcomeLabel2=Este programa instalará {#MyAppName} {#MyAppVersion} en su ordenador.%n%nPor favor, cierre todas las demás aplicaciones antes de continuar.
spanish.UpdateCheckTitle=Actualización disponible
spanish.UpdateCheckMsg=Hay una versión más reciente de {#MyAppName} disponible: %1%n%nEstá a punto de instalar la versión {#MyAppVersion} (antigua).%n%n¿Desea descargar la última versión en su lugar?%n(Haga clic en No para continuar instalando esta versión antigua.)
spanish.UpdateCheckBtn=Descargar la última versión
spanish.WatchPresentation=Ver el vídeo de presentación (YouTube)
spanish.WatchTutorial=Ver el tutorial completo (YouTube)
spanish.DaVinciGroup=Integracion DaVinci Resolve Studio (requiere edicion Studio)
spanish.DaVinciScriptsDesc=Instalar scripts Pandora Send y Pandora Bridge%n  Pandora Send — envia clips seleccionados de DaVinci al Estudio IA de PANDORA%n  Pandora Bridge — servicio en segundo plano; importa videos IA automaticamente al Media Pool

; ── Italian ──────────────────────────────────────────────────────────────────
italian.WelcomeLabel2=Questo programma installerà {#MyAppName} {#MyAppVersion} sul tuo computer.%n%nChiudi tutte le altre applicazioni prima di continuare.
italian.UpdateCheckTitle=Aggiornamento disponibile
italian.UpdateCheckMsg=È disponibile una nuova versione di {#MyAppName}: %1%n%nStai per installare la versione {#MyAppVersion} (precedente).%n%nVuoi scaricare invece l'ultima versione?%n(Clicca No per continuare comunque con questa versione precedente.)
italian.UpdateCheckBtn=Scarica l'ultima versione
italian.WatchPresentation=Guarda il video di presentazione (YouTube)
italian.WatchTutorial=Guarda il tutorial completo (YouTube)
italian.DaVinciGroup=Integrazione DaVinci Resolve Studio (richiede edizione Studio)
italian.DaVinciScriptsDesc=Installa script Pandora Send e Pandora Bridge%n  Pandora Send — invia clip selezionate da DaVinci allo Studio IA di PANDORA%n  Pandora Bridge — servizio in background; importa video IA automaticamente nel Media Pool

; ── Portuguese (Brazilian) ───────────────────────────────────────────────────
portuguese.WelcomeLabel2=Este programa instalará {#MyAppName} {#MyAppVersion} no seu computador.%n%nFeche todos os outros aplicativos antes de continuar.
portuguese.UpdateCheckTitle=Atualização disponível
portuguese.UpdateCheckMsg=Uma versão mais recente de {#MyAppName} está disponível: %1%n%nVocê está prestes a instalar a versão {#MyAppVersion} (mais antiga).%n%nDeseja baixar a versão mais recente?%n(Clique em Não para continuar instalando esta versão mais antiga.)
portuguese.UpdateCheckBtn=Baixar a versão mais recente
portuguese.WatchPresentation=Assistir ao vídeo de apresentação (YouTube)
portuguese.WatchTutorial=Assistir ao tutorial completo (YouTube)
portuguese.DaVinciGroup=Integracao DaVinci Resolve Studio (requer edicao Studio)
portuguese.DaVinciScriptsDesc=Instalar scripts Pandora Send e Pandora Bridge%n  Pandora Send — envia clips selecionados do DaVinci para o Studio IA do PANDORA%n  Pandora Bridge — servico em segundo plano; importa videos IA automaticamente para o Media Pool

; ── Dutch ─────────────────────────────────────────────────────────────────────
dutch.WelcomeLabel2=Dit programma installeert {#MyAppName} {#MyAppVersion} op uw computer.%n%nSluit alle andere toepassingen voordat u doorgaat.
dutch.UpdateCheckTitle=Update beschikbaar
dutch.UpdateCheckMsg=Er is een nieuwere versie van {#MyAppName} beschikbaar: %1%n%nU staat op het punt versie {#MyAppVersion} (ouder) te installeren.%n%nWilt u in plaats daarvan de nieuwste versie downloaden?%n(Klik op Nee om toch deze oudere versie te installeren.)
dutch.UpdateCheckBtn=Nieuwste versie downloaden
dutch.WatchPresentation=Bekijk de presentatievideo (YouTube)
dutch.WatchTutorial=Bekijk de volledige tutorial (YouTube)
dutch.DaVinciGroup=DaVinci Resolve Studio integratie (vereist Studio-editie)
dutch.DaVinciScriptsDesc=Pandora Send en Pandora Bridge scripts installeren%n  Pandora Send — stuurt geselecteerde clips van DaVinci naar PANDORA AI Studio%n  Pandora Bridge — achtergrondservice; importeert AI-videos automatisch in de Media Pool

; ── Russian ───────────────────────────────────────────────────────────────────
russian.WelcomeLabel2=Эта программа установит {#MyAppName} {#MyAppVersion} на ваш компьютер.%n%nПожалуйста, закройте все другие приложения перед продолжением.
russian.UpdateCheckTitle=Доступно обновление
russian.UpdateCheckMsg=Доступна более новая версия {#MyAppName}: %1%n%nВы собираетесь установить версию {#MyAppVersion} (устаревшую).%n%nХотите загрузить последнюю версию?%n(Нажмите Нет, чтобы продолжить установку этой старой версии.)
russian.UpdateCheckBtn=Загрузить последнюю версию
russian.WatchPresentation=Смотреть видео-презентацию (YouTube)
russian.WatchTutorial=Смотреть полное руководство (YouTube)
russian.DaVinciGroup=Интеграция DaVinci Resolve Studio (требует Studio-версии)
russian.DaVinciScriptsDesc=Установить скрипты Pandora Send и Pandora Bridge%n  Pandora Send — отправляет выбранные клипы из DaVinci в AI Studio PANDORA%n  Pandora Bridge — фоновый сервис; автоматически импортирует AI-видео в Media Pool

; ── Polish ────────────────────────────────────────────────────────────────────
polish.WelcomeLabel2=Ten program zainstaluje {#MyAppName} {#MyAppVersion} na twoim komputerze.%n%nZamknij wszystkie inne aplikacje przed kontynuowaniem.
polish.UpdateCheckTitle=Dostępna aktualizacja
polish.UpdateCheckMsg=Dostępna jest nowsza wersja {#MyAppName}: %1%n%nZamierzasz zainstalować wersję {#MyAppVersion} (starszą).%n%nCzy chcesz pobrać najnowszą wersję?%n(Kliknij Nie, aby kontynuować instalację tej starszej wersji.)
polish.UpdateCheckBtn=Pobierz najnowszą wersję
polish.WatchPresentation=Obejrzyj film prezentacyjny (YouTube)
polish.WatchTutorial=Obejrzyj pełny samouczek (YouTube)
polish.DaVinciGroup=Integracja DaVinci Resolve Studio (wymaga edycji Studio)
polish.DaVinciScriptsDesc=Zainstaluj skrypty Pandora Send i Pandora Bridge%n  Pandora Send — wysyla wybrane klipy z DaVinci do AI Studio PANDORA%n  Pandora Bridge — usluga w tle; automatycznie importuje wideo AI do Media Pool

; ── Turkish ───────────────────────────────────────────────────────────────────
turkish.WelcomeLabel2=Bu program bilgisayarınıza {#MyAppName} {#MyAppVersion} kuracak.%n%nDevam etmeden önce lütfen diğer tüm uygulamaları kapatın.
turkish.UpdateCheckTitle=Güncelleme mevcut
turkish.UpdateCheckMsg={#MyAppName} uygulamasının daha yeni bir sürümü mevcut: %1%n%n{#MyAppVersion} (eski) sürümünü yüklemek üzeresiniz.%n%nBunun yerine en son sürümü indirmek ister misiniz?%n(Bu eski sürümü yüklemeye devam etmek için Hayır'a tıklayın.)
turkish.UpdateCheckBtn=En son sürümü indir
turkish.WatchPresentation=Tanıtım videosunu izle (YouTube)
turkish.WatchTutorial=Tam eğitimi izle (YouTube)
turkish.DaVinciGroup=DaVinci Resolve Studio entegrasyonu (Studio surumu gerektirir)
turkish.DaVinciScriptsDesc=Pandora Send ve Pandora Bridge betiklerini yukle%n  Pandora Send — secili klipleri DaVinci'den PANDORA AI Studio'ya gonderir%n  Pandora Bridge — arka plan servisi; AI videolarini Media Pool'a otomatik olarak aktar

; ── Japanese ──────────────────────────────────────────────────────────────────
japanese.WelcomeLabel2=このプログラムはコンピューターに {#MyAppName} {#MyAppVersion} をインストールします。%n%n続行する前に他のすべてのアプリケーションを閉じてください。
japanese.UpdateCheckTitle=アップデートが利用可能
japanese.UpdateCheckMsg={#MyAppName} の新しいバージョンが利用可能です: %1%n%nバージョン {#MyAppVersion}（古いバージョン）をインストールしようとしています。%n%n代わりに最新バージョンをダウンロードしますか？%n（いいえをクリックすると、この古いバージョンのインストールを続行します。）
japanese.UpdateCheckBtn=最新バージョンをダウンロード
japanese.WatchPresentation=プレゼンテーション動画を見る (YouTube)
japanese.WatchTutorial=完全なチュートリアルを見る (YouTube)
japanese.DaVinciGroup=DaVinci Resolve Studio 統合（Studio版が必要）
japanese.DaVinciScriptsDesc=Pandora SendとPandora Bridgeスクリプトをインストール%n  Pandora Send — DaVinciからPANDORA AIスタジオへクリップを送信%n  Pandora Bridge — バックグラウンドサービス；AI動画をMedia Poolへ自動インポート

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
; Liens vidéo — page de fin d'installation
Filename: "https://youtu.be/ci9jA_Tye2E"; Description: "{cm:WatchPresentation}"; Flags: shellexec nowait postinstall skipifsilent unchecked
Filename: "https://www.youtube.com/watch?v=SC3pRI5bR1Q"; Description: "{cm:WatchTutorial}"; Flags: shellexec nowait postinstall skipifsilent unchecked

[UninstallDelete]
; Nettoyage propre — supprimer les données utilisateur seulement si vide
; (les données projet sont dans les dossiers choisis par l'utilisateurs — jamais supprimées)
; La config dans %LOCALAPPDATA%\PANDORA\ est intentionnellement conservée

[Code]

{ ── Utilitaire : extraction d'une valeur JSON simple (string) ─────────────── }
function ExtractJsonString(const Json, Key: String): String;
var
  I, J: Integer;
  SearchStr: String;
begin
  Result := '';
  SearchStr := '"' + Key + '"';
  I := Pos(SearchStr, Json);
  if I = 0 then Exit;
  I := I + Length(SearchStr);
  while (I <= Length(Json)) and ((Json[I] = ' ') or (Json[I] = ':') or
        (Json[I] = #9) or (Json[I] = #10) or (Json[I] = #13)) do
    I := I + 1;
  if (I > Length(Json)) or (Json[I] <> '"') then Exit;
  I := I + 1;
  J := I;
  while (J <= Length(Json)) and (Json[J] <> '"') do
    J := J + 1;
  Result := Copy(Json, I, J - I);
end;

{ ── Utilitaire : compare deux versions X.Y.Z (retourne 1 si A>B, -1 si A<B, 0 si égal) }
function CompareVersionStr(const A, B: String): Integer;
var
  VerA, VerB: String;
  PartsA, PartsB: TStringList;
  NumA, NumB, I: Integer;
begin
  Result := 0;
  VerA := A;
  VerB := B;
  if (Length(VerA) > 0) and (VerA[1] = 'v') then VerA := Copy(VerA, 2, MaxInt);
  if (Length(VerB) > 0) and (VerB[1] = 'v') then VerB := Copy(VerB, 2, MaxInt);
  PartsA := TStringList.Create;
  PartsB := TStringList.Create;
  try
    PartsA.Delimiter := '.';
    PartsA.DelimitedText := VerA;
    PartsB.Delimiter := '.';
    PartsB.DelimitedText := VerB;
    for I := 0 to 2 do
    begin
      if I < PartsA.Count then NumA := StrToIntDef(PartsA[I], 0) else NumA := 0;
      if I < PartsB.Count then NumB := StrToIntDef(PartsB[I], 0) else NumB := 0;
      if NumA > NumB then begin Result := 1; Exit; end;
      if NumA < NumB then begin Result := -1; Exit; end;
    end;
  finally
    PartsA.Free;
    PartsB.Free;
  end;
end;

{ ── Vérification de mise à jour via GitHub Releases API ─────────────────────
  Appelée depuis InitializeWizard (après sélection de langue).
  Si une version plus récente existe, propose d'ouvrir la page de téléchargement. }
function GetLatestGithubVersion(): String;
var
  Http: Variant;
  Json: String;
begin
  Result := '';
  try
    Http := CreateOleObject('WinHttp.WinHttpRequest.5.1');
    Http.Open('GET', '{#MyGithubAPI}', False);
    Http.SetRequestHeader('User-Agent', 'PANDORA-Installer/{#MyAppVersion}');
    Http.SetTimeouts(5000, 10000, 10000, 10000);
    Http.Send('');
    if Http.Status = 200 then
    begin
      Json := Http.ResponseText;
      Result := ExtractJsonString(Json, 'tag_name');
    end;
  except
    // Pas de réseau ou erreur — on continue silencieusement
  end;
end;

procedure CheckForUpdate();
var
  LatestVer, Msg: String;
  MsgRes, ErrCode: Integer;
begin
  LatestVer := GetLatestGithubVersion();
  if LatestVer = '' then Exit;

  if CompareVersionStr(LatestVer, '{#MyAppVersion}') > 0 then
  begin
    Msg := FmtMessage(CustomMessage('UpdateCheckMsg'), [LatestVer]);
    MsgRes := MsgBox(Msg, mbConfirmation, MB_YESNO);
    if MsgRes = IDYES then
    begin
      ShellExec('open', '{#MyAppURL}/releases/latest', '', '', SW_SHOW, ewNoWait, ErrCode);
      Abort(); // Ferme l'installeur — l'utilisateur va télécharger la nouvelle version
    end;
  end;
end;

{ ── Détection DaVinci Resolve ─────────────────────────────────────────────── }
function DaVinciInstalled(): Boolean;
begin
  Result := FileExists('C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe');
end;

{ ── Copie des scripts bridge après installation ──────────────────────────────
  seedance_bridge.py  → Espace de travail → Scripts → seedance_bridge
  pandora_send.py     → Espace de travail → Scripts → pandora_send (Ctrl+Shift+P) }
procedure InstallDaVinciScripts();
var
  ScriptsDir : String;
  AppDavinci : String;
begin
  ScriptsDir := 'C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility';
  AppDavinci := ExpandConstant('{app}\davinci');

  ForceDirectories(ScriptsDir);
  CopyFile(AppDavinci + '\bridge_server.py', ScriptsDir + '\seedance_bridge.py', False);
  CopyFile(AppDavinci + '\pandora_send.py',  ScriptsDir + '\pandora_send.py',  False);
end;

{ ── Appelé après la sélection de langue, avant le premier écran du wizard ── }
procedure InitializeWizard();
begin
  CheckForUpdate();
end;

{ ── Exécuté à la fin de l'installation principale ───────────────────────────}
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if DaVinciInstalled() then
      InstallDaVinciScripts();
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;
