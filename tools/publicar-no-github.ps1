# Primeira publicação do PJe-Calc Studio no GitHub (uma vez só). Veja PUBLICAR.md.
#
#   powershell -ExecutionPolicy Bypass -File tools\publicar-no-github.ps1 -Usuario <seu usuário do GitHub>
#
# 1. troca o marcador SEU-USUARIO pelo seu usuário nos links de download, no instalador e na atualização automática;
# 2. cria o repositório git local (ramo main) e o primeiro commit;
# 3. envia para https://github.com/<usuário>/<repositório> (o repositório precisa já existir, vazio, no site);
# 4. se você quiser, publica a primeira versão (tools\publicar-versao.ps1).
# Na primeira vez, o Git abre o navegador para você entrar na sua conta do GitHub.
param(
    [Parameter(Mandatory = $true)][string]$Usuario,
    [string]$Repositorio = "pjecalc-studio",
    [string]$Nome,
    [string]$Email
)
$ErrorActionPreference = "Stop"
$raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $raiz

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "O Git não está instalado. Instale com:  winget install Git.Git  (ou baixe em https://git-scm.com) e rode este comando de novo."
}
if ($Usuario -notmatch '^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$') { throw "Usuário do GitHub inválido: $Usuario" }
if ($Repositorio -notmatch '^[A-Za-z0-9._-]+$') { throw "Nome de repositório inválido: $Repositorio" }
$alvo = "$Usuario/$Repositorio"

# 1. marcador -> usuário/repositório (mantém a codificação e o fim de linha de cada arquivo)
$marcador = "SEU-USUARIO/pjecalc-studio"
$eu = (Resolve-Path $PSCommandPath).Path
Get-ChildItem -Recurse -File | Where-Object {
    $_.FullName -notmatch '\\(\.git|python|dist|dados)\\' -and $_.FullName -ne $eu -and
    $_.Extension -in ".py", ".md", ".iss", ".js", ".json", ".html", ".txt", ".yml", ".ps1"
} | ForEach-Object {
    $bytes = [IO.File]::ReadAllBytes($_.FullName)
    $bom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
    $texto = (New-Object Text.UTF8Encoding $false).GetString($bytes, [int]$bom * 3, $bytes.Length - [int]$bom * 3)
    if ($texto.Contains($marcador)) {
        [IO.File]::WriteAllText($_.FullName, $texto.Replace($marcador, $alvo), (New-Object Text.UTF8Encoding $bom))
        "Link atualizado: $($_.FullName.Substring($raiz.Length + 1))"
    }
}

# 2. repositório local e primeiro commit
if (-not (Test-Path (Join-Path $raiz ".git"))) { git init -b main | Out-Null }
if (-not (git config user.name)) {
    if (-not $Nome) { $Nome = Read-Host "Seu nome (aparece no histórico do projeto)" }
    git config user.name $Nome
}
if (-not (git config user.email)) {
    if (-not $Email) {
        "Para não publicar o seu e-mail, use o e-mail privado do GitHub (github.com > Settings > Emails,"
        "algo como 12345678+$Usuario@users.noreply.github.com). Deixe em branco para usar $Usuario@users.noreply.github.com."
        $Email = Read-Host "E-mail para o histórico"
        if (-not $Email) { $Email = "$Usuario@users.noreply.github.com" }
    }
    git config user.email $Email
}
git add -A
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { git commit -q -m "PJe-Calc Studio: publicação no GitHub"; if ($LASTEXITCODE -ne 0) { throw "git commit falhou" } }

# 3. envio
$url = "https://github.com/$alvo.git"
if (git remote) { git remote set-url origin $url } else { git remote add origin $url }
""
"Enviando para $url ..."
"(Se o navegador abrir pedindo para entrar no GitHub, entre na sua conta e autorize.)"
git push -u origin main
if ($LASTEXITCODE -ne 0) {
    throw "O envio falhou. Confira se o repositório https://github.com/$alvo já existe (vazio, sem README) e se você entrou na conta certa."
}
""
"Pronto: o código está em https://github.com/$alvo"

# 4. primeira versão
$resp = Read-Host "Publicar agora a primeira versão (gera o instalador no GitHub)? [S/n]"
if ($resp -notmatch '^[nN]') { & (Join-Path $PSScriptRoot "publicar-versao.ps1") }
else { "Quando quiser: powershell -ExecutionPolicy Bypass -File tools\publicar-versao.ps1" }
