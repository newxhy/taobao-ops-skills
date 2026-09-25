# ---------------------------------------------------------------------------
# Shared environment resolver for the bsk helper scripts (Codex + WorkBuddy).
#
# Why this file exists:
#   * Codex's default shell is PowerShell, and its PATH has NO bash / sed / wc.
#     So we must locate a real bash explicitly.
#   * $HOME can be an EMPTY STRING inside the Codex sandbox. USERPROFILE is set,
#     so BSK_HOME is always built from USERPROFILE in Windows form.
#   * The daemon cannot be started from inside the sandbox. We never start it
#     here; we only connect. BSK_AUTO_START is forced to 0 so a missing daemon
#     fails loudly instead of half-working.
#
# NOTE: this file is intentionally ASCII-only. Windows PowerShell 5.1 reads
# .ps1 files as ANSI when they have no BOM, which would corrupt any non-ASCII
# character here.
# ---------------------------------------------------------------------------

$script:SkillBashShimThreshold = 200000  # real bash.exe is ~2.4MB, the shim ~47KB

function Get-SkillBashCandidates {
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:SKILL_BASH) { $candidates.Add($env:SKILL_BASH) }

    foreach ($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)) {
        if (-not $root) { continue }
        $candidates.Add((Join-Path $root 'Git\usr\bin\bash.exe'))
        $candidates.Add((Join-Path $root 'Programs\Git\usr\bin\bash.exe'))
    }

    $portableRoots = @(
        (Join-Path $env:USERPROFILE '.workbuddy\binaries\PortableGit\versions')
    )
    foreach ($root in $portableRoots) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
            Sort-Object -Property Name -Descending |
            ForEach-Object { $candidates.Add((Join-Path $_.FullName 'usr\bin\bash.exe')) }
    }

    $cmd = Get-Command bash.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { $candidates.Add($cmd.Source) }

    return $candidates
}

function Resolve-SkillBash {
    $rejected = New-Object System.Collections.Generic.List[string]
    foreach ($candidate in (Get-SkillBashCandidates)) {
        if (-not $candidate) { continue }
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $size = (Get-Item -LiteralPath $candidate).Length
        if ($size -lt $script:SkillBashShimThreshold) {
            $rejected.Add("$candidate (shim, $size bytes)")
            continue
        }
        return $candidate
    }
    $hint = @()
    if ($rejected.Count -gt 0) { $hint += "Only shim bash found: $($rejected -join '; ')" }
    throw ("No real bash found. Install Git for Windows (gives <Git>\usr\bin\bash.exe, ~2.4MB) " +
           "or set SKILL_BASH to the full path. " + ($hint -join ' '))
}

function Initialize-SkillEnv {
    param([string]$WorkDir)

    if (-not $env:USERPROFILE) {
        throw 'USERPROFILE is not set; cannot locate BSK_HOME.'
    }
    if (-not $env:BSK_HOME) {
        $env:BSK_HOME = Join-Path $env:USERPROFILE '.bsk'
    }
    if (-not $env:BSK_AUTO_START) {
        $env:BSK_AUTO_START = '0'
    }
    if ($WorkDir) {
        $env:SKILL_WORKDIR = (Resolve-Path -LiteralPath $WorkDir -ErrorAction SilentlyContinue)
        if (-not $env:SKILL_WORKDIR) {
            New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
            $env:SKILL_WORKDIR = (Resolve-Path -LiteralPath $WorkDir).Path
        }
    } elseif (-not $env:SKILL_WORKDIR) {
        $env:SKILL_WORKDIR = (Get-Location).Path
    }
}
