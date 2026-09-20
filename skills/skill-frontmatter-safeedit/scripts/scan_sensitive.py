# -*- coding: utf-8 -*-
"""发布前敏感信息扫描器 —— 传**公开仓库** / 传**开放平台**前必跑。

为什么需要它：技能是"实战里长出来的"，很容易顺手把**店铺名、品牌名、内部称呼、
真实 ID** 写进正文当案例 —— 而这些东西：

  · 传开放平台 → 所有下载你技能的人都能看到
  · 推公开仓库 → 全世界都能看到，且 **git 历史里永久留存**（删了也在）

最坑的是：**不报错、不崩、功能完全正常**，你根本不会发现。

用法:
  python scripts/scan_sensitive.py <技能目录> [<技能目录2> ...]
  python scripts/scan_sensitive.py <技能目录> --words "店名A,品牌B,内部称呼"
  python scripts/scan_sensitive.py --init-words       # 生成默认词表模板

词表文件（存在即自动加载，不用每次敲）:
  ~/.workbuddy/sensitive-words.txt     每行一个词，# 开头为注释

退出码: 0 = 无高危, 1 = 发现高危
"""
import sys
import os
import re

WORD_FILE = os.path.join(os.path.expanduser("~"), ".workbuddy", "sensitive-words.txt")
TEXT_EXT = (".md", ".html", ".htm", ".sh", ".py", ".json", ".txt", ".yaml", ".yml", ".css", ".js")
SKIP_SUFFIX = (".bak", ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".zip")

# 通用模式：不需要配置就能查出来的
GENERIC = [
    ("邮箱", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "high"),
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "high"),
    ("密钥/Token", re.compile(r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})"), "high"),
    ("本机绝对路径", re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+(?!<)[^\\/\s\"'|,)]+"), "mid"),
    ("长数字(≥8位)", re.compile(r"(?<![\d.])\d{8,}(?![\d.])"), "mid"),
]

WORDS_TEMPLATE = """# 敏感词表 —— 每行一个，扫描时命中即报高危
# 把你的店铺名 / 品牌名 / 合作方名 / 内部称呼都写进来
# 以 # 开头的行为注释；填的时候把行首的 # 去掉

# --- 自己的店铺 / 品牌（暴露 = 别人能摸到你的店、抄你的打法）---
# 店铺名A
# 品牌名B

# --- 别人的店（写案例时尤其要脱敏，这是商业关系风险）---
# 合作店铺C

# --- 内部称呼（对外人毫无意义，还会暴露"这是内部对话"）---
# 内部称呼D
"""


def load_words(cli_words):
    words = set()
    if os.path.isfile(WORD_FILE):
        for line in open(WORD_FILE, encoding="utf-8", errors="ignore"):
            w = line.strip()
            if w and not w.startswith("#"):
                words.add(w)
    if cli_words:
        for w in re.split(r"[,，\s]+", cli_words):
            if w.strip():
                words.add(w.strip())
    return sorted(words)


def classify(matched, kind):
    """给疑似结果降级，减少噪声。"""
    if kind == "长数字(≥8位)":
        if re.fullmatch(r"20\d{6}", matched):
            return "note", "疑似日期"
        if re.fullmatch(r"(\d)\1{7,}", matched) or matched.endswith("0000000"):
            return "note", "疑似示例/占位 ID"
    if kind in ("邮箱", "手机号", "密钥/Token"):
        return "high", ""
    return "mid", ""


def scan_dir(root, words):
    findings = []
    word_pats = [(w, re.compile(re.escape(w), re.I)) for w in words]

    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            if not f.endswith(TEXT_EXT) or f.endswith(SKIP_SUFFIX):
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace("\\", "/")
            try:
                text = open(p, "rb").read().decode("utf-8", "ignore")
            except Exception:
                continue
            for lineno, line in enumerate(text.split("\n"), 1):
                # 自定义词表 —— 命中即高危
                for w, pat in word_pats:
                    if pat.search(line):
                        findings.append(("high", rel, lineno, f"词表命中：{w}", line.strip()[:70]))
                # 通用模式
                for kind, pat, level in GENERIC:
                    for m in pat.finditer(line):
                        s = m.group(0)
                        if kind == "本机绝对路径" and "<" in s:
                            continue
                        lv, why = classify(s, kind)
                        findings.append((lv, rel, lineno, f"{kind}：{s}" + (f"（{why}）" if why else ""),
                                         line.strip()[:70]))
    return findings


def main():
    args = sys.argv[1:]
    if "--init-words" in args:
        os.makedirs(os.path.dirname(WORD_FILE), exist_ok=True)
        if os.path.exists(WORD_FILE):
            print(f"词表已存在，未覆盖：{WORD_FILE}")
        else:
            open(WORD_FILE, "w", encoding="utf-8", newline="").write(WORDS_TEMPLATE)
            print(f"已生成词表模板：{WORD_FILE}\n请打开它，把店铺名/品牌名填进去（去掉行首的 #）")
        return 0

    cli_words = None
    if "--words" in args:
        i = args.index("--words")
        cli_words = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return 1

    words = load_words(cli_words)
    print(f"词表规模：{len(words)} 个" + (f" -> {words}" if words else "（空，建议 --init-words 建一个）"))
    print()

    total_high = 0
    for root in args:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            print(f"跳过（不是目录）：{root}")
            continue
        name = os.path.basename(root)
        found = scan_dir(root, words)
        high = [x for x in found if x[0] == "high"]
        mid = [x for x in found if x[0] == "mid"]
        note = [x for x in found if x[0] == "note"]
        total_high += len(high)

        print("=" * 66)
        print(f"技能：{name}   高危 {len(high)} / 待确认 {len(mid)} / 提示 {len(note)}")
        for lv, tag, title in (("high", "🔴 高危", "必须先处理，否则不要发布"),
                               ("mid", "🟡 待确认", "人工判断是否可公开"),
                               ("note", "⚪ 提示", "大概率无害（示例/占位符）")):
            items = {"high": high, "mid": mid, "note": note}[lv]
            if not items:
                continue
            print(f"  {tag} —— {title}")
            for _, rel, ln, what, ctx in items:
                print(f"      {rel}:{ln}  {what}")
                if lv == "high":
                    print(f"          ↳ {ctx}")
        if not found:
            print("  ✅ 干净，可以直接发布")

    print()
    print("=" * 66)
    if total_high:
        print(f"❌ 发现 {total_high} 处高危 —— 脱敏后重跑，别急着传。")
        print("   注意：公开仓库一旦 push，敏感内容会永久留在 git 历史里（删掉文件也不算）。")
        return 1
    print("✅ 无高危，可以发布。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
