#define MyAppName "SCP:SL Auto-Joiner"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "MasterNazz"
#define MyAppExeName "SCP-SL-Auto-Joiner.exe"

[Setup]
AppId={{7B1A2A7B-3A7D-4B27-AF20-7E7EAF5F7B0D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SCP-SL-Auto-Joiner
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
OutputDir=dist
OutputBaseFilename=SCP-SL-Auto-Joiner-v{#MyAppVersion}-win-x64-setup
SetupIconFile=assets\app.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\SCP-SL-Auto-Joiner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
