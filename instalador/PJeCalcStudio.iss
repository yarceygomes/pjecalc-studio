; PJe-Calc Studio — instalador (Inno Setup 6). Gerado por tools\gerar-instalador.ps1, que passa:
;   /DVersao=0.1.0  /DOrigem=<pasta do pacote montado por empacotar.ps1>  [/DAssinar + /Sassinar=...]
; Instala só para o usuário (sem pedir administrador), em %LOCALAPPDATA%\Programs\PJeCalcStudio.
; Os cálculos ficam em %LOCALAPPDATA%\PJeCalcStudio\dados: atualizar ou desinstalar o programa não os apaga.

#ifndef Versao
  #error Informe /DVersao=x.y.z
#endif
#ifndef Origem
  #error Informe /DOrigem=<pasta do pacote>
#endif
; repositório no GitHub (tools/publicar-no-github.ps1 troca o marcador)
#define Repositorio "yarceygomes/pjecalc-studio"

[Setup]
AppId={{6F3B2C1A-8E4D-4B7A-9C2E-5D1F0A7B3E91}
AppName=PJe-Calc Studio
AppVersion={#Versao}
AppVerName=PJe-Calc Studio {#Versao}
AppPublisher=PJe-Calc Studio
AppPublisherURL=https://github.com/{#Repositorio}
AppSupportURL=https://github.com/{#Repositorio}/issues
AppUpdatesURL=https://github.com/{#Repositorio}/releases
VersionInfoVersion={#Versao}
DefaultDirName={localappdata}\Programs\PJeCalcStudio
DefaultGroupName=PJe-Calc Studio
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputBaseFilename=PJeCalcStudio-{#Versao}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; o Studio roda sem janela (pythonw) e o Restart Manager do Windows não consegue fechá-lo: o [Code] o encerra antes
; de instalar e de desinstalar (senão os arquivos do Python ficam presos e a instalação sai pela metade)
CloseApplications=no
UninstallDisplayName=PJe-Calc Studio
UninstallDisplayIcon={app}\python\pythonw.exe
#ifdef Assinar
SignTool=assinar
SignedUninstaller=yes
#endif

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalhodesktop"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "{#Origem}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{localappdata}\PJeCalcStudio\dados"

[Icons]
Name: "{autoprograms}\PJe-Calc Studio"; Filename: "{app}\python\pythonw.exe"; Parameters: "-I ""{app}\servidor.py"" --dados ""{localappdata}\PJeCalcStudio\dados"""; WorkingDir: "{app}"; Comment: "Abre o PJe-Calc Studio no navegador"
Name: "{autoprograms}\Como usar o PJe-Calc Studio"; Filename: "{app}\COMO USAR.html"; Comment: "Guia ilustrado do PJe-Calc Studio (funciona sem internet)"
Name: "{autodesktop}\PJe-Calc Studio"; Filename: "{app}\python\pythonw.exe"; Parameters: "-I ""{app}\servidor.py"" --dados ""{localappdata}\PJeCalcStudio\dados"""; WorkingDir: "{app}"; Tasks: atalhodesktop

[Run]
; instalação normal: oferece abrir o Studio ao terminar
Filename: "{app}\python\pythonw.exe"; Parameters: "-I ""{app}\servidor.py"" --dados ""{localappdata}\PJeCalcStudio\dados"""; WorkingDir: "{app}"; Description: "Abrir o PJe-Calc Studio"; Flags: postinstall nowait skipifsilent
; atualização automática (silenciosa): reabre o Studio sem abrir outra aba (a aba aberta recarrega sozinha)
Filename: "{app}\python\pythonw.exe"; Parameters: "-I ""{app}\servidor.py"" --dados ""{localappdata}\PJeCalcStudio\dados"" --sem-navegador"; WorkingDir: "{app}"; Flags: nowait runhidden; Check: AtualizacaoAutomatica

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\ponte\__pycache__"

[Code]
// Encerra o Studio (e qualquer Python) que esteja rodando a partir da pasta do programa.
procedure EncerrarStudio;
var
  Codigo: Integer;
  Pasta: String;
begin
  Pasta := ExpandConstant('{app}');
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "' +
    '$p = ''' + Pasta + '\''; ' +
    'Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($p, [StringComparison]::OrdinalIgnoreCase) } | ' +
    'ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Start-Sleep -Milliseconds 1500"',
    '', SW_HIDE, ewWaitUntilTerminated, Codigo);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  EncerrarStudio;
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  EncerrarStudio;
  Result := True;
end;

function AtualizacaoAutomatica: Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), '/ATUALIZACAO') = 0 then
      Result := True;
end;
