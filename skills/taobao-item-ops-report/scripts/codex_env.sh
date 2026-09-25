#!/usr/bin/env bash
# -*- coding: utf-8 -*-
#
# 运行环境解析器（Codex / WorkBuddy 双端通用）
# =====================================================================
# 被本目录下的 bsk_grab.sh / bsk_check.sh `source` 使用。
# 作用：把原先硬编码在脚本里的 WorkBuddy 路径，换成运行期探测。
#
# 四条设计约束（都在 Codex 端实测过，不是猜的）：
#   ① Codex 的默认 shell 是 PowerShell，PATH 里**没有 bash / sed / wc**
#      → 调本目录脚本必须用「真 bash」的绝对路径（见 bsk_grab.ps1）
#   ② Codex 沙箱里 $HOME 可能是**空串**（不是未设置）
#      → 一律写 ${HOME:-...}，并优先用 USERPROFILE
#   ③ bsk.exe 是 Windows 程序，BSK_HOME 必须传 **Windows 形式**（C:\...）
#      → 传 POSIX 形式（/c/...）会导致 daemon 发现失败
#   ④ daemon 必须由**沙箱外的常驻任务**启动；脚本内只连接、不 start
#      → 所以这里固定 BSK_AUTO_START=0，把失败暴露成明确报错而不是静默重启
# =====================================================================

# ---------- PATH 引导（必须最先做，且只能用 bash 内建） ----------
# 非登录 shell 下 Git-bash 不读 /etc/profile，继承来的 PATH 里可能没有 /usr/bin，
# 于是连 dirname / sed / wc 都找不到。这里先用纯内建把工具目录塞回 PATH。
_ce_bin="${BASH:-}"
case "$_ce_bin" in
  /*) PATH="${_ce_bin%/*}:/usr/bin:/bin:/mingw64/bin:$PATH" ;;
  *)  PATH="/usr/bin:/bin:/mingw64/bin:$PATH" ;;
esac
export PATH


# 幂等：重复 source 不重复干活
if [ -n "${CE_ENV_LOADED:-}" ]; then
  return 0 2>/dev/null || exit 0
fi
CE_ENV_LOADED=1

# ---------- 输出helper ----------
ce_info() { printf '  %s\n' "$*"; }
ce_ok()   { printf '  ok    %s\n' "$*"; }
ce_warn() { printf '  warn  %s\n' "$*" >&2; }
ce_die()  { printf '  FAIL  %s\n' "$*" >&2; exit "${CE_EXIT_CODE:-1}"; }

# ---------- 1. 主目录（Windows + POSIX 两种形式） ----------
CE_HOMEW="${USERPROFILE:-}"
if [ -z "$CE_HOMEW" ] && [ -n "${HOME:-}" ]; then
  if command -v cygpath >/dev/null 2>&1; then
    CE_HOMEW="$(cygpath -w "$HOME" 2>/dev/null || true)"
  else
    CE_HOMEW="$HOME"
  fi
fi
if [ -z "$CE_HOMEW" ]; then
  ce_die "拿不到用户主目录：USERPROFILE 与 HOME 都为空。请在调用前显式设置 USERPROFILE 或 HOME。"
fi

if command -v cygpath >/dev/null 2>&1; then
  CE_HOMEU="$(cygpath -u "$CE_HOMEW" 2>/dev/null || true)"
fi
CE_HOMEU="${CE_HOMEU:-${HOME:-/c/Users/$(basename "$CE_HOMEW")}}"
# 把可能为空的 HOME 补正 —— 后续脚本大量用 $HOME
export HOME="$CE_HOMEU"
export USERPROFILE="$CE_HOMEW"
export CE_HOMEW CE_HOMEU

# ---------- 2. PATH：真 bash 的工具链必须在前 ----------
# 真 bash 的 usr/bin 里才有 sed / wc / sleep（Codex 的 PowerShell PATH 里没有）
if [ -n "${BASH:-}" ]; then
  CE_BASH_BIN="$BASH"
elif [ -x /usr/bin/bash.exe ]; then
  CE_BASH_BIN=/usr/bin/bash.exe
else
  CE_BASH_BIN="$(command -v bash 2>/dev/null || true)"
fi

CE_BASH_DIR=""
if [ -n "$CE_BASH_BIN" ]; then
  # 纯参数展开取目录（不依赖 dirname）
  case "$CE_BASH_BIN" in
    */*) CE_BASH_DIR="${CE_BASH_BIN%/*}" ;;
  esac
fi
for d in "$CE_BASH_DIR" /usr/bin /bin /usr/local/bin \
         "$CE_HOMEU/.local/bin" \
         /c/Windows/System32 /c/Windows; do
  [ -n "$d" ] && [ -d "$d" ] && case ":$PATH:" in
    *":$d:"*) ;;
    *) PATH="$d:$PATH" ;;
  esac
done
export PATH
export CE_BASH_BIN CE_BASH_DIR

# ---------- 3. bsk CLI ----------
CE_BSK_EXE="${SKILL_BSK:-${BSK_EXE:-}}"
if [ -z "$CE_BSK_EXE" ]; then
  for cand in "$CE_HOMEU/.local/bin/bsk.exe" "$CE_HOMEU/.local/bin/bsk"; do
    [ -x "$cand" ] && CE_BSK_EXE="$cand" && break
  done
fi
if [ -z "$CE_BSK_EXE" ]; then
  cand="$(command -v bsk.exe 2>/dev/null || command -v bsk 2>/dev/null || true)"
  [ -n "$cand" ] && CE_BSK_EXE="$cand"
