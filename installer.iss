; Inno Setup Script for ZLZ-translator (Gemini-version)

#define MyAppName "ZLZ-translator (Gemini-version)"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "ZLZ Studio"
#define MyAppURL "https://github.com/superbabybob/ZLZ-Translator-Gemini"
#define MyAppExeName "ZLZ-translator.exe"

[Setup]
AppId={{9B7E34B5-6031-4191-B738-92E8728E4334}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\ZLZ-Translator
DisableProgramGroupPage=yes
OutputBaseFilename=ZLZ-Translator-Setup
OutputDir=dist
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Start automatically with Windows (Startup)"; GroupDescription: "Startup Options:"

[Files]
; The main PyInstaller distribution
Source: "dist\ZLZ-translator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Default configuration and user-editable files (do not overwrite existing on update)
Source: "config.toml"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "glossary.md"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: ".env.example"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
