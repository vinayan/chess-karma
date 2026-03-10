; Chess Karma – Inno Setup installer script
; Requires Inno Setup 6+  (https://jrsoftware.org/isinfo.php)
;
; Prerequisites before running this script:
;   1. tools\create_blank_db.py must have been run  →  chess_karma_blank.db
;   2. PyInstaller must have been run               →  dist\Chess Karma\
;
; Build:
;   iscc installer.iss
;
; Output: installer\Chess_Karma_Setup.exe

#define AppName      "Chess Karma"
#define AppVersion   "0.1.0"
#define AppPublisher "Chess Karma"
#define AppExeName   "Chess Karma.exe"
#define DistDir      "dist\Chess Karma"

[Setup]
AppId={{B3A7F2E1-4C8D-4F5A-9E3B-2D1C6A0F8E4D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL=https://github.com/chess-karma/chess-karma
AppSupportURL=https://github.com/chess-karma/chess-karma/issues
AppUpdatesURL=https://github.com/chess-karma/chess-karma/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename=Chess_Karma_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
; Uncomment and set icon path when an .ico file is available:
; SetupIconFile=chess_karma.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main application bundle produced by PyInstaller
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";       Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
{ Database initialisation is handled entirely by the application on first launch.
  The blank schema DB (chess_karma_blank.db) is bundled inside the application
  directory and will be copied to %USERPROFILE%\chess_karma.db only when that
  file does not already exist. No action is needed from the installer. }
