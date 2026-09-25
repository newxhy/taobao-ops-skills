# Thin PowerShell wrapper around bsk_check.sh (environment / daemon health check).
# Run this BEFORE any scraping: it tells you whether bash, python, bsk and the
# browser extension are all reachable from Codex.

[CmdletBinding()]
param([string]$WorkDir = '')

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir 'codex_env.ps1')

Initialize-SkillEnv -WorkDir $WorkDir
$bash = Resolve-SkillBash
$target = (Join-Path $scriptDir 'bsk_check.sh') -replace '\\', '/'

& $bash $target
exit $LASTEXITCODE
