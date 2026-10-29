# Assina um executável com o certificado de assinatura de código (Authenticode, SHA-256, com carimbo de tempo).
# Usado pelo Inno Setup (instalador e desinstalador) e por gerar-instalador.ps1.
#
# Certificado, um dos dois:
#   -Impressao <thumbprint>  certificado instalado no Windows (Cert:\CurrentUser\My), inclusive em token USB
#   -Pfx <arquivo.pfx>       arquivo .pfx; a senha vem da variável de ambiente PJSTUDIO_PFX_SENHA
# (ou as variáveis PJSTUDIO_CERT_IMPRESSAO / PJSTUDIO_PFX, para o Inno Setup chamar sem argumentos extras)
#
# O carimbo de tempo mantém a assinatura válida depois que o certificado vencer.
param(
    [Parameter(Mandatory = $true)][string]$Arquivo,
    [string]$Impressao = $env:PJSTUDIO_CERT_IMPRESSAO,
    [string]$Pfx = $env:PJSTUDIO_PFX,
    [string]$Carimbo = "http://timestamp.digicert.com"
)
$ErrorActionPreference = "Stop"
if ($Impressao) {
    $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Thumbprint -eq $Impressao.Replace(" ", "").ToUpper() }
    if (-not $cert) { throw "Certificado $Impressao não encontrado em Cert:\CurrentUser\My (ou não é de assinatura de código)." }
} elseif ($Pfx) {
    $senha = $env:PJSTUDIO_PFX_SENHA
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($Pfx, $senha)
} else {
    throw "Informe -Impressao ou -Pfx (ou as variáveis PJSTUDIO_CERT_IMPRESSAO / PJSTUDIO_PFX)."
}
for ($tentativa = 1; $tentativa -le 3; $tentativa++) {  # o servidor de carimbo de tempo às vezes falha
    $r = Set-AuthenticodeSignature -FilePath $Arquivo -Certificate $cert -HashAlgorithm SHA256 -TimestampServer $Carimbo
    if ($r.Status -eq "Valid") { "Assinado: $Arquivo"; exit 0 }
    Start-Sleep -Seconds (3 * $tentativa)
}
throw "Falha ao assinar $Arquivo ($($r.Status)): $($r.StatusMessage)"
