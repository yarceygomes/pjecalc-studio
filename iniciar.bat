@echo off
rem PJe-Calc Studio - inicia a interface local (http://127.0.0.1:8765/) e abre o navegador.
rem Pre-requisito: o PJe-Calc Cidadao iniciado pelo atalho oficial (iniciarPjeCalc.bat).
rem O pacote de distribuicao traz o Python na subpasta "python"; sem ela, usa o Python instalado no computador.
chcp 65001 >nul
cd /d "%~dp0"
title PJe-Calc Studio
if exist "%~dp0python\python.exe" (
  "%~dp0python\python.exe" -I servidor.py %*
  goto :fim
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -I servidor.py %*
  goto :fim
)
where python >nul 2>nul
if %errorlevel%==0 (
  python -I servidor.py %*
  goto :fim
)
echo Python nao encontrado. Use o pacote completo do PJe-Calc Studio (com a pasta "python")
echo ou instale o Python 3.10 ou superior pelo site python.org e execute novamente.
pause
:fim
if errorlevel 1 (
  echo.
  echo O PJe-Calc Studio foi encerrado com erro. Veja as mensagens acima.
  pause
)
