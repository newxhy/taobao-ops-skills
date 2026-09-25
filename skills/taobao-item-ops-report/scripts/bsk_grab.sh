#!/usr/bin/env bash
# -*- coding: utf-8 -*-
#
# 单页抓取器（Codex / WorkBuddy 双端）
# =====================================================================
# 一条命令内跑完：
#   session start -> tab create --url ->(切口径)-> 等待 -> evaluate -> session stop
# 绝不跨命令复用 session（跨命令必 session not registered）。
#
# 用法：
#   bsk_grab.sh <URL> <OUT_FILE> [CLICK_TEXT] [WAIT_MS] [NAV_TIMEOUT] [JS]
#
#   CLICK_TEXT 为空则不点击；填 "7天" / "周" / "日" 等页面上的**精确叶子节点文本**
#   JS 为空则默认抓整页 innerText；传自定义 JS 可做结构化抽取（见 SKILL.md §3 取数铁律）
#   NAV_TIMEOUT 收 45000（毫秒）或 45s / 1m（bsk 原生写法）
#
# 环境变量：
#   BSK_GRAB_MODE=tab|navigate   默认 tab（tab create --url，2026-09-18 实战定型，优先）
#   SKILL_WORKDIR=<目录>          产物落盘根目录（默认当前目录）
#   SKILL_BSK / SKILL_PY / SKILL_BASH   显式指定 bsk.exe / python / 真 bash
#
# 退出码：0=成功；2=环境问题（找不到 bsk/python/bash）；3=session 起不来（多半 daemon 没常驻）
# =====================================================================
set -u

# ---------- PATH 引导（必须最先做，且只能用 bash 内建） ----------
_ce_bin="${BASH:-}"
case "$_ce_bin" in
  /*) PATH="${_ce_bin%/*}:/usr/bin:/bin:/mingw64/bin:$PATH" ;;
  *)  PATH="/usr/bin:/bin:/mingw64/bin:$PATH" ;;
esac
export PATH

# ---------- 自处理 CRLF（Windows 下写出的脚本可能带 \r） ----------
sed -i 's/\r$//' "$0" 2>/dev/null || true

# 脚本自身目录：纯参数展开（此时 dirname 可能还不可用）
_ce_self="${BASH_SOURCE[0]:-$0}"
case "$_ce_self" in
  */*) _ce_dir="${_ce_self%/*}" ;;
  *)   _ce_dir="." ;;
