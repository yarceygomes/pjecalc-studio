# Gera o pacote de distribuição do PJe-Calc Studio: programa + Python portátil (pasta "python") + LEIA-ME.
# Quem recebe só descompacta e dá dois cliques em iniciar.bat; não precisa instalar o Python.
#
# Uso: powershell -ExecutionPolicy Bypass -File tools\empacotar.ps1 [-Python <pasta do Python>] [-Saida <arquivo.zip>] [-SemZip]
#   -SemZip: só monta a pasta do pacote e devolve o caminho (usado por gerar-instalador.ps1).
#   -Python: instalação do Python 3.10+ 64 bits a copiar (padrão: a do lançador "py").
#            O Python é distribuído sob a licença PSF, que permite a redistribuição (LICENSE.txt vai junto).
param(
    [string]$Python,
    [string]$Saida = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "..\PJeCalcStudio.zip"),
    [switch]$SemZip
)
$ErrorActionPreference = "Stop"
$raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $Python) { $Python = (& py -3 -I -c "import sys; print(sys.base_prefix)").Trim() }
if (-not (Test-Path (Join-Path $Python "python.exe"))) { throw "python.exe não encontrado em $Python" }

$estagio = Join-Path $env:TEMP "pjstudio-pacote"
$destino = Join-Path $estagio "PJeCalcStudio"
if (Test-Path $estagio) { Remove-Item -Recurse -Force $estagio }
New-Item -ItemType Directory -Force $destino | Out-Null

# 1. programa (sem cálculos, caches nem cópias de trabalho)
robocopy $raiz $destino /E /XD __pycache__ dados python .git .github dist /XF *.pyc studio.log* .gitignore .gitattributes /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "falha ao copiar o programa (robocopy $LASTEXITCODE)" }

# 2. Python portátil enxuto: interpretador, bibliotecas nativas e biblioteca padrão, sem interface
#    gráfica (Tk), pip, IDLE, documentação nem pacotes de terceiros
$py = Join-Path $destino "python"
New-Item -ItemType Directory -Force $py | Out-Null
#    Na raiz, só o interpretador e as DLLs dele: a pasta de um Python instalado pode guardar outros .exe (o
#    Python do GitHub Actions traz o próprio instalador do python.org, com 32 MB) e as versões free-threaded.
Get-ChildItem $Python -File | Where-Object { $_.Name -match '^(pythonw?\.exe|python3\d*\.dll|vcruntime140(_1)?\.dll|LICENSE\.txt)$' } |
    Copy-Item -Destination $py
robocopy (Join-Path $Python "DLLs") (Join-Path $py "DLLs") /E /XF tcl*.dll tk*.dll _tkinter.pyd _test*.pyd *.pdb /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "falha ao copiar DLLs (robocopy $LASTEXITCODE)" }
robocopy (Join-Path $Python "Lib") (Join-Path $py "Lib") /E `
    /XD site-packages __pycache__ ensurepip idlelib tkinter turtledemo pydoc_data venv test tests `
    /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "falha ao copiar a biblioteca padrão (robocopy $LASTEXITCODE)" }

# 3. conferência: o Python copiado precisa iniciar sozinho e importar tudo o que o servidor usa
$teste = "import sys, os; assert os.path.samefile(sys.base_prefix, r'$py'), sys.base_prefix; " +
         "import http.server, urllib.request, json, zipfile, xml.etree.ElementTree, html.parser, http.cookiejar, " +
         "hashlib, secrets, unicodedata, decimal, threading, webbrowser, mimetypes, unittest; print('python ok', sys.version.split()[0])"
& (Join-Path $py "python.exe") -I -B -c $teste  # -B: a conferência não deixa cache (.pyc) dentro do pacote
if ($LASTEXITCODE -ne 0) { throw "o Python portátil não passou na conferência" }

# 3b. guia ilustrado na raiz do pacote ("COMO USAR.html", abre com dois cliques e funciona offline)
$guia = Get-Content (Join-Path $raiz "docs\como-usar.html") -Raw -Encoding UTF8
$pagina = "<!doctype html>`r`n<html lang=`"pt-BR`"><head><meta charset=`"utf-8`">" +
          "<meta name=`"viewport`" content=`"width=device-width, initial-scale=1, viewport-fit=cover`"></head><body>`r`n" +
          $guia + "`r`n</body></html>`r`n"
[System.IO.File]::WriteAllText((Join-Path $destino "COMO USAR.html"), $pagina, (New-Object System.Text.UTF8Encoding $false))

if ($SemZip) { return $destino }

# 4. compacta
if (Test-Path $Saida) { Remove-Item -Force $Saida }
Compress-Archive -Path $destino -DestinationPath $Saida -CompressionLevel Optimal
$mb = (Get-Item $Saida).Length / 1MB
"Pacote: {0} ({1:N1} MB)" -f (Resolve-Path $Saida).Path, $mb
