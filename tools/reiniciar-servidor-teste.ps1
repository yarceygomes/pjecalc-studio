# Desenvolvimento: espelha o projeto em %TEMP% (o Python deste ambiente não enxerga a pasta da sessão)
# e reinicia o servidor apontando para a instância de teste do PJe-Calc.
param([int]$Porta = 8765, [string]$Dados = (Join-Path $env:USERPROFILE "PJeCalcStudio-teste\dados"))
$p = (Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue).OwningProcess
if ($p) { Stop-Process -Id $p -Force -Confirm:$false; Start-Sleep 1 }
$d = & (Join-Path $PSScriptRoot "sync-run.ps1") -Src (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$log = Split-Path $Dados -Parent
New-Item -ItemType Directory -Force $log | Out-Null
Start-Process -FilePath "py" -ArgumentList @("-I", "-X", "utf8", "`"$d\servidor.py`"", "--porta", $Porta, "--dados", "`"$Dados`"", "--sem-navegador") `
    -WindowStyle Hidden -RedirectStandardError (Join-Path $log "servidor.log") -RedirectStandardOutput (Join-Path $log "servidor.out")
Start-Sleep 3
"Servidor: " + (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Porta/api/estado").StatusCode
