#!/usr/bin/env bash
# -*- coding: utf-8 -*-
#
# 环境自检（抓数前先跑这个）
# =====================================================================
# 一次把你需要知道的都打出来：
#   bash / python / bsk 的解析结果、BSK_HOME、daemon 发现文件、
#   bsk status、扩展连接情况、以及下一步该做什么。
#
# 用法： bsk_check.sh
# 退出码：0=全部就绪；5=环境就绪但 daemon/扩展没连上；2=基础环境缺失
# =====================================================================
set -u

# ---------- PATH 引导（必须最先做，且只能用 bash 内建） ----------
_ce_bin="${BASH:-}"
case "$_ce_bin" in
  /*) PATH="${_ce_bin%/*}:/usr/bin:/bin:/mingw64/bin:$PATH" ;;
  *)  PATH="/usr/bin:/bin:/mingw64/bin:$PATH" ;;
esac
export PATH

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

. "$CE_SCRIPT_DIR/codex_env.sh" || exit 2

echo "=== bsk 环境自检 ==="
ce_status

echo
echo "--- daemon 发现文件 ($BSK_HOME\\daemon.json) ---"
DAEMON_JSON="$CE_HOMEU/.bsk/daemon.json"
if [ -f "$DAEMON_JSON" ]; then
  cat "$DAEMON_JSON"
else
  echo "（不存在——daemon 从来没起来过，或 BSK_HOME 不对）"
fi

echo
echo "--- bsk status --json ---"
STATUS_OUT="$("$CE_BSK_EXE" status --json 2>&1)"
echo "$STATUS_OUT"

echo
if printf '%s' "$STATUS_OUT" | grep -qiE '"(browsers|connected)"'; then
  if printf '%s' "$STATUS_OUT" | grep -qiE '"browsers"[[:space:]]*:[[:space:]]*\[[[:space:]]*\]'; then
    echo "⚠ daemon 在跑，但 browsers 列表为空 → 浏览器扩展还没连上。"
    echo "  处置：在浏览器里打开/启用 bsk 扩展（详见 bsk-browser-sandbox-setup 技能）。"
    exit 5
  fi
  echo "✅ daemon 已连接，浏览器可用。可以开始抓数。"
  exit 0
fi

echo "❌ daemon 没连上（或 status 返回了错误）。"
echo
echo "Codex 里 daemon 起不来是正常的——沙箱会回收子进程、且禁止 Job Object breakaway。"
echo "请在【普通 PowerShell 窗口】里执行下面两行，并保持窗口开着："
echo
echo "    \$env:BSK_HOME = \"$BSK_HOME\""
echo "    & \"$CE_BSK_EXEW\" daemon start --foreground --daemon-idle 8h"
echo
echo "若窗口里报端口占用/已在跑，说明 daemon 已存在，直接回来重跑本自检。"
echo "若 bsk 命令静默失败 / 无输出 / SIGTERM，走 bsk-browser-sandbox-setup 技能（CLI 与扩展版本错配）。"
exit 5