fi
[ -n "$CE_BSK_EXE" ] || ce_die "找不到 bsk CLI。装法见 https://github.com/Tencent/BrowserSkill/blob/main/AGENT_INSTALL.md（默认落在 ~/.local/bin/bsk.exe），或用 SKILL_BSK=/绝对路径 指定。"
[ -x "$CE_BSK_EXE" ] || ce_die "bsk 存在但不可执行: $CE_BSK_EXE"

# ---------- 4. BSK_HOME（必须是 Windows 形式）+ 不自动起 daemon ----------
if [ -z "${BSK_HOME:-}" ]; then
  BSK_HOME="${CE_HOMEW}\\.bsk"
fi
case "$BSK_HOME" in
  /*) ce_warn "BSK_HOME 看起来是 POSIX 形式（$BSK_HOME）——bsk.exe 是 Windows 程序，可能解析失败；建议用 Windows 形式，如 ${CE_HOMEW}\\.bsk" ;;
esac
export BSK_HOME
export BSK_AUTO_START="${BSK_AUTO_START:-0}"
export CE_BSK_EXE

# Windows 形式的 bsk 路径（提示用户去普通 PowerShell 窗口执行命令时用）
if command -v cygpath >/dev/null 2>&1; then
  CE_BSK_EXEW="$(cygpath -w "$CE_BSK_EXE" 2>/dev/null || echo "$CE_BSK_EXE")"
  CE_SKILL_DIRW="$(cygpath -w "${CE_SCRIPT_DIR:-$PWD}" 2>/dev/null || echo "${CE_SCRIPT_DIR:-$PWD}")"
else
  CE_BSK_EXEW="$CE_BSK_EXE"
  CE_SKILL_DIRW="${CE_SCRIPT_DIR:-$PWD}"
fi
export CE_BSK_EXEW CE_SKILL_DIRW

# ---------- 5. Python（先 Codex 自带，再系统，再 WorkBuddy） ----------
CE_PY="${SKILL_PY:-${PYTHON:-}}"
if [ -z "$CE_PY" ]; then
  for cand in "$(command -v python3 2>/dev/null || true)" "$(command -v python 2>/dev/null || true)"; do
    [ -n "$cand" ] && CE_PY="$cand" && break
  done
fi
if [ -z "$CE_PY" ]; then
  # Codex 自带运行时（优先，不依赖 WorkBuddy 是否安装）
  for cand in "$CE_HOMEU"/.cache/codex-runtimes/*/dependencies/python/python.exe; do
    [ -x "$cand" ] && CE_PY="$cand" && break
  done
fi
if [ -z "$CE_PY" ]; then
  # WorkBuddy 自带（装了 WorkBuddy 就有）
  for cand in "$CE_HOMEU"/.workbuddy/binaries/python/versions/*/python.exe; do
    [ -x "$cand" ] && CE_PY="$cand" && break
  done
fi
[ -n "$CE_PY" ] || ce_die "找不到 Python 3.9+。请安装 Python，或用 SKILL_PY=/绝对路径 指定。"
export CE_PY

# ---------- 6. 工作目录 ----------
# 抓取产物 / 报表的落盘根目录。优先 SKILL_WORKDIR，其次当前目录。
CE_WORKDIR="${SKILL_WORKDIR:-$(pwd -P)}"
# 统一成 POSIX 形式：调用方（PowerShell 包装脚本）常传 Windows 形式的 C:\...，
# 直接塞进 bash 会因为反斜杠被 MSYS 转义而变成不存在的路径。
if command -v cygpath >/dev/null 2>&1; then
  CE_WORKDIR="$(cygpath -u "$CE_WORKDIR" 2>/dev/null || echo "$CE_WORKDIR")"
fi
export CE_WORKDIR

# ---------- 7. 只读诊断 ----------
# ---------- 建目录（绕开 Codex 沙箱的一个坑） ----------
# 实测：在 Codex 沙箱里 `mkdir -p /c/Users/.../x`（绝对路径）会报
#   mkdir: cannot create directory '/c/Users/...': Permission denied
# 而 `cd <已有的父目录> && mkdir -p <相对路径>` 正常。
# 所以这里先退到「已存在的最深祖先」，再 cd 过去用相对路径创建。
ce_ensure_dir() {
  _ced="$1"
  [ -d "$_ced" ] && return 0
  _cebase=""
  _cecur="$_ced"
  while [ ! -d "$_cecur" ] && [ "$_cecur" != "/" ] && [ -n "$_cecur" ]; do
    _cebase="$(basename "$_cecur")${_cebase:+/$_cebase}"
    _ceparent="$(dirname "$_cecur")"
    [ "$_ceparent" = "$_cecur" ] && break
    _cecur="$_ceparent"
  done
  ( cd "$_cecur" 2>/dev/null && mkdir -p "$_cebase" ) 2>/dev/null && return 0
  mkdir -p "$_ced" 2>/dev/null && return 0
  return 1
}
export -f ce_ensure_dir 2>/dev/null || true

ce_status() {
  ce_info "bash      : ${CE_BASH_BIN:-?}"
  ce_info "python    : $CE_PY ($("$CE_PY" -V 2>&1))"
  ce_info "bsk       : $CE_BSK_EXE ($("$CE_BSK_EXE" --version 2>&1 | head -1))"
  ce_info "BSK_HOME  : $BSK_HOME"
  ce_info "AUTO_START: $BSK_AUTO_START"
  ce_info "workdir   : $CE_WORKDIR"
}
