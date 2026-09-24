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
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Start automatically with Windows (Startup)"; GroupDescription: "Startup Options:"

[InstallDelete]
; Clean up any leftover internal dependencies from previous versions before installing
Type: filesandordirs; Name: "{app}\_internal"

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
  ApiKeyCustomPage: TWizardPage;
  ApiKeyEdit: TNewEdit;
  DiscordCustomPage: TWizardPage;
  DiscordEdit: TNewEdit;
  DiscordAutoStartCheck: TNewCheckBox;

function GetExistingEnvValue(const Key: String): String;
var
  EnvPath: String;
  Lines: TArrayOfString;
  I: Integer;
  Line: String;
  Prefix: String;
begin
  Result := '';
  Prefix := Key + '=';
  EnvPath := ExpandConstant('{localappdata}\Programs\ZLZ-Translator\.env');
  
  if FileExists(EnvPath) and LoadStringsFromFile(EnvPath, Lines) then
  begin
    for I := 0 to GetArrayLength(Lines) - 1 do
    begin
      Line := Trim(Lines[I]);
      if Pos(Prefix, Line) = 1 then
      begin
        Result := Trim(Copy(Line, Length(Prefix) + 1, Length(Line)));
        Break;
      end;
    end;
  end;
end;

procedure GeminiLinkClick(Sender: TObject);
var
  ErrorCode: Integer;
