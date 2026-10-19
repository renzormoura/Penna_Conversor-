; =====================================================================
; PENNA CONVERSOR - Instalador Windows (Inno Setup 6)
; Compilar com: ISCC.exe installer.iss   (ou use build_installer.bat)
; Nao usa caminhos absolutos: tudo e relativo a pasta do produto.
; Saida: installer_output\PennaConversor_Installer.exe
; =====================================================================

#define MyAppName "Penna Conversor"
#define MyAppExeName "PennaConversor.exe"
#define MyAppVersion "1.0.0"

[Setup]
AppId={{7C4A1F09-3E86-4B2D-8A15-9F0C6D2E7B31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppName}
DefaultDirName={autopf}\PennaConversor
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=PennaConversor_Installer
SetupIconFile=apac_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
CloseApplications=yes
CloseApplicationsFilter={#MyAppExeName}
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=LICENSE.txt
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion restartreplace
; Modelo da ficha PDF ao lado do .exe (padrao do penna_config.json:
; local que o cliente pode editar sem novo build; o bundle tambem o embute)
Source: "dados\modelo_ficha_oci_oftalmologia.xlsx"; DestDir: "{app}\dados"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Limpa arquivos criados pelo programa em runtime (logs/temp), se existirem
Type: filesandordirs; Name: "{app}\__pycache__"
