# Publica uma versão do PJe-Calc Studio no GitHub. Veja PUBLICAR.md.
#
#   powershell -ExecutionPolicy Bypass -File tools\publicar-versao.ps1                  (publica a versão de servidor.py)
#   powershell -ExecutionPolicy Bypass -File tools\publicar-versao.ps1 -Versao 0.2.1    (troca a versão e publica)
#
# Antes: escreva em NOVIDADES.md a seção "## <versão>" com o que mudou (vira a página da versão e o aviso de
# atualização dentro do Studio). O script cria a tag v<versão> e a envia; o GitHub (.github/workflows/release.yml)
# roda os testes, gera o instalador e publica a versão em alguns minutos.
param([string]$Versao)
$ErrorActionPreference = "Stop"
$raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $raiz
$servidor = Join-Path $raiz "servidor.py"

if ($Versao) {
    if ($Versao -notmatch '^\d+\.\d+\.\d+$') { throw "Versão inválida: use o formato 1.2.3." }
    $texto = [IO.File]::ReadAllText($servidor)
    $novo = [regex]::Replace($texto, '(?m)^VERSAO_APP = "[0-9.]+"', "VERSAO_APP = `"$Versao`"")
    [IO.File]::WriteAllText($servidor, $novo, (New-Object Text.UTF8Encoding $false))
}
$Versao = (Select-String -Path $servidor -Pattern '^VERSAO_APP = "([0-9.]+)"').Matches[0].Groups[1].Value
$tag = "v$Versao"

if (-not (Select-String -Path (Join-Path $raiz "NOVIDADES.md") -Pattern "^## $([regex]::Escape($Versao))\b" -Quiet)) {
    throw "Escreva em NOVIDADES.md a seção '## $Versao' com o que mudou nesta versão e rode de novo."
}
git rev-parse -q --verify "refs/tags/$tag" | Out-Null
if ($LASTEXITCODE -eq 0) { throw "A versão $Versao já foi publicada (tag $tag). Use -Versao com um número novo." }

git add -A
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { git commit -q -m "Versão $Versao"; if ($LASTEXITCODE -ne 0) { throw "git commit falhou" } }
git tag -a $tag -m "PJe-Calc Studio $Versao"
git push origin HEAD
if ($LASTEXITCODE -ne 0) { git tag -d $tag | Out-Null; throw "O envio do código falhou; nada foi publicado." }
git push origin $tag
if ($LASTEXITCODE -ne 0) { git tag -d $tag | Out-Null; throw "O envio da versão falhou; nada foi publicado." }

$origem = (git remote get-url origin) -replace '\.git$', ''
""
"Versão $Versao enviada. O GitHub está gerando o instalador (leva uns 5 minutos):"
"  acompanhe em  $origem/actions"
"  depois fica em  $origem/releases/latest"
