<#
.SYNOPSIS
    Execucao diaria do hf-papers-db, para o Agendador de Tarefas do Windows.

.DESCRIPTION
    Ativa o ambiente Python, roda `python -m hfpapers run`, escreve a saida num
    log rotativo em logs/ e propaga o codigo de saida. Codigo != 0 faz o
    Agendador marcar a execucao como falha - e assim a falha aparece sem que
    ninguem precise ler o log.

.PARAMETER Data
    Forca uma data especifica (YYYY-MM-DD). Sem isso, o pipeline descobre os
    dias faltantes sozinho.

.PARAMETER DiasDeLog
    Quantos dias de log manter. Padrao: 30.

.EXAMPLE
    .\scripts\run_daily.ps1
    .\scripts\run_daily.ps1 -Data 2026-08-25
#>
[CmdletBinding()]
param(
    [string]$Data,
    [int]$DiasDeLog = 30
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Raiz = Split-Path -Parent $PSScriptRoot
$DirLogs = Join-Path $Raiz 'logs'
New-Item -ItemType Directory -Force -Path $DirLogs | Out-Null

$Carimbo = Get-Date -Format 'yyyy-MM-dd_HHmmss'
$Log = Join-Path $DirLogs "run_$Carimbo.log"

function Escrever($Mensagem) {
    $linha = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Mensagem
    Write-Host $linha
    Add-Content -Path $Log -Value $linha -Encoding UTF8
}

# ── ambiente Python ─────────────────────────────────────────────────────────
# Ordem de procura: venv local, depois o conda env do projeto, depois o python
# do PATH. Ajuste $PythonExe se o seu ambiente ficar em outro lugar.
$Candidatos = @(
    (Join-Path $Raiz '.venv\Scripts\python.exe'),
    (Join-Path $env:USERPROFILE 'miniconda3\envs\digest-hf\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
)
$PythonExe = $Candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $PythonExe = $cmd.Source }
}
if (-not $PythonExe) {
    Escrever 'ERRO: nenhum interpretador Python encontrado.'
    exit 2
}

Escrever "raiz:   $Raiz"
Escrever "python: $PythonExe"

# ── execucao ────────────────────────────────────────────────────────────────
$Args = @('-m', 'hfpapers', 'run')
if ($Data) { $Args += @('--data', $Data) }

Push-Location $Raiz
try {
    Escrever ("comando: {0} {1}" -f $PythonExe, ($Args -join ' '))
    & $PythonExe @Args 2>&1 | Tee-Object -FilePath $Log -Append
    $Codigo = $LASTEXITCODE
}
catch {
    Escrever "ERRO: $($_.Exception.Message)"
    $Codigo = 1
}
finally {
    Pop-Location
}

Escrever "codigo de saida: $Codigo"

# ── rotacao do log ──────────────────────────────────────────────────────────
Get-ChildItem -Path $DirLogs -Filter 'run_*.log' |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$DiasDeLog) } |
    Remove-Item -Force -ErrorAction SilentlyContinue

exit $Codigo
