# Gera o instalador do PJe-Calc Studio (PJeCalcStudio-<versão>.exe), assinado quando há certificado.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File tools\gerar-instalador.ps1                          (sem assinatura: só para testes)
#   powershell -ExecutionPolicy Bypass -File tools\gerar-instalador.ps1 -Impressao <thumbprint>  (certificado no Windows / token)
#   powershell -ExecutionPolicy Bypass -File tools\gerar-instalador.ps1 -Pfx C:\certs\codigo.pfx  (senha em PJSTUDIO_PFX_SENHA)
#
# Pré-requisito: Inno Setup 6 (https://jrsoftware.org/isinfo.php ou "winget install JRSoftware.InnoSetup").
# Gera PJeCalcStudio-<versão>.exe, a cópia com nome fixo PJeCalcStudio-Instalador.exe (a que o GitHub publica e a
# atualização automática procura) e PJeCalcStudio-Instalador.exe.sha256.
# -Python: Python 3.10+ 64 bits a embutir (padrão: o do lançador "py"; o GitHub Actions passa o dele).
param(
    [string]$Impressao,
    [string]$Pfx,
    [string]$Saida = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "dist"),
    [string]$Iscc,
    [string]$Python
)
$ErrorActionPreference = "Stop"
$raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
New-Item -ItemType Directory -Force $Saida | Out-Null
$Saida = (Resolve-Path $Saida).Path

if (-not $Iscc) {
    $Iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
              "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $Iscc) { throw "Inno Setup 6 não encontrado. Instale (winget install JRSoftware.InnoSetup) ou informe -Iscc <ISCC.exe>." }

$versao = (Select-String -Path (Join-Path $raiz "servidor.py") -Pattern '^VERSAO_APP = "([0-9.]+)"').Matches[0].Groups[1].Value
if (-not $versao) { throw "VERSAO_APP não encontrada em servidor.py" }
"PJe-Calc Studio $versao"

# 1. pacote (programa + Python portátil), conferido por empacotar.ps1
$argsPacote = @{ SemZip = $true }
if ($Python) { $argsPacote.Python = $Python }
$pacote = & (Join-Path $PSScriptRoot "empacotar.ps1") @argsPacote | Select-Object -Last 1
if (-not (Test-Path (Join-Path $pacote "python\pythonw.exe"))) { throw "pacote sem python\pythonw.exe: $pacote" }
# marca de versão instalada: liga as atualizações automáticas (ponte/atualizacao.py)
[System.IO.File]::WriteAllText((Join-Path $pacote "instalacao.json"), (@{ canal = "estavel"; versao = $versao } | ConvertTo-Json -Compress),
    (New-Object System.Text.UTF8Encoding $false))

# 2. instalador
$parametros = @("/DVersao=$versao", "/DOrigem=$pacote", "/O$Saida", "/Q")
$assinar = $Impressao -or $Pfx
if ($assinar) {
    if ($Impressao) { $env:PJSTUDIO_CERT_IMPRESSAO = $Impressao } else { $env:PJSTUDIO_PFX = (Resolve-Path $Pfx).Path }
    $script = Join-Path $PSScriptRoot "assinar.ps1"
    $parametros += "/DAssinar"
    $parametros += "/Sassinar=powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`" -Arquivo `$f"
} else {
    Write-Warning "Sem certificado: o instalador sai SEM assinatura (o Windows mostrará 'editor desconhecido'). Use só para testes."
}
& $Iscc @parametros (Join-Path $raiz "instalador\PJeCalcStudio.iss")
if ($LASTEXITCODE -ne 0) { throw "o Inno Setup falhou ($LASTEXITCODE)" }
$exe = Join-Path $Saida "PJeCalcStudio-$versao.exe"

# 3. conferência
if ($assinar) {
    $sig = Get-AuthenticodeSignature $exe
    if ($sig.Status -ne "Valid") { throw "assinatura inválida em ${exe}: $($sig.Status) $($sig.StatusMessage)" }
    "Assinatura: $($sig.SignerCertificate.Subject) (carimbo de tempo: $([bool]$sig.TimeStamperCertificate))"
}
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
"Instalador: $exe ({0:N1} MB)" -f ((Get-Item $exe).Length / 1MB)
"SHA-256: $hash"

# 4. cópia com nome fixo e o SHA-256 dela (o link "baixar a versão mais nova" e a atualização automática usam este nome)
$fixo = Join-Path $Saida "PJeCalcStudio-Instalador.exe"
Copy-Item $exe $fixo -Force
[System.IO.File]::WriteAllText("$fixo.sha256", "$hash  PJeCalcStudio-Instalador.exe`n", (New-Object System.Text.UTF8Encoding $false))
"Para publicar: $fixo e $fixo.sha256"
