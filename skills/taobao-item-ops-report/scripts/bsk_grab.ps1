# Thin PowerShell wrapper around bsk_grab.sh.
# Codex runs PowerShell by default and has no bash on PATH, so this wrapper
# resolves a real bash, sets up BSK_HOME / BSK_AUTO_START / SKILL_WORKDIR and
# forwards every argument to the bash implementation (which holds the logic).
#
# Usage:
#   .\bsk_grab.ps1 -Url "https://sycm.taobao.com/portal/home.htm" -Out "sycm_home.txt"
#   .\bsk_grab.ps1 -Url "https://sycm.taobao.com/portal/home.htm" -Out "sycm_week.txt" `
#                  -Click "周" -Js $metricsJs -WorkDir "C:\path\to\workspace"

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$Click = '',
    [string]$WaitMs = '12000',
    [string]$NavTimeout = '45s',
    [string]$Js = '',
    [string]$WorkDir = ''
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir 'codex_env.ps1')

Initialize-SkillEnv -WorkDir $WorkDir
$bash = Resolve-SkillBash
$target = (Join-Path $scriptDir 'bsk_grab.sh') -replace '\\', '/'

& $bash $target $Url $Out $Click $WaitMs $NavTimeout $Js
exit $LASTEXITCODE
