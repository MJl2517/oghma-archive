#define AppName "Oghma Archive"
#ifndef AppVersion
#define AppVersion "1.1.0"
#endif
#define AppPublisher "MJl2517"
#define AppURL "https://github.com/MJl2517/oghma-archive"
#define AppExeName "Oghma.exe"

[Setup]
AppId={{B643947C-B468-4429-B1F2-74F2FA5FD74C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\Oghma Archive
DefaultGroupName=Oghma Archive
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist-installer
OutputBaseFilename=Oghma-Archive-Setup-{#AppVersion}
SetupIconFile=..\static\img\ogma-icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ChangesEnvironment=no
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
english.DesktopShortcut=Create a desktop shortcut
russian.DesktopShortcut=Создать ярлык на рабочем столе
english.Autostart=Start Oghma Archive when Windows starts
russian.Autostart=Запускать Oghma Archive при входе в Windows
english.LaunchProgram=Launch Oghma Archive
russian.LaunchProgram=Запустить Oghma Archive
english.NetworkConfigFailed=Setup could not configure oghma.local. Check that local port 80 is free, then run setup again.
russian.NetworkConfigFailed=Не удалось настроить oghma.local. Убедитесь, что локальный порт 80 свободен, затем запустите установку снова.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "autostart"; Description: "{cm:Autostart}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\build\package\Oghma\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "configure-local-network.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "cleanup-legacy-launchers.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "launch-update.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{commonstartup}\Oghma Archive.lnk"
Type: files; Name: "{autodesktop}\Oghma Archive.lnk"

[Icons]
Name: "{autoprograms}\Oghma Archive"; Filename: "{app}\{#AppExeName}"; Parameters: "--open"; WorkingDir: "{app}"
Name: "{autodesktop}\Oghma Archive"; Filename: "{app}\{#AppExeName}"; Parameters: "--open"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{commonstartup}\Oghma Archive"; Filename: "{app}\{#AppExeName}"; Parameters: "--startup"; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExeName}"; Parameters: "--stop"; Flags: runhidden waituntilterminated runasoriginaluser
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\cleanup-legacy-launchers.ps1"""; Flags: runhidden waituntilterminated runasoriginaluser
Filename: "{app}\{#AppExeName}"; Parameters: "--open"; Description: "{cm:LaunchProgram}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{app}\{#AppExeName}"; Parameters: "--stop"; Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "StopOghma"
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\configure-local-network.ps1"" -Uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveOghmaNetwork"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  PowerShellPath: String;
  ScriptPath: String;
begin
  if CurStep <> ssPostInstall then
    Exit;

  PowerShellPath := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  ScriptPath := ExpandConstant('{app}\installer\configure-local-network.ps1');
  if (not Exec(
    PowerShellPath,
    '-NoProfile -ExecutionPolicy Bypass -File "' + ScriptPath + '" -Install',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  )) or (ResultCode <> 0) then
    RaiseException(CustomMessage('NetworkConfigFailed'));
end;
