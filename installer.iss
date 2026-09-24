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

[Code]
var
  ApiKeyPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  ApiKeyPage := CreateInputQueryPage(
    wpSelectTasks,
    'Google Gemini API Key',
    'Configure your free translation API key (1,500 free requests/day)',
    'You can obtain a free Gemini API Key at https://aistudio.google.com/apikey'#13#10#13#10 +
    'Paste your GEMINI_API_KEY below (or leave blank to configure later in the app):'
  );
  ApiKeyPage.Add('GEMINI_API_KEY:', False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ApiKey: String;
  EnvPath: String;
  Lines: TArrayOfString;
  I: Integer;
  Found: Boolean;
begin
  if CurStep = ssPostInstall then
  begin
    ApiKey := Trim(ApiKeyPage.Values[0]);
    EnvPath := ExpandConstant('{app}\.env');
    
    if ApiKey <> '' then
    begin
      Found := False;
      if FileExists(EnvPath) then
      begin
        if LoadStringsFromFile(EnvPath, Lines) then
        begin
          for I := 0 to GetArrayLength(Lines) - 1 do
          begin
            if Pos('GEMINI_API_KEY=', Lines[I]) = 1 then
            begin
              Lines[I] := 'GEMINI_API_KEY=' + ApiKey;
              Found := True;
              Break;
            end;
          end;
        end;
      end;
      if Found then
        SaveStringsToFile(EnvPath, Lines, False)
      else
        SaveStringToFile(EnvPath, 'GEMINI_API_KEY=' + ApiKey + #13#10, False);
    end
    else
    begin
      if not FileExists(EnvPath) and FileExists(ExpandConstant('{app}\.env.example')) then
      begin
        CopyFile(ExpandConstant('{app}\.env.example'), EnvPath, False);
      end;
    end;
  end;
end;