esac
case "$_ce_dir" in
  /*|[A-Za-z]:/*|[A-Za-z]:\\*) : ;;   # 已是绝对路径（POSIX 或 Windows 盘符）
  *)  _ce_dir="$PWD/$_ce_dir" ;;
esac
CE_SCRIPT_DIR="$(cd "$_ce_dir" && pwd -P)"

# ---------- 真 bash 自愈：shim 只有 47KB，真 bash 是 2.4MB ----------
# Codex 的 PowerShell PATH 里没有 bash；WorkBuddy 沙箱 PATH 里的 bin/bash.exe 是 shim。
# 两种情况都在这里兜住：发现自己跑在 shim 上，就换真 bash 重跑一次。
if [ -n "${BASH:-}" ] && [ -r "$BASH" ]; then
  CE_BASH_SIZE="$(stat -c %s "$BASH" 2>/dev/null || echo 0)"
  if [ "${CE_BASH_SIZE:-0}" -lt 200000 ]; then
    for cand in "$(dirname "$(dirname "$BASH")")/usr/bin/bash.exe" \
                "/d/Program Files/Git/usr/bin/bash.exe" \
                "/c/Program Files/Git/usr/bin/bash.exe" \
                "${USERPROFILE:-}/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin/bash.exe"; do
      if [ -x "$cand" ]; then
        exec "$cand" "$0" "$@"
      fi
    done
    printf '  FAIL  当前 bash 是 shim（%s 字节），且找不到真 bash。\n' "$CE_BASH_SIZE" >&2
    printf '        真 bash 在 Git for Windows 的 usr/bin 下（约 2.4MB），或 WorkBuddy PortableGit 的 usr/bin 下。\n' >&2
    exit 2
  fi
fi

# ---------- 环境解析 ----------
# shellcheck source=./codex_env.sh
. "$CE_SCRIPT_DIR/codex_env.sh" || exit 2

URL="${1:?usage: bsk_grab.sh <URL> <OUT_FILE> [CLICK_TEXT] [WAIT_MS] [NAV_TIMEOUT] [JS]}"
OUT="${2:?usage: bsk_grab.sh <URL> <OUT_FILE> [CLICK_TEXT] [WAIT_MS] [NAV_TIMEOUT] [JS]}"
CLICK="${3:-}"
WAIT_MS="${4:-12000}"
NAV_TIMEOUT="${5:-45s}"
JS_OVERRIDE="${6:-}"
MODE="${BSK_GRAB_MODE:-tab}"

# NAV_TIMEOUT 兼容两种写法：纯毫秒（45000）或 bsk 原生（45s / 1m）
case "$NAV_TIMEOUT" in
  *[a-zA-Z]*) : ;;
  *) NAV_TIMEOUT="${NAV_TIMEOUT}ms" ;;
esac

# OUT 落到工作区（相对路径按 CE_WORKDIR 展开）
if command -v cygpath >/dev/null 2>&1; then
  OUT="$(cygpath -u "$OUT" 2>/dev/null || echo "$OUT")"
fi
case "$OUT" in
  /*|[A-Za-z]:*) : ;;
  *) OUT="$CE_WORKDIR/$OUT" ;;
esac
ce_ensure_dir "$(dirname "$OUT")" || {
  echo "  FAIL  建不出产物目录：$(dirname "$OUT")" >&2
  exit 2
}

# JSON 取值：实现放在 ce_json.py（避免把 Python 源码塞进 shell 引号里）
ce_json_pick() {
  "$CE_PY" "$CE_SCRIPT_DIR/ce_json.py" "$1"
}

: > "$OUT" || exit 2

{
  echo "### bsk_grab  $(date '+%Y-%m-%d %H:%M:%S')"
  echo "URL=$URL"
  echo "MODE=$MODE"
  echo "CLICK=${CLICK:-（无）}"
  echo "WAIT_MS=$WAIT_MS   NAV_TIMEOUT=$NAV_TIMEOUT"
  echo "BSK_HOME=$BSK_HOME   BSK_AUTO_START=$BSK_AUTO_START"
  echo "SKILL_DIR=$CE_SCRIPT_DIR"
  echo "OUT=$OUT"
} >> "$OUT"

# ---------- session start ----------
SID="$("$CE_BSK_EXE" session start --json 2>>"$OUT" | ce_json_pick session_id)"
if [ -z "${SID:-}" ]; then
  {
    echo "=== SESSION_START_FAILED ==="
    echo "症状：bsk session start 没返回 session_id。"
    echo "最常见原因是 daemon 没有常驻（Codex 沙箱内起不来，必须由沙箱外的常驻任务启动）。"
    echo "下一步："
    echo "  1) 在【普通终端】（不是 Codex 里）执行："
    echo "     \$env:BSK_HOME = \"${BSK_HOME}\""
    echo "     & \"${CE_BSK_EXEW}\" daemon start --foreground --daemon-idle 8h"
    echo "  2) 回到 Codex 跑：& \"$CE_SKILL_DIRW\\bsk_check.ps1\"  确认 daemon 与扩展已连上"
    echo "  3) 仍失败就看 $BSK_HOME\\daemon.json 与 bsk logs"
  } >> "$OUT"
  echo "GRAB_FAILED session start 失败（daemon 常驻了吗？看 $OUT）" >&2
  exit 3
fi
echo "SID=$SID" >> "$OUT"

TAB=""
if [ "$MODE" = "tab" ]; then
  TAB_OUT="$("$CE_BSK_EXE" tab create --session "$SID" --url "$URL" --json 2>>"$OUT")"
  TAB="$(printf '%s' "$TAB_OUT" | ce_json_pick tab_id)"
  {
    echo "=== TAB CREATE ==="
    printf '%s\n' "$TAB_OUT"
    echo "TAB=${TAB:-（未解析出，后续将打到活动标签）}"
  } >> "$OUT"
else
  "$CE_BSK_EXE" navigate "$URL" --session "$SID" --timeout "$NAV_TIMEOUT" >> "$OUT" 2>&1
fi

# 页面异步拉数：等不够会拿到「正在努力加载」的空表
sleep $(( WAIT_MS / 1000 + 2 ))

# ---------- 切口径 ----------
if [ -n "$CLICK" ]; then
  echo "=== CLICK_ATTEMPT [$CLICK] ===" >> "$OUT"
  # 用叶子节点精确文本点击，不用索引/坐标（对应 SKILL.md §3 禁止脆弱定位）
  CLICK_JSON="$("$CE_PY" -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$CLICK")"
  CLICK_JS="(function(){var t=$CLICK_JSON;var els=document.querySelectorAll('a,button,span,div,li,label');for(var i=0;i<els.length;i++){if(((els[i].innerText||'').trim())===t&&els[i].children.length===0){els[i].click();return 'clicked';}}return 'notfound';})()"
  if [ -n "$TAB" ]; then
    "$CE_BSK_EXE" evaluate "$CLICK_JS" --session "$SID" --tab-id "$TAB" >> "$OUT" 2>&1
  else
    "$CE_BSK_EXE" evaluate "$CLICK_JS" --session "$SID" >> "$OUT" 2>&1
  fi
  # 切口径后重新拉数，需要更长等待
  sleep 18
fi

# ---------- 取数 ----------
echo "=== BODY ===" >> "$OUT"
if [ -n "$JS_OVERRIDE" ]; then
  JS="$JS_OVERRIDE"
else
  JS="(function(){return (document.body.innerText||'').replace(/\n{2,}/g,'\n');})()"
fi
if [ -n "$TAB" ]; then
  "$CE_BSK_EXE" evaluate "$JS" --session "$SID" --tab-id "$TAB" >> "$OUT" 2>&1
else
  "$CE_BSK_EXE" evaluate "$JS" --session "$SID" >> "$OUT" 2>&1
fi

"$CE_BSK_EXE" session stop "$SID" >> "$OUT" 2>&1
echo "DONE" >> "$OUT"

echo "GRAB_OK out=$OUT lines=$(wc -l < "$OUT" 2>/dev/null | tr -d ' ')"
