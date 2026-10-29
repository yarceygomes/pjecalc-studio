# Sobe uma CÓPIA de teste do PJe-Calc (extraída do instalador oficial) em portas alternativas,
# com os mesmos parâmetros de JVM do iniciarPjeCalc.bat. Usada para testes de integração e de
# equivalência sem tocar na instalação de trabalho do usuário.
#
# Uso: .\iniciar-instancia-teste.ps1 -Instalador "C:\...\pjecalc-2.16.0-instalador-x64.exe" [-Pasta ...] [-Deslocamento 10000]
param(
    [string]$Instalador,
    [string]$Pasta = (Join-Path $env:LOCALAPPDATA "PJeCalcStudio\sandbox"),
    [int]$Deslocamento = 10000
)
$raiz = Join-Path $Pasta "pjecalc-windows64-2.16.0"
if (-not (Test-Path (Join-Path $raiz "bin\pjecalc.jar"))) {
    if (-not $Instalador) { throw "Informe -Instalador para extrair a cópia de teste." }
    New-Item -ItemType Directory -Force $Pasta | Out-Null
    $py = "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])"
    py -I -c $py $Instalador $Pasta
}
# portas: 9256/9257/9258 -> +Deslocamento (a instalação de trabalho continua livre para usar as originais)
$server = Join-Path $raiz "tomcat\conf\server.xml"
$xml = Get-Content $server -Raw -Encoding UTF8
foreach ($p in 9256, 9257, 9258) { $xml = $xml -replace "port=`"$p`"", "port=`"$($p + $Deslocamento)`"" }
Set-Content -Path $server -Value $xml -Encoding UTF8
$meta = Join-Path $raiz "tomcat\webapps\pjecalc\WEB-INF\classes\META-INF"
if (-not (Test-Path (Join-Path $meta "persistence.xml"))) { Copy-Item (Join-Path $meta "persistence.xml.tmp") (Join-Path $meta "persistence.xml") }

$java = Join-Path $raiz "bin\jre\bin\java.exe"
$args = @("-Duser.timezone=GMT-3", "-Dfile.encoding=ISO-8859-1",
    "-Dseguranca.pjecalc.tokenServicos=pW4jZ4g9VM5MCy6FnB5pEfQe",
    "-Dseguranca.pjekz.servico.contexto=https://pje.trtXX.jus.br/pje-seguranca",
    "-Xms1024m", "-Xmx2048m", "-XX:MaxPermSize=512m", "-Dcaminho.instalacao=$raiz",
    "-Dcatalina.home=$(Join-Path $raiz 'tomcat')", "-Dcatalina.base=$(Join-Path $raiz 'tomcat')",
    "-cp", "`"$(Join-Path $raiz 'bin\lib\*')`"", "org.apache.catalina.startup.Bootstrap", "start")
$logs = Join-Path $Pasta "logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$proc = Start-Process -FilePath $java -ArgumentList $args -WorkingDirectory $raiz -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logs "stdout.log") -RedirectStandardError (Join-Path $logs "stderr.log")
$url = "http://127.0.0.1:$(9257 + $Deslocamento)/pjecalc/"
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 3
    try { if ((Invoke-WebRequest -UseBasicParsing "$($url)versao.html" -TimeoutSec 5).StatusCode -eq 200) { break } } catch {}
}
"Instância de teste (PID $($proc.Id)) em $url"