begin
  ShellExec('open', 'https://aistudio.google.com/apikey', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
end;

procedure DiscordLinkClick(Sender: TObject);
var
  ErrorCode: Integer;
begin
  ShellExec('open', 'https://discord.com/developers/applications', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
end;

procedure ApiKeyPageActivate(Sender: TWizardPage);
var
  ExistingKey: String;
begin
  if Trim(ApiKeyEdit.Text) = '' then
  begin
    ExistingKey := GetExistingEnvValue('GEMINI_API_KEY');
    if ExistingKey <> '' then
      ApiKeyEdit.Text := ExistingKey;
  end;
end;

procedure DiscordPageActivate(Sender: TWizardPage);
var
  ExistingToken: String;
begin
  if Trim(DiscordEdit.Text) = '' then
  begin
    ExistingToken := GetExistingEnvValue('DISCORD_TOKEN');
    if ExistingToken <> '' then
    begin
      DiscordEdit.Text := ExistingToken;
      DiscordAutoStartCheck.Checked := True;
    end;
  end;
end;

procedure UpdateEnvKey(const EnvPath, Key, Value: String);
var
  Lines: TArrayOfString;
  I: Integer;
  Found: Boolean;
  Prefix: String;
begin
  Prefix := Key + '=';
  Found := False;
  if FileExists(EnvPath) and LoadStringsFromFile(EnvPath, Lines) then
  begin
    for I := 0 to GetArrayLength(Lines) - 1 do
    begin
      if (Pos(Prefix, Lines[I]) = 1) or (Pos('# ' + Prefix, Lines[I]) = 1) or (Pos('#' + Prefix, Lines[I]) = 1) then
      begin
        if Value <> '' then
          Lines[I] := Prefix + Value
        else
          Lines[I] := '# ' + Prefix;
        Found := True;
        Break;
      end;
    end;
    if Found then
    begin
      SaveStringsToFile(EnvPath, Lines, False);
      Exit;
    end;
  end;

  if Value <> '' then
  begin
    if FileExists(EnvPath) then
      SaveStringToFile(EnvPath, Prefix + Value + #13#10, True)
    else
      SaveStringToFile(EnvPath, Prefix + Value + #13#10, False);
  end;
end;

procedure UpdateDiscordAutostart(const ConfigPath: String; AutoStart: Boolean);
var
  Lines: TArrayOfString;
  I: Integer;
  InDiscordSection: Boolean;
  ValStr: String;
begin
  if not FileExists(ConfigPath) then Exit;
  if AutoStart then ValStr := 'autostart = true' else ValStr := 'autostart = false';
  
  if LoadStringsFromFile(ConfigPath, Lines) then
  begin
    InDiscordSection := False;
    for I := 0 to GetArrayLength(Lines) - 1 do
    begin
      if Pos('[discord]', LowerCase(Trim(Lines[I]))) = 1 then
        InDiscordSection := True
      else if (Pos('[', Trim(Lines[I])) = 1) and InDiscordSection then
        InDiscordSection := False;
        
      if InDiscordSection and (Pos('autostart', LowerCase(Trim(Lines[I]))) = 1) then
      begin
        Lines[I] := ValStr;
        SaveStringsToFile(ConfigPath, Lines, False);
        Exit;
      end;
    end;
  end;
end;

procedure InitializeWizard;
var
  InfoLabel: TNewStaticText;
  LinkLabel: TNewStaticText;
  PromptLabel: TNewStaticText;
  InputLabel: TNewStaticText;
  ExistingKey: String;
  ExistingToken: String;
  
  DInfoLabel: TNewStaticText;
  DStep1Label: TNewStaticText;
  DLinkLabel: TNewStaticText;
  DStep2Label: TNewStaticText;
  DInputLabel: TNewStaticText;
  DSkipHintLabel: TNewStaticText;
begin
  { --- Page 1: Google Gemini API Key --- }
  ApiKeyCustomPage := CreateCustomPage(
    wpSelectTasks,
    'Google Gemini API Key',
    'Configure your free translation API key (1,500 free requests/day)'
  );
  ApiKeyCustomPage.OnActivate := @ApiKeyPageActivate;

  InfoLabel := TNewStaticText.Create(ApiKeyCustomPage);
  InfoLabel.Parent := ApiKeyCustomPage.Surface;
  InfoLabel.Top := ScaleY(8);
  InfoLabel.Left := ScaleX(0);
  InfoLabel.Caption := 'You can obtain a free Gemini API Key at:';

  LinkLabel := TNewStaticText.Create(ApiKeyCustomPage);
  LinkLabel.Parent := ApiKeyCustomPage.Surface;
  LinkLabel.Top := InfoLabel.Top + InfoLabel.Height + ScaleY(4);
  LinkLabel.Left := ScaleX(0);
  LinkLabel.Caption := 'https://aistudio.google.com/apikey';
  LinkLabel.Cursor := crHand;
  LinkLabel.Font.Color := clBlue;
  LinkLabel.Font.Style := [fsUnderline];
  LinkLabel.OnClick := @GeminiLinkClick;

  PromptLabel := TNewStaticText.Create(ApiKeyCustomPage);
  PromptLabel.Parent := ApiKeyCustomPage.Surface;
  PromptLabel.Top := LinkLabel.Top + LinkLabel.Height + ScaleY(18);
  PromptLabel.Left := ScaleX(0);
  PromptLabel.Caption := 'Paste your GEMINI_API_KEY below (automatically loaded if previously configured):';

  InputLabel := TNewStaticText.Create(ApiKeyCustomPage);
  InputLabel.Parent := ApiKeyCustomPage.Surface;
  InputLabel.Top := PromptLabel.Top + PromptLabel.Height + ScaleY(16);
  InputLabel.Left := ScaleX(0);
  InputLabel.Caption := 'GEMINI_API_KEY:';

  ApiKeyEdit := TNewEdit.Create(ApiKeyCustomPage);
  ApiKeyEdit.Parent := ApiKeyCustomPage.Surface;
  ApiKeyEdit.Top := InputLabel.Top + InputLabel.Height + ScaleY(4);
  ApiKeyEdit.Left := ScaleX(0);
  ApiKeyEdit.Width := ApiKeyCustomPage.SurfaceWidth;

  ExistingKey := GetExistingEnvValue('GEMINI_API_KEY');
  if ExistingKey <> '' then
    ApiKeyEdit.Text := ExistingKey;

  { --- Page 2: Discord Bot Integration (Optional) --- }
  DiscordCustomPage := CreateCustomPage(
    ApiKeyCustomPage.ID,
    'Discord Bot Integration (Optional)',
    'Configure Discord bot for right-click translation & mobile support'
  );
  DiscordCustomPage.OnActivate := @DiscordPageActivate;

  DInfoLabel := TNewStaticText.Create(DiscordCustomPage);
  DInfoLabel.Parent := DiscordCustomPage.Surface;
  DInfoLabel.Top := ScaleY(0);
  DInfoLabel.Left := ScaleX(0);
  DInfoLabel.Caption := '1. Open Discord Developer Portal:';

  DLinkLabel := TNewStaticText.Create(DiscordCustomPage);
  DLinkLabel.Parent := DiscordCustomPage.Surface;
  DLinkLabel.Top := DInfoLabel.Top + DInfoLabel.Height + ScaleY(2);
  DLinkLabel.Left := ScaleX(0);
  DLinkLabel.Caption := 'https://discord.com/developers/applications';
  DLinkLabel.Cursor := crHand;
  DLinkLabel.Font.Color := clBlue;
  DLinkLabel.Font.Style := [fsUnderline];
  DLinkLabel.OnClick := @DiscordLinkClick;

  DStep2Label := TNewStaticText.Create(DiscordCustomPage);
  DStep2Label.Parent := DiscordCustomPage.Surface;
  DStep2Label.Top := DLinkLabel.Top + DLinkLabel.Height + ScaleY(6);
  DStep2Label.Left := ScaleX(0);
  DStep2Label.Caption := 
    '2. Click "New Application" to create your bot app.'#13#10 +
    '3. "Installation" tab (Crucial):'#13#10 +
    '   - Check "User Install" (enables bot in personal DMs, servers & mobile)'#13#10 +
    '   - Scopes: select "applications.commands"'#13#10 +
    '   - Install Link: choose "Discord Provided Link" -> click "Save Changes"'#13#10 +
    '   - Copy link, open in browser and click "Authorize" (Add to My Apps)'#13#10 +
    '4. "Bot" tab: click "Reset Token", copy token, and paste below:';

  DInputLabel := TNewStaticText.Create(DiscordCustomPage);
  DInputLabel.Parent := DiscordCustomPage.Surface;
  DInputLabel.Top := DStep2Label.Top + DStep2Label.Height + ScaleY(6);
  DInputLabel.Left := ScaleX(0);
  DInputLabel.Caption := 'DISCORD_TOKEN:';

  DiscordEdit := TNewEdit.Create(DiscordCustomPage);
  DiscordEdit.Parent := DiscordCustomPage.Surface;
  DiscordEdit.Top := DInputLabel.Top + DInputLabel.Height + ScaleY(3);
  DiscordEdit.Left := ScaleX(0);
  DiscordEdit.Width := DiscordCustomPage.SurfaceWidth;

  DiscordAutoStartCheck := TNewCheckBox.Create(DiscordCustomPage);
  DiscordAutoStartCheck.Parent := DiscordCustomPage.Surface;
  DiscordAutoStartCheck.Top := DiscordEdit.Top + DiscordEdit.Height + ScaleY(6);
  DiscordAutoStartCheck.Left := ScaleX(0);
  DiscordAutoStartCheck.Width := DiscordCustomPage.SurfaceWidth;
  DiscordAutoStartCheck.Caption := 'Automatically launch Discord Bot background service with ZLZ-translator';
  DiscordAutoStartCheck.Checked := False;

  DSkipHintLabel := TNewStaticText.Create(DiscordCustomPage);
  DSkipHintLabel.Parent := DiscordCustomPage.Surface;
  DSkipHintLabel.Top := DiscordAutoStartCheck.Top + DiscordAutoStartCheck.Height + ScaleY(4);
  DSkipHintLabel.Left := ScaleX(0);
  DSkipHintLabel.Caption := '* Optional: You can skip this step at any time by leaving it blank and clicking Next.';
  DSkipHintLabel.Font.Color := clGray;

  ExistingToken := GetExistingEnvValue('DISCORD_TOKEN');
  if ExistingToken <> '' then
  begin
    DiscordEdit.Text := ExistingToken;
    DiscordAutoStartCheck.Checked := True;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ApiKey: String;
  DiscordToken: String;
  EnvPath: String;
  ConfigPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    ApiKey := Trim(ApiKeyEdit.Text);
    DiscordToken := Trim(DiscordEdit.Text);
    EnvPath := ExpandConstant('{app}\.env');
    ConfigPath := ExpandConstant('{app}\config.toml');
    
    if not FileExists(EnvPath) and FileExists(ExpandConstant('{app}\.env.example')) then
      CopyFile(ExpandConstant('{app}\.env.example'), EnvPath, False);

    if ApiKey <> '' then
      UpdateEnvKey(EnvPath, 'GEMINI_API_KEY', ApiKey);
      
    if DiscordToken <> '' then
    begin
      UpdateEnvKey(EnvPath, 'DISCORD_TOKEN', DiscordToken);
      UpdateDiscordAutostart(ConfigPath, DiscordAutoStartCheck.Checked);
    end;
  end;
end;
