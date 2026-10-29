param([string]$Src)
$dst = Join-Path $env:TEMP "pjstudio-run"
robocopy $Src $dst /MIR /XD __pycache__ .git dados /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }  # robocopy: 0-7 = sucesso
$dst
