#!/usr/bin/env bash
# 单页抓取器：一条命令内跑完 session start -> navigate ->(点击口径)-> 等待 -> evaluate -> session stop
#
# 【调用方式 — 重要】必须用 REAL bash，不能用裸 `bash`：
#   沙箱 PATH 里的 .../PortableGit/versions/*/bin/bash.exe 是个 47KB 的 shim，
#   直接 `bash xx.sh` 会报 `line 3: bash: command not found`（exit 127）。
#   真实 bash 在 .../PortableGit/versions/*/usr/bin/bash.exe（2.4MB 二进制）。
#   正确调用（二选一）：
#     export PATH="/c/Users/<u>/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
#     /usr/bin/bash bsk_grab.sh <URL> <OUT> [CLICK] [WAIT_MS] [TIMEOUT] [JS]
#     # 或把 usr/bin 放到 PATH 最前，再 `bash bsk_grab.sh ...`
#
# 用法： <real-bash> bsk_grab.sh <URL> <OUT_FILE> [CLICK_TEXT] [WAIT_BEFORE_MS] [NAV_TIMEOUT_MS] [JS]
#   CLICK_TEXT 为空则不点击；填 "7天" / "周" / "日" 等页面上的精确文本（只匹配叶子节点）
#   JS 为空则默认抓整页 innerText；传自定义 JS 可做结构化抽取（见 SKILL.md「结构化取数」）
# 前置：bsk daemon 已常驻（见 SKILL.md 第 0 节）。本脚本不负责启动 daemon。
set -u

# 自处理 CRLF（Windows 下写出的脚本可能带 \r，导致 $'\r': command not found）
sed -i 's/\r$//' "$0" 2>/dev/null || true

URL="${1:?usage: bsk_grab.sh <URL> <OUT_FILE> [CLICK_TEXT] [WAIT_BEFORE_MS] [NAV_TIMEOUT_MS]}"
OUT="${2:?usage: bsk_grab.sh <URL> <OUT_FILE> [CLICK_TEXT] [WAIT_BEFORE_MS] [NAV_TIMEOUT_MS]}"
CLICK="${3:-}"
WAIT_MS="${4:-12000}"
NAV_TIMEOUT="${5:-45000}"
JS_OVERRIDE="${6:-}"

# WorkBuddy 沙箱的 bash PATH 常损坏（dirname/head/cat not found），必须重置
# 用户主目录（跨机可移植）：优先 $HOME / $USERPROFILE，回退按用户名拼
HOMEU="${HOME:-/c/Users/$USERNAME}"
HOMEW="${USERPROFILE:-C:\\Users\\$USERNAME}"
# 版本号（PortableGit / Python）按本机实际安装调整
PGV=1.2.0
PYV=3.13.12
export PATH="$HOMEU/.local/bin:$HOMEU/.workbuddy/binaries/PortableGit/versions/$PGV/usr/bin:/c/Windows/System32:/c/Windows:/usr/bin:/bin:$HOMEU/.workbuddy/binaries/python/versions/$PYV:$PATH"
export BSK_HOME="${BSK_HOME:-$HOMEW\\.bsk}"
export BSK_AUTO_START=0

B="$HOMEU/.local/bin/bsk.exe"
PY="$HOMEU/.workbuddy/binaries/python/versions/$PYV/python.exe"

: > "$OUT"

SID=$("$B" session start --json 2>/dev/null | "$PY" -c "import sys,json;print(json.load(sys.stdin)['session_id'])" 2>/dev/null)
if [ -z "${SID:-}" ]; then
  echo "SESSION_START_FAILED (daemon 常驻了吗？先看 SKILL.md 第 0 节 / bsk-browser-sandbox-setup)" >> "$OUT"
  exit 1
fi
echo "SID=$SID" >> "$OUT"
echo "URL=$URL" >> "$OUT"
echo "CLICK=$CLICK" >> "$OUT"

"$B" navigate "$URL" --session "$SID" --timeout "$NAV_TIMEOUT" >> "$OUT" 2>&1

# 初次等待：页面异步拉数，等不够会拿到"正在努力加载"空表
sleep $(( WAIT_MS / 1000 + 2 ))

if [ -n "$CLICK" ]; then
  echo "=== CLICK_ATTEMPT [$CLICK] ===" >> "$OUT"
  "$B" evaluate "(function(){var t='$CLICK';var els=document.querySelectorAll('a,button,span,div,li,label');for(var i=0;i<els.length;i++){if(((els[i].innerText||'').trim())===t&&els[i].children.length===0){els[i].click();return 'clicked';}}return 'notfound';})()" --session "$SID" >> "$OUT" 2>&1
  # 切口径后重新拉数，需要更长等待
  sleep 18
fi

echo "=== BODY ===" >> "$OUT"
if [ -n "$JS_OVERRIDE" ]; then
  JS="$JS_OVERRIDE"
else
  JS="(function(){return (document.body.innerText||'').replace(/\n{2,}/g,'\n');})()"
fi
"$B" evaluate "$JS" --session "$SID" >> "$OUT" 2>&1

"$B" session stop "$SID" >> "$OUT" 2>&1
echo "DONE" >> "$OUT"

echo "GRAB_OK out=$OUT lines=$(wc -l < "$OUT" 2>/dev/null)"
